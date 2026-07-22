"""
MedCP - Medical Context Protocol Server

An MCP server that integrates electronic health record databases and a large-scale
heterogeneous knowledge graph for rapid clinical record query and fast biomedical
knowledge inference.

The electronic health record (clinical records) backend is pluggable and supports
three SQL engines:

* ``mssql``  - Microsoft SQL Server (via ``pymssql``)
* ``mysql``  - MySQL / MariaDB (via ``pymysql``)
* ``sqlite`` - a local SQLite database file (via the stdlib ``sqlite3`` module)

The backend is selected with the ``CLINICAL_RECORDS_BACKEND`` setting.
"""
import json
import logging
import os
import re
from typing import Any, Literal, Optional

from fastmcp.exceptions import ToolError
from fastmcp.server import FastMCP
from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import ToolAnnotations
from neo4j import GraphDatabase, Result, Transaction
from neo4j.exceptions import ClientError, Neo4jError
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("MedCP")

SQLBackend = Literal["mssql", "mysql", "sqlite"]


class KnowledgeGraphConfig(BaseModel):
    """Biomedical knowledge graph configuration (Neo4j)"""
    uri: str = Field(..., description="Knowledge graph connection URI (e.g., bolt://localhost:7687)")
    username: str = Field(..., description="Knowledge graph database username")
    password: str = Field(..., description="Knowledge graph database password")
    database: str = Field("neo4j", description="Knowledge graph database name")


class ClinicalRecordsConfig(BaseModel):
    """Electronic health records database configuration.

    Supports three SQL backends selected with ``backend``:

    * ``mssql``  - requires ``server``, ``database``, ``username``, ``password``
    * ``mysql``  - requires ``server``, ``database``, ``username``, ``password``
    * ``sqlite`` - requires ``sqlite_path`` (a local database file)
    """
    backend: SQLBackend = Field("mssql", description="SQL engine: 'mssql', 'mysql', or 'sqlite'")
    server: Optional[str] = Field(None, description="EHR database server host (mssql/mysql)")
    database: Optional[str] = Field(None, description="EHR database name (mssql/mysql)")
    username: Optional[str] = Field(None, description="EHR database username (mssql/mysql)")
    password: Optional[str] = Field(None, description="EHR database password (mssql/mysql)")
    port: Optional[int] = Field(None, description="EHR database port (mssql/mysql, optional)")
    sqlite_path: Optional[str] = Field(None, description="Path to the local SQLite database file (sqlite backend)")

    @model_validator(mode="after")
    def _check_backend_requirements(self) -> "ClinicalRecordsConfig":
        if self.backend == "sqlite":
            if not self.sqlite_path:
                raise ValueError("sqlite backend requires 'sqlite_path' (CLINICAL_RECORDS_SQLITE_PATH)")
        elif self.backend in ("mssql", "mysql"):
            missing = [
                name for name, value in (
                    ("server", self.server),
                    ("database", self.database),
                    ("username", self.username),
                    ("password", self.password),
                ) if not value
            ]
            if missing:
                raise ValueError(
                    f"{self.backend} backend requires: {', '.join(missing)}"
                )
        else:  # pragma: no cover - guarded by Literal typing
            raise ValueError(f"Unsupported clinical records backend: {self.backend}")
        return self


class MedCPConfig(BaseModel):
    """Complete MedCP server configuration"""
    knowledge_graph: Optional[KnowledgeGraphConfig] = Field(None, description="Biomedical knowledge graph configuration (optional)")
    clinical_records: Optional[ClinicalRecordsConfig] = Field(None, description="Electronic health records database configuration (optional)")
    namespace: str = Field("", description="Tool namespace prefix")
    log_level: str = Field("INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")


def _format_namespace(namespace: str) -> str:
    """Format namespace with trailing dash if needed"""
    if namespace:
        return namespace if namespace.endswith("-") else namespace + "-"
    return ""


