"""
Job d'envoi du resume journalier du portefeuille.

Ce job s'execute tous les jours a 18h pour:
- Calculer les statistiques du jour (P&L, performances)
- Identifier les top gagnants et perdants
- Envoyer un resume formate via Telegram

SCHEDULE: Tous les jours a 18h00 (heure locale)

UTILISATION:
    Ce job est automatiquement enregistre par le scheduler.
    Voir src/jobs/scheduler.py pour la configuration.
"""

import logging
import asyncio
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional
from datetime import datetime, date

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

from src.infrastructure.brokers.saxo.saxo_broker import SaxoBroker
from src.application.services.alert_service import AlertService
from src.infrastructure.notifications.telegram_service import get_telegram_service

logger = logging.getLogger(__name__)

# Heure d'envoi du resume (18h00)
SUMMARY_HOUR = 18
SUMMARY_MINUTE = 0


async def send_daily_summary_async() -> None:
    """
    Genere et envoie le resume journalier du portefeuille.

    Cette fonction est appelée par le job APScheduler
    et executee dans une boucle d'evenements asyncio.
    """
    try:
        broker = SaxoBroker()
        telegram = get_telegram_service()

        # Verifier si Telegram est configure
        if not telegram.is_configured:
            logger.warning("Daily summary: Telegram not configured, skipping")
            return

        # Verifier si authentifie
        if not await broker.is_authenticated():
            logger.warning("Daily summary: not authenticated to Saxo, skipping")

            # Envoyer notification de non-connexion
            await telegram.send_message(
                "⚠️ <b>RESUME IMPOSSIBLE</b>\n\n"
                "Non connecte a Saxo Bank.\n"
                "Veuillez vous reconnecter pour recevoir les resumes."
            )
            return

        # Recuperer le portefeuille
        portfolio = await broker.get_portfolio()

        if not portfolio:
            logger.warning("Daily summary: could not fetch portfolio")
            return

        # Calculer les statistiques
        stats = _calculate_portfolio_stats(portfolio)

        # Recuperer le nombre d'alertes du jour
        alert_service = AlertService()
        alerts_triggered = await _get_today_alerts_count(alert_service)

        # Envoyer le resume
        await telegram.send_portfolio_daily_summary(
            total_value=stats["total_value"],
            daily_pnl=stats["daily_pnl"],
            daily_pnl_percent=stats["daily_pnl_percent"],
            positions_count=stats["positions_count"],
            alerts_triggered=alerts_triggered,
            top_gainers=stats["top_gainers"],
            top_losers=stats["top_losers"],
        )

        logger.info(
            f"Daily summary sent: {stats['positions_count']} positions, "
            f"P&L: {stats['daily_pnl']:.2f}€ ({stats['daily_pnl_percent']:.2f}%)"
        )

    except Exception as e:
        logger.exception(f"Error in daily summary job: {e}")

        # Essayer d'envoyer une notification d'erreur
        try:
            telegram = get_telegram_service()
            if telegram.is_configured:
                await telegram.send_message(
                    f"❌ <b>ERREUR RESUME</b>\n\n"
                    f"Impossible de generer le resume journalier.\n"
                    f"Erreur: {str(e)[:100]}"
                )
        except Exception:
            pass


def _calculate_portfolio_stats(portfolio: Dict) -> Dict:
    """
    Calcule les statistiques du portefeuille.

    Args:
        portfolio: Donnees du portefeuille Saxo

    Returns:
        Dict avec les statistiques calculees
    """
    positions = portfolio.get("positions", [])
    balance = portfolio.get("balance", {})

    # Valeur totale
    total_value = balance.get("TotalValue", 0)

    # Calculer P&L et performances par position
    position_perfs: List[Tuple[str, float, float]] = []  # (symbol, pnl, pnl_pct)
    total_daily_pnl = 0

    for position in positions:
        position_view = position.get("PositionView", {})

        symbol = position_view.get("Symbol", "Unknown")
        pnl = position_view.get("ProfitLossOnTrade", 0)
        pnl_pct = position_view.get("ProfitLossOnTradeInPercentage", 0)

        position_perfs.append((symbol, pnl, pnl_pct))
        total_daily_pnl += pnl

    # Trier par performance
    sorted_by_pct = sorted(position_perfs, key=lambda x: x[2], reverse=True)

    # Top gainers (positifs)
    top_gainers = [(s, p) for s, _, p in sorted_by_pct if p > 0][:3]

    # Top losers (negatifs)
    top_losers = [(s, p) for s, _, p in sorted_by_pct if p < 0][-3:]
    top_losers.reverse()  # Du moins pire au pire

    # P&L en pourcentage du portfolio
    daily_pnl_percent = (total_daily_pnl / total_value * 100) if total_value > 0 else 0

    return {
        "total_value": total_value,
        "daily_pnl": total_daily_pnl,
        "daily_pnl_percent": daily_pnl_percent,
        "positions_count": len(positions),
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


async def _get_today_alerts_count(alert_service: AlertService) -> int:
    """
    Compte le nombre d'alertes declenchees aujourd'hui.

    Args:
        alert_service: Instance du service d'alertes

    Returns:
        Nombre d'alertes declenchees aujourd'hui
    """
    try:
        # Recuperer toutes les alertes
        all_alerts = await alert_service.get_all_alerts()

        today = date.today()
        count = 0

        for alert in all_alerts:
            triggered_at = alert.get("triggered_at")
            if triggered_at:
                # Parser la date
                try:
                    if isinstance(triggered_at, str):
                        triggered_date = datetime.fromisoformat(triggered_at).date()
                    else:
                        triggered_date = triggered_at.date()

                    if triggered_date == today:
                        count += 1
                except Exception:
                    pass

        return count

    except Exception as e:
        logger.error(f"Error counting today's alerts: {e}")
        return 0


def send_daily_summary_job() -> None:
    """
    Point d'entree du job pour APScheduler.

    APScheduler appelle cette fonction synchrone,
    qui cree une boucle d'evenements pour executer la version async.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(send_daily_summary_async())
        finally:
            loop.close()

    except Exception as e:
        logger.exception(f"Error running daily summary: {e}")


def register_daily_summary(scheduler: "BackgroundScheduler") -> None:
    """
    Enregistre le job de resume journalier.

    Args:
        scheduler: Instance APScheduler
    """
    scheduler.add_job(
        send_daily_summary_job,
        "cron",
        hour=SUMMARY_HOUR,
        minute=SUMMARY_MINUTE,
        id="daily_summary",
        name="Portfolio Daily Summary",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        f"Daily summary job registered "
        f"(schedule: every day at {SUMMARY_HOUR:02d}:{SUMMARY_MINUTE:02d})"
    )


async def trigger_daily_summary_now() -> None:
    """
    Declenche manuellement l'envoi du resume journalier.

    Utile pour tester ou forcer l'envoi.
    """
    logger.info("Triggering daily summary manually...")
    await send_daily_summary_async()
