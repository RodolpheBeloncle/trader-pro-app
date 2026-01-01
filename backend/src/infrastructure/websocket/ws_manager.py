"""
Gestionnaire de connexions WebSocket.

Gere les connexions, deconnexions et le broadcast de messages.

ARCHITECTURE:
- Singleton pattern
- Gestion des rooms par ticker
- Thread-safe avec asyncio

UTILISATION:
    manager = WebSocketManager()
    await manager.connect(websocket, client_id)
    await manager.subscribe(client_id, "AAPL")
    await manager.broadcast_to_ticker("AAPL", {"price": 185.50})
    await manager.disconnect(client_id)
"""

import logging
import json
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class ClientConnection:
    """
    Represente une connexion client WebSocket.

    Attributes:
        websocket: L'objet WebSocket FastAPI
        client_id: Identifiant unique du client
        subscriptions: Set des tickers auxquels le client est abonne
        connected_at: Date/heure de connexion
    """
    websocket: WebSocket
    client_id: str
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.now)


class WebSocketManager:
    """
    Gestionnaire central des connexions WebSocket.

    Fonctionnalites:
    - Connexion/deconnexion des clients
    - Subscription/unsubscription aux tickers
    - Broadcast aux clients abonnes
    - Gestion des rooms par ticker

    Thread-safe grace a asyncio.Lock.
    """

    def __init__(self):
        """Initialise le gestionnaire."""
        # Client ID -> ClientConnection
        self._connections: Dict[str, ClientConnection] = {}

        # Ticker -> Set[client_id]
        self._ticker_rooms: Dict[str, Set[str]] = {}

        # Lock pour thread-safety
        self._lock = asyncio.Lock()

        logger.info("WebSocketManager initialized")

    @property
    def connection_count(self) -> int:
        """Nombre de connexions actives."""
        return len(self._connections)

    @property
    def active_tickers(self) -> Set[str]:
        """Ensemble des tickers avec au moins un abonne."""
        return {
            ticker for ticker, clients in self._ticker_rooms.items()
            if len(clients) > 0
        }

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str
    ) -> None:
        """
        Enregistre une nouvelle connexion.

        Args:
            websocket: WebSocket FastAPI
            client_id: Identifiant unique du client
        """
        await websocket.accept()

        async with self._lock:
            self._connections[client_id] = ClientConnection(
                websocket=websocket,
                client_id=client_id,
            )

        logger.info(f"Client connected: {client_id} (total: {self.connection_count})")

        # Envoyer un message de bienvenue
        await self.send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat(),
        })

    async def disconnect(self, client_id: str) -> None:
        """
        Deconnecte un client.

        Args:
            client_id: Identifiant du client
        """
        async with self._lock:
            if client_id not in self._connections:
                return

            connection = self._connections[client_id]

            # Retirer de toutes les rooms
            for ticker in list(connection.subscriptions):
                if ticker in self._ticker_rooms:
                    self._ticker_rooms[ticker].discard(client_id)
                    if not self._ticker_rooms[ticker]:
                        del self._ticker_rooms[ticker]

            # Supprimer la connexion
            del self._connections[client_id]

        logger.info(f"Client disconnected: {client_id} (remaining: {self.connection_count})")

    async def subscribe(
        self,
        client_id: str,
        ticker: str
    ) -> bool:
        """
        Abonne un client a un ticker.

        Args:
            client_id: Identifiant du client
            ticker: Symbole du ticker

        Returns:
            True si l'abonnement a reussi
        """
        ticker = ticker.upper()

        async with self._lock:
            if client_id not in self._connections:
                return False

            connection = self._connections[client_id]

            # Ajouter a la subscription du client
            connection.subscriptions.add(ticker)

            # Ajouter a la room du ticker
            if ticker not in self._ticker_rooms:
                self._ticker_rooms[ticker] = set()
            self._ticker_rooms[ticker].add(client_id)

        logger.debug(f"Client {client_id} subscribed to {ticker}")

        # Confirmer l'abonnement
        await self.send_to_client(client_id, {
            "type": "subscribed",
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
        })

        return True

    async def unsubscribe(
        self,
        client_id: str,
        ticker: str
    ) -> bool:
        """
        Desabonne un client d'un ticker.

        Args:
            client_id: Identifiant du client
            ticker: Symbole du ticker

        Returns:
            True si le desabonnement a reussi
        """
        ticker = ticker.upper()

        async with self._lock:
            if client_id not in self._connections:
                return False

            connection = self._connections[client_id]

            # Retirer de la subscription du client
            connection.subscriptions.discard(ticker)

            # Retirer de la room du ticker
            if ticker in self._ticker_rooms:
                self._ticker_rooms[ticker].discard(client_id)
                if not self._ticker_rooms[ticker]:
                    del self._ticker_rooms[ticker]

        logger.debug(f"Client {client_id} unsubscribed from {ticker}")

        # Confirmer le desabonnement
        await self.send_to_client(client_id, {
            "type": "unsubscribed",
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
        })

        return True

    async def send_to_client(
        self,
        client_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Envoie un message a un client specifique.

        Args:
            client_id: Identifiant du client
            message: Message a envoyer (dict JSON-serializable)

        Returns:
            True si le message a ete envoye
        """
        if client_id not in self._connections:
            return False

        connection = self._connections[client_id]

        try:
            await connection.websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Error sending to client {client_id}: {e}")
            # Deconnecter le client en erreur
            await self.disconnect(client_id)
            return False

    async def broadcast_to_ticker(
        self,
        ticker: str,
        message: Dict[str, Any]
    ) -> int:
        """
        Broadcast un message a tous les clients abonnes a un ticker.

        Args:
            ticker: Symbole du ticker
            message: Message a envoyer

        Returns:
            Nombre de clients qui ont recu le message
        """
        ticker = ticker.upper()

        if ticker not in self._ticker_rooms:
            return 0

        client_ids = list(self._ticker_rooms.get(ticker, set()))
        sent_count = 0

        for client_id in client_ids:
            if await self.send_to_client(client_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_all(
        self,
        message: Dict[str, Any]
    ) -> int:
        """
        Broadcast un message a tous les clients connectes.

        Args:
            message: Message a envoyer

        Returns:
            Nombre de clients qui ont recu le message
        """
        client_ids = list(self._connections.keys())
        sent_count = 0

        for client_id in client_ids:
            if await self.send_to_client(client_id, message):
                sent_count += 1

        return sent_count

    def get_subscribers(self, ticker: str) -> Set[str]:
        """
        Retourne les IDs des clients abonnes a un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            Set des client IDs
        """
        ticker = ticker.upper()
        return self._ticker_rooms.get(ticker, set()).copy()

    def get_client_subscriptions(self, client_id: str) -> Set[str]:
        """
        Retourne les tickers auxquels un client est abonne.

        Args:
            client_id: Identifiant du client

        Returns:
            Set des tickers
        """
        if client_id not in self._connections:
            return set()
        return self._connections[client_id].subscriptions.copy()


# Instance globale (singleton)
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """
    Retourne l'instance globale du WebSocketManager.

    Returns:
        WebSocketManager singleton
    """
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
