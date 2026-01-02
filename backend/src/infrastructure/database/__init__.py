"""
Infrastructure de base de données SQLite pour Stock Analyzer.

Ce package fournit:
- Connexion singleton async à SQLite
- Migrations automatiques
- Repositories pour les entités (alerts, trades, journal, news, backtest)

ARCHITECTURE: Couche INFRASTRUCTURE
"""

from src.infrastructure.database.connection import (
    DatabaseConnection,
    get_database,
)
from src.infrastructure.database.migrations import run_migrations

__all__ = [
    "DatabaseConnection",
    "get_database",
    "run_migrations",
]
