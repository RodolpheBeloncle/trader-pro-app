"""
Routes API pour la gestion de la configuration.

Ces routes permettent de:
- Consulter le statut des services configurés
- Mettre à jour les credentials Saxo Bank et Telegram
- Basculer entre environnement DEMO et LIVE
- Supprimer des credentials

SÉCURITÉ:
Toutes les opérations de modification requièrent une vérification OTP
via Telegram. Le flow est le suivant:
1. POST /config/otp/request - Demande un code OTP
2. POST /config/{action} - Soumet le code + données
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.application.services.otp_service import get_otp_service, OTPAction
from src.application.services.config_service import get_config_service
from src.infrastructure.notifications.telegram_service import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["Configuration"])


# ==================== MODELS ====================


class OTPRequestBody(BaseModel):
    """Demande de code OTP."""
    action: str = Field(..., description="Action à effectuer (update_saxo, update_telegram, etc.)")


class OTPVerifyMixin(BaseModel):
    """Mixin pour les requêtes nécessitant OTP."""
    otp_code: str = Field(..., min_length=6, max_length=6, description="Code OTP reçu via Telegram")


class UpdateSaxoRequest(OTPVerifyMixin):
    """Mise à jour configuration Saxo Bank."""
    app_key: Optional[str] = Field(None, description="Clé d'application Saxo")
    app_secret: Optional[str] = Field(None, description="Secret d'application Saxo")
    environment: Optional[str] = Field(None, description="Environnement (SIM ou LIVE)")
    redirect_uri: Optional[str] = Field(None, description="URI de redirection OAuth")


class UpdateTelegramRequest(OTPVerifyMixin):
    """Mise à jour configuration Telegram."""
    bot_token: Optional[str] = Field(None, description="Token du bot Telegram")
    chat_id: Optional[str] = Field(None, description="ID du chat Telegram")


class SwitchEnvironmentRequest(OTPVerifyMixin):
    """Changement d'environnement Saxo."""
    environment: str = Field(..., description="Nouvel environnement (SIM ou LIVE)")


class DeleteCredentialsRequest(OTPVerifyMixin):
    """Suppression de credentials."""
    service: str = Field(..., description="Service à supprimer (saxo ou telegram)")


# ==================== ROUTES ====================


@router.get("/status")
async def get_config_status():
    """
    Retourne le statut de configuration des services.

    Les valeurs sensibles sont masquées.

    Returns:
        Statut des services (Saxo, Telegram)
    """
    config_service = get_config_service()
    return config_service.get_status()


@router.post("/otp/request")
async def request_otp(body: OTPRequestBody):
    """
    Demande un code OTP pour une action.

    Le code sera envoyé via Telegram et expire après 5 minutes.

    Args:
        body: Action pour laquelle demander le code

    Returns:
        Message de confirmation
    """
    # Mapper l'action string vers l'enum
    action_map = {
        "update_saxo": OTPAction.UPDATE_SAXO,
        "update_telegram": OTPAction.UPDATE_TELEGRAM,
        "delete_credentials": OTPAction.DELETE_CREDENTIALS,
        "switch_environment": OTPAction.SWITCH_ENVIRONMENT,
    }

    action = action_map.get(body.action)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action inconnue: {body.action}"
        )

    # Vérifier que Telegram est configuré pour envoyer l'OTP
    config_service = get_config_service()
    telegram_creds = config_service.get_telegram_credentials()

    if not telegram_creds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram doit être configuré d'abord pour utiliser la vérification OTP. "
                   "Utilisez /config/telegram/setup pour la configuration initiale."
        )

    # Générer et envoyer l'OTP
    otp_service = get_otp_service()

    try:
        code, message = otp_service.request_otp(action)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )

    # Envoyer via Telegram
    telegram = TelegramService(
        bot_token=telegram_creds["bot_token"],
        chat_id=telegram_creds["chat_id"]
    )

    try:
        sent = await telegram.send_message(message)
        if not sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Impossible d'envoyer le code OTP via Telegram"
            )
    finally:
        await telegram.close()

    return {
        "success": True,
        "message": "Code OTP envoyé sur Telegram",
        "expires_in": 300  # 5 minutes
    }


