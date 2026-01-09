"""
Chargeur de donnees historiques pour le backtesting.

Recupere les donnees OHLCV depuis Yahoo Finance
et les transforme au format attendu par le moteur.
"""

import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import asyncio

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

# Limite du cache pour eviter une consommation memoire excessive
MAX_CACHE_ENTRIES = 50


@dataclass
class OHLCV:
    """
    Donnees OHLCV pour une bougie.

    Attributes:
        date: Date/heure
        open: Prix d'ouverture
        high: Prix le plus haut
        low: Prix le plus bas
        close: Prix de cloture
        volume: Volume
    """
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def typical_price(self) -> float:
        """Prix typique (H+L+C)/3."""
        return (self.high + self.low + self.close) / 3


class BacktestDataLoader:
    """
    Charge les donnees historiques pour le backtesting.

    Features:
    - Cache des donnees avec limite LRU
    - Support multi-timeframe
    - Validation des donnees
    """

    def __init__(self, max_cache_size: int = MAX_CACHE_ENTRIES):
        self._cache: OrderedDict = OrderedDict()
        self._max_cache_size = max_cache_size

    async def load(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> List[OHLCV]:
        """
        Charge les donnees historiques.

        Args:
            ticker: Symbole du ticker
            start_date: Date de debut (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)
            interval: Intervalle (1d, 1h, etc.)

        Returns:
            Liste de donnees OHLCV
        """
        cache_key = f"{ticker}_{start_date}_{end_date}_{interval}"

        if cache_key in self._cache:
            # Deplacer en fin pour comportement LRU
            self._cache.move_to_end(cache_key)
            logger.debug(f"Using cached data for {ticker}")
            return self._cache[cache_key]

        logger.info(f"Loading data for {ticker} from {start_date} to {end_date}")

        try:
            # Telecharger les donnees via yfinance
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    progress=False,
                )
            )

            if df.empty:
                logger.warning(f"No data found for {ticker}")
                return []

            # Convertir en liste d'OHLCV
            data = []
            for index, row in df.iterrows():
                ohlcv = OHLCV(
                    date=index.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                )
                data.append(ohlcv)

            # Mettre en cache avec limite LRU
            self._cache[cache_key] = data
            # Supprimer les anciennes entrees si on depasse la limite
            while len(self._cache) > self._max_cache_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache LRU eviction: {oldest_key}")

            logger.info(f"Loaded {len(data)} bars for {ticker} (cache: {len(self._cache)}/{self._max_cache_size})")
            return data

        except Exception as e:
            logger.exception(f"Error loading data for {ticker}: {e}")
            return []

    def clear_cache(self) -> None:
        """Vide le cache."""
        self._cache.clear()
        logger.debug("Data cache cleared")

    async def load_multiple(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> dict:
        """
        Charge les donnees pour plusieurs tickers.

        Args:
            tickers: Liste des symboles
            start_date: Date de debut
            end_date: Date de fin
            interval: Intervalle

        Returns:
            Dict[ticker, List[OHLCV]]
        """
        result = {}

        for ticker in tickers:
            data = await self.load(ticker, start_date, end_date, interval)
            result[ticker] = data

        return result
