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
from src.api.routes.alerts import router as alerts_router
from src.api.routes.journal import router as journal_router
from src.api.routes.news import router as news_router
from src.api.routes.backtest import router as backtest_router
from src.api.routes.sources import router as sources_router
from src.api.routes.saxo import router as saxo_router
from src.api.routes.notifications import router as notifications_router
from src.api.routes.config import router as config_router

__all__ = [
    "health_router",
    "stocks_router",
    "brokers_router",
    "markets_router",
    "websocket_router",
    "recommendations_router",
    "alerts_router",
    "journal_router",
    "news_router",
    "backtest_router",
    "sources_router",
    "saxo_router",
    "notifications_router",
    "config_router",
]
