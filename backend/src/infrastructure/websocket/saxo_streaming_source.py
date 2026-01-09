"""
Saxo Bank WebSocket Streaming Source - Prix temps reel via compte Saxo.

Utilise l'API streaming de Saxo OpenAPI pour recevoir des prix en temps reel.
Gratuit si vous avez un compte Saxo (SIM ou LIVE).

DOCUMENTATION:
https://www.developer.saxo/openapi/learn/plain-websocket-streaming

USAGE:
    source = SaxoStreamingSource()
    await source.connect()
    await source.subscribe("AAPL", callback)
"""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Set, List, Any
from datetime import datetime
from dataclasses import dataclass

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from src.infrastructure.websocket.price_source import (
    PriceSource,
    PriceQuote,
    PriceCallback,
)
from src.infrastructure.persistence.token_store import get_token_store
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Configuration Saxo Streaming
# SIM: wss://streaming.saxobank.com/sim/openapi/streamingws/connect
# LIVE: wss://streaming.saxobank.com/openapi/streamingws/connect
SAXO_STREAMING_URL_SIM = "wss://streaming.saxobank.com/sim/openapi/streamingws/connect"
SAXO_STREAMING_URL_LIVE = "wss://streaming.saxobank.com/openapi/streamingws/connect"

RECONNECT_DELAY = 5
MAX_RECONNECT_ATTEMPTS = 10
HEARTBEAT_INTERVAL = 30  # Saxo attend un heartbeat toutes les 30s


@dataclass
class SaxoSubscription:
    """Configuration d'une souscription Saxo."""
    context_id: str
    reference_id: str
    uic: int
    asset_type: str
    ticker: str


