"""
Job de verification periodique des alertes de prix et techniques.

Ce job s'execute toutes les 60 secondes pour:
- Verifier toutes les alertes actives contre les prix actuels
- Verifier les indicateurs techniques (RSI, MACD, Bollinger)
- Declencher les notifications Telegram pour les alertes satisfaites
- Reessayer les notifications echouees

UTILISATION:
    Ce job est automatiquement enregistre par le scheduler.
    Voir src/jobs/scheduler.py pour la configuration.
"""

import logging
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

from src.application.services.alert_service import AlertService
from src.application.services.technical_alert_service import get_technical_alert_service

logger = logging.getLogger(__name__)

# Intervalle de vérification en secondes
CHECK_INTERVAL_SECONDS = 60


async def check_alerts_async() -> None:
    """
    Verifie toutes les alertes actives (version async).

    Cette fonction est appelee par le job APScheduler
    et executee dans une boucle d'evenements asyncio.

    Verifie:
    1. Alertes de prix classiques (price_above, price_below, etc.)
    2. Alertes techniques (RSI, MACD, Bollinger Bands)
    """
    try:
        # 1. Verification des alertes de prix classiques
        service = AlertService()
        result = await service.check_all_alerts()

        if result["triggered"] > 0:
            logger.info(
                f"Alert check: {result['checked']} checked, "
                f"{result['triggered']} triggered"
            )
        else:
            logger.debug(f"Alert check: {result['checked']} checked, none triggered")

        # Reessayer les notifications echouees
        retry_count = await service.retry_failed_notifications()
        if retry_count > 0:
            logger.info(f"Retried {retry_count} failed notification(s)")

        # 2. Verification des alertes techniques (RSI, MACD, Bollinger)
        try:
            technical_service = get_technical_alert_service()
            signals = await technical_service.check_portfolio_signals()

            if signals:
                sent_count = await technical_service.notify_signals(signals)
                logger.info(
                    f"Technical alerts: {len(signals)} signals detected, "
                    f"{sent_count} notifications sent"
                )
            else:
                logger.debug("Technical alerts: no signals detected")

        except Exception as e:
            logger.warning(f"Error checking technical alerts: {e}")

    except Exception as e:
        logger.exception(f"Error in alert checker job: {e}")


def check_alerts_job() -> None:
    """
    Point d'entrée du job pour APScheduler.

    APScheduler appelle cette fonction synchrone,
    qui crée une boucle d'événements pour exécuter la version async.
    """
    try:
        # Créer une nouvelle boucle pour ce thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(check_alerts_async())
        finally:
            loop.close()

    except Exception as e:
        logger.exception(f"Error running alert checker: {e}")


def register_alert_checker(scheduler: "BackgroundScheduler") -> None:
    """
    Enregistre le job de vérification des alertes.

    Args:
        scheduler: Instance APScheduler
    """
    scheduler.add_job(
        check_alerts_job,
        "interval",
        seconds=CHECK_INTERVAL_SECONDS,
        id="alert_checker",
        name="Alert Price Checker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(f"Alert checker job registered (interval: {CHECK_INTERVAL_SECONDS}s)")
