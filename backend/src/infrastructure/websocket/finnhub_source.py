"""
Finnhub WebSocket Price Source - Temps reel gratuit.

Utilise l'API WebSocket de Finnhub pour recevoir des prix en temps reel.
Utilise la cle API deja configuree dans settings (FINNHUB_API_KEY).

USAGE:
    source = FinnhubPriceSource()
    await source.connect()
    await source.subscribe("AAPL", callback)
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Set, Callable, Awaitable
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from src.infrastructure.websocket.price_source import (
    PriceSource,
    PriceQuote,
    PriceCallback,
)
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Configuration Finnhub
FINNHUB_WS_URL = "wss://ws.finnhub.io"
RECONNECT_DELAY = 5  # secondes
MAX_RECONNECT_ATTEMPTS = 10
PING_INTERVAL = 30  # secondes


class FinnhubPriceSource(PriceSource):
    """
    Source de prix temps reel via Finnhub WebSocket.

    Gratuit avec limites:
    - 60 messages/seconde
    - Support US stocks, forex, crypto

    Attributes:
        api_key: Cle API Finnhub (depuis settings)
        _ws: Connexion WebSocket
        _callbacks: Callbacks par ticker
        _subscribed: Tickers actuellement abonnes
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Cle API Finnhub (optionnel, utilise settings par defaut)
        """
        self._api_key = api_key or settings.FINNHUB_API_KEY or ""
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._callbacks: Dict[str, Set[PriceCallback]] = {}
        self._subscribed: Set[str] = set()
        self._running = False
        self._connected = False
        self._reconnect_attempts = 0
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._last_prices: Dict[str, PriceQuote] = {}

        if not self._api_key:
            logger.warning(
                "Finnhub API key not configured. "
                "Set FINNHUB_API_KEY environment variable or pass api_key parameter. "
                "Get free key at: https://finnhub.io/register"
            )

    @property
    def source_name(self) -> str:
        return "finnhub"

    @property
    def is_realtime(self) -> bool:
        return True

    async def is_available(self) -> bool:
        """Verifie si Finnhub est disponible (cle API configuree)."""
        return bool(self._api_key)

    async def is_connected(self) -> bool:
        """Verifie si Finnhub est actuellement connecte."""
        return self._connected

    async def connect(self) -> bool:
        """
        Etablit la connexion WebSocket avec Finnhub.

        Returns:
            True si connecte avec succes
        """
        if not self._api_key:
            logger.error("Cannot connect: Finnhub API key not configured")
            return False

        if self._connected:
            return True

        try:
            url = f"{FINNHUB_WS_URL}?token={self._api_key}"
            self._ws = await websockets.connect(
                url,
                ping_interval=PING_INTERVAL,
                ping_timeout=10,
            )

            self._connected = True
            self._running = True
            self._reconnect_attempts = 0

            # Demarrer la reception des messages
            self._receive_task = asyncio.create_task(self._receive_loop())

            logger.info("Connected to Finnhub WebSocket")

            # Re-souscrire aux tickers si reconnexion
            for ticker in list(self._subscribed):
                await self._send_subscribe(ticker)

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Finnhub: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Ferme la connexion WebSocket."""
        self._running = False
        self._connected = False

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

        logger.info("Disconnected from Finnhub WebSocket")

    async def subscribe(
        self,
        ticker: str,
        callback: PriceCallback
    ) -> bool:
        """
        S'abonne aux mises a jour de prix pour un ticker.

        Args:
            ticker: Symbole du ticker (format: AAPL pour US stocks)
            callback: Fonction appelee lors des mises a jour

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
            await self.connect()

        # Envoyer la souscription si pas deja abonne
        if ticker not in self._subscribed:
            success = await self._send_subscribe(ticker)
            if success:
                self._subscribed.add(ticker)
                logger.info(f"Subscribed to {ticker} on Finnhub")
            return success

        return True

    async def unsubscribe(self, ticker: str) -> bool:
        """Se desabonne d'un ticker."""
        ticker = ticker.upper()

        # Retirer des callbacks
        if ticker in self._callbacks:
            del self._callbacks[ticker]

        # Envoyer le desabonnement
        if ticker in self._subscribed and self._connected and self._ws:
            try:
                message = {"type": "unsubscribe", "symbol": ticker}
                await self._ws.send(json.dumps(message))
                self._subscribed.discard(ticker)
                logger.info(f"Unsubscribed from {ticker} on Finnhub")
                return True
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {ticker}: {e}")

        return False

    async def get_current_price(self, ticker: str) -> Optional[PriceQuote]:
        """
        Recupere le dernier prix connu pour un ticker.

        Note: Pour temps reel, utiliser subscribe() avec callback.
        Cette methode retourne le dernier prix recu via WebSocket.
        """
        ticker = ticker.upper()
        return self._last_prices.get(ticker)

    async def _send_subscribe(self, ticker: str) -> bool:
        """Envoie une commande de souscription."""
        if not self._ws or not self._connected:
            return False

        try:
            message = {"type": "subscribe", "symbol": ticker}
            await self._ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {ticker}: {e}")
            return False

    async def _receive_loop(self) -> None:
        """Boucle de reception des messages WebSocket."""
        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)

            except ConnectionClosed as e:
                logger.warning(f"Finnhub connection closed: {e}")
                self._connected = False
                await self._reconnect()

            except Exception as e:
                logger.error(f"Error receiving Finnhub message: {e}")
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _handle_message(self, raw_message: str) -> None:
        """
        Traite un message recu de Finnhub.

        Format des messages de trade:
        {
            "type": "trade",
            "data": [
                {"s": "AAPL", "p": 150.25, "v": 100, "t": 1609459200000}
            ]
        }
        """
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type")

            if msg_type == "trade":
                for trade in message.get("data", []):
                    await self._process_trade(trade)

            elif msg_type == "ping":
                # Finnhub envoie des pings periodiques
                pass

            elif msg_type == "error":
                logger.error(f"Finnhub error: {message.get('msg')}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from Finnhub: {raw_message[:100]}")
        except Exception as e:
            logger.error(f"Error handling Finnhub message: {e}")

    async def _process_trade(self, trade: Dict) -> None:
        """
        Traite un trade individuel.

        Args:
            trade: Dict avec s=symbol, p=price, v=volume, t=timestamp
        """
        ticker = trade.get("s", "").upper()
        price = trade.get("p")
        volume = trade.get("v")
        timestamp_ms = trade.get("t", 0)

        if not ticker or price is None:
            return

        # Calculer le changement si on a un prix precedent
        previous = self._last_prices.get(ticker)
        change = None
        change_percent = None

        if previous and previous.price:
            change = price - previous.price
            change_percent = (change / previous.price) * 100

        # Creer le quote
        quote = PriceQuote(
            ticker=ticker,
            price=float(price),
            volume=int(volume) if volume else None,
            change=change,
            change_percent=change_percent,
            timestamp=datetime.fromtimestamp(timestamp_ms / 1000).isoformat() if timestamp_ms else None,
            source=self.source_name,
        )

        # Sauvegarder le dernier prix
        self._last_prices[ticker] = quote

        # Notifier les callbacks
        callbacks = self._callbacks.get(ticker, set())
        for callback in callbacks:
            try:
                await callback(quote)
            except Exception as e:
                logger.error(f"Error in Finnhub callback for {ticker}: {e}")

    async def _reconnect(self) -> None:
        """Tente de se reconnecter apres une deconnexion."""
        if not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached for Finnhub")
            self._running = False
            return

        delay = RECONNECT_DELAY * self._reconnect_attempts
        logger.info(f"Reconnecting to Finnhub in {delay}s (attempt {self._reconnect_attempts})")

        await asyncio.sleep(delay)
        await self.connect()

    def get_stats(self) -> Dict:
        """Retourne des statistiques sur la source."""
        return {
            "source": self.source_name,
            "connected": self._connected,
            "subscribed_count": len(self._subscribed),
            "subscribed_tickers": list(self._subscribed),
            "reconnect_attempts": self._reconnect_attempts,
            "is_realtime": self.is_realtime,
            "api_key_configured": bool(self._api_key),
        }


# Instance globale
_finnhub_source: Optional[FinnhubPriceSource] = None


def get_finnhub_source() -> FinnhubPriceSource:
    """Retourne l'instance singleton de FinnhubPriceSource."""
    global _finnhub_source
    if _finnhub_source is None:
        _finnhub_source = FinnhubPriceSource()
    return _finnhub_source
