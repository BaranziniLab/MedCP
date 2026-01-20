"""
MedCP - Medical Context Protocol Server

An MCP server that integrates electronic health record databases and a large-scale
heterogeneous knowledge graph for rapid clinical record query and fast biomedical
knowledge inference.
"""

__version__ = "0.3.0"

from medcp.server import create_medcp_server, main, MedCPConfig

__all__ = ["create_medcp_server", "main", "MedCPConfig", "__version__"]
