"""
Entités pour l'analyse de structure de marché professionnelle.

Ce module implémente les concepts utilisés par les traders institutionnels :
- Structure de marché (HH/HL/LH/LL - Swing Points)
- Régime de marché (Tendance / Range / Volatilité)
- Zones de liquidité
- Fair Value Gaps (FVG) / Imbalances
- Points of Interest (POI)

RÉFÉRENCES :
- Wyckoff Method (Accumulation/Distribution)
- James Dalton - Mind Over Markets (Auction Theory)
- Adam Grimes - The Art and Science of Technical Analysis

PRINCIPE FONDAMENTAL :
> Un trader pro ne cherche pas à prédire, il cherche à exploiter
> des asymétries de probabilité dans un contexte donné.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import numpy as np


class MarketRegime(str, Enum):
    """
    Régime de marché actuel.

    Chaque régime nécessite une stratégie différente :
    - TRENDING_UP : Suivre la tendance, acheter les pullbacks
    - TRENDING_DOWN : Suivre la tendance, vendre les rallyes
    - RANGING : Acheter les supports, vendre les résistances
    - HIGH_VOLATILITY : Réduire la taille des positions
    - LOW_VOLATILITY : Attention aux breakouts (squeeze)
    - TRANSITIONAL : Pas de position, observer
    """
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITIONAL = "transitional"


class SwingType(str, Enum):
    """Type de point swing."""
    HIGHER_HIGH = "HH"    # Plus haut plus haut (tendance haussière)
    HIGHER_LOW = "HL"     # Plus bas plus haut (tendance haussière)
    LOWER_HIGH = "LH"     # Plus haut plus bas (tendance baissière)
    LOWER_LOW = "LL"      # Plus bas plus bas (tendance baissière)
    EQUAL_HIGH = "EH"     # Double top potentiel
    EQUAL_LOW = "EL"      # Double bottom potentiel


class StructureBias(str, Enum):
    """Biais de structure de marché."""
    BULLISH = "bullish"           # Structure haussière confirmée
    BEARISH = "bearish"           # Structure baissière confirmée
    NEUTRAL = "neutral"           # Pas de biais clair
    BULLISH_WEAKENING = "bullish_weakening"  # Haussier mais s'affaiblit
    BEARISH_WEAKENING = "bearish_weakening"  # Baissier mais s'affaiblit


class LiquidityType(str, Enum):
    """Type de zone de liquidité."""
    BUY_SIDE = "buy_side"       # Stops des vendeurs (au-dessus des highs)
    SELL_SIDE = "sell_side"     # Stops des acheteurs (en-dessous des lows)
    EQUAL_HIGHS = "equal_highs" # Liquidité concentrée (double top)
    EQUAL_LOWS = "equal_lows"   # Liquidité concentrée (double bottom)


def _datetime_to_str(dt: datetime) -> str:
    """Convertit un datetime ou pandas Timestamp en string ISO."""
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


@dataclass
class SwingPoint:
    """
    Point swing (pivot) dans la structure de marché.

    Les swing points définissent la structure :
    - HH + HL = Tendance haussière
    - LH + LL = Tendance baissière
    """
    date: datetime
    price: float
    swing_type: SwingType
    strength: int = 1  # Nombre de bougies de chaque côté pour confirmer

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": _datetime_to_str(self.date),
            "price": round(self.price, 2),
            "swing_type": self.swing_type.value,
            "strength": self.strength,
        }


@dataclass
class FairValueGap:
    """
    Fair Value Gap (FVG) / Imbalance.

    Zone où le prix a bougé trop vite, créant un déséquilibre
    entre acheteurs et vendeurs. Le prix tend à revenir combler ces gaps.

    FVG Haussier : gap entre le high de la bougie 1 et le low de la bougie 3
    FVG Baissier : gap entre le low de la bougie 1 et le high de la bougie 3
    """
    start_date: datetime
    end_date: datetime
    top: float       # Haut du gap
    bottom: float    # Bas du gap
    is_bullish: bool  # Direction du mouvement qui a créé le gap
    filled: bool = False  # Le gap a-t-il été comblé ?
    fill_percentage: float = 0.0  # Pourcentage de comblement

    @property
    def size(self) -> float:
        """Taille du gap en valeur absolue."""
        return abs(self.top - self.bottom)

    @property
    def midpoint(self) -> float:
        """Point médian du gap (objectif de comblement partiel)."""
        return (self.top + self.bottom) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": _datetime_to_str(self.start_date),
            "end_date": _datetime_to_str(self.end_date),
            "top": round(self.top, 2),
            "bottom": round(self.bottom, 2),
            "midpoint": round(self.midpoint, 2),
            "size": round(self.size, 2),
            "is_bullish": self.is_bullish,
            "filled": self.filled,
            "fill_percentage": round(self.fill_percentage, 1),
        }


@dataclass
class LiquidityZone:
    """
    Zone de liquidité (où se trouvent les stops).

    Les market makers et institutions ciblent ces zones
    pour collecter la liquidité avant de reverser.

    PRINCIPE : "Liquidity is fuel for price movement"
    """
    price_level: float
    zone_type: LiquidityType
    strength: int  # Nombre de fois testée sans break
    last_test: datetime
    created_at: datetime
    is_swept: bool = False  # La zone a-t-elle été balayée ?

    @property
    def age_days(self) -> int:
        """Âge de la zone en jours."""
        # Gérer les timestamps pandas timezone-aware
        now = datetime.now()
        created = self.created_at
        # Convertir en datetime naive si nécessaire
        if hasattr(created, 'tz') and created.tz is not None:
            created = created.tz_localize(None) if hasattr(created, 'tz_localize') else created.replace(tzinfo=None)
        elif hasattr(created, 'tzinfo') and created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        return (now - created).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price_level": round(self.price_level, 2),
            "zone_type": self.zone_type.value,
            "strength": self.strength,
            "age_days": self.age_days,
            "is_swept": self.is_swept,
            "last_test": _datetime_to_str(self.last_test),
        }


@dataclass
class OrderBlock:
    """
    Order Block - Zone où les institutions ont placé des ordres significatifs.

    Généralement la dernière bougie opposée avant un mouvement impulsif.
    - Order Block Haussier : dernière bougie baissière avant impulsion haussière
    - Order Block Baissier : dernière bougie haussière avant impulsion baissière
    """
    date: datetime
    high: float
    low: float
    is_bullish: bool  # Type d'order block
    is_mitigated: bool = False  # A-t-il été revisité ?

    @property
    def midpoint(self) -> float:
        """Point d'entrée optimal (milieu du block)."""
        return (self.high + self.low) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": _datetime_to_str(self.date),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "midpoint": round(self.midpoint, 2),
            "is_bullish": self.is_bullish,
            "is_mitigated": self.is_mitigated,
        }


