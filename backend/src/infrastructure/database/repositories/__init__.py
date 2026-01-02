"""
Repositories pour l'accès aux données SQLite.

Chaque repository implémente le pattern Repository pour une entité spécifique.
"""

from src.infrastructure.database.repositories.alert_repository import AlertRepository
from src.infrastructure.database.repositories.trade_repository import TradeRepository
from src.infrastructure.database.repositories.journal_repository import JournalRepository
from src.infrastructure.database.repositories.news_repository import NewsRepository
from src.infrastructure.database.repositories.backtest_repository import BacktestRepository

__all__ = [
    "AlertRepository",
    "TradeRepository",
    "JournalRepository",
    "NewsRepository",
    "BacktestRepository",
]
