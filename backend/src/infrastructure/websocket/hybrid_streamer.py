"""
Hybrid Price Streamer - Combine plusieurs sources de prix.

Features:
- Utilise la meilleure source disponible
- Fallback automatique si une source echoue
- Support pour tickers prioritaires (rafraichissement plus rapide)
- Gestion automatique des abonnements
"""

import logging
import asyncio
from typing import Optional, Dict, Set, List, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.infrastructure.websocket.ws_manager import WebSocketManager
from src.infrastructure.websocket.price_source import (
    PriceSource,
    PriceQuote,
    PriceCallback,
)
from src.infrastructure.websocket.yahoo_source import YahooPriceSource

logger = logging.getLogger(__name__)


@dataclass
class TickerConfig:
    """Configuration par ticker."""
    ticker: str
    priority: int = 1  # 1=normal, 2=high (portfolio), 3=critical
    source: Optional[str] = None  # Forcer une source specifique
    subscribed_at: datetime = field(default_factory=datetime.now)


class HybridPriceStreamer:
    """
    Streamer de prix hybride multi-sources.

    Combine Yahoo Finance (polling) avec possibilite d'ajouter
    Saxo WebSocket quand authentifie.

    Attributes:
        manager: WebSocketManager pour broadcast
        sources: Liste des sources de prix disponibles
    """

    def __init__(
        self,
        manager: WebSocketManager,
        poll_interval: float = 10.0,
        priority_interval: float = 5.0,
    ):
        """
        Args:
            manager: WebSocketManager pour broadcast
            poll_interval: Intervalle normal de polling (secondes)
            priority_interval: Intervalle pour tickers prioritaires
        """
        self.manager = manager
        self._poll_interval = poll_interval
        self._priority_interval = priority_interval

        # Sources de prix
        self._sources: Dict[str, PriceSource] = {}
        self._default_source: Optional[PriceSource] = None

        # Configuration des tickers
        self._ticker_configs: Dict[str, TickerConfig] = {}

        # Etat
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._priority_task: Optional[asyncio.Task] = None

        # Initialiser la source Yahoo par defaut
        self._init_default_sources()

        logger.info(f"HybridPriceStreamer initialized")

    def _init_default_sources(self) -> None:
        """Initialise les sources par defaut."""
        yahoo = YahooPriceSource(poll_interval=self._poll_interval)
        self.register_source(yahoo)
        self._default_source = yahoo

    def register_source(self, source: PriceSource) -> None:
        """
        Enregistre une nouvelle source de prix.

        Args:
            source: Source de prix a enregistrer
        """
        self._sources[source.source_name] = source
        logger.info(f"Registered price source: {source.source_name}")

    async def start(self) -> None:
        """Demarre le streaming."""
        if self._running:
            return

        self._running = True

        # Tache de polling normal
        self._poll_task = asyncio.create_task(
            self._poll_loop(self._poll_interval, priority=False)
        )

        # Tache de polling prioritaire
        self._priority_task = asyncio.create_task(
            self._poll_loop(self._priority_interval, priority=True)
        )

        logger.info("HybridPriceStreamer started")

    async def stop(self) -> None:
        """Arrete le streaming."""
        self._running = False

        for task in [self._poll_task, self._priority_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._poll_task = None
        self._priority_task = None

        logger.info("HybridPriceStreamer stopped")

    async def subscribe(
        self,
        ticker: str,
        priority: int = 1,
        source: Optional[str] = None,
    ) -> bool:
        """
        S'abonne aux mises a jour de prix.

        Args:
            ticker: Symbole du ticker
            priority: Niveau de priorite (1=normal, 2=high, 3=critical)
            source: Nom de la source a utiliser (optionnel)

        Returns:
            True si l'abonnement a reussi
        """
        ticker = ticker.upper()

        self._ticker_configs[ticker] = TickerConfig(
            ticker=ticker,
            priority=priority,
            source=source,
        )

        logger.debug(f"Subscribed to {ticker} (priority={priority})")

        # Envoyer le prix actuel immediatement
        await self.force_update(ticker)

        return True

    async def unsubscribe(self, ticker: str) -> bool:
        """Se desabonne d'un ticker."""
        ticker = ticker.upper()

        if ticker in self._ticker_configs:
            del self._ticker_configs[ticker]
            logger.debug(f"Unsubscribed from {ticker}")

        return True

    async def set_priority(self, ticker: str, priority: int) -> None:
        """
        Change la priorite d'un ticker.

        Args:
            ticker: Symbole du ticker
            priority: Nouvelle priorite
        """
        ticker = ticker.upper()

        if ticker in self._ticker_configs:
            self._ticker_configs[ticker].priority = priority
            logger.debug(f"Changed {ticker} priority to {priority}")

    async def force_update(self, ticker: str) -> Optional[PriceQuote]:
        """
        Force une mise a jour immediate.

        Args:
            ticker: Symbole du ticker

        Returns:
            PriceQuote ou None
        """
        ticker = ticker.upper()
        config = self._ticker_configs.get(ticker, TickerConfig(ticker=ticker))

        # Determiner la source
        source = self._get_source_for_ticker(config)
        if not source:
            logger.warning(f"No source available for {ticker}")
            return None

        # Recuperer le prix
        quote = await source.get_current_price(ticker)

        if quote:
            await self._broadcast_quote(quote)

        return quote

    def _get_source_for_ticker(self, config: TickerConfig) -> Optional[PriceSource]:
        """Determine la meilleure source pour un ticker."""
        # Si une source est specifiee
        if config.source and config.source in self._sources:
            return self._sources[config.source]

        # Sinon utiliser la source par defaut
        return self._default_source

    async def _poll_loop(
        self,
        interval: float,
        priority: bool = False
    ) -> None:
        """
        Boucle de polling.

        Args:
            interval: Intervalle en secondes
            priority: Si True, ne poll que les tickers prioritaires
        """
        while self._running:
            try:
                await self._poll_tickers(priority_only=priority)
            except Exception as e:
                logger.exception(f"Error in polling loop: {e}")

            await asyncio.sleep(interval)

    async def _poll_tickers(self, priority_only: bool = False) -> None:
        """Poll les tickers selon leurs priorites."""
        # Recuperer les tickers actifs du WebSocket manager
        active_tickers = self.manager.active_tickers

        for ticker in active_tickers:
            config = self._ticker_configs.get(
                ticker,
                TickerConfig(ticker=ticker)
            )

            # Filtrer par priorite
            if priority_only and config.priority < 2:
                continue
            if not priority_only and config.priority >= 2:
                continue  # Gere par la tache prioritaire

            try:
                await self.force_update(ticker)
            except Exception as e:
                logger.warning(f"Error polling {ticker}: {e}")

    async def _broadcast_quote(self, quote: PriceQuote) -> None:
        """Broadcast un quote a tous les clients abonnes."""
        message = quote.to_dict()
        sent = await self.manager.broadcast_to_ticker(quote.ticker, message)
        logger.debug(f"Broadcasted {quote.ticker} to {sent} clients ({quote.source})")

    @property
    def is_running(self) -> bool:
        """Indique si le streamer est en cours."""
        return self._running

    @property
    def subscribed_tickers(self) -> List[str]:
        """Liste des tickers abonnes."""
        return list(self._ticker_configs.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Retourne des statistiques sur le streamer."""
        return {
            "running": self._running,
            "sources": list(self._sources.keys()),
            "default_source": self._default_source.source_name if self._default_source else None,
            "subscribed_count": len(self._ticker_configs),
            "priority_tickers": [
                t for t, c in self._ticker_configs.items() if c.priority >= 2
            ],
            "poll_interval": self._poll_interval,
            "priority_interval": self._priority_interval,
        }


# Instance globale
_hybrid_streamer: Optional[HybridPriceStreamer] = None


def get_hybrid_streamer(
    manager: Optional[WebSocketManager] = None
) -> HybridPriceStreamer:
    """
    Retourne l'instance globale du HybridPriceStreamer.

    Args:
        manager: WebSocketManager (requis a la premiere creation)

    Returns:
        HybridPriceStreamer singleton
    """
    global _hybrid_streamer

    if _hybrid_streamer is None:
        if manager is None:
            from src.infrastructure.websocket.ws_manager import get_ws_manager
            manager = get_ws_manager()
        _hybrid_streamer = HybridPriceStreamer(manager)

    return _hybrid_streamer
