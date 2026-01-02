"""
Outils MCP pour la gestion des notifications.

Ce module permet d'envoyer des notifications depuis Claude Desktop
via Telegram ou d'autres canaux.
"""

import json
import logging
from typing import Optional

from src.infrastructure.notifications.telegram_service import get_telegram_service

logger = logging.getLogger(__name__)


async def test_notification() -> str:
    """
    Teste la connexion aux services de notification.

    Returns:
        Statut de la connexion Telegram
    """
    try:
        # Créer une nouvelle instance pour éviter les problèmes de connexion
        from src.infrastructure.notifications.telegram_service import TelegramService
        telegram = TelegramService()

        result = {
            "telegram": {
                "configured": telegram.is_configured,
                "connected": False,
                "message_sent": False
            }
        }

        if telegram.is_configured:
            connected = await telegram.test_connection()
            result["telegram"]["connected"] = connected

            if connected:
                sent = await telegram.send_message(
                    "🧪 <b>Test de connexion réussi!</b>\n\n"
                    "Les notifications depuis Claude Desktop fonctionnent correctement."
                )
                result["telegram"]["message_sent"] = sent

        await telegram.close()
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.exception(f"Error testing notifications: {e}")
        return json.dumps({"error": str(e)})


async def send_notification(
    message: str,
    title: Optional[str] = None,
    notification_type: str = "info"
) -> str:
    """
    Envoie une notification personnalisée.

    Args:
        message: Le message à envoyer
        title: Titre optionnel (défaut: selon le type)
        notification_type: Type de notification (info, success, warning, error, trade)

    Returns:
        Statut de l'envoi
    """
    try:
        telegram = get_telegram_service()

        if not telegram.is_configured:
            return json.dumps({
                "success": False,
                "error": "Telegram non configuré. Ajoutez TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans .env"
            })

        # Emoji et titre selon le type
        type_config = {
            "info": {"emoji": "ℹ️", "default_title": "Information"},
            "success": {"emoji": "✅", "default_title": "Succès"},
            "warning": {"emoji": "⚠️", "default_title": "Attention"},
            "error": {"emoji": "❌", "default_title": "Erreur"},
            "trade": {"emoji": "📊", "default_title": "Signal de Trading"},
            "alert": {"emoji": "🔔", "default_title": "Alerte"},
            "analysis": {"emoji": "📈", "default_title": "Analyse"},
        }

        config = type_config.get(notification_type, type_config["info"])
        display_title = title or config["default_title"]

        formatted_message = (
            f"{config['emoji']} <b>{display_title}</b>\n\n"
            f"{message}\n\n"
            f"<i>📱 Stock Analyzer via Claude</i>"
        )

        sent = await telegram.send_message(formatted_message)

        return json.dumps({
            "success": sent,
            "channel": "telegram",
            "type": notification_type
        })

    except Exception as e:
        logger.exception(f"Error sending notification: {e}")
        return json.dumps({"success": False, "error": str(e)})


async def send_market_alert(
    ticker: str,
    alert_type: str,
    message: str,
    current_price: Optional[float] = None,
    target_price: Optional[float] = None,
    recommendation: Optional[str] = None
) -> str:
    """
    Envoie une alerte de marché détaillée.

    Args:
        ticker: Symbole du ticker
        alert_type: Type d'alerte (breakout, reversal, volume, momentum, support, resistance)
        message: Description de l'alerte
        current_price: Prix actuel
        target_price: Prix cible
        recommendation: Recommandation (buy, sell, hold, watch)

    Returns:
        Statut de l'envoi
    """
    try:
        telegram = get_telegram_service()

        if not telegram.is_configured:
            return json.dumps({
                "success": False,
                "error": "Telegram non configuré"
            })

        # Emoji selon le type d'alerte
        type_emojis = {
            "breakout": "🚀",
            "reversal": "🔄",
            "volume": "📊",
            "momentum": "⚡",
            "support": "🛡️",
            "resistance": "🧱",
            "opportunity": "💎",
            "warning": "⚠️"
        }

        # Emoji selon la recommandation
        rec_emojis = {
            "buy": "🟢 ACHAT",
            "sell": "🔴 VENTE",
            "hold": "🟡 CONSERVER",
            "watch": "👀 SURVEILLER"
        }

        emoji = type_emojis.get(alert_type, "📌")

        formatted_message = f"{emoji} <b>ALERTE {alert_type.upper()}: {ticker}</b>\n\n"
        formatted_message += f"📝 {message}\n"

        if current_price:
            formatted_message += f"\n💰 Prix actuel: <code>{current_price:.2f}</code>"
        if target_price:
            formatted_message += f"\n🎯 Prix cible: <code>{target_price:.2f}</code>"
        if recommendation:
            rec_text = rec_emojis.get(recommendation.lower(), recommendation)
            formatted_message += f"\n\n📋 Recommandation: <b>{rec_text}</b>"

        formatted_message += "\n\n<i>📱 Stock Analyzer via Claude</i>"

        sent = await telegram.send_message(formatted_message)

        return json.dumps({
            "success": sent,
            "ticker": ticker,
            "alert_type": alert_type
        })

    except Exception as e:
        logger.exception(f"Error sending market alert: {e}")
        return json.dumps({"success": False, "error": str(e)})


