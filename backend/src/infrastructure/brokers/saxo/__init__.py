"""
Module d'intégration Saxo Bank.

Fournit l'implémentation complète du broker Saxo:
- OAuth2 avec PKCE
- Client API HTTP
- Mappers pour conversion des données
- Service broker complet
"""

from src.infrastructure.brokers.saxo.saxo_broker import (
    SaxoBroker,
    create_saxo_broker,
)
from src.infrastructure.brokers.saxo.saxo_oauth import (
    SaxoOAuthService,
    create_saxo_oauth_service,
    TokenResponse,
)
from src.infrastructure.brokers.saxo.saxo_api_client import (
    SaxoApiClient,
    create_saxo_api_client,
)

__all__ = [
    # Broker principal
    "SaxoBroker",
    "create_saxo_broker",
    # OAuth
    "SaxoOAuthService",
    "create_saxo_oauth_service",
    "TokenResponse",
    # API Client
    "SaxoApiClient",
    "create_saxo_api_client",
]
