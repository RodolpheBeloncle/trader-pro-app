"""
Hybrid Price Streamer - Combine plusieurs sources de prix.

Features:
- Utilise la meilleure source disponible
- Fallback automatique si une source echoue
- Support pour tickers prioritaires (rafraichissement plus rapide)
- Gestion automatique des abonnements
- Support des modes de trading (long_term, swing, scalping)
- Integration Finnhub et Saxo pour temps reel
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
from src.infrastructure.websocket.trading_mode import (
    TradingMode,
    TradingModeConfig,
    get_current_config,
    get_mode_config,
    set_current_mode,
)

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

    Combine Yahoo Finance (polling) avec Finnhub et Saxo WebSocket
    pour le temps reel.

    Supporte 3 modes de trading:
    - LONG_TERM: Polling 60s (Yahoo)
    - SWING: Polling 10s (Yahoo/Finnhub)
    - SCALPING: WebSocket temps reel (Finnhub/Saxo)

    Attributes:
        manager: WebSocketManager pour broadcast
        sources: Liste des sources de prix disponibles
        trading_mode: Mode de trading actuel
    """

    def __init__(
        self,
        manager: WebSocketManager,
        poll_interval: float = 10.0,
        priority_interval: float = 5.0,
        trading_mode: Optional[TradingMode] = None,
    ):
        """
        Args:
            manager: WebSocketManager pour broadcast
            poll_interval: Intervalle normal de polling (secondes)
            priority_interval: Intervalle pour tickers prioritaires
            trading_mode: Mode de trading initial (None = utilise config globale)
        """
        self.manager = manager

        # Mode de trading
        self._trading_mode = trading_mode or TradingMode.LONG_TERM
        self._mode_config = get_mode_config(self._trading_mode)

        # Appliquer les intervalles du mode (0.0 est valide pour temps reel)
        self._poll_interval = self._mode_config.poll_interval if self._mode_config.poll_interval is not None else poll_interval
        self._priority_interval = self._mode_config.priority_interval if self._mode_config.priority_interval is not None else priority_interval

        # Sources de prix
        self._sources: Dict[str, PriceSource] = {}
        self._default_source: Optional[PriceSource] = None
        self._realtime_sources: Dict[str, PriceSource] = {}  # Sources WebSocket

        # Configuration des tickers
        self._ticker_configs: Dict[str, TickerConfig] = {}

        # Etat
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._priority_task: Optional[asyncio.Task] = None

        # Initialiser les sources
        self._init_default_sources()

        logger.info(
            f"HybridPriceStreamer initialized (mode={self._trading_mode.value}, "
            f"poll={self._poll_interval}s)"
        )

    def _init_default_sources(self) -> None:
        """Initialise les sources par defaut."""
        yahoo = YahooPriceSource(poll_interval=self._poll_interval)
        self.register_source(yahoo)
        self._default_source = yahoo

        # Initialiser les sources temps reel si disponibles
        self._init_realtime_sources()

    def _init_realtime_sources(self) -> None:
        """Initialise les sources temps reel (Finnhub, Saxo)."""
        # Finnhub (si cle API configuree)
        try:
            from src.infrastructure.websocket.finnhub_source import get_finnhub_source
            from src.application.services.app_config_service import get_app_config_service

            config_service = get_app_config_service()
            is_configured = config_service.is_finnhub_configured()

            logger.info(f"Finnhub configured: {is_configured}")

            if is_configured:
                # Mettre a jour la cle dans la source si necessaire
                api_key = config_service.get_finnhub_api_key()
                finnhub = get_finnhub_source()
                if api_key:
                    finnhub._api_key = api_key
                self.register_source(finnhub)
                self._realtime_sources["finnhub"] = finnhub
                logger.info("Finnhub realtime source registered")
            else:
                logger.warning("Finnhub not configured - set FINNHUB_API_KEY in .env or via UI")
        except ImportError as e:
            logger.warning(f"Finnhub source import error: {e}")
        except Exception as e:
            logger.exception(f"Failed to init Finnhub source: {e}")

        # Saxo Streaming (toujours enregistre, disponibilite verifiee a l'usage)
        try:
            from src.infrastructure.websocket.saxo_streaming_source import get_saxo_streaming_source
            saxo = get_saxo_streaming_source()
            self.register_source(saxo)
            self._realtime_sources["saxo"] = saxo
            logger.info("Saxo streaming source registered")
        except ImportError as e:
            logger.warning(f"Saxo streaming source import error: {e}")
        except Exception as e:
            logger.exception(f"Failed to init Saxo streaming source: {e}")

    async def set_trading_mode(self, mode: TradingMode) -> Dict[str, Any]:
        """
        Change le mode de trading.

        Cela reconfigure les intervalles de polling et active/desactive
        les sources temps reel selon le mode.

        Args:
            mode: Nouveau mode de trading

        Returns:
            Dict avec la nouvelle configuration
        """
        old_mode = self._trading_mode
        self._trading_mode = mode
        self._mode_config = get_mode_config(mode)

        # Mettre a jour la config globale
        set_current_mode(mode)

        logger.info(f"Trading mode changed: {old_mode.value} -> {mode.value}")

        # Mettre a jour les intervalles (attention: 0.0 est valide pour scalping)
        self._poll_interval = self._mode_config.poll_interval if self._mode_config.poll_interval is not None else 60.0
        self._priority_interval = self._mode_config.priority_interval if self._mode_config.priority_interval is not None else 30.0

        # Redemarrer si en cours d'execution
        was_running = self._running
        if was_running:
            await self.stop()

        # Gerer les sources temps reel
        if self._mode_config.use_websocket:
            # Activer les sources temps reel
            await self._activate_realtime_sources()
        else:
            # Desactiver les sources temps reel
            await self._deactivate_realtime_sources()

        # Redemarrer
        if was_running:
            await self.start()

        return {
            "mode": mode.value,
            "display_name": self._mode_config.display_name,
            "poll_interval": self._poll_interval,
            "use_websocket": self._mode_config.use_websocket,
            "sources": list(self._sources.keys()),
        }

    async def _activate_realtime_sources(self) -> None:
        """Active les sources temps reel pour le mode scalping."""
        for name, source in self._realtime_sources.items():
            if source.is_realtime:
                try:
                    if hasattr(source, 'connect'):
                        await source.connect()
                        logger.info(f"Activated realtime source: {name}")

                    # S'abonner aux tickers actifs avec callback temps reel
                    if hasattr(source, 'subscribe'):
                        active_tickers = self.manager.active_tickers
                        for ticker in active_tickers:
                            try:
                                await source.subscribe(ticker, self._handle_realtime_quote)
                                logger.debug(f"Subscribed {ticker} to realtime source {name}")
                            except Exception as e:
                                logger.warning(f"Failed to subscribe {ticker} to {name}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to activate {name}: {e}")

    async def _handle_realtime_quote(self, quote: PriceQuote) -> None:
        """Callback pour les prix temps reel - broadcast direct au frontend."""
        if quote:
            await self._broadcast_quote(quote)

    async def _deactivate_realtime_sources(self) -> None:
        """Desactive les sources temps reel."""
        for name, source in self._realtime_sources.items():
            if source.is_realtime:
                try:
                    if hasattr(source, 'disconnect'):
                        await source.disconnect()
                        logger.info(f"Deactivated realtime source: {name}")
                except Exception as e:
                    logger.warning(f"Failed to deactivate {name}: {e}")

    @property
    def trading_mode(self) -> TradingMode:
        """Retourne le mode de trading actuel."""
        return self._trading_mode

    @property
    def mode_config(self) -> TradingModeConfig:
        """Retourne la configuration du mode actuel."""
        return self._mode_config

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

        # Si en mode temps reel, s'abonner aux sources WebSocket
        if self._mode_config.use_websocket:
            for name, rt_source in self._realtime_sources.items():
                if rt_source.is_realtime and hasattr(rt_source, 'subscribe'):
                    try:
                        await rt_source.subscribe(ticker, self._handle_realtime_quote)
                        logger.info(f"Subscribed {ticker} to realtime source {name}")
                    except Exception as e:
                        logger.warning(f"Failed to subscribe {ticker} to {name}: {e}")

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
        # En mode scalping (interval=0), utiliser un intervalle minimum pour eviter surcharge
        # Le temps reel est gere par les WebSocket sources, pas par le polling
        effective_interval = max(interval, 2.0) if interval == 0 else interval

        while self._running:
            try:
                await self._poll_tickers(priority_only=priority)
            except Exception as e:
                logger.exception(f"Error in polling loop: {e}")

            await asyncio.sleep(effective_interval)

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
            "trading_mode": self._trading_mode.value,
            "trading_mode_name": self._mode_config.display_name,
            "use_websocket": self._mode_config.use_websocket,
            "sources": list(self._sources.keys()),
            "realtime_sources": list(self._realtime_sources.keys()),
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