@router.post("/telegram/setup")
async def setup_telegram_initial(
    bot_token: str,
    chat_id: str
):
    """
    Configuration initiale de Telegram (sans OTP).

    Cette route permet de configurer Telegram pour la première fois
    puisqu'on ne peut pas encore envoyer d'OTP sans Telegram configuré.

    Args:
        bot_token: Token du bot
        chat_id: ID du chat

    Returns:
        Résultat de la configuration
    """
    config_service = get_config_service()

    # Vérifier si déjà configuré
    current_status = config_service.get_status()
    if current_status["telegram"]["configured"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram est déjà configuré. Utilisez /config/telegram avec OTP pour modifier."
        )

    # Configurer et valider
    result = await config_service.update_telegram(
        bot_token=bot_token,
        chat_id=chat_id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Erreur de configuration")
        )

    # Envoyer notification de confirmation
    telegram = TelegramService(bot_token=bot_token, chat_id=chat_id)
    try:
        await telegram.send_message(
            "🎉 <b>Telegram configuré avec succès!</b>\n\n"
            "Vous recevrez maintenant les codes OTP pour sécuriser "
            "les modifications de configuration.\n\n"
            "<i>Stock Analyzer</i>"
        )
    finally:
        await telegram.close()

    return result


@router.post("/saxo/setup")
async def setup_saxo_initial(
    app_key: str,
    app_secret: str,
    environment: str = "SIM",
    redirect_uri: str = "http://localhost:5173"
):
    """
    Configuration initiale de Saxo Bank (sans OTP).

    Cette route permet de configurer Saxo pour la première fois.
    Si Saxo est déjà configuré, utiliser /config/saxo avec OTP.

    Args:
        app_key: Clé d'application Saxo
        app_secret: Secret d'application Saxo
        environment: Environnement (SIM ou LIVE)
        redirect_uri: URI de redirection OAuth

    Returns:
        Résultat de la configuration
    """
    config_service = get_config_service()

    # Vérifier si déjà configuré
    current_status = config_service.get_status()
    if current_status["saxo"]["configured"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Saxo est déjà configuré. Utilisez /config/saxo avec OTP pour modifier."
        )

    # Configurer
    result = await config_service.update_saxo(
        app_key=app_key,
        app_secret=app_secret,
        environment=environment,
        redirect_uri=redirect_uri
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Erreur de configuration")
        )

    # Envoyer notification si Telegram est configuré
    await _send_config_notification(
        "🔐 Saxo Bank configuré avec succès!",
        f"Environnement: {environment}"
    )

    return result


@router.post("/saxo")
async def update_saxo_config(body: UpdateSaxoRequest):
    """
    Met à jour la configuration Saxo Bank.

    Nécessite un code OTP valide.

    Args:
        body: Nouvelles valeurs de configuration + code OTP

    Returns:
        Résultat de la mise à jour
    """
    # Vérifier OTP
    otp_service = get_otp_service()
    valid, message = otp_service.verify_otp(OTPAction.UPDATE_SAXO, body.otp_code)

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )

    # Appliquer les modifications
    config_service = get_config_service()
    result = await config_service.update_saxo(
        app_key=body.app_key,
        app_secret=body.app_secret,
        environment=body.environment,
        redirect_uri=body.redirect_uri
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Erreur de configuration")
        )

    # Envoyer notification de confirmation
    await _send_config_notification(
        "🔐 Configuration Saxo Bank mise à jour",
        f"Environnement: {result.get('environment', 'N/A')}"
    )

    return result


@router.post("/telegram")
async def update_telegram_config(body: UpdateTelegramRequest):
    """
    Met à jour la configuration Telegram.

    Nécessite un code OTP valide (envoyé à l'ancienne configuration).

    Args:
        body: Nouvelles valeurs de configuration + code OTP

    Returns:
        Résultat de la mise à jour
    """
    # Vérifier OTP
    otp_service = get_otp_service()
    valid, message = otp_service.verify_otp(OTPAction.UPDATE_TELEGRAM, body.otp_code)

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )

    config_service = get_config_service()

    # Garder trace des anciens credentials pour notification
    old_creds = config_service.get_telegram_credentials()

    # Appliquer les modifications
    result = await config_service.update_telegram(
        bot_token=body.bot_token,
        chat_id=body.chat_id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Erreur de configuration")
        )

    # Envoyer notification aux deux (ancien et nouveau)
    new_creds = config_service.get_telegram_credentials()

    message = (
        "📱 <b>Configuration Telegram mise à jour</b>\n\n"
        "Les notifications seront maintenant envoyées ici.\n\n"
        "<i>Stock Analyzer</i>"
    )

    # Notifier la nouvelle configuration
    if new_creds:
        telegram = TelegramService(
            bot_token=new_creds["bot_token"],
            chat_id=new_creds["chat_id"]
        )
        try:
            await telegram.send_message(message)
        finally:
            await telegram.close()

    return result


