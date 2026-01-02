"""
Infrastructure de notifications pour Stock Analyzer.

Fournit:
- Service Telegram pour les alertes de prix
- Interface abstraite pour d'autres canaux (email, SMS, etc.)
"""

from src.infrastructure.notifications.telegram_service import (
    TelegramService,
    get_telegram_service,
)

__all__ = [
    "TelegramService",
    "get_telegram_service",
]
