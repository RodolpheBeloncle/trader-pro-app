"""
Injection de dépendances FastAPI.

Fournit les instances des services et use cases pour les routes.
Centralise la création et la gestion du cycle de vie des dépendances.

ARCHITECTURE:
- Pattern Dependency Injection via FastAPI Depends
- Singleton pour les services partagés (Settings, TokenStore)
- Factory pour les use cases (créés à la demande)

UTILISATION:
    from src.api.dependencies import get_analyze_stock_use_case

    @router.get("/analyze")
    async def analyze(use_case = Depends(get_analyze_stock_use_case)):
        ...
"""

import logging
from datetime import datetime
from functools import lru_cache
from typing import Optional

from fastapi import Request

from src.config.settings import Settings
from src.application.interfaces.broker_service import BrokerCredentials
from src.application.use_cases import (
    AnalyzeStockUseCase,
    AnalyzeBatchUseCase,
    GetPortfolioUseCase,
    PlaceOrderUseCase,
)
from src.infrastructure.providers import YahooFinanceProvider
from src.infrastructure.brokers import BrokerFactory
from src.infrastructure.persistence.token_store import FileTokenStore
from src.infrastructure.persistence.encryption import EncryptionService

logger = logging.getLogger(__name__)


# =============================================================================
# SETTINGS (Singleton)
# =============================================================================

@lru_cache()
def get_settings() -> Settings:
    """
    Retourne l'instance des settings (singleton).

    Utilise lru_cache pour ne créer qu'une seule instance.
    """
    return Settings()


# =============================================================================
# INFRASTRUCTURE (Singletons)
# =============================================================================

@lru_cache()
def get_encryption_service() -> Optional[EncryptionService]:
    """
    Retourne le service de chiffrement.

    Retourne None si la clé de chiffrement n'est pas configurée.
    """
    settings = get_settings()

    if not settings.ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not set, token encryption disabled")
        return None

    return EncryptionService(settings.ENCRYPTION_KEY)


@lru_cache()
def get_token_store() -> Optional[FileTokenStore]:
    """
    Retourne le store de tokens.

    Retourne None si le chiffrement n'est pas configuré.
    """
    encryption = get_encryption_service()

    if not encryption:
        logger.warning("Token store disabled (no encryption)")
        return None

    return FileTokenStore(encryption)


@lru_cache()
def get_stock_provider() -> YahooFinanceProvider:
    """
    Retourne le provider Yahoo Finance (singleton).
    """
    return YahooFinanceProvider()


# =============================================================================
# BROKER FACTORY
# =============================================================================

async def get_broker_factory() -> BrokerFactory:
    """
    Retourne la factory de brokers.

    Crée une nouvelle instance à chaque appel car les brokers
    peuvent avoir un état (cache de client_key, etc.).
    """
    settings = get_settings()
    token_store = get_token_store()

    return BrokerFactory(settings, token_store)


# =============================================================================
# USE CASES
# =============================================================================

async def get_analyze_stock_use_case() -> AnalyzeStockUseCase:
    """
    Retourne le use case d'analyse de stock.
    """
    provider = get_stock_provider()
    return AnalyzeStockUseCase(provider)


async def get_analyze_batch_use_case() -> AnalyzeBatchUseCase:
    """
    Retourne le use case d'analyse batch.
    """
    provider = get_stock_provider()
    return AnalyzeBatchUseCase(provider)


async def get_portfolio_use_case(broker_name: str) -> GetPortfolioUseCase:
    """
    Retourne le use case de récupération de portefeuille.

    Args:
        broker_name: Nom du broker
    """
    factory = await get_broker_factory()
    broker = factory.create(broker_name)
    provider = get_stock_provider()

    return GetPortfolioUseCase(broker, provider)


async def get_place_order_use_case(broker_name: str) -> PlaceOrderUseCase:
    """
    Retourne le use case de placement d'ordre.

    Args:
        broker_name: Nom du broker
    """
    factory = await get_broker_factory()
    broker = factory.create(broker_name)

    return PlaceOrderUseCase(broker)


# =============================================================================
# SESSION / CREDENTIALS
# =============================================================================

async def get_credentials(
    request: Request,
    broker: str,
) -> Optional[BrokerCredentials]:
    """
    Récupère les credentials depuis la session.

    Args:
        request: Requête HTTP
        broker: Nom du broker

    Returns:
        BrokerCredentials ou None si non authentifié
    """
    # Vérifier si la session existe
    if not hasattr(request, "session"):
        logger.debug("No session available")
        return None

    session_key = f"{broker}_credentials"
    creds_data = request.session.get(session_key)

    if not creds_data:
        logger.debug(f"No credentials in session for {broker}")
        return None

    try:
        return BrokerCredentials(
            access_token=creds_data["access_token"],
            refresh_token=creds_data.get("refresh_token"),
            expires_at=datetime.fromisoformat(creds_data["expires_at"]),
            broker=broker,
        )
    except (KeyError, ValueError) as e:
        logger.warning(f"Invalid credentials in session: {e}")
        return None


async def get_credentials_from_token_store(
    broker: str,
    user_id: str = "default",
) -> Optional[BrokerCredentials]:
    """
    Récupère les credentials depuis le token store.

    Alternative à la session pour le stockage persistant.

    Args:
        broker: Nom du broker
        user_id: ID de l'utilisateur

    Returns:
        BrokerCredentials ou None
    """
    token_store = get_token_store()

    if not token_store:
        return None

    stored = await token_store.get_token(user_id, broker)

    if not stored:
        return None

    return BrokerCredentials(
        access_token=stored.access_token,
        refresh_token=stored.refresh_token,
        expires_at=stored.expires_at,
        broker=broker,
    )


# =============================================================================
# CLEANUP
# =============================================================================

def clear_caches():
    """
    Vide tous les caches des singletons.

    Utile pour les tests ou le rechargement de configuration.
    """
    get_settings.cache_clear()
    get_encryption_service.cache_clear()
    get_token_store.cache_clear()
    get_stock_provider.cache_clear()
    logger.info("All dependency caches cleared")
