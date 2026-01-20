"""
MedCP - Medical Context Protocol Server

Command-line interface for the MedCP server.
"""

import logging
import os
from typing import Optional

from medcp.server import main as server_main


logger = logging.getLogger("MedCP")


def main() -> None:
    """
    Main entry point for the MedCP CLI.

    Reads configuration from environment variables and starts the server.
    Environment variables are typically set by the MCP client.
    """

    # Set up logging
    log_level = os.getenv("MEDCP_LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, log_level.upper()))

    logger.info("Starting MedCP - Medical Context Protocol Server")

    # Run the server with configuration from environment variables
    server_main(
        knowledge_graph_uri=os.getenv("KNOWLEDGE_GRAPH_URI"),
        knowledge_graph_username=os.getenv("KNOWLEDGE_GRAPH_USERNAME"),
        knowledge_graph_password=os.getenv("KNOWLEDGE_GRAPH_PASSWORD"),
        knowledge_graph_database=os.getenv("KNOWLEDGE_GRAPH_DATABASE"),
        clinical_records_server=os.getenv("CLINICAL_RECORDS_SERVER"),
        clinical_records_database=os.getenv("CLINICAL_RECORDS_DATABASE"),
        clinical_records_username=os.getenv("CLINICAL_RECORDS_USERNAME"),
        clinical_records_password=os.getenv("CLINICAL_RECORDS_PASSWORD"),
        namespace=os.getenv("MEDCP_NAMESPACE", ""),
        log_level=log_level
    )


if __name__ == "__main__":
    main()
