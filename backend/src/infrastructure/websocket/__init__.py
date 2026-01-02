"""
Module WebSocket pour les mises a jour en temps reel.

Ce module fournit:
- WebSocketManager: Gestion des connexions WebSocket
- PriceStreamer: Service de streaming des prix (legacy)
- HybridPriceStreamer: Streaming multi-sources avec priorites
- PriceSource: Interface abstraite pour sources de prix
- YahooPriceSource: Implementation Yahoo Finance

ARCHITECTURE:
- Utilise FastAPI WebSocket
- Pattern Observer pour les subscriptions
- Support multi-sources (Yahoo polling, Saxo WebSocket future)
- Tickers prioritaires pour portfolio

UTILISATION:
    from src.infrastructure.websocket import (
        WebSocketManager,
        HybridPriceStreamer,
        get_hybrid_streamer,
    )

    manager = WebSocketManager()
    streamer = get_hybrid_streamer(manager)
    await streamer.start()
"""

from src.infrastructure.websocket.ws_manager import (
    WebSocketManager,
    get_ws_manager,
)
from src.infrastructure.websocket.price_streamer import (
    PriceStreamer,
    get_price_streamer,
)
from src.infrastructure.websocket.hybrid_streamer import (
    HybridPriceStreamer,
    get_hybrid_streamer,
)
from src.infrastructure.websocket.price_source import (
    PriceSource,
    PriceQuote,
)
from src.infrastructure.websocket.yahoo_source import YahooPriceSource

__all__ = [
    # Managers
    "WebSocketManager",
    "get_ws_manager",
    # Streamers
    "PriceStreamer",
    "get_price_streamer",
    "HybridPriceStreamer",
    "get_hybrid_streamer",
    # Sources
    "PriceSource",
    "PriceQuote",
    "YahooPriceSource",
]
