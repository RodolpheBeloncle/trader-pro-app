"""
Job de monitoring du portefeuille Saxo.

Ce job s'execute toutes les 5 minutes pour:
- Detecter les nouvelles positions dans le portefeuille Saxo
- Creer automatiquement des alertes Stop Loss/Take Profit
- Notifier via Telegram les nouvelles positions

PARAMETRES PAR DEFAUT:
- Stop Loss: 8% sous le prix d'entree
- Take Profit: 24% au-dessus du prix d'entree

UTILISATION:
    Ce job est automatiquement enregistre par le scheduler.
    Voir src/jobs/scheduler.py pour la configuration.
"""

import logging
import asyncio
from typing import TYPE_CHECKING, Dict, Set, Optional
from datetime import datetime

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.brokers.saxo.saxo_broker import SaxoBroker
from src.application.services.alert_service import AlertService
from src.infrastructure.notifications.telegram_service import get_telegram_service

logger = logging.getLogger(__name__)

# Intervalle de verification en secondes (5 minutes)
MONITOR_INTERVAL_SECONDS = 300

# Parametres par defaut pour les alertes auto
DEFAULT_STOP_LOSS_PERCENT = 8.0  # 8% sous le prix d'entree
DEFAULT_TAKE_PROFIT_PERCENT = 24.0  # 24% au-dessus du prix d'entree

# Cache des positions connues (pour detecter les nouvelles)
_known_positions: Set[str] = set()  # Set de position_id


async def monitor_portfolio_async() -> None:
    """
    Monitore le portefeuille et cree des alertes pour les nouvelles positions.

    Cette fonction est appelée par le job APScheduler
    et executee dans une boucle d'evenements asyncio.
    """
    global _known_positions

    try:
        broker = SaxoBroker()

        # Verifier si authentifie
        if not await broker.is_authenticated():
            logger.debug("Portfolio monitor: not authenticated, skipping")
            return

        # Recuperer le portefeuille
        portfolio = await broker.get_portfolio()

        if not portfolio or "positions" not in portfolio:
            logger.debug("Portfolio monitor: no positions found")
            return

        positions = portfolio.get("positions", [])
        current_position_ids = set()
        new_positions = []

        for position in positions:
            # Identifier unique de la position
            position_id = _get_position_identifier(position)
            current_position_ids.add(position_id)

            # Detecter les nouvelles positions
            if position_id not in _known_positions:
                new_positions.append(position)

        # Traiter les nouvelles positions
        if new_positions:
            await _process_new_positions(new_positions)

        # Mettre a jour le cache
        _known_positions = current_position_ids

        logger.debug(
            f"Portfolio monitor: {len(positions)} positions, "
            f"{len(new_positions)} new"
        )

    except Exception as e:
        logger.exception(f"Error in portfolio monitor job: {e}")


def _get_position_identifier(position: Dict) -> str:
    """
    Genere un identifiant unique pour une position.

    Args:
        position: Donnees de la position Saxo

    Returns:
        Identifiant unique (UIC + AssetType)
    """
    uic = position.get("PositionBase", {}).get("Uic", "")
    asset_type = position.get("PositionBase", {}).get("AssetType", "")
    return f"{uic}_{asset_type}"


async def _process_new_positions(positions: list) -> None:
    """
    Traite les nouvelles positions detectees.

    Args:
        positions: Liste des nouvelles positions
    """
    alert_service = AlertService()
    telegram = get_telegram_service()

    for position in positions:
        try:
            # Extraire les informations de la position
            position_base = position.get("PositionBase", {})
            position_view = position.get("PositionView", {})

            uic = position_base.get("Uic")
            ticker = position_view.get("Symbol", f"UIC_{uic}")
            entry_price = position_view.get("AverageOpenPrice", 0)
            current_price = position_view.get("CurrentPrice", entry_price)
            amount = position_base.get("Amount", 0)

            if entry_price <= 0:
                logger.warning(f"Invalid entry price for {ticker}, skipping")
                continue

            # Calculer les niveaux SL/TP
            stop_loss_price = entry_price * (1 - DEFAULT_STOP_LOSS_PERCENT / 100)
            take_profit_price = entry_price * (1 + DEFAULT_TAKE_PROFIT_PERCENT / 100)

            logger.info(
                f"New position detected: {ticker} @ {entry_price:.2f}, "
                f"SL: {stop_loss_price:.2f}, TP: {take_profit_price:.2f}"
            )

            # Creer alerte Stop Loss
            sl_result = await alert_service.create_alert(
                ticker=ticker,
                alert_type="stop_loss",
                condition="price_below",
                target_value=stop_loss_price,
                notes=f"Auto SL: {DEFAULT_STOP_LOSS_PERCENT}% sous entree ({entry_price:.2f})"
            )

            # Creer alerte Take Profit
            tp_result = await alert_service.create_alert(
                ticker=ticker,
                alert_type="take_profit",
                condition="price_above",
                target_value=take_profit_price,
                notes=f"Auto TP: {DEFAULT_TAKE_PROFIT_PERCENT}% au-dessus entree ({entry_price:.2f})"
            )

            # Notification Telegram
            if telegram.is_configured:
                direction = "long" if amount > 0 else "short"
                await telegram.send_trade_opened(
                    ticker=ticker,
                    direction=direction,
                    entry_price=entry_price,
                    stop_loss=stop_loss_price,
                    take_profit=take_profit_price,
                    position_size=abs(int(amount)),
                )

            logger.info(
                f"Auto-alerts created for {ticker}: "
                f"SL={sl_result.get('success', False)}, "
                f"TP={tp_result.get('success', False)}"
            )

        except Exception as e:
            logger.error(f"Error processing new position: {e}")


def monitor_portfolio_job() -> None:
    """
    Point d'entree du job pour APScheduler.

    APScheduler appelle cette fonction synchrone,
    qui cree une boucle d'evenements pour executer la version async.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(monitor_portfolio_async())
        finally:
            loop.close()

    except Exception as e:
        logger.exception(f"Error running portfolio monitor: {e}")


def register_portfolio_monitor(scheduler: "BackgroundScheduler") -> None:
    """
    Enregistre le job de monitoring du portefeuille.

    Args:
        scheduler: Instance APScheduler
    """
    scheduler.add_job(
        monitor_portfolio_job,
        "interval",
        seconds=MONITOR_INTERVAL_SECONDS,
        id="portfolio_monitor",
        name="Portfolio Position Monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        f"Portfolio monitor job registered "
        f"(interval: {MONITOR_INTERVAL_SECONDS}s / {MONITOR_INTERVAL_SECONDS // 60}min)"
    )


def reset_known_positions() -> None:
    """
    Reset le cache des positions connues.

    Utile pour forcer la re-detection de toutes les positions.
    """
    global _known_positions
    _known_positions = set()
    logger.info("Known positions cache reset")