@dataclass
class MarketStructureAnalysis:
    """
    Analyse complète de la structure de marché.

    Combine tous les éléments pour donner un contexte clair
    avant toute décision de trading.
    """
    ticker: str

    # Régime de marché
    regime: MarketRegime
    regime_confidence: float  # 0-100%

    # Structure (swing points)
    structure_bias: StructureBias
    swing_points: List[SwingPoint]
    last_swing_high: Optional[SwingPoint]
    last_swing_low: Optional[SwingPoint]

    # Break of Structure (BOS) - Confirmation de tendance
    bos_level: Optional[float]  # Niveau du dernier BOS
    bos_direction: Optional[str]  # "bullish" ou "bearish"

    # Change of Character (CHoCH) - Potentiel retournement
    choch_detected: bool
    choch_level: Optional[float]

    # Zones de liquidité
    liquidity_zones: List[LiquidityZone]
    nearest_buy_side_liquidity: Optional[float]
    nearest_sell_side_liquidity: Optional[float]

    # Fair Value Gaps
    fair_value_gaps: List[FairValueGap]
    unfilled_fvg_count: int

    # Order Blocks
    order_blocks: List[OrderBlock]
    nearest_bullish_ob: Optional[OrderBlock]
    nearest_bearish_ob: Optional[OrderBlock]

    # Prix actuel et contexte
    current_price: float
    atr: float  # Average True Range pour le contexte de volatilité

    analyzed_at: datetime = field(default_factory=datetime.now)

    @property
    def trading_bias(self) -> str:
        """
        Biais de trading basé sur la structure.

        Un trader pro ne trade QUE dans le sens du biais,
        sauf s'il y a un CHoCH confirmé.
        """
        if self.choch_detected:
            return "CAUTION - Potential reversal detected"

        if self.structure_bias == StructureBias.BULLISH:
            return "LONG ONLY - Buy pullbacks to demand zones"
        elif self.structure_bias == StructureBias.BEARISH:
            return "SHORT ONLY - Sell rallies to supply zones"
        elif self.structure_bias == StructureBias.BULLISH_WEAKENING:
            return "REDUCE LONGS - Watch for CHoCH"
        elif self.structure_bias == StructureBias.BEARISH_WEAKENING:
            return "REDUCE SHORTS - Watch for CHoCH"
        return "NO TRADE - Wait for clear structure"

    @property
    def key_levels(self) -> Dict[str, float]:
        """Niveaux clés pour le trading."""
        levels = {
            "current_price": self.current_price,
        }

        if self.last_swing_high:
            levels["last_swing_high"] = self.last_swing_high.price
        if self.last_swing_low:
            levels["last_swing_low"] = self.last_swing_low.price
        if self.bos_level:
            levels["bos_level"] = self.bos_level
        if self.nearest_buy_side_liquidity:
            levels["buy_side_liquidity"] = self.nearest_buy_side_liquidity
        if self.nearest_sell_side_liquidity:
            levels["sell_side_liquidity"] = self.nearest_sell_side_liquidity

        return levels

    @property
    def context_summary(self) -> str:
        """Résumé du contexte pour le journal de trading."""
        parts = [
            f"Régime: {self.regime.value} (confiance: {self.regime_confidence:.0f}%)",
            f"Structure: {self.structure_bias.value}",
            f"Biais: {self.trading_bias}",
        ]

        if self.choch_detected:
            parts.append(f"⚠️ CHoCH détecté à {self.choch_level}")

        if self.unfilled_fvg_count > 0:
            parts.append(f"FVG non comblés: {self.unfilled_fvg_count}")

        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "regime": self.regime.value,
            "regime_confidence": round(self.regime_confidence, 1),
            "structure_bias": self.structure_bias.value,
            "trading_bias": self.trading_bias,
            "swing_points": [sp.to_dict() for sp in self.swing_points[-10:]],  # 10 derniers
            "last_swing_high": self.last_swing_high.to_dict() if self.last_swing_high else None,
            "last_swing_low": self.last_swing_low.to_dict() if self.last_swing_low else None,
            "bos_level": round(self.bos_level, 2) if self.bos_level else None,
            "bos_direction": self.bos_direction,
            "choch_detected": self.choch_detected,
            "choch_level": round(self.choch_level, 2) if self.choch_level else None,
            "liquidity_zones": [lz.to_dict() for lz in self.liquidity_zones],
            "nearest_buy_side_liquidity": round(self.nearest_buy_side_liquidity, 2) if self.nearest_buy_side_liquidity else None,
            "nearest_sell_side_liquidity": round(self.nearest_sell_side_liquidity, 2) if self.nearest_sell_side_liquidity else None,
            "fair_value_gaps": [fvg.to_dict() for fvg in self.fair_value_gaps if not fvg.filled],
            "unfilled_fvg_count": self.unfilled_fvg_count,
            "order_blocks": [ob.to_dict() for ob in self.order_blocks if not ob.is_mitigated],
            "key_levels": {k: round(v, 2) for k, v in self.key_levels.items()},
            "current_price": round(self.current_price, 2),
            "atr": round(self.atr, 2),
            "context_summary": self.context_summary,
            "analyzed_at": self.analyzed_at.isoformat(),
        }
