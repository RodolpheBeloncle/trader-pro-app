"""
Entités pour l'analyse technique avancée.

Ce module contient les structures de données pour les indicateurs techniques
et les signaux de trading utilisés par le système d'aide à la décision.

ARCHITECTURE:
- Couche DOMAINE
- Contient les règles métier pour l'interprétation des indicateurs
- Indépendant de l'infrastructure

INDICATEURS SUPPORTÉS:
- RSI (Relative Strength Index) : Momentum
- MACD (Moving Average Convergence Divergence) : Tendance + Momentum
- Bollinger Bands : Volatilité + Support/Résistance
- SMA/EMA (Moving Averages) : Tendance
- ATR (Average True Range) : Volatilité
- Volume Analysis : Confirmation de tendance
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal


class Signal(str, Enum):
    """Signaux de trading générés par les indicateurs."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class Trend(str, Enum):
    """Direction de la tendance."""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    SIDEWAYS = "sideways"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class TimeHorizon(str, Enum):
    """Horizon d'investissement."""
    SHORT_TERM = "short_term"      # 1-6 mois
    MEDIUM_TERM = "medium_term"    # 6 mois - 2 ans
    LONG_TERM = "long_term"        # 2-5+ ans


@dataclass
class RSIIndicator:
    """
    Relative Strength Index (RSI).

    Mesure la vitesse et le changement des mouvements de prix.
    Valeurs: 0-100
    - RSI > 70: Suracheté (potentiel de baisse)
    - RSI < 30: Survendu (potentiel de hausse)
    - RSI 40-60: Zone neutre
    """
    value: float
    period: int = 14

    @property
    def signal(self) -> Signal:
        """Génère un signal basé sur le RSI."""
        if self.value >= 80:
            return Signal.STRONG_SELL
        elif self.value >= 70:
            return Signal.SELL
        elif self.value <= 20:
            return Signal.STRONG_BUY
        elif self.value <= 30:
            return Signal.BUY
        return Signal.NEUTRAL

    @property
    def interpretation(self) -> str:
        """Interprétation textuelle du RSI."""
        if self.value >= 70:
            return "Suracheté - Risque de correction"
        elif self.value <= 30:
            return "Survendu - Opportunité d'achat potentielle"
        elif self.value > 50:
            return "Momentum haussier"
        elif self.value < 50:
            return "Momentum baissier"
        return "Neutre"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": round(self.value, 2),
            "period": self.period,
            "signal": self.signal.value,
            "interpretation": self.interpretation,
        }


@dataclass
class MACDIndicator:
    """
    Moving Average Convergence Divergence (MACD).

    Suit la tendance et montre la relation entre deux moyennes mobiles.
    - MACD Line: EMA(12) - EMA(26)
    - Signal Line: EMA(9) du MACD
    - Histogram: MACD - Signal
    """
    macd_line: float
    signal_line: float
    histogram: float
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9

    @property
    def signal(self) -> Signal:
        """Génère un signal basé sur le MACD."""
        # Croisement haussier fort
        if self.histogram > 0 and self.macd_line > 0:
            return Signal.STRONG_BUY if self.histogram > abs(self.signal_line) * 0.1 else Signal.BUY
        # Croisement baissier fort
        elif self.histogram < 0 and self.macd_line < 0:
            return Signal.STRONG_SELL if abs(self.histogram) > abs(self.signal_line) * 0.1 else Signal.SELL
        # Croisement en cours
        elif self.histogram > 0:
            return Signal.BUY
        elif self.histogram < 0:
            return Signal.SELL
        return Signal.NEUTRAL

    @property
    def trend(self) -> Trend:
        """Détermine la tendance basée sur le MACD."""
        if self.macd_line > 0 and self.histogram > 0:
            return Trend.STRONG_UPTREND
        elif self.macd_line > 0:
            return Trend.UPTREND
        elif self.macd_line < 0 and self.histogram < 0:
            return Trend.STRONG_DOWNTREND
        elif self.macd_line < 0:
            return Trend.DOWNTREND
        return Trend.SIDEWAYS

    @property
    def interpretation(self) -> str:
        """Interprétation textuelle du MACD."""
        if self.histogram > 0 and self.macd_line > 0:
            return "Tendance haussière confirmée - Momentum positif"
        elif self.histogram > 0 and self.macd_line < 0:
            return "Retournement haussier potentiel en cours"
        elif self.histogram < 0 and self.macd_line > 0:
            return "Essoufflement de la hausse - Prudence"
        elif self.histogram < 0 and self.macd_line < 0:
            return "Tendance baissière confirmée"
        return "Marché indécis"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "macd_line": round(self.macd_line, 4),
            "signal_line": round(self.signal_line, 4),
            "histogram": round(self.histogram, 4),
            "signal": self.signal.value,
            "trend": self.trend.value,
            "interpretation": self.interpretation,
        }


