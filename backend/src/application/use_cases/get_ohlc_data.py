"""
Use case pour recuperer les donnees OHLC pour les graphiques TradingView.

Retourne les donnees au format attendu par lightweight-charts.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

from src.application.interfaces.stock_data_provider import StockDataProvider
from src.domain.value_objects.ticker import Ticker
from src.domain.entities.stock import OHLCDataPoint

logger = logging.getLogger(__name__)


class GetOHLCDataUseCase:
    """
    Use case pour recuperer les donnees OHLC.

    Retourne les donnees formatees pour TradingView lightweight-charts.
    """

    def __init__(self, provider: StockDataProvider):
        """
        Args:
            provider: Provider de donnees bousieres
        """
        self._provider = provider

    async def execute(
        self,
        ticker: str,
        days: int = 365,
        interval: str = "1d",
    ) -> Dict[str, Any]:
        """
        Recupere les donnees OHLC pour un ticker.

        Args:
            ticker: Symbole boursier
            days: Nombre de jours d'historique
            interval: Intervalle (1d, 1h, etc.)

        Returns:
            Dict avec:
            - ticker: str
            - candles: List[Dict] (format TradingView)
            - volume: List[Dict] (format TradingView)
        """
        logger.info(f"Fetching OHLC data for {ticker}, {days} days")

        ticker_vo = Ticker(ticker.upper())

        # Recuperer les donnees historiques
        historical_data = await self._provider.get_historical_data(
            ticker=ticker_vo,
            days=days,
            interval=interval,
        )

        if not historical_data:
            return {
                "ticker": ticker.upper(),
                "candles": [],
                "volume": [],
            }

        # Convertir au format TradingView
        candles = []
        volume = []

        for point in historical_data:
            # Timestamp Unix en secondes
            timestamp = int(point.date.timestamp())

            # Donnees candlestick
            candles.append({
                "time": timestamp,
                "open": round(point.open, 2),
                "high": round(point.high, 2),
                "low": round(point.low, 2),
                "close": round(point.close, 2),
            })

            # Donnees volume (couleur basee sur close vs open)
            color = "#26a69a" if point.close >= point.open else "#ef5350"
            volume.append({
                "time": timestamp,
                "value": point.volume,
                "color": color,
            })

        logger.info(f"Returned {len(candles)} candles for {ticker}")

        return {
            "ticker": ticker.upper(),
            "candles": candles,
            "volume": volume,
        }
