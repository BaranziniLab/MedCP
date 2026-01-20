"""
MedCP - Medical Context Protocol Server

An MCP server that integrates electronic health record databases and a large-scale 
heterogeneous knowledge graph for rapid clinical record query and fast biomedical 
knowledge inference.
"""
import json
import logging
import os
import re
import sys
from typing import Any, Literal, Optional

import pymssql
from fastmcp.exceptions import ToolError
from fastmcp.server import FastMCP
from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import ToolAnnotations
from neo4j import Driver, GraphDatabase, Result, Transaction
from neo4j.exceptions import ClientError, Neo4jError
from pydantic import BaseModel, Field

logger = logging.getLogger("MedCP")

class KnowledgeGraphConfig(BaseModel):
    """Biomedical knowledge graph configuration (Neo4j)"""
    uri: str = Field(..., description="Knowledge graph connection URI (e.g., bolt://localhost:7687)")
    username: str = Field(..., description="Knowledge graph database username")
    password: str = Field(..., description="Knowledge graph database password")
    database: str = Field("neo4j", description="Knowledge graph database name")


class ClinicalRecordsConfig(BaseModel):
    """Electronic health records database configuration (SQL Server)"""
    server: str = Field(..., description="EHR database server host (e.g., ehr-server.hospital.org)")
    database: str = Field(..., description="EHR database name")
    username: str = Field(..., description="EHR database username")
    password: str = Field(..., description="EHR database password")


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
    return re.search(r"\b(MERGE|CREATE|SET|DELETE|REMOVE|ADD|INSERT|UPDATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|SP_)\b", query, re.IGNORECASE) is not None


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
            
        # Check for SQL injection patterns
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
        """Get clinical records database connection"""
        if not clinical_config:
            raise ToolError("Clinical records database not configured")
        
        try:
            return pymssql.connect(
                server=clinical_config.server,
                user=clinical_config.username,
                password=clinical_config.password,
                database=clinical_config.database
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
            """Execute a READ-ONLY SQL query on electronic health records for rapid clinical data retrieval."""
            
            # Validate query is read-only
            if not ClinicalQueryValidator.is_read_only_clinical_query(sql_query):
                raise ToolError("Only SELECT queries are allowed for clinical record queries")
            
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
                    csv_lines.extend([",".join(map(str, row)) for row in rows])
                    result_text = "\n".join(csv_lines)
                else:
                    result_text = "Clinical query executed successfully (no results returned)"
                
                cursor.close()
                conn.close()
                
                logger.debug(f"Clinical records query returned {len(rows) if rows else 0} rows")
                
                return ToolResult(content=[TextContent(type="text", text=result_text)])
                
            except Exception as e:
                logger.error(f"Clinical records query error: {e}")
                raise ToolError(f"Electronic health records error: {e}")

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
            
            query = """
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
            
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
                conn.close()
                
                return ToolResult(content=[TextContent(type="text", text=json.dumps(table_list, indent=2))])
                
            except Exception as e:
                logger.error(f"Error listing clinical tables: {e}")
                raise ToolError(f"Error listing clinical data tables: {e}")
    
    return mcp


def main(
    transport: Literal["stdio", "sse", "http"] = "stdio",
    knowledge_graph_uri: Optional[str] = None,
    knowledge_graph_username: Optional[str] = None,
    knowledge_graph_password: Optional[str] = None,
    knowledge_graph_database: Optional[str] = None,
    clinical_records_server: Optional[str] = None,
    clinical_records_database: Optional[str] = None,
    clinical_records_username: Optional[str] = None,
    clinical_records_password: Optional[str] = None,
    namespace: str = "",
    log_level: str = "INFO",
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp/",
) -> None:
    """Main entry point for the MedCP server"""
    
    # Build configuration
    config_dict = {"namespace": namespace, "log_level": log_level}
    
    # Add knowledge graph config if provided
    if knowledge_graph_uri and knowledge_graph_username and knowledge_graph_password:
        config_dict["knowledge_graph"] = {
            "uri": knowledge_graph_uri,
            "username": knowledge_graph_username,
            "password": knowledge_graph_password,
            "database": knowledge_graph_database
        }
    
    # Add clinical records config if provided
    if clinical_records_server and clinical_records_database and clinical_records_username and clinical_records_password:
        config_dict["clinical_records"] = {
            "server": clinical_records_server,
            "database": clinical_records_database,
            "username": clinical_records_username,
            "password": clinical_records_password
        }
    
    # Validate at least one database is configured
    if not config_dict.get("knowledge_graph") and not config_dict.get("clinical_records"):
        raise ValueError("At least one database (knowledge graph or clinical records) must be configured")
    
    config = MedCPConfig(**config_dict)
    
    logger.info("Starting MedCP - Medical Context Protocol Server")
    logger.info("Purpose: Electronic health record databases and biomedical knowledge graph integration")
    logger.info(f"Knowledge graph configured: {'Yes' if config.knowledge_graph else 'No'}")
    logger.info(f"Clinical records configured: {'Yes' if config.clinical_records else 'No'}")
    
    mcp = create_medcp_server(config)
    mcp.run()


if __name__ == "__main__":
    # Configuration provided by MCP client through environment variables
    # These are set by the MCP client based on the user_config in the manifest
    main(
        knowledge_graph_uri=os.getenv("KNOWLEDGE_GRAPH_URI"),
        knowledge_graph_username=os.getenv("KNOWLEDGE_GRAPH_USERNAME"),
        knowledge_graph_password=os.getenv("KNOWLEDGE_GRAPH_PASSWORD"),
        knowledge_graph_database=os.getenv("KNOWLEDGE_GRAPH_DATABASE"),
        clinical_records_server=os.getenv("CLINICAL_RECORDS_SERVER"),
        clinical_records_database=os.getenv("CLINICAL_RECORDS_DATABASE"),
        clinical_records_username=os.getenv("CLINICAL_RECORDS_USERNAME"),
        clinical_records_password=os.getenv("CLINICAL_RECORDS_PASSWORD"),
        namespace=os.getenv("MEDCP_NAMESPACE", "MedCP"),
        log_level=os.getenv("MEDCP_LOG_LEVEL", "INFO")
    )

