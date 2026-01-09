"""
Routes WebSocket pour les prix en temps reel.

Endpoints REST:
- GET /streaming/modes - Liste des modes de trading disponibles
- GET /streaming/status - Statut actuel du streaming
- POST /streaming/mode - Changer le mode de trading

Endpoint WebSocket:
- GET /ws/prices - Connexion WebSocket pour les prix

PROTOCOLE:
Les messages sont en JSON avec un champ "type":

Client -> Serveur:
    {"type": "subscribe", "ticker": "AAPL"}
    {"type": "unsubscribe", "ticker": "AAPL"}
    {"type": "ping"}

Serveur -> Client:
    {"type": "connected", "client_id": "..."}
    {"type": "subscribed", "ticker": "AAPL"}
    {"type": "unsubscribed", "ticker": "AAPL"}
    {"type": "price_update", "ticker": "AAPL", "price": 185.50, ...}
    {"type": "pong"}
    {"type": "error", "message": "..."}
"""

import logging
import json
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from src.infrastructure.websocket.ws_manager import get_ws_manager
from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer
from src.infrastructure.websocket.trading_mode import (
    TradingMode,
    get_all_modes,
    get_current_mode,
    get_current_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


# =============================================================================
# REST ENDPOINTS - Trading Mode Configuration
# =============================================================================

class SetModeRequest(BaseModel):
    """Requete pour changer le mode de trading."""
    mode: str  # "long_term", "swing", "scalping"


@router.get("/streaming/modes")
async def get_trading_modes():
    """
    Retourne la liste des modes de trading disponibles.

    Returns:
        Liste des modes avec leurs configurations
    """
    return {
        "modes": get_all_modes(),
        "current_mode": get_current_mode().value,
    }


@router.get("/streaming/status")
async def get_streaming_status():
    """
    Retourne le statut actuel du streaming.

    Returns:
        Statut du streamer avec mode, sources, etc.
    """
    try:
        streamer = get_hybrid_streamer()
        stats = streamer.get_stats()
        config = get_current_config()

        # Verifier la disponibilite des sources
        source_status = await _get_source_availability_async()

        return {
            "status": "running" if stats.get("running") else "stopped",
            "trading_mode": config.mode.value,
            "trading_mode_name": config.display_name,
            "poll_interval": stats.get("poll_interval"),
            "use_websocket": config.use_websocket,
            "sources": stats.get("sources", []),
            "realtime_sources": stats.get("realtime_sources", []),
            "subscribed_count": stats.get("subscribed_count", 0),
            "source_availability": source_status,
        }
    except Exception as e:
        logger.error(f"Error getting streaming status: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def _get_source_availability_async() -> dict:
    """Verifie la disponibilite de chaque source (async)."""
    from src.config.settings import settings
    from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth

    result = {
        "yahoo": {"available": True, "reason": "Toujours disponible"},
        "finnhub": {"available": False, "reason": ""},
        "saxo": {"available": False, "reason": ""},
    }

    # Finnhub
    if settings.is_finnhub_configured:
        result["finnhub"]["available"] = True
        result["finnhub"]["reason"] = "Cle API configuree"
    else:
        result["finnhub"]["reason"] = "Cle API non configuree (FINNHUB_API_KEY)"

    # Saxo - utiliser le meme systeme d'auth que le reste de l'app
    try:
        saxo_auth = get_saxo_auth()
        token = saxo_auth.get_valid_token()
        if token and not token.is_expired:
            result["saxo"]["available"] = True
            result["saxo"]["reason"] = "Token OAuth valide"
        else:
            result["saxo"]["reason"] = "Non connecte ou token expire"
    except Exception as e:
        result["saxo"]["reason"] = f"Erreur: {str(e)}"

    return result


def _get_source_availability() -> dict:
    """Version sync pour les contextes non-async."""
    from src.config.settings import settings

    result = {
        "yahoo": {"available": True, "reason": "Toujours disponible"},
        "finnhub": {"available": False, "reason": ""},
        "saxo": {"available": False, "reason": "Verifier onglet Mon Portfolio"},
    }

    # Finnhub
    if settings.is_finnhub_configured:
        result["finnhub"]["available"] = True
        result["finnhub"]["reason"] = "Cle API configuree"
    else:
        result["finnhub"]["reason"] = "Cle API non configuree (FINNHUB_API_KEY)"

    return result


@router.post("/streaming/mode")
async def set_trading_mode(request: SetModeRequest):
    """
    Change le mode de trading.

    Args:
        request: Mode de trading souhaite

    Returns:
        Nouvelle configuration du streamer
    """
    try:
        # Valider le mode
        try:
            mode = TradingMode(request.mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Mode invalide: {request.mode}. "
                       f"Valeurs possibles: long_term, swing, scalping"
            )

        # Changer le mode
        streamer = get_hybrid_streamer()
        result = await streamer.set_trading_mode(mode)

        logger.info(f"Trading mode changed to: {mode.value}")

        return {
            "success": True,
            "message": f"Mode change en {result['display_name']}",
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error changing trading mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================


@router.websocket("/prices")
async def websocket_prices(websocket: WebSocket):
    """
    Endpoint WebSocket pour les mises a jour de prix en temps reel.

    Protocole:
    1. Client se connecte
    2. Client envoie des messages subscribe/unsubscribe
    3. Serveur broadcast les mises a jour de prix
    4. Client se deconnecte ou perd la connexion
    """
    manager = get_ws_manager()
    client_id = str(uuid.uuid4())[:8]  # ID court pour le debug

    try:
        # Connecter le client
        await manager.connect(websocket, client_id)
        logger.info(f"WebSocket client connected: {client_id}")

        # Boucle de reception des messages
        while True:
            try:
                # Attendre un message du client
                data = await websocket.receive_text()
                await _handle_client_message(manager, client_id, data)

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {client_id}")
                break
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from client {client_id}: {e}")
                await _send_error(manager, client_id, "Invalid JSON format")
            except Exception as e:
                logger.exception(f"Error handling message from {client_id}: {e}")
                await _send_error(manager, client_id, str(e))

    finally:
        # Toujours deconnecter proprement
        await manager.disconnect(client_id)


async def _handle_client_message(
    manager,
    client_id: str,
    raw_data: str
) -> None:
    """
    Traite un message du client.

    Args:
        manager: WebSocketManager
        client_id: ID du client
        raw_data: Message JSON brut
    """
    try:
        message = json.loads(raw_data)
    except json.JSONDecodeError:
        await _send_error(manager, client_id, "Invalid JSON")
        return

    msg_type = message.get("type", "").lower()

    if msg_type == "subscribe":
        ticker = message.get("ticker", "").upper()
        if ticker:
            # Ajouter au WebSocket manager (pour broadcast)
            await manager.subscribe(client_id, ticker)

            # IMPORTANT: Aussi souscrire au HybridPriceStreamer pour qu'il poll les prix
            from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer
            streamer = get_hybrid_streamer()
            await streamer.subscribe(ticker)

            logger.info(f"Client {client_id} subscribed to {ticker}")
        else:
            await _send_error(manager, client_id, "Missing ticker for subscribe")

    elif msg_type == "unsubscribe":
        ticker = message.get("ticker", "").upper()
        if ticker:
            await manager.unsubscribe(client_id, ticker)

            # Verifier si d'autres clients sont encore abonnes avant de desabonner le streamer
            remaining_subscribers = manager.get_subscribers(ticker)
            if not remaining_subscribers:
                from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer
                streamer = get_hybrid_streamer()
                await streamer.unsubscribe(ticker)

            logger.info(f"Client {client_id} unsubscribed from {ticker}")
        else:
            await _send_error(manager, client_id, "Missing ticker for unsubscribe")

    elif msg_type == "ping":
        await manager.send_to_client(client_id, {"type": "pong"})

    elif msg_type == "get_subscriptions":
        subscriptions = manager.get_client_subscriptions(client_id)
        await manager.send_to_client(client_id, {
            "type": "subscriptions",
            "tickers": list(subscriptions),
        })

    else:
        await _send_error(manager, client_id, f"Unknown message type: {msg_type}")


async def _send_error(
    manager,
    client_id: str,
    message: str
) -> None:
    """
    Envoie un message d'erreur au client.

    Args:
        manager: WebSocketManager
        client_id: ID du client
        message: Message d'erreur
    """
    await manager.send_to_client(client_id, {
        "type": "error",
        "message": message,
    })