async def send_portfolio_update(
    total_value: float,
    daily_pnl: float,
    daily_pnl_percent: float,
    positions_summary: Optional[str] = None,
    top_gainers: Optional[str] = None,
    top_losers: Optional[str] = None
) -> str:
    """
    Envoie un résumé du portfolio.

    Args:
        total_value: Valeur totale du portfolio
        daily_pnl: P&L du jour en valeur
        daily_pnl_percent: P&L du jour en pourcentage
        positions_summary: Résumé des positions
        top_gainers: Top gagnants
        top_losers: Top perdants

    Returns:
        Statut de l'envoi
    """
    try:
        telegram = get_telegram_service()

        if not telegram.is_configured:
            return json.dumps({
                "success": False,
                "error": "Telegram non configuré"
            })

        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
        pnl_color = "+" if daily_pnl >= 0 else ""

        formatted_message = (
            f"💼 <b>MISE À JOUR PORTFOLIO</b>\n\n"
            f"💰 Valeur totale: <code>{total_value:,.2f}</code>\n"
            f"{pnl_emoji} P&L du jour: <code>{pnl_color}{daily_pnl:,.2f}</code> ({pnl_color}{daily_pnl_percent:.2f}%)\n"
        )

        if positions_summary:
            formatted_message += f"\n📊 <b>Positions:</b>\n{positions_summary}\n"

        if top_gainers:
            formatted_message += f"\n🏆 <b>Top Gagnants:</b>\n{top_gainers}\n"

        if top_losers:
            formatted_message += f"\n📉 <b>Top Perdants:</b>\n{top_losers}\n"

        formatted_message += "\n<i>📱 Stock Analyzer via Claude</i>"

        sent = await telegram.send_message(formatted_message)

        return json.dumps({
            "success": sent,
            "total_value": total_value,
            "daily_pnl": daily_pnl
        })

    except Exception as e:
        logger.exception(f"Error sending portfolio update: {e}")
        return json.dumps({"success": False, "error": str(e)})


async def get_notification_status() -> str:
    """
    Retourne le statut des services de notification.

    Returns:
        Statut de configuration des services
    """
    try:
        telegram = get_telegram_service()

        status = {
            "telegram": {
                "configured": telegram.is_configured,
                "status": "ready" if telegram.is_configured else "not_configured",
                "instructions": None
            }
        }

        if not telegram.is_configured:
            status["telegram"]["instructions"] = (
                "Pour configurer Telegram:\n"
                "1. Créez un bot via @BotFather sur Telegram\n"
                "2. Copiez le token dans TELEGRAM_BOT_TOKEN\n"
                "3. Envoyez /start à votre bot\n"
                "4. Utilisez @userinfobot pour obtenir votre chat_id\n"
                "5. Ajoutez-le dans TELEGRAM_CHAT_ID"
            )

        return json.dumps(status, indent=2)

    except Exception as e:
        logger.exception(f"Error getting notification status: {e}")
        return json.dumps({"error": str(e)})
