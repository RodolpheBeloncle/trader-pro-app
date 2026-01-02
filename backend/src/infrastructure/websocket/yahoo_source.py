"""
Source de prix Yahoo Finance via polling.

Implementation de PriceSource pour Yahoo Finance.
Utilise un polling periodique car Yahoo n'offre pas de WebSocket.

Features:
- Retry automatique avec backoff exponentiel
- Rate limiting intelligent
- Health tracking pour le monitoring
"""

import logging
import asyncio
import time
from typing import Optional, Dict, Set
from datetime import datetime, timedelta

import yfinance as yf

from src.infrastructure.websocket.price_source import (
    PriceSource,
    PriceQuote,
    PriceCallback,
)

logger = logging.getLogger(__name__)

# Rate limiting configuration
MAX_REQUESTS_PER_MINUTE = 30  # Yahoo limite à ~60, on prend une marge
REQUEST_INTERVAL = 60.0 / MAX_REQUESTS_PER_MINUTE  # ~2 secondes entre requêtes
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # secondes
MAX_BACKOFF = 30.0  # secondes


class YahooPriceSource(PriceSource):
    """
    Source de prix via Yahoo Finance polling.

    Features:
    - Polling configurable
    - Cache des derniers prix
    - Batch fetching pour plusieurs tickers
    - Retry automatique avec backoff exponentiel
    - Rate limiting pour éviter les blocages
    - Health tracking
    """

    def __init__(self, poll_interval: float = 10.0):
        """
        Args:
            poll_interval: Intervalle de polling en secondes
        """
        self._poll_interval = poll_interval
        self._subscriptions: Dict[str, Set[PriceCallback]] = {}
        self._last_prices: Dict[str, float] = {}
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

        # Rate limiting
        self._last_request_time: float = 0
        self._request_count: int = 0
        self._rate_limit_reset: float = 0

        # Health tracking
        self._success_count: int = 0
        self._error_count: int = 0
        self._last_error: Optional[str] = None
        self._last_success: Optional[datetime] = None
        self._is_rate_limited: bool = False
        self._rate_limit_until: Optional[datetime] = None

    @property
    def source_name(self) -> str:
        return "yahoo"

    @property
    def is_realtime(self) -> bool:
        return False  # Yahoo est du polling, pas du temps reel

    async def is_available(self) -> bool:
        """Vérifie si Yahoo est disponible (pas rate limited)."""
        # Vérifier si on est en rate limit
        if self._is_rate_limited and self._rate_limit_until:
            if datetime.now() < self._rate_limit_until:
                return False
            # Rate limit expiré
            self._is_rate_limited = False
            self._rate_limit_until = None

        return True

    async def _wait_for_rate_limit(self) -> None:
        """Attend si nécessaire pour respecter le rate limiting."""
        now = time.time()

        # Reset le compteur toutes les minutes
        if now - self._rate_limit_reset > 60:
            self._request_count = 0
            self._rate_limit_reset = now

        # Vérifier si on dépasse la limite
        if self._request_count >= MAX_REQUESTS_PER_MINUTE:
            wait_time = 60 - (now - self._rate_limit_reset)
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._rate_limit_reset = time.time()

        # Attendre l'intervalle minimum entre requêtes
        time_since_last = now - self._last_request_time
        if time_since_last < REQUEST_INTERVAL:
            await asyncio.sleep(REQUEST_INTERVAL - time_since_last)

        self._last_request_time = time.time()
        self._request_count += 1

    async def _fetch_with_retry(self, ticker: str) -> Optional[float]:
        """Fetch avec retry et backoff exponentiel."""
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES):
            try:
                await self._wait_for_rate_limit()

                loop = asyncio.get_event_loop()
                stock = await loop.run_in_executor(None, yf.Ticker, ticker)

                # Essayer fast_info d'abord
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

                if price:
                    self._success_count += 1
                    self._last_success = datetime.now()
                    self._record_success()
                    return float(price)

                return None

            except Exception as e:
                error_str = str(e).lower()
                self._error_count += 1
                self._last_error = str(e)

                # Détecter le rate limiting
                if "rate limit" in error_str or "too many requests" in error_str or "429" in error_str:
                    self._is_rate_limited = True
                    self._rate_limit_until = datetime.now() + timedelta(minutes=1)
                    logger.warning(f"Yahoo rate limited, backing off for 1 minute")
                    self._record_error()
                    return None

                # Retry avec backoff
                if attempt < MAX_RETRIES - 1:
                    logger.debug(f"Retry {attempt + 1}/{MAX_RETRIES} for {ticker} after {backoff}s: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                else:
                    logger.warning(f"Failed to fetch {ticker} after {MAX_RETRIES} attempts: {e}")
                    self._record_error()

        return None

    def _record_success(self) -> None:
        """Enregistre un succès pour le health tracking."""
        try:
            from src.api.routes.sources import record_source_success
            record_source_success(self.source_name)
        except ImportError:
            pass

    def _record_error(self) -> None:
        """Enregistre une erreur pour le health tracking."""
        try:
            from src.api.routes.sources import record_source_error
            record_source_error(self.source_name)
        except ImportError:
            pass

    def get_health_stats(self) -> dict:
        """Retourne les statistiques de santé."""
        total = self._success_count + self._error_count
        success_rate = (self._success_count / total * 100) if total > 0 else 100.0

        return {
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": round(success_rate, 1),
            "last_error": self._last_error,
            "last_success": self._last_success.isoformat() if self._last_success else None,
            "is_rate_limited": self._is_rate_limited,
            "rate_limit_until": self._rate_limit_until.isoformat() if self._rate_limit_until else None,
        }

    async def subscribe(
        self,
        ticker: str,
        callback: PriceCallback
    ) -> bool:
        """S'abonne aux mises a jour de prix."""
        ticker = ticker.upper()

        if ticker not in self._subscriptions:
            self._subscriptions[ticker] = set()

        self._subscriptions[ticker].add(callback)
        logger.debug(f"Subscribed to {ticker} (Yahoo)")

        # Envoyer le prix actuel immediatement
        quote = await self.get_current_price(ticker)
        if quote:
            await callback(quote)

        # Demarrer le polling si pas deja en cours
        if not self._running:
            await self._start_polling()

        return True

    async def unsubscribe(self, ticker: str) -> bool:
        """Se desabonne d'un ticker."""
        ticker = ticker.upper()

        if ticker in self._subscriptions:
            del self._subscriptions[ticker]
            logger.debug(f"Unsubscribed from {ticker} (Yahoo)")

        # Arreter le polling si plus d'abonnements
        if not self._subscriptions and self._running:
            await self._stop_polling()

        return True

    async def get_current_price(self, ticker: str) -> Optional[PriceQuote]:
        """Récupère le prix actuel via yfinance avec retry."""
        # Vérifier la disponibilité
        if not await self.is_available():
            logger.debug(f"Yahoo not available (rate limited), skipping {ticker}")
            return None

        # Utiliser le cache si disponible et récent (moins de 5 secondes)
        cached = self._last_prices.get(ticker)

        # Fetch avec retry
        price = await self._fetch_with_retry(ticker)

        if not price:
            return None

        # Calculer le changement
        previous = self._last_prices.get(ticker)
        change = None
        change_percent = None

        if previous and previous > 0:
            change = price - previous
            change_percent = (change / previous) * 100

        # Mettre à jour le cache
        self._last_prices[ticker] = price

        return PriceQuote(
            ticker=ticker,
            price=round(price, 2),
            change=round(change, 2) if change else None,
            change_percent=round(change_percent, 2) if change_percent else None,
            source=self.source_name,
        )

    async def _start_polling(self) -> None:
        """Demarre le polling."""
        if self._running:
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Yahoo price polling started")

    async def _stop_polling(self) -> None:
        """Arrete le polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("Yahoo price polling stopped")

    async def _poll_loop(self) -> None:
        """Boucle principale de polling."""
        while self._running:
            try:
                await self._poll_all_tickers()
            except Exception as e:
                logger.exception(f"Error in Yahoo polling: {e}")

            await asyncio.sleep(self._poll_interval)

    async def _poll_all_tickers(self) -> None:
        """Poll tous les tickers abonnes."""
        tickers = list(self._subscriptions.keys())
        if not tickers:
            return

        for ticker in tickers:
            try:
                quote = await self.get_current_price(ticker)
                if quote:
                    callbacks = self._subscriptions.get(ticker, set())
                    for callback in callbacks:
                        try:
                            await callback(quote)
                        except Exception as e:
                            logger.warning(f"Error in price callback: {e}")
            except Exception as e:
                logger.warning(f"Error polling {ticker}: {e}")
