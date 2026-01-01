"""
Service de streaming des prix en temps reel.

Recupere periodiquement les prix des tickers abonnes
et les broadcast aux clients.

ARCHITECTURE:
- Utilise le YahooFinanceProvider pour les prix
- Polling periodique (configurable)
- Broadcast via WebSocketManager

UTILISATION:
    manager = WebSocketManager()
    streamer = PriceStreamer(manager)
    await streamer.start()
    # ...
    await streamer.stop()
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, Set, Dict, Any
from dataclasses import dataclass

from src.infrastructure.websocket.ws_manager import WebSocketManager
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


# Intervalle de polling par defaut (secondes)
DEFAULT_POLL_INTERVAL = 10


@dataclass
class PriceUpdate:
    """
    Mise a jour de prix pour un ticker.

    Attributes:
        ticker: Symbole du ticker
        price: Prix actuel
        change: Variation absolue
        change_percent: Variation en pourcentage
        timestamp: Date/heure de la mise a jour
    """
    ticker: str
    price: float
    change: Optional[float] = None
    change_percent: Optional[float] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dict pour JSON."""
        return {
            "type": "price_update",
            "ticker": self.ticker,
            "price": self.price,
            "change": self.change,
            "change_percent": self.change_percent,
            "timestamp": self.timestamp,
        }


class PriceStreamer:
    """
    Service de streaming des prix.

    Interroge periodiquement Yahoo Finance pour les tickers
    auxquels des clients sont abonnes, et broadcast les mises a jour.

    Attributes:
        manager: WebSocketManager pour le broadcast
        poll_interval: Intervalle entre les polls (secondes)
    """

    def __init__(
        self,
        manager: WebSocketManager,
        poll_interval: int = DEFAULT_POLL_INTERVAL
    ):
        """
        Initialise le streamer.

        Args:
            manager: WebSocketManager pour le broadcast
            poll_interval: Intervalle de polling en secondes
        """
        self.manager = manager
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_prices: Dict[str, float] = {}

        logger.info(f"PriceStreamer initialized (poll interval: {poll_interval}s)")

    @property
    def is_running(self) -> bool:
        """Indique si le streamer est en cours d'execution."""
        return self._running

    async def start(self) -> None:
        """
        Demarre le streaming des prix.

        Lance une tache en arriere-plan qui poll les prix.
        """
        if self._running:
            logger.warning("PriceStreamer already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("PriceStreamer started")

    async def stop(self) -> None:
        """
        Arrete le streaming des prix.

        Annule la tache de polling.
        """
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("PriceStreamer stopped")

    async def _poll_loop(self) -> None:
        """
        Boucle principale de polling.

        S'execute tant que self._running est True.
        """
        while self._running:
            try:
                await self._poll_prices()
            except Exception as e:
                logger.exception(f"Error in price polling: {e}")

            await asyncio.sleep(self.poll_interval)

    async def _poll_prices(self) -> None:
        """
        Poll les prix de tous les tickers actifs.

        Recupere les prix via yfinance et broadcast les mises a jour.
        """
        active_tickers = self.manager.active_tickers

        if not active_tickers:
            logger.debug("No active tickers to poll")
            return

        logger.debug(f"Polling prices for {len(active_tickers)} tickers")

        for ticker in active_tickers:
            try:
                price_update = await self._get_price(ticker)
                if price_update:
                    await self._broadcast_update(price_update)
            except Exception as e:
                logger.warning(f"Error getting price for {ticker}: {e}")

    async def _get_price(self, ticker: str) -> Optional[PriceUpdate]:
        """
        Recupere le prix actuel d'un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            PriceUpdate ou None si erreur
        """
        try:
            # Utiliser yfinance en mode synchrone via run_in_executor
            import yfinance as yf

            loop = asyncio.get_event_loop()
            stock = await loop.run_in_executor(None, yf.Ticker, ticker)

            # Recuperer le prix rapide
            info = await loop.run_in_executor(
                None,
                lambda: stock.fast_info
            )

            price = info.get("lastPrice") or info.get("regularMarketPrice")
            if not price:
                # Fallback sur history
                hist = await loop.run_in_executor(
                    None,
                    lambda: stock.history(period="1d")
                )
                if not hist.empty:
                    price = hist['Close'].iloc[-1]

            if not price:
                return None

            # Calculer le changement
            previous_price = self._last_prices.get(ticker)
            change = None
            change_percent = None

            if previous_price and previous_price > 0:
                change = price - previous_price
                change_percent = (change / previous_price) * 100

            # Mettre a jour le cache
            self._last_prices[ticker] = price

            return PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                change=round(change, 2) if change else None,
                change_percent=round(change_percent, 2) if change_percent else None,
            )

        except Exception as e:
            logger.warning(f"Failed to get price for {ticker}: {e}")
            return None

    async def _broadcast_update(self, update: PriceUpdate) -> None:
        """
        Broadcast une mise a jour de prix.

        Args:
            update: Mise a jour a broadcaster
        """
        message = update.to_dict()
        sent = await self.manager.broadcast_to_ticker(update.ticker, message)
        logger.debug(f"Broadcasted {update.ticker} price to {sent} clients")

    async def force_update(self, ticker: str) -> Optional[PriceUpdate]:
        """
        Force une mise a jour immediate pour un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            PriceUpdate ou None si erreur
        """
        ticker = ticker.upper()
        update = await self._get_price(ticker)

        if update:
            await self._broadcast_update(update)

        return update


# Instance globale
_price_streamer: Optional[PriceStreamer] = None


def get_price_streamer(manager: Optional[WebSocketManager] = None) -> PriceStreamer:
    """
    Retourne l'instance globale du PriceStreamer.

    Args:
        manager: WebSocketManager (requis a la premiere creation)

    Returns:
        PriceStreamer singleton
    """
    global _price_streamer

    if _price_streamer is None:
        if manager is None:
            from src.infrastructure.websocket.ws_manager import get_ws_manager
            manager = get_ws_manager()
        _price_streamer = PriceStreamer(manager)

    return _price_streamer
