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
    2. Alertes techniques (RSI, MACD, Bollinger Bands) - si activees

    Respecte la configuration des alertes techniques:
    - enabled: activation globale
    - trading_hours_only: heures de trading
    - cooldown: evite les doublons
    """
    try:
        # 1. Verification des alertes de prix classiques (toujours active)
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

        # 2. Verification des alertes techniques (si activees)
        try:
            from src.application.services.alert_config_service import get_alert_config_service

            config_service = get_alert_config_service()

            # Verifier si les alertes techniques sont activees
            if not config_service.should_scan_now():
                logger.debug("Technical alerts: skipped (disabled or outside trading hours)")
                return

            config = config_service.config
            technical_service = get_technical_alert_service()

            # Passer la configuration au service technique
            signals = await technical_service.check_portfolio_signals(
                rsi_enabled=config.rsi_enabled,
                rsi_overbought=config.rsi_overbought,
                rsi_oversold=config.rsi_oversold,
                macd_enabled=config.macd_enabled,
                bollinger_enabled=config.bollinger_enabled,
            )

            if signals:
                # Filtrer les signaux en cooldown
                filtered_signals = []
                for signal in signals:
                    if not config_service.is_in_cooldown(signal.ticker, signal.signal_type):
                        filtered_signals.append(signal)
                        # Enregistrer dans l'historique
                        config_service.add_signal(
                            ticker=signal.ticker,
                            signal_type=signal.signal_type,
                            indicator_value=signal.indicator_value,
                            price=signal.current_price,
                            severity=signal.severity,
                        )

                if filtered_signals:
                    # Filtrer par severite si configure
                    if config.notify_only_high_severity:
                        filtered_signals = [s for s in filtered_signals if s.severity == "high"]

                    if filtered_signals and config.notify_telegram:
                        sent_count = await technical_service.notify_signals(filtered_signals)
                        # Mettre a jour l'historique avec le statut notifie
                        logger.info(
                            f"Technical alerts: {len(filtered_signals)} signals, "
                            f"{sent_count} notifications sent"
                        )
                    else:
                        logger.debug(f"Technical alerts: {len(signals)} signals detected (filtered or notifications disabled)")
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
