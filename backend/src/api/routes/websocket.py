"""
Routes WebSocket pour les prix en temps reel.

Endpoint:
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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.websocket.ws_manager import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


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
            await manager.subscribe(client_id, ticker)
            logger.debug(f"Client {client_id} subscribed to {ticker}")
        else:
            await _send_error(manager, client_id, "Missing ticker for subscribe")

    elif msg_type == "unsubscribe":
        ticker = message.get("ticker", "").upper()
        if ticker:
            await manager.unsubscribe(client_id, ticker)
            logger.debug(f"Client {client_id} unsubscribed from {ticker}")
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