@dataclass
class BollingerBands:
    """
    Bandes de Bollinger.

    Mesurent la volatilité et identifient les niveaux de support/résistance.
    - Upper Band: SMA + (2 * std)
    - Middle Band: SMA(20)
    - Lower Band: SMA - (2 * std)
    """
    upper_band: float
    middle_band: float
    lower_band: float
    current_price: float
    bandwidth: float  # (upper - lower) / middle
    percent_b: float  # (price - lower) / (upper - lower)
    period: int = 20
    std_dev: float = 2.0

    @property
    def signal(self) -> Signal:
        """Génère un signal basé sur la position dans les bandes."""
        if self.percent_b >= 1.0:
            return Signal.STRONG_SELL  # Au-dessus de la bande supérieure
        elif self.percent_b >= 0.8:
            return Signal.SELL  # Proche de la bande supérieure
        elif self.percent_b <= 0.0:
            return Signal.STRONG_BUY  # En-dessous de la bande inférieure
        elif self.percent_b <= 0.2:
            return Signal.BUY  # Proche de la bande inférieure
        return Signal.NEUTRAL

    @property
    def volatility_state(self) -> str:
        """État de la volatilité basé sur le bandwidth."""
        if self.bandwidth > 0.2:
            return "Haute volatilité - Marché nerveux"
        elif self.bandwidth < 0.05:
            return "Basse volatilité - Squeeze potentiel (explosion à venir)"
        return "Volatilité normale"

    @property
    def interpretation(self) -> str:
        """Interprétation de la position dans les bandes."""
        if self.percent_b >= 1.0:
            return "Prix au-dessus des bandes - Suracheté extrême"
        elif self.percent_b >= 0.8:
            return "Prix proche de la bande supérieure - Résistance"
        elif self.percent_b <= 0.0:
            return "Prix sous les bandes - Survendu extrême"
        elif self.percent_b <= 0.2:
            return "Prix proche de la bande inférieure - Support"
        elif 0.4 <= self.percent_b <= 0.6:
            return "Prix autour de la moyenne - Zone d'équilibre"
        return "Prix en zone normale"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "upper_band": round(self.upper_band, 2),
            "middle_band": round(self.middle_band, 2),
            "lower_band": round(self.lower_band, 2),
            "current_price": round(self.current_price, 2),
            "bandwidth": round(self.bandwidth, 4),
            "percent_b": round(self.percent_b, 4),
            "signal": self.signal.value,
            "volatility_state": self.volatility_state,
            "interpretation": self.interpretation,
        }


@dataclass
class MovingAverages:
    """
    Moyennes mobiles multiples pour analyse de tendance.

    Utilisé pour identifier la tendance et les points d'entrée/sortie.
    """
    sma_20: float   # Court terme
    sma_50: float   # Moyen terme
    sma_200: float  # Long terme
    ema_12: float   # Court terme réactif
    ema_26: float   # Moyen terme réactif
    current_price: float

    @property
    def trend(self) -> Trend:
        """Détermine la tendance globale."""
        above_sma_20 = self.current_price > self.sma_20
        above_sma_50 = self.current_price > self.sma_50
        above_sma_200 = self.current_price > self.sma_200

        # Golden Cross / Death Cross
        golden_cross = self.sma_50 > self.sma_200

        if above_sma_20 and above_sma_50 and above_sma_200 and golden_cross:
            return Trend.STRONG_UPTREND
        elif above_sma_50 and above_sma_200:
            return Trend.UPTREND
        elif not above_sma_20 and not above_sma_50 and not above_sma_200 and not golden_cross:
            return Trend.STRONG_DOWNTREND
        elif not above_sma_50 and not above_sma_200:
            return Trend.DOWNTREND
        return Trend.SIDEWAYS

    @property
    def signal(self) -> Signal:
        """Génère un signal basé sur les moyennes mobiles."""
        trend = self.trend
        if trend == Trend.STRONG_UPTREND:
            return Signal.STRONG_BUY
        elif trend == Trend.UPTREND:
            return Signal.BUY
        elif trend == Trend.STRONG_DOWNTREND:
            return Signal.STRONG_SELL
        elif trend == Trend.DOWNTREND:
            return Signal.SELL
        return Signal.NEUTRAL

    @property
    def support_levels(self) -> List[float]:
        """Niveaux de support basés sur les MAs."""
        levels = []
        if self.current_price > self.sma_20:
            levels.append(self.sma_20)
        if self.current_price > self.sma_50:
            levels.append(self.sma_50)
        if self.current_price > self.sma_200:
            levels.append(self.sma_200)
        return sorted(levels, reverse=True)

    @property
    def resistance_levels(self) -> List[float]:
        """Niveaux de résistance basés sur les MAs."""
        levels = []
        if self.current_price < self.sma_20:
            levels.append(self.sma_20)
        if self.current_price < self.sma_50:
            levels.append(self.sma_50)
        if self.current_price < self.sma_200:
            levels.append(self.sma_200)
        return sorted(levels)

    @property
    def interpretation(self) -> str:
        """Interprétation des moyennes mobiles."""
        trend = self.trend
        if trend == Trend.STRONG_UPTREND:
            return "Toutes les MAs alignées à la hausse - Tendance forte"
        elif trend == Trend.UPTREND:
            return "Tendance haussière établie"
        elif trend == Trend.STRONG_DOWNTREND:
            return "Toutes les MAs alignées à la baisse - Tendance baissière forte"
        elif trend == Trend.DOWNTREND:
            return "Tendance baissière établie"
        return "Marché en consolidation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sma_20": round(self.sma_20, 2),
            "sma_50": round(self.sma_50, 2),
            "sma_200": round(self.sma_200, 2),
            "ema_12": round(self.ema_12, 2),
            "ema_26": round(self.ema_26, 2),
            "current_price": round(self.current_price, 2),
            "trend": self.trend.value,
            "signal": self.signal.value,
            "support_levels": [round(s, 2) for s in self.support_levels],
            "resistance_levels": [round(r, 2) for r in self.resistance_levels],
            "interpretation": self.interpretation,
        }


