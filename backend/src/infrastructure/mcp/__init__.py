"""
Module MCP (Model Context Protocol) pour Stock Analyzer.

Expose les fonctionnalites de Stock Analyzer a Claude Desktop
via le protocole MCP.

ARCHITECTURE:
- mcp_server.py: Serveur MCP principal
- tools/: Outils MCP individuels

UTILISATION:
    python -m src.infrastructure.mcp.mcp_server

Pour configurer Claude Desktop, voir mcp_config.json
"""

from src.infrastructure.mcp.mcp_server import create_mcp_server

__all__ = ["create_mcp_server"]
