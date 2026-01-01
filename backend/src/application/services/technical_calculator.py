"""
Service de calcul des indicateurs techniques.

Ce module implémente les algorithmes de calcul pour tous les indicateurs
techniques utilisés dans le système d'aide à la décision.

INDICATEURS CALCULÉS:
- RSI (14 périodes)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- SMA/EMA (20, 50, 200 / 12, 26)
- ATR (14 périodes)
- Volume Analysis

UTILISATION:
    calculator = TechnicalCalculator()
    indicators = await calculator.calculate_all(ticker, historical_data)
"""

import logging
from typing import List, Optional
from datetime import datetime

import numpy as np
import pandas as pd

from src.application.interfaces.stock_data_provider import HistoricalDataPoint
from src.domain.entities.technical_analysis import (
    RSIIndicator,
    MACDIndicator,
    BollingerBands,
    MovingAverages,
    VolumeAnalysis,
    TechnicalIndicators,
)

logger = logging.getLogger(__name__)


class TechnicalCalculator:
    """
    Calculateur d'indicateurs techniques.

    Implémente les algorithmes standards de l'analyse technique
    utilisés par les traders professionnels.
    """

    def __init__(self):
        """Initialise le calculateur."""
        pass

    async def calculate_all(
        self,
        ticker: str,
        data: List[HistoricalDataPoint],
    ) -> Optional[TechnicalIndicators]:
        """
        Calcule tous les indicateurs techniques pour un actif.

        Args:
            ticker: Symbole de l'actif
            data: Données historiques (min 200 points recommandés)

        Returns:
            TechnicalIndicators ou None si données insuffisantes
        """
        if len(data) < 50:
            logger.warning(f"Données insuffisantes pour {ticker}: {len(data)} points")
            return None

        try:
            # Convertir en DataFrame pandas
            df = self._to_dataframe(data)

            # Calculer chaque indicateur
            rsi = self._calculate_rsi(df)
            macd = self._calculate_macd(df)
            bollinger = self._calculate_bollinger(df)
            moving_averages = self._calculate_moving_averages(df)
            volume = self._calculate_volume(df)
            atr, atr_percent = self._calculate_atr(df)

            return TechnicalIndicators(
                ticker=ticker,
                rsi=rsi,
                macd=macd,
                bollinger=bollinger,
                moving_averages=moving_averages,
                volume=volume,
                atr=atr,
                atr_percent=atr_percent,
                calculated_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Erreur calcul indicateurs pour {ticker}: {e}")
            return None

    def _to_dataframe(self, data: List[HistoricalDataPoint]) -> pd.DataFrame:
        """Convertit les données historiques en DataFrame pandas."""
        df = pd.DataFrame([
            {
                'date': point.date,
                'open': point.open,
                'high': point.high,
                'low': point.low,
                'close': point.close,
                'volume': point.volume,
            }
            for point in data
        ])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        return df

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> RSIIndicator:
        """
        Calcule le RSI (Relative Strength Index).

        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        delta = df['close'].diff()

        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        # Utilise EMA pour plus de réactivité (méthode Wilder)
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        current_rsi = rsi.iloc[-1]
        if pd.isna(current_rsi):
            current_rsi = 50.0  # Valeur neutre par défaut

        return RSIIndicator(value=float(current_rsi), period=period)

    def _calculate_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> MACDIndicator:
        """
        Calcule le MACD (Moving Average Convergence Divergence).

        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD Line, signal)
        Histogram = MACD Line - Signal Line
        """
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return MACDIndicator(
            macd_line=float(macd_line.iloc[-1]),
            signal_line=float(signal_line.iloc[-1]),
            histogram=float(histogram.iloc[-1]),
            fast_period=fast,
            slow_period=slow,
            signal_period=signal,
        )

    def _calculate_bollinger(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> BollingerBands:
        """
        Calcule les Bandes de Bollinger.

        Middle Band = SMA(period)
        Upper Band = Middle + (std_dev * StdDev)
        Lower Band = Middle - (std_dev * StdDev)
        """
        middle = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()

        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        current_price = float(df['close'].iloc[-1])
        upper_band = float(upper.iloc[-1])
        middle_band = float(middle.iloc[-1])
        lower_band = float(lower.iloc[-1])

        # Bandwidth = (Upper - Lower) / Middle
        bandwidth = (upper_band - lower_band) / middle_band if middle_band != 0 else 0

        # %B = (Price - Lower) / (Upper - Lower)
        band_width = upper_band - lower_band
        percent_b = (current_price - lower_band) / band_width if band_width != 0 else 0.5

        return BollingerBands(
            upper_band=upper_band,
            middle_band=middle_band,
            lower_band=lower_band,
            current_price=current_price,
            bandwidth=bandwidth,
            percent_b=percent_b,
            period=period,
            std_dev=std_dev,
        )

    def _calculate_moving_averages(self, df: pd.DataFrame) -> MovingAverages:
        """
        Calcule les moyennes mobiles simples et exponentielles.
        """
        sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
        sma_50 = df['close'].rolling(window=50).mean().iloc[-1]

        # SMA 200 - utiliser ce qu'on a si moins de 200 jours
        if len(df) >= 200:
            sma_200 = df['close'].rolling(window=200).mean().iloc[-1]
        else:
            sma_200 = df['close'].rolling(window=len(df)).mean().iloc[-1]

        ema_12 = df['close'].ewm(span=12, adjust=False).mean().iloc[-1]
        ema_26 = df['close'].ewm(span=26, adjust=False).mean().iloc[-1]
        current_price = df['close'].iloc[-1]

        return MovingAverages(
            sma_20=float(sma_20) if not pd.isna(sma_20) else float(current_price),
            sma_50=float(sma_50) if not pd.isna(sma_50) else float(current_price),
            sma_200=float(sma_200) if not pd.isna(sma_200) else float(current_price),
            ema_12=float(ema_12),
            ema_26=float(ema_26),
            current_price=float(current_price),
        )

    def _calculate_volume(self, df: pd.DataFrame) -> VolumeAnalysis:
        """
        Analyse le volume et calcule l'OBV trend.
        """
        current_volume = int(df['volume'].iloc[-1])
        avg_volume_20 = float(df['volume'].rolling(window=20).mean().iloc[-1])
        avg_volume_50 = float(df['volume'].rolling(window=50).mean().iloc[-1])

        # Changement de volume en %
        prev_volume = df['volume'].iloc[-2] if len(df) > 1 else current_volume
        volume_change = ((current_volume - prev_volume) / prev_volume * 100) if prev_volume > 0 else 0

        # On-Balance Volume (OBV) trend
        obv = self._calculate_obv(df)
        obv_sma = obv.rolling(window=20).mean()

        if obv.iloc[-1] > obv_sma.iloc[-1]:
            obv_trend = "rising"
        elif obv.iloc[-1] < obv_sma.iloc[-1]:
            obv_trend = "falling"
        else:
            obv_trend = "flat"

        return VolumeAnalysis(
            current_volume=current_volume,
            avg_volume_20=avg_volume_20,
            avg_volume_50=avg_volume_50,
            volume_change_percent=float(volume_change),
            on_balance_volume_trend=obv_trend,
        )

    def _calculate_obv(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcule l'On-Balance Volume (OBV).

        OBV augmente quand le prix monte, diminue quand il baisse.
        """
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])

        return pd.Series(obv, index=df.index)

    def _calculate_atr(
        self,
        df: pd.DataFrame,
        period: int = 14,
    ) -> tuple[float, float]:
        """
        Calcule l'Average True Range (ATR).

        True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        ATR = EMA(True Range, period)

        Returns:
            Tuple (ATR absolu, ATR en % du prix)
        """
        high = df['high']
        low = df['low']
        close = df['close']

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()

        current_atr = float(atr.iloc[-1])
        current_price = float(close.iloc[-1])
        atr_percent = (current_atr / current_price * 100) if current_price > 0 else 0

        return current_atr, atr_percent


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_technical_calculator() -> TechnicalCalculator:
    """Factory function pour créer un calculateur d'indicateurs."""
    return TechnicalCalculator()
