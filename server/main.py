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

import anyio
from mcp.server import CacheHint, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from neo4j import GraphDatabase, Result, Transaction
from neo4j.exceptions import ClientError, Neo4jError
from pydantic import BaseModel, Field, model_validator

__version__ = "0.10.0"

logger = logging.getLogger("MedCP")

SQLBackend = Literal["mssql", "mysql", "sqlite"]
MAX_TOOL_NAME_LENGTH = 128
LONGEST_TOOL_NAME = "get_knowledge_graph_schema"


def _load_spoke_defaults() -> dict:
    """Return the default SPOKE (production) knowledge-graph connection.

    The credentials for the lab-hosted, read-only SPOKE graph are shipped
    obfuscated so they are not sitting in plaintext in the repo, letting users
    query SPOKE out of the box without supplying any credentials of their own.

    NOTE: this is obfuscation, not secrecy — the derivation key ships with the
    code, so a determined reader can recover the value. SPOKE prod is a shared,
    read-only research graph, so this is acceptable; do not use this mechanism
    for genuinely sensitive secrets.
    """
    import base64
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt = b"medcp-spoke-defaults-v1"
    passphrase = b"".join([b"MedCP", b"::", b"spoke", b"-prod", b"::", b"kg-default", b"-2026"])
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
    key = base64.urlsafe_b64encode(kdf.derive(passphrase))
    token = (
        b"gAAAAABqYQ53ZEor9C6vOTxH8TAl2mEjUwzHbY9kvim7kDPqJOY4fkr2bvBxci1dKfbaNS3bu"
        b"CsqdBIOtq4E3a9dGIblWzPDtkylRL9lu1v6gB3K-GePbVnsVWPm7aFawa89yz6ZkOXOgED_2G"
        b"VLdOOYoxbE9MS0C4dMhpJipffIw6BcRF9-i616diHoTdjzaMtBVhDWHeHcELBq2J-X_BpQj6Jd"
        b"tss-UA=="
    )
    return json.loads(Fernet(key).decrypt(token))


class KnowledgeGraphConfig(BaseModel):
    """Biomedical knowledge graph configuration (Neo4j or compatible)"""
    uri: str = Field(..., description="Knowledge graph connection URI (e.g., bolt://localhost:7687)")
    username: str = Field("neo4j", description="Knowledge graph database username")
    password: str = Field("", description="Knowledge graph database password")
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
    """Validate a tool namespace and format it with a trailing dash."""
    if not namespace:
        return ""

    prefix = namespace if namespace.endswith("-") else namespace + "-"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", prefix):
        raise ValueError(
            "MEDCP_NAMESPACE may contain only ASCII letters, digits, '_', '-', and '.'"
        )
    if len(prefix) + len(LONGEST_TOOL_NAME) > MAX_TOOL_NAME_LENGTH:
        raise ValueError(
            f"MEDCP_NAMESPACE is too long; generated tool names must be at most "
            f"{MAX_TOOL_NAME_LENGTH} characters"
        )
    return prefix


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


