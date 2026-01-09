"""
Factory de l'application FastAPI.

Crée et configure l'application FastAPI avec:
- Routes
- Middlewares (CORS, sessions)
- Handlers d'erreurs
- OpenAPI/Swagger

ARCHITECTURE:
- Pattern Application Factory
- Configuration centralisée
- Extensible pour tests

UTILISATION:
    from src.api.app import create_app

    app = create_app()
    # ou pour tests
    app = create_app(settings=test_settings)
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from src.config.settings import Settings
from src.api.dependencies import get_settings
from src.api.routes import (
    health_router,
    stocks_router,
    brokers_router,
    markets_router,
    websocket_router,
    recommendations_router,
    alerts_router,
    journal_router,
    news_router,
    backtest_router,
    sources_router,
    saxo_router,
    notifications_router,
    config_router,
)
from src.domain.exceptions import (
    DomainError,
    TickerNotFoundError,
    TokenExpiredError,
    BrokerAuthenticationError,
    BrokerNotConfiguredError,
    OrderValidationError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """
    Crée et configure l'application FastAPI.

    Args:
        settings: Settings optionnels (pour les tests)

    Returns:
        Application FastAPI configurée
    """
    if settings is None:
        settings = get_settings()

    # Créer l'application
    app = FastAPI(
        title="Stock Analyzer API",
        description=(
            "API pour l'analyse de stocks selon la méthodologie 'trader writer'. "
            "Calcule les performances sur 5 périodes et identifie les stocks résilients."
        ),
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Configurer les middlewares
    configure_middlewares(app, settings)

    # Configurer les handlers d'erreurs
    configure_error_handlers(app)

    # Enregistrer les routes
    register_routes(app)

    # Événements de cycle de vie
    configure_lifecycle(app)

    logger.info("Application created and configured")
    return app


def configure_middlewares(app: FastAPI, settings: Settings) -> None:
    """
    Configure les middlewares de l'application.

    Args:
        app: Application FastAPI
        settings: Configuration
    """
    # CORS
    origins = settings.cors_origins_list

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Sessions (pour stocker les credentials OAuth)
    session_secret = settings.SESSION_SECRET or "default-secret-change-in-production"
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="session",
        max_age=86400,  # 24 heures
        https_only=not settings.DEBUG,
    )

    logger.debug("Middlewares configured")


def configure_error_handlers(app: FastAPI) -> None:
    """
    Configure les handlers d'erreurs globaux.

    Args:
        app: Application FastAPI
    """

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        """Handler pour les erreurs du domaine."""
        status_code = get_status_code_for_error(exc)

        logger.warning(f"Domain error: {exc.code} - {exc.message}")

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        """Handler pour les erreurs non gérées."""
        logger.exception(f"Unhandled error: {exc}")

        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "Une erreur inattendue s'est produite",
                "details": {},
            },
        )

    logger.debug("Error handlers configured")


def get_status_code_for_error(exc: DomainError) -> int:
    """
    Détermine le code HTTP pour une erreur du domaine.

    Args:
        exc: Exception du domaine

    Returns:
        Code HTTP approprié
    """
    if isinstance(exc, TickerNotFoundError):
        return 404
    if isinstance(exc, (TokenExpiredError, BrokerAuthenticationError)):
        return 401
    if isinstance(exc, BrokerNotConfiguredError):
        return 400
    if isinstance(exc, OrderValidationError):
        return 400
    if isinstance(exc, RateLimitError):
        return 429
    return 400


def register_routes(app: FastAPI) -> None:
    """
    Enregistre tous les routeurs.

    Args:
        app: Application FastAPI
    """
    # Prefixe /api pour toutes les routes HTTP
    app.include_router(health_router, prefix="/api")
    app.include_router(stocks_router, prefix="/api")
    app.include_router(brokers_router, prefix="/api")
    app.include_router(markets_router, prefix="/api")
    app.include_router(recommendations_router, prefix="/api")
    app.include_router(alerts_router, prefix="/api")
    app.include_router(journal_router, prefix="/api")
    app.include_router(news_router, prefix="/api")
    app.include_router(backtest_router, prefix="/api")
    app.include_router(sources_router, prefix="/api")
    app.include_router(saxo_router, prefix="/api")
    app.include_router(notifications_router, prefix="/api")
    app.include_router(config_router, prefix="/api")

    # WebSocket routes (pas de prefixe /api)
    app.include_router(websocket_router)

    logger.debug("Routes registered")


def configure_lifecycle(app: FastAPI) -> None:
    """
    Configure les evenements du cycle de vie.

    Args:
        app: Application FastAPI
    """
    from src.jobs.scheduler import create_scheduler, start_scheduler, stop_scheduler
    from src.infrastructure.websocket.ws_manager import get_ws_manager
    from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer
    from src.infrastructure.database.connection import init_database, close_database

    @app.on_event("startup")
    async def startup():
        """Evenement de demarrage."""
        logger.info("Application starting up...")

        # Charger la configuration (fichier chiffré ou .env)
        # et appliquer aux settings globaux
        try:
            from src.application.services.config_service import get_config_service
            get_config_service()  # Initialise et applique les credentials
            logger.info("Configuration service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize config service: {e}")

        # Initialiser la base de données SQLite
        try:
            await init_database()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

        # Verifier la configuration
        settings = get_settings()

        if settings.is_saxo_configured:
            logger.info("Saxo broker configured")
        else:
            logger.warning("Saxo broker NOT configured")

        if settings.is_telegram_configured:
            logger.info("Telegram notifications configured")
        else:
            logger.warning("Telegram NOT configured")

        if settings.is_finnhub_configured:
            logger.info("Finnhub news API configured")
        else:
            logger.warning("Finnhub NOT configured")

        # Demarrer le scheduler de jobs
        try:
            scheduler = create_scheduler()
            start_scheduler(scheduler)
            logger.info("Background job scheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

        # Demarrer le hybrid price streamer
        try:
            ws_manager = get_ws_manager()
            price_streamer = get_hybrid_streamer(ws_manager)
            await price_streamer.start()
            print(f"[STREAMER] Started - running: {price_streamer.is_running}, sources: {list(price_streamer._sources.keys())}", flush=True)
            logger.info("Hybrid price streamer started")
        except Exception as e:
            print(f"[STREAMER] Failed to start: {e}", flush=True)
            logger.error(f"Failed to start price streamer: {e}")

        # Executer le nettoyage au demarrage (news cache, WAL checkpoint)
        try:
            from src.jobs.cleanup_jobs import run_startup_cleanup_async
            await run_startup_cleanup_async()
        except Exception as e:
            logger.error(f"Startup cleanup failed (non-blocking): {e}")

        logger.info("Application startup complete")

    @app.on_event("shutdown")
    async def shutdown():
        """Evenement d'arret."""
        logger.info("Application shutting down...")

        # Arreter le hybrid price streamer
        try:
            price_streamer = get_hybrid_streamer()
            await price_streamer.stop()
            logger.info("Hybrid price streamer stopped")
        except Exception as e:
            logger.error(f"Error stopping price streamer: {e}")

        # Arreter le scheduler
        try:
            stop_scheduler()
            logger.info("Background job scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")

        # Fermer la connexion à la base de données
        try:
            await close_database()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

        # Nettoyer les ressources si necessaire
        from src.api.dependencies import clear_caches
        clear_caches()

        logger.info("Application shutdown complete")


# =============================================================================
# INSTANCE PAR DÉFAUT
# =============================================================================

# Pour uvicorn: uvicorn src.api.app:app
app = create_app()
