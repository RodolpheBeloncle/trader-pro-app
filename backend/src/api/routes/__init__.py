"""
Routes API.

Expose tous les routeurs pour inclusion dans l'application FastAPI.
"""

from src.api.routes.health import router as health_router
from src.api.routes.stocks import router as stocks_router
from src.api.routes.brokers import router as brokers_router
from src.api.routes.markets import router as markets_router
from src.api.routes.websocket import router as websocket_router
from src.api.routes.recommendations import router as recommendations_router

__all__ = [
    "health_router",
    "stocks_router",
    "brokers_router",
    "markets_router",
    "websocket_router",
    "recommendations_router",
]
