"""
Outils MCP pour Stock Analyzer.

Chaque outil est une fonction async qui retourne une string JSON formatee.
Ces outils sont exposes via le serveur MCP pour Claude Desktop.
"""

from src.infrastructure.mcp.tools.analyze_tool import (
    analyze_stock_tool,
    analyze_batch_tool,
)
from src.infrastructure.mcp.tools.portfolio_tool import get_portfolio_tool
from src.infrastructure.mcp.tools.market_tool import (
    list_markets_tool,
    get_market_tickers_tool,
)

__all__ = [
    "analyze_stock_tool",
    "analyze_batch_tool",
    "get_portfolio_tool",
    "list_markets_tool",
    "get_market_tickers_tool",
]
