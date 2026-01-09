"""
Job de rafraichissement proactif des tokens Saxo.

Ce job s'execute regulierement pour maintenir les tokens valides
AVANT qu'ils n'expirent, evitant ainsi les deconnexions.

ARCHITECTURE:
- Execute toutes les 10 minutes (reduit de 15 pour plus de securite)
- Utilise TokenRefreshService avec retry et backoff
- Run au demarrage pour garantir un token frais
- Notifie via Telegram si le refresh echoue

SECURITE:
- Refresh proactif AVANT expiration
- Track les deux tokens: access ET refresh
- Retry avec backoff exponentiel
- Health monitoring
"""

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from src.services.token_refresh_service import (
    get_token_refresh_service,
    TokenStatus,
    RefreshResult,
)

logger = logging.getLogger(__name__)

# Intervalle de verification (5 minutes pour refresh agressif)
# Avec offline_access scope, le refresh_token dure plusieurs jours
# mais on refresh souvent pour garantir que le token reste frais
REFRESH_INTERVAL_MINUTES = 5


def refresh_saxo_token_job() -> RefreshResult:
    """
    Job de rafraichissement proactif du token Saxo.

    Execute par le scheduler periodiquement.
    Utilise le TokenRefreshService pour gerer le refresh intelligemment.

    Returns:
        RefreshResult avec le resultat de l'operation
    """
    try:
        service = get_token_refresh_service()
        result = service.check_and_refresh()

        # Log selon le resultat (avec print pour visibilite Docker)
        if result.status == TokenStatus.MISSING:
            print("[TOKEN] No Saxo token found, skipping refresh", flush=True)
        elif result.status == TokenStatus.VALID:
            expires_min = result.access_token_expires_in // 60
            print(f"[TOKEN] Saxo token OK - expires in {expires_min} min", flush=True)
            logger.info(f"Token OK - expires in {result.access_token_expires_in}s ({expires_min}min)")
        elif result.status == TokenStatus.REFRESH_FAILED:
            print(f"[TOKEN] Saxo token refresh FAILED: {result.error}", flush=True)
            logger.error(f"Token refresh FAILED: {result.error}")
        elif result.status == TokenStatus.EXPIRING_SOON:
            print("[TOKEN] Saxo token expiring soon, refresh attempted", flush=True)
            logger.warning("Token expiring soon but refresh not attempted")

        return result

    except Exception as e:
        logger.exception(f"Error in token refresh job: {e}")
        return RefreshResult(
            success=False,
            status=TokenStatus.REFRESH_FAILED,
            error=str(e)
        )


def register_token_refresh_job(scheduler: BackgroundScheduler) -> None:
    """
    Enregistre le job de refresh dans le scheduler.

    Configuration:
    - Intervalle: 10 minutes
    - Run au demarrage (next_run_time=now)
    - coalesce=True pour eviter les executions multiples
    - max_instances=1 pour eviter les conflits

    Args:
        scheduler: Instance du scheduler APScheduler
    """
    from datetime import datetime

    # Job periodique
    scheduler.add_job(
        refresh_saxo_token_job,
        "interval",
        minutes=REFRESH_INTERVAL_MINUTES,
        id="saxo_token_refresh",
        name="Saxo Token Refresh",
        replace_existing=True,
        next_run_time=datetime.now(),  # Run immediatement au demarrage
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 5,  # 5 minutes de grace
    )

    logger.info(
        f"Saxo token refresh job registered "
        f"(every {REFRESH_INTERVAL_MINUTES} minutes, runs at startup)"
    )


def force_refresh_token() -> dict:
    """
    Force un refresh immediat du token.

    Utile pour les tests ou pour forcer un refresh manuel.

    Returns:
        dict avec le statut du refresh et les metriques
    """
    try:
        service = get_token_refresh_service()

        # Forcer un refresh en modifiant temporairement la strategie
        from src.config.settings import get_settings
        from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth

        settings = get_settings()

        if not settings.is_saxo_configured:
            return {"success": False, "error": "Saxo not configured"}

        auth = get_saxo_auth(settings)
        token = auth.token_manager.get(auth.environment)

        if not token:
            return {"success": False, "error": "No token found"}

        if not token.refresh_token:
            return {"success": False, "error": "No refresh token available"}

        # Executer le refresh directement
        result = service._do_refresh_with_retry(auth, token.refresh_token)

        return {
            "success": result.success,
            "status": result.status.value,
            "environment": auth.environment,
            "expires_in_seconds": result.access_token_expires_in,
            "expires_in_minutes": result.access_token_expires_in // 60,
            "attempts": result.attempts,
            "error": result.error,
            "stats": service.stats,
        }

    except Exception as e:
        logger.exception(f"Force refresh failed: {e}")
        return {"success": False, "error": str(e)}


def get_token_health() -> dict:
    """
    Retourne l'etat de sante du systeme de tokens.

    Returns:
        dict avec l'etat de sante et les statistiques
    """
    try:
        service = get_token_refresh_service()
        health = service.get_health()

        if health is None:
            return {
                "status": "not_configured",
                "message": "Saxo not configured",
            }

        return {
            "status": health.status.value,
            "environment": health.environment,
            "access_token": {
                "expires_in_seconds": health.access_token_expires_in,
                "expires_in_minutes": health.access_token_expires_in // 60,
            },
            "refresh_token": {
                "expires_in_seconds": health.refresh_token_expires_in,
                "expires_in_minutes": health.refresh_token_expires_in // 60,
            },
            "last_refresh": health.last_refresh.isoformat() if health.last_refresh else None,
            "next_refresh_in_seconds": health.next_refresh_in,
            "consecutive_failures": health.consecutive_failures,
            "stats": service.stats,
        }

    except Exception as e:
        logger.exception(f"Failed to get token health: {e}")
        return {"status": "error", "error": str(e)}