class SaxoStreamingSource(PriceSource):
    """
    Source de prix temps reel via Saxo Bank WebSocket Streaming.

    Utilise le token OAuth existant pour se connecter au flux de prix.
    Supporte tous les instruments disponibles sur votre compte Saxo.

    Attributes:
        _ws: Connexion WebSocket
        _callbacks: Callbacks par ticker
        _subscriptions: Souscriptions actives
    """

    def __init__(self, user_id: str = "default"):
        """
        Args:
            user_id: ID utilisateur pour recuperer le token (default="default")
        """
        self._user_id = user_id
        self._token_store = get_token_store()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._callbacks: Dict[str, Set[PriceCallback]] = {}
        self._subscriptions: Dict[str, SaxoSubscription] = {}
        self._uic_to_ticker: Dict[int, str] = {}  # Map UIC -> ticker symbol
        self._ticker_to_uic: Dict[str, int] = {}  # Map ticker -> UIC
        self._running = False
        self._connected = False
        self._reconnect_attempts = 0
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_prices: Dict[str, PriceQuote] = {}
        self._context_id = f"ctx_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._ref_counter = 0
        self._access_token: Optional[str] = None

    @property
    def source_name(self) -> str:
        return "saxo"

    @property
    def is_realtime(self) -> bool:
        return True

    async def is_available(self) -> bool:
        """Verifie si Saxo streaming est disponible (token OAuth existant)."""
        token = await self._get_token()
        return token is not None

    async def is_connected(self) -> bool:
        """Verifie si Saxo est actuellement connecte au streaming."""
        return self._connected

    async def _get_token(self) -> Optional[str]:
        """Recupere le token Saxo depuis le store."""
        try:
            stored = await self._token_store.get_token(self._user_id, "saxo")
            if stored and not stored.is_expired:
                return stored.access_token
            logger.warning("Saxo token expired or not found")
            return None
        except Exception as e:
            logger.error(f"Error getting Saxo token: {e}")
            return None

    def _get_streaming_url(self) -> str:
        """Retourne l'URL de streaming selon l'environnement."""
        env = getattr(settings, 'saxo_environment', 'SIM').upper()
        if env == 'LIVE':
            return SAXO_STREAMING_URL_LIVE
        return SAXO_STREAMING_URL_SIM

    async def connect(self) -> bool:
        """
        Etablit la connexion WebSocket avec Saxo Streaming.

        Returns:
            True si connecte avec succes
        """
        token = await self._get_token()
        if not token:
            logger.error("Cannot connect: Saxo token not available")
            return False

        if self._connected:
            return True

        try:
            self._access_token = token
            url = f"{self._get_streaming_url()}?authorization=Bearer {token}&contextId={self._context_id}"

            self._ws = await websockets.connect(
                url,
                ping_interval=None,  # On gere le heartbeat nous-memes
                ping_timeout=None,
            )

            self._connected = True
            self._running = True
            self._reconnect_attempts = 0

            # Demarrer la reception des messages
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Demarrer le heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info(f"Connected to Saxo Streaming (context: {self._context_id})")

            # Re-souscrire aux tickers si reconnexion
            for ticker, sub in list(self._subscriptions.items()):
                await self._send_subscription(sub.uic, sub.asset_type, ticker)

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Saxo Streaming: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Ferme la connexion WebSocket."""
        self._running = False
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("Disconnected from Saxo Streaming")

    async def subscribe(
        self,
        ticker: str,
        callback: PriceCallback,
        uic: Optional[int] = None,
        asset_type: str = "Stock"
    ) -> bool:
        """
        S'abonne aux mises a jour de prix pour un ticker.

        Args:
            ticker: Symbole du ticker (ex: AAPL)
            callback: Fonction appelee lors des mises a jour
            uic: Universal Instrument Code Saxo (optionnel)
            asset_type: Type d'actif (Stock, Etf, etc.)

        Returns:
            True si l'abonnement a reussi
        """
        ticker = ticker.upper()

        # Ajouter le callback
        if ticker not in self._callbacks:
            self._callbacks[ticker] = set()
        self._callbacks[ticker].add(callback)

        # Se connecter si necessaire
        if not self._connected:
            connected = await self.connect()
            if not connected:
                return False

        # Si on a deja une souscription, pas besoin de re-souscrire
        if ticker in self._subscriptions:
            return True

        # Envoyer la souscription si on a l'UIC
        if uic:
            self._ticker_to_uic[ticker] = uic
            self._uic_to_ticker[uic] = ticker
            success = await self._send_subscription(uic, asset_type, ticker)
            if success:
                logger.info(f"Subscribed to {ticker} (UIC={uic}) on Saxo Streaming")
            return success

        # Sans UIC, on ne peut pas souscrire via streaming
        # (il faudrait chercher l'UIC via l'API REST)
        logger.warning(f"Cannot subscribe to {ticker}: UIC not provided")
        return False

    async def subscribe_position(
        self,
        ticker: str,
        uic: int,
        asset_type: str,
        callback: PriceCallback
    ) -> bool:
        """
        S'abonne a une position du portfolio (UIC connu).

        Args:
            ticker: Symbole du ticker
            uic: Universal Instrument Code
            asset_type: Type d'actif
            callback: Callback pour les prix

        Returns:
            True si reussi
        """
        return await self.subscribe(ticker, callback, uic=uic, asset_type=asset_type)

    async def unsubscribe(self, ticker: str) -> bool:
        """Se desabonne d'un ticker."""
        ticker = ticker.upper()

        # Retirer des callbacks
        if ticker in self._callbacks:
            del self._callbacks[ticker]

        # Envoyer le desabonnement
        if ticker in self._subscriptions and self._connected and self._ws:
            sub = self._subscriptions[ticker]
            try:
                # Saxo utilise DELETE sur l'endpoint REST pour desabonner
                # Via WebSocket, on ne peut pas vraiment se desabonner
                # On retire juste de notre tracking
                del self._subscriptions[ticker]
                logger.info(f"Unsubscribed from {ticker} on Saxo Streaming")
                return True
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {ticker}: {e}")

        return False

    async def get_current_price(self, ticker: str) -> Optional[PriceQuote]:
        """
        Recupere le dernier prix connu pour un ticker.

        Note: Pour temps reel, utiliser subscribe() avec callback.
        """
        ticker = ticker.upper()
        return self._last_prices.get(ticker)

    async def _send_subscription(
        self,
        uic: int,
        asset_type: str,
        ticker: str
    ) -> bool:
        """Envoie une commande de souscription aux prix."""
        if not self._ws or not self._connected:
            return False

        try:
            self._ref_counter += 1
            reference_id = f"price_{uic}_{self._ref_counter}"

            # Format de souscription Saxo Streaming
            # On souscrit aux InfoPrices pour avoir bid/ask/last
            subscription = {
                "ReferenceId": reference_id,
                "Arguments": {
                    "Uic": uic,
                    "AssetType": asset_type,
                    "FieldGroups": [
                        "Quote",          # Bid, Ask, Mid
                        "PriceInfo",      # High, Low, Open
                        "PriceInfoDetails"  # LastTraded, Volume
                    ]
                }
            }

            # Message de souscription
            message = {
                "ReferenceId": reference_id,
                "ContextId": self._context_id,
                "ServicePath": "trade/v1/infoprices/subscriptions",
                "HttpMethod": "POST",
                "Body": subscription
            }

            await self._ws.send(json.dumps(message))

            # Enregistrer la souscription
            self._subscriptions[ticker] = SaxoSubscription(
                context_id=self._context_id,
                reference_id=reference_id,
                uic=uic,
                asset_type=asset_type,
                ticker=ticker
            )

            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to {ticker}: {e}")
            return False

    async def _heartbeat_loop(self) -> None:
        """Envoie des heartbeats periodiques."""
        while self._running and self._ws:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                if self._ws and self._connected:
                    # Saxo attend un message de heartbeat
                    heartbeat = {
                        "ReferenceId": "heartbeat",
                        "Heartbeat": True
                    }
                    await self._ws.send(json.dumps(heartbeat))
                    logger.debug("Sent Saxo heartbeat")

            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                if not self._running:
                    break

    async def _receive_loop(self) -> None:
        """Boucle de reception des messages WebSocket."""
        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)

            except ConnectionClosed as e:
                logger.warning(f"Saxo connection closed: {e}")
                self._connected = False
                await self._reconnect()

            except Exception as e:
                logger.error(f"Error receiving Saxo message: {e}")
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _handle_message(self, raw_message: str) -> None:
        """
        Traite un message recu de Saxo Streaming.

        Les messages Saxo ont plusieurs formats:
        - Heartbeat response
        - Subscription confirmation
        - Price update (delta)
        """
        try:
            # Les messages Saxo peuvent etre binaires ou JSON
            if isinstance(raw_message, bytes):
                message = json.loads(raw_message.decode('utf-8'))
            else:
                message = json.loads(raw_message)

            # Traiter selon le type
            if isinstance(message, list):
                # Batch de messages
                for msg in message:
                    await self._process_message(msg)
            else:
                await self._process_message(message)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from Saxo: {str(raw_message)[:100]}")
        except Exception as e:
            logger.error(f"Error handling Saxo message: {e}")

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Traite un message individuel."""
        ref_id = message.get("ReferenceId", "")

        # Heartbeat
        if message.get("Heartbeat"):
            logger.debug("Received Saxo heartbeat response")
            return

        # Confirmation de souscription
        if "Snapshot" in message:
            await self._handle_snapshot(message)
            return

        # Mise a jour de prix
        if "Data" in message or "Quote" in message:
            await self._handle_price_update(message, ref_id)
            return

        # Erreur
        if "ErrorCode" in message:
            logger.error(f"Saxo error: {message.get('ErrorCode')} - {message.get('Message')}")
            return

    async def _handle_snapshot(self, message: Dict[str, Any]) -> None:
        """Traite un snapshot initial apres souscription."""
        ref_id = message.get("ReferenceId", "")
        snapshot = message.get("Snapshot", {})

        # Trouver le ticker associe
        ticker = None
        for t, sub in self._subscriptions.items():
            if sub.reference_id == ref_id:
                ticker = t
                break

        if not ticker:
            return

        # Extraire les donnees de prix
        quote = snapshot.get("Quote", {})
        price_info = snapshot.get("PriceInfo", {})

        price = quote.get("Mid") or quote.get("Ask") or quote.get("Bid") or price_info.get("LastTraded")

        if price:
            price_quote = PriceQuote(
                ticker=ticker,
                price=float(price),
                bid=quote.get("Bid"),
                ask=quote.get("Ask"),
                volume=price_info.get("Volume"),
                timestamp=datetime.now().isoformat(),
                source=self.source_name,
            )

            self._last_prices[ticker] = price_quote
            await self._notify_callbacks(ticker, price_quote)

    async def _handle_price_update(self, message: Dict[str, Any], ref_id: str) -> None:
        """Traite une mise a jour de prix."""
        # Trouver le ticker associe
        ticker = None
        for t, sub in self._subscriptions.items():
            if sub.reference_id == ref_id:
                ticker = t
                break

        if not ticker:
            return

        # Les updates peuvent etre dans Data ou directement dans le message
        data = message.get("Data", [message])
        if not isinstance(data, list):
            data = [data]

        for update in data:
            quote_data = update.get("Quote", {})
            price_info = update.get("PriceInfo", {})

            # Determiner le prix
            price = (
                quote_data.get("Mid") or
                quote_data.get("Ask") or
                quote_data.get("Bid") or
                price_info.get("LastTraded")
            )

            if price is None:
                continue

            # Calculer le changement
            previous = self._last_prices.get(ticker)
            change = None
            change_percent = None

            if previous and previous.price:
                change = float(price) - previous.price
                change_percent = (change / previous.price) * 100

            price_quote = PriceQuote(
                ticker=ticker,
                price=float(price),
                bid=quote_data.get("Bid"),
                ask=quote_data.get("Ask"),
                change=change,
                change_percent=change_percent,
                volume=price_info.get("Volume"),
                timestamp=datetime.now().isoformat(),
                source=self.source_name,
            )

            self._last_prices[ticker] = price_quote
            await self._notify_callbacks(ticker, price_quote)

    async def _notify_callbacks(self, ticker: str, quote: PriceQuote) -> None:
        """Notifie les callbacks pour un ticker."""
        callbacks = self._callbacks.get(ticker, set())
        for callback in callbacks:
            try:
                await callback(quote)
            except Exception as e:
                logger.error(f"Error in Saxo callback for {ticker}: {e}")

    async def _reconnect(self) -> None:
        """Tente de se reconnecter apres une deconnexion."""
        if not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached for Saxo Streaming")
            self._running = False
            return

        delay = RECONNECT_DELAY * self._reconnect_attempts
        logger.info(f"Reconnecting to Saxo Streaming in {delay}s (attempt {self._reconnect_attempts})")

        await asyncio.sleep(delay)

        # Rafraichir le token si necessaire
        self._access_token = await self._get_token()
        if self._access_token:
            await self.connect()

    def get_stats(self) -> Dict:
        """Retourne des statistiques sur la source."""
        return {
            "source": self.source_name,
            "connected": self._connected,
            "context_id": self._context_id,
            "subscribed_count": len(self._subscriptions),
            "subscribed_tickers": list(self._subscriptions.keys()),
            "reconnect_attempts": self._reconnect_attempts,
            "is_realtime": self.is_realtime,
        }


# Instance globale
_saxo_streaming: Optional[SaxoStreamingSource] = None


def get_saxo_streaming_source(user_id: str = "default") -> SaxoStreamingSource:
    """Retourne l'instance singleton de SaxoStreamingSource."""
    global _saxo_streaming
    if _saxo_streaming is None:
        _saxo_streaming = SaxoStreamingSource(user_id=user_id)
    return _saxo_streaming