@router.post("/environment")
async def switch_environment(body: SwitchEnvironmentRequest):
    """
    Bascule l'environnement Saxo Bank (DEMO/LIVE).

    ⚠️ Attention: En mode LIVE, les trades sont réels!

    Args:
        body: Nouvel environnement + code OTP

    Returns:
        Résultat du changement
    """
    # Vérifier OTP
    otp_service = get_otp_service()
    valid, message = otp_service.verify_otp(OTPAction.SWITCH_ENVIRONMENT, body.otp_code)

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )

    config_service = get_config_service()
    result = await config_service.switch_saxo_environment(body.environment)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Erreur de changement")
        )

    # Notification avec warning si passage en LIVE
    emoji = "⚠️" if body.environment == "LIVE" else "✅"
    await _send_config_notification(
        f"{emoji} Environnement Saxo modifié",
        result.get("environment_label", body.environment)
    )

    return result


@router.post("/delete")
async def delete_credentials(body: DeleteCredentialsRequest):
    """
    Supprime les credentials d'un service.

    Args:
        body: Service à supprimer (saxo ou telegram) + code OTP

    Returns:
        Résultat de la suppression
    """
    # Vérifier OTP
    otp_service = get_otp_service()
    valid, message = otp_service.verify_otp(OTPAction.DELETE_CREDENTIALS, body.otp_code)

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )

    config_service = get_config_service()

    if body.service == "saxo":
        result = await config_service.delete_saxo()
        service_name = "Saxo Bank"
    elif body.service == "telegram":
        # Envoyer notification AVANT suppression
        await _send_config_notification(
            "🗑️ Configuration Telegram supprimée",
            "Vous ne recevrez plus de notifications."
        )
        result = await config_service.delete_telegram()
        service_name = "Telegram"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service inconnu: {body.service}"
        )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Erreur de suppression")
        )

    # Notification (sauf pour Telegram qui est déjà fait)
    if body.service != "telegram":
        await _send_config_notification(
            f"🗑️ Credentials {service_name} supprimés",
            "La configuration a été réinitialisée."
        )

    return result


@router.post("/otp/cancel")
async def cancel_otp(body: OTPRequestBody):
    """
    Annule un OTP en cours.

    Args:
        body: Action à annuler

    Returns:
        Résultat de l'annulation
    """
    action_map = {
        "update_saxo": OTPAction.UPDATE_SAXO,
        "update_telegram": OTPAction.UPDATE_TELEGRAM,
        "delete_credentials": OTPAction.DELETE_CREDENTIALS,
        "switch_environment": OTPAction.SWITCH_ENVIRONMENT,
    }

    action = action_map.get(body.action)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action inconnue: {body.action}"
        )

    otp_service = get_otp_service()
    cancelled = otp_service.cancel_otp(action)

    return {
        "success": True,
        "cancelled": cancelled,
        "message": "OTP annulé" if cancelled else "Aucun OTP actif pour cette action"
    }


# ==================== HELPERS ====================


async def _send_config_notification(title: str, details: str) -> None:
    """
    Envoie une notification de configuration via Telegram.

    Args:
        title: Titre de la notification
        details: Détails supplémentaires
    """
    config_service = get_config_service()
    creds = config_service.get_telegram_credentials()

    if not creds:
        return

    message = (
        f"{title}\n\n"
        f"{details}\n\n"
        f"<i>Stock Analyzer - {__import__('datetime').datetime.now().strftime('%H:%M:%S')}</i>"
    )

    telegram = TelegramService(
        bot_token=creds["bot_token"],
        chat_id=creds["chat_id"]
    )

    try:
        await telegram.send_message(message)
    except Exception as e:
        logger.error(f"Erreur notification config: {e}")
    finally:
        await telegram.close()
