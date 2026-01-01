"""
Module WebSocket pour les mises a jour en temps reel.

Ce module fournit:
- WebSocketManager: Gestion des connexions WebSocket
- PriceStreamer: Service de streaming des prix

ARCHITECTURE:
- Utilise FastAPI WebSocket
- Pattern Observer pour les subscriptions
- Polling Yahoo Finance pour les prix

UTILISATION:
    from src.infrastructure.websocket import WebSocketManager, PriceStreamer

    manager = WebSocketManager()
    streamer = PriceStreamer(manager)
"""

from src.infrastructure.websocket.ws_manager import WebSocketManager
from src.infrastructure.websocket.price_streamer import PriceStreamer

__all__ = [
    "WebSocketManager",
    "PriceStreamer",
]