def create_medcp_server(config: MedCPConfig) -> MCPServer:
    """Create MedCP server with configured biomedical database tools"""

    # Set up logging
    logging.basicConfig(level=getattr(logging, config.log_level.upper()))

    private_catalog_cache = CacheHint(ttl_ms=300_000, scope="private")
    mcp = MCPServer(
        "MedCP",
        description=(
            "Read-only electronic health record and biomedical knowledge graph tools"
        ),
        version=__version__,
        cache_hints={
            "server/discover": private_catalog_cache,
            "tools/list": private_catalog_cache,
        },
    )
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

        def _get_knowledge_graph_schema_impl() -> CallToolResult:
            """Blocking schema fetch (apoc.meta.schema); run off the event loop via anyio.to_thread."""

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

                    return CallToolResult(content=[TextContent(type="text", text=json.dumps(schema_clean))])

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
            name=f"{namespace_prefix}get_knowledge_graph_schema",
            annotations=ToolAnnotations(
                title="Get Knowledge Graph Schema",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=True
            )
        )
        async def get_knowledge_graph_schema() -> CallToolResult:
            """
            List all nodes, their attributes and their relationships in the biomedical knowledge graph.
            This provides the schema for drug-disease associations, protein interactions, pathways,
            and other biomedical entities. Requires APOC plugin to be installed and enabled.

            The blocking Neo4j session runs in a worker thread (anyio.to_thread).
            """
            return await anyio.to_thread.run_sync(_get_knowledge_graph_schema_impl)

        def _query_knowledge_graph_impl(cypher_query: str, parameters: dict) -> CallToolResult:
            """Blocking Cypher query; run off the event loop via anyio.to_thread."""
            try:
                with kg_driver.session(database=config.knowledge_graph.database) as session:
                    results_json_str = session.execute_read(_read_knowledge_graph, cypher_query, parameters)

                    logger.debug(f"Knowledge graph query returned {len(results_json_str)} characters")

                    return CallToolResult(content=[TextContent(type="text", text=results_json_str)])

            except Neo4jError as e:
                logger.error(f"Knowledge graph error executing query: {e}")
                raise ToolError(f"Biomedical knowledge graph error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in knowledge graph query: {e}")
                raise ToolError(f"Error executing biomedical knowledge query: {e}")

        @mcp.tool(
            name=f"{namespace_prefix}query_knowledge_graph",
            annotations=ToolAnnotations(
                title="Query Biomedical Knowledge Graph",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=True
            )
        )
        async def query_knowledge_graph(
            cypher_query: str = Field(..., description="The Cypher query for biomedical knowledge inference (e.g., drug-disease associations, protein interactions)"),
            parameters: dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the knowledge graph query")
        ) -> CallToolResult:
            """Execute a read-only Cypher query on the biomedical knowledge graph for fast knowledge inference.

            The blocking Neo4j session runs in a worker thread (anyio.to_thread) so
            concurrent tool calls do not block the async event loop.
            """
            if _is_write_query(cypher_query):
                raise ToolError("Only read queries (MATCH, RETURN, etc.) are allowed for knowledge graph queries")

            return await anyio.to_thread.run_sync(_query_knowledge_graph_impl, cypher_query, parameters)

    # Clinical Records Tools
    if clinical_config:

        def _query_clinical_records_impl(sql_query: str) -> CallToolResult:
            """Blocking clinical query; run off the event loop via anyio.to_thread."""
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

                return CallToolResult(content=[TextContent(type="text", text=result_text)])

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
            name=f"{namespace_prefix}query_clinical_records",
            annotations=ToolAnnotations(
                title="Query Electronic Health Records",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False
            )
        )
        async def query_clinical_records(
            sql_query: str = Field(..., description="SQL SELECT query for rapid clinical record retrieval (read-only)")
        ) -> CallToolResult:
            """Execute a READ-ONLY SQL query on electronic health records for rapid clinical data retrieval.

            Works against the configured backend (SQL Server, MySQL, or a local SQLite file).
            The blocking database call runs in a worker thread (anyio.to_thread) so
            concurrent tool calls do not block the async event loop.
            """

            # Validate query is read-only (cheap; do it before offloading to a thread)
            if not ClinicalQueryValidator.is_read_only_clinical_query(sql_query):
                raise ToolError("Only SELECT queries are allowed for clinical record queries")

            return await anyio.to_thread.run_sync(_query_clinical_records_impl, sql_query)

        def _list_clinical_tables_impl() -> CallToolResult:
            """Blocking table listing; run off the event loop via anyio.to_thread."""
            if clinical_config.backend == "sqlite":
                query = (
                    "SELECT 'main' AS table_schema, name AS table_name, type AS table_type "
                    "FROM sqlite_master "
                    "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            elif clinical_config.backend == "mysql":
                # In MySQL, INFORMATION_SCHEMA.TABLES spans every database, so scope
                # it to the connected one (otherwise mysql/sys system tables leak in).
                query = (
                    "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = DATABASE() "
                    "ORDER BY TABLE_NAME"
                )
            else:
                # SQL Server's INFORMATION_SCHEMA is already scoped to the current database.
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

                return CallToolResult(content=[TextContent(type="text", text=json.dumps(table_list, indent=2))])

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

        @mcp.tool(
            name=f"{namespace_prefix}list_clinical_tables",
            annotations=ToolAnnotations(
                title="List Clinical Data Tables",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False
            )
        )
        async def list_clinical_tables() -> CallToolResult:
            """List all available clinical data tables in the electronic health records database.

            The blocking database call runs in a worker thread (anyio.to_thread).
            """
            return await anyio.to_thread.run_sync(_list_clinical_tables_impl)

    return mcp


def _int_or_none(value: Optional[str]) -> Optional[int]:
    """Parse an optional integer environment value."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _env_bool(value: Optional[str]) -> bool:
    """Parse a truthy environment value ('1', 'true', 'yes', 'on')."""
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def main(
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
    disable_knowledge_graph: bool = False,
    namespace: str = "",
    log_level: str = "INFO",
) -> None:
    """Run the MedCP server over stdio.

    Network transports are intentionally not exposed by this entry point.
    Deploying clinical-data tools over HTTP requires a separate authentication,
    origin-validation, and data-governance review.
    """

    # Build configuration
    config_dict: dict[str, Any] = {"namespace": namespace, "log_level": log_level}

    # Knowledge graph selection:
    #   * user supplies their own KNOWLEDGE_GRAPH_URI  -> use their graph
    #   * nothing supplied                             -> default to SPOKE (prod),
    #     whose read-only credentials ship obfuscated so no config is needed
    #   * explicitly disabled                          -> no knowledge graph
    user_kg_uri = (knowledge_graph_uri or "").strip()
    if disable_knowledge_graph:
        logger.info("Knowledge graph disabled by configuration")
    elif user_kg_uri:
        config_dict["knowledge_graph"] = {
            "uri": user_kg_uri,
            "username": knowledge_graph_username or "neo4j",
            "password": knowledge_graph_password or "",
            "database": knowledge_graph_database or "neo4j",
        }
    else:
        # No user-provided graph: fall back to the bundled SPOKE production graph.
        try:
            config_dict["knowledge_graph"] = _load_spoke_defaults()
            logger.info("Using bundled SPOKE production knowledge graph (no user config supplied)")
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Could not load bundled SPOKE defaults: {e}")

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
        disable_knowledge_graph=_env_bool(os.getenv("MEDCP_DISABLE_KNOWLEDGE_GRAPH")),
        namespace=os.getenv("MEDCP_NAMESPACE", "MedCP"),
        log_level=os.getenv("MEDCP_LOG_LEVEL", "INFO"),
    )


if __name__ == "__main__":
    # Configuration provided by MCP client through environment variables
    # These are set by the MCP client based on the user_config in the manifest
    main_from_env()