def _read_knowledge_graph(tx: Transaction, cypher_query: str, params: dict[str, Any]) -> str:
    """Execute read-only knowledge graph transaction"""
    raw_results = tx.run(cypher_query, params)
    eager_results = raw_results.to_eager_result()
    return json.dumps([r.data() for r in eager_results.records], default=str)


def _write_knowledge_graph(tx: Transaction, cypher_query: str, params: dict[str, Any]) -> Result:
    """Execute write knowledge graph transaction"""
    return tx.run(cypher_query, params)


def _is_write_query(query: str) -> bool:
    """Check if the query contains write operations"""
    return re.search(r"\b(MERGE|CREATE|SET|DELETE|REMOVE|ADD|INSERT|UPDATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|SP_|ATTACH|DETACH|PRAGMA|REINDEX|VACUUM|REPLACE)\b", query, re.IGNORECASE) is not None


class ClinicalQueryValidator:
    """Clinical record query validator for read-only operations"""

    @staticmethod
    def is_read_only_clinical_query(query: str) -> bool:
        clean_query = query.strip().upper()

        # Allowed statements for clinical record queries
        allowed_statements = ['SELECT', 'WITH', 'DECLARE']

        # Check if starts with allowed statement
        starts_with_allowed = any(clean_query.startswith(stmt) for stmt in allowed_statements)
        if not starts_with_allowed:
            return False

        # Check for forbidden statements
        if _is_write_query(query):
            return False

        # Check for SQL injection / statement-stacking patterns
        has_dangerous_chars = re.search(r';\s*\w+', clean_query)
        if has_dangerous_chars:
            return False

        return True


