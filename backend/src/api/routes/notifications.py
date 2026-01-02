"""
Routes API pour les notifications.

Permet d'envoyer des notifications depuis l'interface web.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.infrastructure.notifications.telegram_service import TelegramService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationRequest(BaseModel):
    """Requête d'envoi de notification."""
    message: str
    title: Optional[str] = None
    notification_type: str = "info"  # info, success, warning, error, trade, alert, analysis


class MarketAlertRequest(BaseModel):
    """Requête d'alerte de marché."""
    ticker: str
    alert_type: str  # breakout, reversal, volume, momentum, support, resistance
    message: str
    current_price: Optional[float] = None
    target_price: Optional[float] = None
    recommendation: Optional[str] = None  # buy, sell, hold, watch


class NotificationResponse(BaseModel):
    """Réponse d'envoi de notification."""
    success: bool
    channel: str = "telegram"
    error: Optional[str] = None


class NotificationStatusResponse(BaseModel):
    """Statut des services de notification."""
    telegram_configured: bool
    telegram_connected: bool


@router.get("/status", response_model=NotificationStatusResponse)
async def get_notification_status():
    """
    Retourne le statut des services de notification.
    """
    telegram = TelegramService()
    configured = telegram.is_configured
    connected = False

    if configured:
        connected = await telegram.test_connection()

    await telegram.close()

    return NotificationStatusResponse(
        telegram_configured=configured,
        telegram_connected=connected
    )


@router.post("/test", response_model=NotificationResponse)
async def test_notification():
    """
    Envoie une notification de test.
    """
    telegram = TelegramService()

    if not telegram.is_configured:
        await telegram.close()
        return NotificationResponse(
            success=False,
            error="Telegram non configuré. Ajoutez TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans .env"
        )

    sent = await telegram.send_message(
        "🧪 <b>Test de notification depuis l'API Web!</b>\n\n"
        "Les notifications fonctionnent correctement."
    )

    await telegram.close()

    return NotificationResponse(success=sent)


@router.post("/send", response_model=NotificationResponse)
async def send_notification(request: NotificationRequest):
    """
    Envoie une notification personnalisée.
    """
    telegram = TelegramService()

    if not telegram.is_configured:
        await telegram.close()
        return NotificationResponse(
            success=False,
            error="Telegram non configuré"
        )

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

    config = type_config.get(request.notification_type, type_config["info"])
    display_title = request.title or config["default_title"]

    formatted_message = (
        f"{config['emoji']} <b>{display_title}</b>\n\n"
        f"{request.message}\n\n"
        f"<i>📱 Stock Analyzer Web</i>"
    )

    sent = await telegram.send_message(formatted_message)
    await telegram.close()

    return NotificationResponse(success=sent)


@router.post("/market-alert", response_model=NotificationResponse)
async def send_market_alert(request: MarketAlertRequest):
    """
    Envoie une alerte de marché détaillée.
    """
    telegram = TelegramService()

    if not telegram.is_configured:
        await telegram.close()
        return NotificationResponse(
            success=False,
            error="Telegram non configuré"
        )

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

    emoji = type_emojis.get(request.alert_type, "📌")

    formatted_message = f"{emoji} <b>ALERTE {request.alert_type.upper()}: {request.ticker}</b>\n\n"
    formatted_message += f"📝 {request.message}\n"

    if request.current_price:
        formatted_message += f"\n💰 Prix actuel: <code>{request.current_price:.2f}</code>"
    if request.target_price:
        formatted_message += f"\n🎯 Prix cible: <code>{request.target_price:.2f}</code>"
    if request.recommendation:
        rec_text = rec_emojis.get(request.recommendation.lower(), request.recommendation)
        formatted_message += f"\n\n📋 Recommandation: <b>{rec_text}</b>"

    formatted_message += "\n\n<i>📱 Stock Analyzer Web</i>"

    sent = await telegram.send_message(formatted_message)
    await telegram.close()

    return NotificationResponse(success=sent)
