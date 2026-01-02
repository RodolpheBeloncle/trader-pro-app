"""
Module d'integration Saxo Bank.

Fournit l'implementation complete du broker Saxo:
- OAuth2 simplifie
- Client API HTTP
- Mappers pour conversion des donnees
- Service broker complet
"""

from src.infrastructure.brokers.saxo.saxo_broker import (
    SaxoBroker,
    create_saxo_broker,
)
from src.infrastructure.brokers.saxo.saxo_auth import (
    SaxoAuthService,
    SaxoToken,
    SaxoTokenManager,
    get_saxo_auth,
)
from src.infrastructure.brokers.saxo.saxo_api_client import (
    SaxoApiClient,
    create_saxo_api_client,
)

__all__ = [
    # Broker principal
    "SaxoBroker",
    "create_saxo_broker",
    # Auth (nouveau)
    "SaxoAuthService",
    "SaxoToken",
    "SaxoTokenManager",
    "get_saxo_auth",
    # API Client
    "SaxoApiClient",
    "create_saxo_api_client",
]