def create_medcp_server(config: MedCPConfig) -> FastMCP:
    """Create MedCP server with configured biomedical database tools"""

    # Set up logging
    logging.basicConfig(level=getattr(logging, config.log_level.upper()))

    mcp = FastMCP("MedCP")
    namespace_prefix = _format_namespace(config.namespace)

    # Knowledge graph driver initialization
    kg_driver = None
    if config.knowledge_graph:
        try:
            kg_driver = GraphDatabase.driver(
                config.knowledge_graph.uri,
                auth=(config.knowledge_graph.username, config.knowledge_graph.password)
            )
            logger.info(f"Knowledge graph driver initialized for {config.knowledge_graph.uri}")
        except Exception as e:
            logger.error(f"Failed to initialize knowledge graph driver: {e}")
            raise ToolError(f"Knowledge graph initialization failed: {e}")

    # Clinical records connection manager
    clinical_config = config.clinical_records

    def get_clinical_records_connection():
        """Open a DB-API connection to the configured clinical records backend.

        Drivers are imported lazily so that a backend the user is not using
        (and may not have installed) never blocks server startup.
        """
        if not clinical_config:
            raise ToolError("Clinical records database not configured")

        backend = clinical_config.backend
        try:
            if backend == "sqlite":
                import sqlite3
                # Open read-only so the EHR file can never be mutated by a tool call.
                path = os.path.abspath(os.path.expanduser(clinical_config.sqlite_path))
                if not os.path.exists(path):
                    raise ToolError(f"SQLite database file not found: {path}")
                uri = f"file:{path}?mode=ro"
                return sqlite3.connect(uri, uri=True)

            if backend == "mysql":
                import pymysql
                return pymysql.connect(
                    host=clinical_config.server,
                    user=clinical_config.username,
                    password=clinical_config.password,
                    database=clinical_config.database,
                    port=clinical_config.port or 3306,
                    read_default_group=None,
                )

            # default: mssql
            import pymssql
            kwargs = dict(
                server=clinical_config.server,
                user=clinical_config.username,
                password=clinical_config.password,
                database=clinical_config.database,
            )
            if clinical_config.port:
                kwargs["port"] = str(clinical_config.port)
            return pymssql.connect(**kwargs)
        except ToolError:
            raise
        except ImportError as e:
            logger.error(f"Missing driver for backend '{backend}': {e}")
            raise ToolError(
                f"Clinical records backend '{backend}' requires a driver that is not installed: {e}"
            )
        except Exception as e:
            logger.error(f"Clinical records connection failed: {e}")
            raise ToolError(f"Clinical records connection failed: {e}")

    # Knowledge Graph Tools
    if kg_driver:

        @mcp.tool(
            name=f"{namespace_prefix}get_knowledge_graph_schema",
            annotations=ToolAnnotations(
                title="Get Knowledge Graph Schema",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=True
            )
        )
        def get_knowledge_graph_schema() -> ToolResult:
            """
            List all nodes, their attributes and their relationships in the biomedical knowledge graph.
            This provides the schema for drug-disease associations, protein interactions, pathways,
            and other biomedical entities. Requires APOC plugin to be installed and enabled.
            """

            def clean_schema(schema: dict) -> dict:
                """Clean and simplify schema output"""
                cleaned = {}
                for key, entry in schema.items():
                    new_entry = {"type": entry["type"]}

                    if "count" in entry:
                        new_entry["count"] = entry["count"]

                    if "labels" in entry and entry["labels"]:
                        new_entry["labels"] = entry["labels"]

                    # Clean properties
                    if "properties" in entry:
                        clean_props = {}
                        for pname, pinfo in entry["properties"].items():
                            cp = {}
                            for attr in ["indexed", "type"]:
                                if attr in pinfo:
                                    cp[attr] = pinfo[attr]
                            if cp:
                                clean_props[pname] = cp
                        if clean_props:
                            new_entry["properties"] = clean_props

                    # Clean relationships
                    if "relationships" in entry:
                        rels_out = {}
                        for rel_name, rel in entry["relationships"].items():
                            cr = {}
                            if "direction" in rel:
                                cr["direction"] = rel["direction"]
                            if "labels" in rel and rel["labels"]:
                                cr["labels"] = rel["labels"]

                            # Clean relationship properties
                            if "properties" in rel:
                                clean_rprops = {}
                                for rpname, rpinfo in rel["properties"].items():
                                    crp = {}
                                    for attr in ["indexed", "type"]:
                                        if attr in rpinfo:
                                            crp[attr] = rpinfo[attr]
                                    if crp:
                                        clean_rprops[rpname] = crp
                                if clean_rprops:
                                    cr["properties"] = clean_rprops

                            if cr:
                                rels_out[rel_name] = cr

                        if rels_out:
                            new_entry["relationships"] = rels_out

                    cleaned[key] = new_entry

                return cleaned

            get_schema_query = "CALL apoc.meta.schema();"

            try:
                with kg_driver.session(database=config.knowledge_graph.database) as session:
                    results_json_str = session.execute_read(_read_knowledge_graph, get_schema_query, {})

                    schema = json.loads(results_json_str)[0].get('value')
                    schema_clean = clean_schema(schema)

                    return ToolResult(content=[TextContent(type="text", text=json.dumps(schema_clean))])

            except ClientError as e:
                if "Neo.ClientError.Procedure.ProcedureNotFound" in str(e):
                    raise ToolError("Knowledge graph APOC plugin not installed. Please install and enable APOC for biomedical knowledge inference.")
                else:
                    raise ToolError(f"Knowledge graph client error: {e}")
            except Neo4jError as e:
                raise ToolError(f"Knowledge graph error: {e}")
            except Exception as e:
                logger.error(f"Error retrieving knowledge graph schema: {e}")
                raise ToolError(f"Unexpected error retrieving biomedical knowledge schema: {e}")

        @mcp.tool(
            name=f"{namespace_prefix}query_knowledge_graph",
            annotations=ToolAnnotations(
                title="Query Biomedical Knowledge Graph",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=True
            )
        )
        def query_knowledge_graph(
            cypher_query: str = Field(..., description="The Cypher query for biomedical knowledge inference (e.g., drug-disease associations, protein interactions)"),
            parameters: dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the knowledge graph query")
        ) -> ToolResult:
            """Execute a read-only Cypher query on the biomedical knowledge graph for fast knowledge inference."""

            if _is_write_query(cypher_query):
                raise ToolError("Only read queries (MATCH, RETURN, etc.) are allowed for knowledge graph queries")

            try:
                with kg_driver.session(database=config.knowledge_graph.database) as session:
                    results_json_str = session.execute_read(_read_knowledge_graph, cypher_query, parameters)

                    logger.debug(f"Knowledge graph query returned {len(results_json_str)} characters")

                    return ToolResult(content=[TextContent(type="text", text=results_json_str)])

            except Neo4jError as e:
                logger.error(f"Knowledge graph error executing query: {e}")
                raise ToolError(f"Biomedical knowledge graph error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in knowledge graph query: {e}")
                raise ToolError(f"Error executing biomedical knowledge query: {e}")

    # Clinical Records Tools
    if clinical_config:

        @mcp.tool(
            name=f"{namespace_prefix}query_clinical_records",
            annotations=ToolAnnotations(
                title="Query Electronic Health Records",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False
            )
        )
        def query_clinical_records(
            sql_query: str = Field(..., description="SQL SELECT query for rapid clinical record retrieval (read-only)")
        ) -> ToolResult:
            """Execute a READ-ONLY SQL query on electronic health records for rapid clinical data retrieval.

            Works against the configured backend (SQL Server, MySQL, or a local SQLite file).
            """

            # Validate query is read-only
            if not ClinicalQueryValidator.is_read_only_clinical_query(sql_query):
                raise ToolError("Only SELECT queries are allowed for clinical record queries")

            conn = None
            try:
                conn = get_clinical_records_connection()
                cursor = conn.cursor()
                cursor.execute(sql_query)

                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                # Get all rows
                rows = cursor.fetchall()

                # Format as CSV
                if columns:
                    csv_lines = [",".join(columns)]
                    csv_lines.extend([",".join("" if v is None else str(v) for v in row) for row in rows])
                    result_text = "\n".join(csv_lines)
                else:
                    result_text = "Clinical query executed successfully (no results returned)"

                cursor.close()

                logger.debug(f"Clinical records query returned {len(rows) if rows else 0} rows")

                return ToolResult(content=[TextContent(type="text", text=result_text)])

            except ToolError:
                raise
            except Exception as e:
                logger.error(f"Clinical records query error: {e}")
                raise ToolError(f"Electronic health records error: {e}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

        @mcp.tool(
            name=f"{namespace_prefix}list_clinical_tables",
            annotations=ToolAnnotations(
                title="List Clinical Data Tables",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False
            )
        )
        def list_clinical_tables() -> ToolResult:
            """List all available clinical data tables in the electronic health records database."""

            if clinical_config.backend == "sqlite":
                query = (
                    "SELECT 'main' AS table_schema, name AS table_name, type AS table_type "
                    "FROM sqlite_master "
                    "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            else:
                # INFORMATION_SCHEMA.TABLES is supported by both SQL Server and MySQL
                query = (
                    "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME"
                )

            conn = None
            try:
                conn = get_clinical_records_connection()
                cursor = conn.cursor()
                cursor.execute(query)

                tables = cursor.fetchall()

                # Format as JSON for better structure
                table_list = [
                    {
                        "schema": table[0],
                        "table_name": table[1],
                        "type": table[2],
                        "full_name": f"{table[0]}.{table[1]}"
                    }
                    for table in tables
                ]

                cursor.close()

                return ToolResult(content=[TextContent(type="text", text=json.dumps(table_list, indent=2))])

            except ToolError:
                raise
            except Exception as e:
                logger.error(f"Error listing clinical tables: {e}")
                raise ToolError(f"Error listing clinical data tables: {e}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

    return mcp


def _int_or_none(value: Optional[str]) -> Optional[int]:
    """Parse an optional integer environment value."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main(
    transport: Literal["stdio", "sse", "http"] = "stdio",
    knowledge_graph_uri: Optional[str] = None,
    knowledge_graph_username: Optional[str] = None,
    knowledge_graph_password: Optional[str] = None,
    knowledge_graph_database: Optional[str] = None,
    clinical_records_backend: Optional[str] = None,
    clinical_records_server: Optional[str] = None,
    clinical_records_database: Optional[str] = None,
    clinical_records_username: Optional[str] = None,
    clinical_records_password: Optional[str] = None,
    clinical_records_port: Optional[int] = None,
    clinical_records_sqlite_path: Optional[str] = None,
    namespace: str = "",
    log_level: str = "INFO",
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp/",
) -> None:
    """Main entry point for the MedCP server"""

    # Build configuration
    config_dict: dict[str, Any] = {"namespace": namespace, "log_level": log_level}

    # Add knowledge graph config if provided
    if knowledge_graph_uri and knowledge_graph_username and knowledge_graph_password:
        kg_config = {
            "uri": knowledge_graph_uri,
            "username": knowledge_graph_username,
            "password": knowledge_graph_password,
        }
        if knowledge_graph_database:
            kg_config["database"] = knowledge_graph_database
        config_dict["knowledge_graph"] = kg_config

    # Add clinical records config if provided.
    backend = (clinical_records_backend or "mssql").strip().lower()
    clinical_configured = False
    if backend == "sqlite":
        if clinical_records_sqlite_path:
            config_dict["clinical_records"] = {
                "backend": "sqlite",
                "sqlite_path": clinical_records_sqlite_path,
            }
            clinical_configured = True
    elif backend in ("mssql", "mysql"):
        if clinical_records_server and clinical_records_database and clinical_records_username and clinical_records_password:
            cr = {
                "backend": backend,
                "server": clinical_records_server,
                "database": clinical_records_database,
                "username": clinical_records_username,
                "password": clinical_records_password,
            }
            if clinical_records_port:
                cr["port"] = clinical_records_port
            config_dict["clinical_records"] = cr
            clinical_configured = True

    # Validate at least one database is configured
    if not config_dict.get("knowledge_graph") and not clinical_configured:
        raise ValueError(
            "At least one database must be configured: a knowledge graph, or a "
            "clinical records backend (sqlite path, or mssql/mysql credentials)."
        )

    config = MedCPConfig(**config_dict)

    logger.info("Starting MedCP - Medical Context Protocol Server")
    logger.info("Purpose: Electronic health record databases and biomedical knowledge graph integration")
    logger.info(f"Knowledge graph configured: {'Yes' if config.knowledge_graph else 'No'}")
    if config.clinical_records:
        logger.info(f"Clinical records configured: Yes (backend: {config.clinical_records.backend})")
    else:
        logger.info("Clinical records configured: No")

    mcp = create_medcp_server(config)
    mcp.run()


def main_from_env() -> None:
    """Run the server using configuration from environment variables."""
    main(
        knowledge_graph_uri=os.getenv("KNOWLEDGE_GRAPH_URI"),
        knowledge_graph_username=os.getenv("KNOWLEDGE_GRAPH_USERNAME"),
        knowledge_graph_password=os.getenv("KNOWLEDGE_GRAPH_PASSWORD"),
        knowledge_graph_database=os.getenv("KNOWLEDGE_GRAPH_DATABASE"),
        clinical_records_backend=os.getenv("CLINICAL_RECORDS_BACKEND"),
        clinical_records_server=os.getenv("CLINICAL_RECORDS_SERVER"),
        clinical_records_database=os.getenv("CLINICAL_RECORDS_DATABASE"),
        clinical_records_username=os.getenv("CLINICAL_RECORDS_USERNAME"),
        clinical_records_password=os.getenv("CLINICAL_RECORDS_PASSWORD"),
        clinical_records_port=_int_or_none(os.getenv("CLINICAL_RECORDS_PORT")),
        clinical_records_sqlite_path=os.getenv("CLINICAL_RECORDS_SQLITE_PATH"),
        namespace=os.getenv("MEDCP_NAMESPACE", "MedCP"),
        log_level=os.getenv("MEDCP_LOG_LEVEL", "INFO"),
    )


if __name__ == "__main__":
    # Configuration provided by MCP client through environment variables
    # These are set by the MCP client based on the user_config in the manifest
    main_from_env()