@dataclass
class VolumeAnalysis:
    """
    Analyse du volume pour confirmation de tendance.
    """
    current_volume: int
    avg_volume_20: float
    avg_volume_50: float
    volume_change_percent: float
    on_balance_volume_trend: str  # "rising", "falling", "flat"

    @property
    def volume_confirmation(self) -> bool:
        """Le volume confirme-t-il le mouvement de prix?"""
        return self.current_volume > self.avg_volume_20

    @property
    def interpretation(self) -> str:
        """Interprétation du volume."""
        ratio = self.current_volume / self.avg_volume_20 if self.avg_volume_20 > 0 else 1
        if ratio > 2:
            return "Volume exceptionnellement élevé - Signal fort"
        elif ratio > 1.5:
            return "Volume élevé - Mouvement significatif"
        elif ratio > 1:
            return "Volume supérieur à la moyenne"
        elif ratio > 0.5:
            return "Volume normal"
        return "Volume faible - Peu de conviction"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_volume": self.current_volume,
            "avg_volume_20": round(self.avg_volume_20, 0),
            "avg_volume_50": round(self.avg_volume_50, 0),
            "volume_change_percent": round(self.volume_change_percent, 2),
            "obv_trend": self.on_balance_volume_trend,
            "volume_confirmation": self.volume_confirmation,
            "interpretation": self.interpretation,
        }


@dataclass
class TechnicalIndicators:
    """
    Agrégation de tous les indicateurs techniques pour un actif.
    """
    ticker: str
    rsi: RSIIndicator
    macd: MACDIndicator
    bollinger: BollingerBands
    moving_averages: MovingAverages
    volume: VolumeAnalysis
    atr: float  # Average True Range (volatilité)
    atr_percent: float  # ATR en % du prix
    calculated_at: datetime = field(default_factory=datetime.now)

    @property
    def overall_signal(self) -> Signal:
        """
        Signal global pondéré basé sur tous les indicateurs.

        Pondération:
        - RSI: 20%
        - MACD: 25%
        - Bollinger: 15%
        - Moving Averages: 30%
        - Volume confirmation: 10%
        """
        signal_scores = {
            Signal.STRONG_BUY: 2,
            Signal.BUY: 1,
            Signal.NEUTRAL: 0,
            Signal.SELL: -1,
            Signal.STRONG_SELL: -2,
        }

        weighted_score = (
            signal_scores[self.rsi.signal] * 0.20 +
            signal_scores[self.macd.signal] * 0.25 +
            signal_scores[self.bollinger.signal] * 0.15 +
            signal_scores[self.moving_averages.signal] * 0.30 +
            (0.5 if self.volume.volume_confirmation else -0.5) * 0.10
        )

        if weighted_score >= 1.2:
            return Signal.STRONG_BUY
        elif weighted_score >= 0.5:
            return Signal.BUY
        elif weighted_score <= -1.2:
            return Signal.STRONG_SELL
        elif weighted_score <= -0.5:
            return Signal.SELL
        return Signal.NEUTRAL

    @property
    def overall_trend(self) -> Trend:
        """Tendance globale basée sur les indicateurs."""
        return self.moving_averages.trend

    @property
    def confidence_level(self) -> str:
        """Niveau de confiance dans le signal."""
        signals = [
            self.rsi.signal,
            self.macd.signal,
            self.bollinger.signal,
            self.moving_averages.signal,
        ]

        # Compte les signaux dans la même direction
        buy_signals = sum(1 for s in signals if s in [Signal.BUY, Signal.STRONG_BUY])
        sell_signals = sum(1 for s in signals if s in [Signal.SELL, Signal.STRONG_SELL])

        if buy_signals >= 3 or sell_signals >= 3:
            return "Haute"
        elif buy_signals >= 2 or sell_signals >= 2:
            return "Moyenne"
        return "Faible"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "rsi": self.rsi.to_dict(),
            "macd": self.macd.to_dict(),
            "bollinger": self.bollinger.to_dict(),
            "moving_averages": self.moving_averages.to_dict(),
            "volume": self.volume.to_dict(),
            "atr": round(self.atr, 2),
            "atr_percent": round(self.atr_percent, 2),
            "overall_signal": self.overall_signal.value,
            "overall_trend": self.overall_trend.value,
            "confidence_level": self.confidence_level,
            "calculated_at": self.calculated_at.isoformat(),
        }
