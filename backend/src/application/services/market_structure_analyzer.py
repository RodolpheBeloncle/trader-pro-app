"""
Analyseur de structure de marché professionnel.

Ce module implémente l'analyse de structure utilisée par les traders institutionnels :
- Détection des swing points (HH/HL/LH/LL)
- Identification du régime de marché
- Detection des Fair Value Gaps
- Zones de liquidité
- Order Blocks

MÉTHODOLOGIE :
- Wyckoff (Accumulation/Distribution)
- ICT Concepts (Smart Money)
- Auction Market Theory (Dalton)

UTILISATION :
    analyzer = MarketStructureAnalyzer()
    structure = await analyzer.analyze(ticker, historical_data)
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd

from src.application.interfaces.stock_data_provider import HistoricalDataPoint
from src.domain.entities.market_structure import (
    MarketRegime,
    SwingType,
    StructureBias,
    LiquidityType,
    SwingPoint,
    FairValueGap,
    LiquidityZone,
    OrderBlock,
    MarketStructureAnalysis,
)

logger = logging.getLogger(__name__)


class MarketStructureAnalyzer:
    """
    Analyseur de structure de marché professionnel.

    Détecte les patterns de structure utilisés par les traders
    institutionnels pour identifier les zones de trading optimales.
    """

    def __init__(self, swing_strength: int = 3):
        """
        Initialise l'analyseur.

        Args:
            swing_strength: Nombre de bougies de chaque côté pour confirmer un swing
        """
        self.swing_strength = swing_strength

    async def analyze(
        self,
        ticker: str,
        data: List[HistoricalDataPoint],
    ) -> Optional[MarketStructureAnalysis]:
        """
        Analyse complète de la structure de marché.

        Args:
            ticker: Symbole de l'actif
            data: Données historiques (minimum 100 points recommandés)

        Returns:
            Analyse de structure complète ou None si données insuffisantes
        """
        if len(data) < 50:
            logger.warning(f"Données insuffisantes pour {ticker}: {len(data)} points")
            return None

        try:
            df = self._to_dataframe(data)

            # 1. Calculer ATR pour le contexte de volatilité
            atr = self._calculate_atr(df)

            # 2. Détecter les swing points
            swing_points = self._detect_swing_points(df)

            # 3. Identifier la structure (HH/HL/LH/LL)
            structure_bias, last_high, last_low = self._identify_structure(swing_points)

            # 4. Détecter BOS et CHoCH
            bos_level, bos_direction = self._detect_bos(swing_points, df['close'].iloc[-1])
            choch_detected, choch_level = self._detect_choch(swing_points, df['close'].iloc[-1])

            # 5. Identifier le régime de marché
            regime, regime_confidence = self._identify_regime(df, swing_points, atr)

            # 6. Détecter les Fair Value Gaps
            fvgs = self._detect_fair_value_gaps(df)
            unfilled_fvgs = [fvg for fvg in fvgs if not fvg.filled]

            # 7. Identifier les zones de liquidité
            liquidity_zones = self._identify_liquidity_zones(swing_points, df['close'].iloc[-1])

            # 8. Détecter les Order Blocks
            order_blocks = self._detect_order_blocks(df)

            # 9. Trouver les niveaux les plus proches
            current_price = df['close'].iloc[-1]
            nearest_buy_liq = self._find_nearest_level(
                [lz.price_level for lz in liquidity_zones if lz.zone_type == LiquidityType.BUY_SIDE],
                current_price,
                above=True
            )
            nearest_sell_liq = self._find_nearest_level(
                [lz.price_level for lz in liquidity_zones if lz.zone_type == LiquidityType.SELL_SIDE],
                current_price,
                above=False
            )

            # 10. Order Blocks les plus proches
            bullish_obs = [ob for ob in order_blocks if ob.is_bullish and not ob.is_mitigated]
            bearish_obs = [ob for ob in order_blocks if not ob.is_bullish and not ob.is_mitigated]

            nearest_bullish_ob = min(bullish_obs, key=lambda x: x.high, default=None) if bullish_obs else None
            nearest_bearish_ob = max(bearish_obs, key=lambda x: x.low, default=None) if bearish_obs else None

            return MarketStructureAnalysis(
                ticker=ticker,
                regime=regime,
                regime_confidence=regime_confidence,
                structure_bias=structure_bias,
                swing_points=swing_points,
                last_swing_high=last_high,
                last_swing_low=last_low,
                bos_level=bos_level,
                bos_direction=bos_direction,
                choch_detected=choch_detected,
                choch_level=choch_level,
                liquidity_zones=liquidity_zones,
                nearest_buy_side_liquidity=nearest_buy_liq,
                nearest_sell_side_liquidity=nearest_sell_liq,
                fair_value_gaps=fvgs,
                unfilled_fvg_count=len(unfilled_fvgs),
                order_blocks=order_blocks,
                nearest_bullish_ob=nearest_bullish_ob,
                nearest_bearish_ob=nearest_bearish_ob,
                current_price=current_price,
                atr=atr,
            )

        except Exception as e:
            logger.error(f"Erreur analyse structure pour {ticker}: {e}")
            return None

    def _to_dataframe(self, data: List[HistoricalDataPoint]) -> pd.DataFrame:
        """Convertit les données en DataFrame."""
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

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcule l'Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0

    def _detect_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Détecte les swing points (pivots hauts et bas).

        Un swing high est confirmé quand il y a N bougies plus basses de chaque côté.
        Un swing low est confirmé quand il y a N bougies plus hautes de chaque côté.
        """
        swing_points = []
        strength = self.swing_strength

        highs = df['high'].values
        lows = df['low'].values
        dates = df.index.tolist()

        # Détecter les swing highs
        for i in range(strength, len(df) - strength):
            is_swing_high = True
            for j in range(1, strength + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_points.append(SwingPoint(
                    date=dates[i],
                    price=float(highs[i]),
                    swing_type=SwingType.HIGHER_HIGH,  # Sera ajusté après
                    strength=strength,
                ))

        # Détecter les swing lows
        for i in range(strength, len(df) - strength):
            is_swing_low = True
            for j in range(1, strength + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_points.append(SwingPoint(
                    date=dates[i],
                    price=float(lows[i]),
                    swing_type=SwingType.LOWER_LOW,  # Sera ajusté après
                    strength=strength,
                ))

        # Trier par date
        swing_points.sort(key=lambda x: x.date)

        # Classifier les swings (HH/HL/LH/LL)
        swing_points = self._classify_swings(swing_points)

        return swing_points

    def _classify_swings(self, swings: List[SwingPoint]) -> List[SwingPoint]:
        """
        Classifie les swings en HH/HL/LH/LL.

        Logique :
        - Si le high actuel > high précédent = HH (Higher High)
        - Si le high actuel < high précédent = LH (Lower High)
        - Si le low actuel > low précédent = HL (Higher Low)
        - Si le low actuel < low précédent = LL (Lower Low)
        """
        if len(swings) < 2:
            return swings

        # Séparer highs et lows
        highs = [s for s in swings if s.swing_type in [SwingType.HIGHER_HIGH, SwingType.LOWER_HIGH, SwingType.EQUAL_HIGH]]
        lows = [s for s in swings if s.swing_type in [SwingType.LOWER_LOW, SwingType.HIGHER_LOW, SwingType.EQUAL_LOW]]

        # Si on n'a que des swings non classifiés, les séparer par prix
        if not highs and not lows:
            # Tous les swings sont temporairement marqués, on doit les re-classifier
            sorted_swings = sorted(swings, key=lambda x: x.date)

            # Identifier alternativement high/low
            last_high = None
            last_low = None

            for i, swing in enumerate(sorted_swings):
                # Déterminer si c'est un high ou low basé sur le contexte
                if i == 0:
                    # Premier swing - garder tel quel
                    continue

                prev_swing = sorted_swings[i - 1]

                # Si le swing actuel est plus haut que le précédent
                if swing.price > prev_swing.price:
                    # C'est probablement un high
                    if last_high is not None:
                        if swing.price > last_high.price:
                            swing.swing_type = SwingType.HIGHER_HIGH
                        elif swing.price < last_high.price:
                            swing.swing_type = SwingType.LOWER_HIGH
                        else:
                            swing.swing_type = SwingType.EQUAL_HIGH
                    last_high = swing
                else:
                    # C'est probablement un low
                    if last_low is not None:
                        if swing.price > last_low.price:
                            swing.swing_type = SwingType.HIGHER_LOW
                        elif swing.price < last_low.price:
                            swing.swing_type = SwingType.LOWER_LOW
                        else:
                            swing.swing_type = SwingType.EQUAL_LOW
                    last_low = swing

        return swings

    def _identify_structure(
        self,
        swings: List[SwingPoint]
    ) -> Tuple[StructureBias, Optional[SwingPoint], Optional[SwingPoint]]:
        """
        Identifie le biais de structure basé sur les swing points.

        Structure haussière : HH + HL
        Structure baissière : LH + LL
        """
        if len(swings) < 4:
            return StructureBias.NEUTRAL, None, None

        # Prendre les 10 derniers swings
        recent_swings = swings[-10:]

        # Séparer highs et lows
        highs = [s for s in recent_swings if "H" in s.swing_type.value and "L" not in s.swing_type.value[-1:]]
        lows = [s for s in recent_swings if "L" in s.swing_type.value[-1:]]

        if not highs or not lows:
            return StructureBias.NEUTRAL, None, None

        last_high = highs[-1] if highs else None
        last_low = lows[-1] if lows else None

        # Compter les HH/HL vs LH/LL
        hh_count = sum(1 for s in recent_swings if s.swing_type == SwingType.HIGHER_HIGH)
        hl_count = sum(1 for s in recent_swings if s.swing_type == SwingType.HIGHER_LOW)
        lh_count = sum(1 for s in recent_swings if s.swing_type == SwingType.LOWER_HIGH)
        ll_count = sum(1 for s in recent_swings if s.swing_type == SwingType.LOWER_LOW)

        bullish_score = hh_count + hl_count
        bearish_score = lh_count + ll_count

        if bullish_score > bearish_score + 2:
            if lh_count > 0 or ll_count > 0:
                return StructureBias.BULLISH_WEAKENING, last_high, last_low
            return StructureBias.BULLISH, last_high, last_low
        elif bearish_score > bullish_score + 2:
            if hh_count > 0 or hl_count > 0:
                return StructureBias.BEARISH_WEAKENING, last_high, last_low
            return StructureBias.BEARISH, last_high, last_low

        return StructureBias.NEUTRAL, last_high, last_low

    def _detect_bos(
        self,
        swings: List[SwingPoint],
        current_price: float
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Détecte un Break of Structure (BOS).

        BOS haussier : Prix casse au-dessus du dernier swing high
        BOS baissier : Prix casse en-dessous du dernier swing low
        """
        if len(swings) < 2:
            return None, None

        # Trouver le dernier swing high et low significatifs
        recent_highs = [s for s in swings[-10:] if "H" in s.swing_type.value and "L" not in s.swing_type.value[-1:]]
        recent_lows = [s for s in swings[-10:] if "L" in s.swing_type.value[-1:]]

        if recent_highs and current_price > recent_highs[-1].price:
            return recent_highs[-1].price, "bullish"
        elif recent_lows and current_price < recent_lows[-1].price:
            return recent_lows[-1].price, "bearish"

        return None, None

    def _detect_choch(
        self,
        swings: List[SwingPoint],
        current_price: float
    ) -> Tuple[bool, Optional[float]]:
        """
        Détecte un Change of Character (CHoCH).

        CHoCH = Cassure de structure dans la direction opposée à la tendance.
        C'est le premier signe d'un potentiel retournement.
        """
        if len(swings) < 4:
            return False, None

        # Identifier la structure dominante
        structure, _, _ = self._identify_structure(swings)

        if structure == StructureBias.BULLISH:
            # En tendance haussière, CHoCH = cassure du dernier HL
            recent_lows = [s for s in swings[-6:] if s.swing_type == SwingType.HIGHER_LOW]
            if recent_lows and current_price < recent_lows[-1].price:
                return True, recent_lows[-1].price

        elif structure == StructureBias.BEARISH:
            # En tendance baissière, CHoCH = cassure du dernier LH
            recent_highs = [s for s in swings[-6:] if s.swing_type == SwingType.LOWER_HIGH]
            if recent_highs and current_price > recent_highs[-1].price:
                return True, recent_highs[-1].price

        return False, None

    def _identify_regime(
        self,
        df: pd.DataFrame,
        swings: List[SwingPoint],
        atr: float
    ) -> Tuple[MarketRegime, float]:
        """
        Identifie le régime de marché actuel.

        Utilise :
        - Structure (swing points)
        - Volatilité (ATR)
        - Direction des moyennes mobiles
        """
        if len(df) < 50:
            return MarketRegime.TRANSITIONAL, 50.0

        # Calculer les indicateurs de tendance
        close = df['close']
        sma_20 = close.rolling(20).mean()
        sma_50 = close.rolling(50).mean()

        current_price = close.iloc[-1]
        current_sma20 = sma_20.iloc[-1]
        current_sma50 = sma_50.iloc[-1]

        # Volatilité relative
        avg_atr = df['high'].sub(df['low']).rolling(50).mean().iloc[-1]
        volatility_ratio = atr / avg_atr if avg_atr > 0 else 1

        # Identifier la structure
        structure, _, _ = self._identify_structure(swings)

        confidence = 50.0

        # Régime de volatilité extrême
        if volatility_ratio > 1.5:
            return MarketRegime.HIGH_VOLATILITY, 80.0
        elif volatility_ratio < 0.5:
            return MarketRegime.LOW_VOLATILITY, 70.0

        # Tendance haussière
        if (structure == StructureBias.BULLISH and
            current_price > current_sma20 > current_sma50):
            confidence = 85.0
            return MarketRegime.TRENDING_UP, confidence

        # Tendance baissière
        if (structure == StructureBias.BEARISH and
            current_price < current_sma20 < current_sma50):
            confidence = 85.0
            return MarketRegime.TRENDING_DOWN, confidence

        # Range (moyennes plates, structure neutre)
        sma_20_slope = (sma_20.iloc[-1] - sma_20.iloc[-10]) / sma_20.iloc[-10] if sma_20.iloc[-10] != 0 else 0
        if abs(sma_20_slope) < 0.02 and structure == StructureBias.NEUTRAL:
            confidence = 70.0
            return MarketRegime.RANGING, confidence

        # Transitionnel (structure s'affaiblit)
        if structure in [StructureBias.BULLISH_WEAKENING, StructureBias.BEARISH_WEAKENING]:
            confidence = 60.0
            return MarketRegime.TRANSITIONAL, confidence

        return MarketRegime.TRANSITIONAL, 50.0

    def _detect_fair_value_gaps(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        Détecte les Fair Value Gaps (imbalances).

        FVG = Zone où le prix a bougé trop vite, laissant un gap
        entre le high de la bougie 1 et le low de la bougie 3.
        """
        fvgs = []
        current_price = df['close'].iloc[-1]

        for i in range(2, len(df)):
            # FVG Haussier : Low[i] > High[i-2]
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_top = df['low'].iloc[i]
                gap_bottom = df['high'].iloc[i-2]

                # Vérifier si le gap a été comblé
                filled = current_price <= gap_top
                fill_pct = 0
                if filled:
                    fill_pct = min(100, ((gap_top - current_price) / (gap_top - gap_bottom)) * 100)

                fvgs.append(FairValueGap(
                    start_date=df.index[i-2],
                    end_date=df.index[i],
                    top=gap_top,
                    bottom=gap_bottom,
                    is_bullish=True,
                    filled=filled,
                    fill_percentage=fill_pct,
                ))

            # FVG Baissier : High[i] < Low[i-2]
            if df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_top = df['low'].iloc[i-2]
                gap_bottom = df['high'].iloc[i]

                # Vérifier si le gap a été comblé
                filled = current_price >= gap_bottom
                fill_pct = 0
                if filled:
                    fill_pct = min(100, ((current_price - gap_bottom) / (gap_top - gap_bottom)) * 100)

                fvgs.append(FairValueGap(
                    start_date=df.index[i-2],
                    end_date=df.index[i],
                    top=gap_top,
                    bottom=gap_bottom,
                    is_bullish=False,
                    filled=filled,
                    fill_percentage=fill_pct,
                ))

        # Garder les 20 derniers FVGs
        return fvgs[-20:]

    def _identify_liquidity_zones(
        self,
        swings: List[SwingPoint],
        current_price: float
    ) -> List[LiquidityZone]:
        """
        Identifie les zones de liquidité (où se trouvent les stops).

        Les stops sont typiquement :
        - Au-dessus des swing highs (buy-side liquidity)
        - En-dessous des swing lows (sell-side liquidity)
        """
        zones = []

        # Grouper les swings proches (equal highs/lows)
        highs = [s for s in swings if "H" in s.swing_type.value and "L" not in s.swing_type.value[-1:]]
        lows = [s for s in swings if "L" in s.swing_type.value[-1:]]

        # Buy-side liquidity (au-dessus des highs)
        for swing in highs:
            zones.append(LiquidityZone(
                price_level=swing.price,
                zone_type=LiquidityType.BUY_SIDE,
                strength=swing.strength,
                last_test=swing.date,
                created_at=swing.date,
                is_swept=current_price > swing.price,
            ))

        # Sell-side liquidity (en-dessous des lows)
        for swing in lows:
            zones.append(LiquidityZone(
                price_level=swing.price,
                zone_type=LiquidityType.SELL_SIDE,
                strength=swing.strength,
                last_test=swing.date,
                created_at=swing.date,
                is_swept=current_price < swing.price,
            ))

        # Détecter les equal highs/lows (liquidité concentrée)
        self._detect_equal_levels(highs, zones, LiquidityType.EQUAL_HIGHS)
        self._detect_equal_levels(lows, zones, LiquidityType.EQUAL_LOWS)

        return zones

    def _detect_equal_levels(
        self,
        swings: List[SwingPoint],
        zones: List[LiquidityZone],
        zone_type: LiquidityType
    ):
        """Détecte les niveaux égaux (double top/bottom)."""
        tolerance = 0.005  # 0.5% de tolérance

        for i, s1 in enumerate(swings):
            for s2 in swings[i+1:]:
                diff = abs(s1.price - s2.price) / s1.price
                if diff <= tolerance:
                    # Double niveau trouvé
                    avg_price = (s1.price + s2.price) / 2
                    zones.append(LiquidityZone(
                        price_level=avg_price,
                        zone_type=zone_type,
                        strength=s1.strength + s2.strength,
                        last_test=max(s1.date, s2.date),
                        created_at=min(s1.date, s2.date),
                    ))

    def _detect_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """
        Détecte les Order Blocks.

        Order Block = Dernière bougie opposée avant un mouvement impulsif.
        """
        order_blocks = []
        current_price = df['close'].iloc[-1]

        # Seuil pour mouvement impulsif (2x ATR)
        atr = self._calculate_atr(df)
        impulse_threshold = atr * 2

        for i in range(2, len(df) - 1):
            # Mouvement impulsif haussier
            move_up = df['close'].iloc[i+1] - df['close'].iloc[i-1]
            if move_up > impulse_threshold:
                # Chercher la dernière bougie baissière avant le mouvement
                for j in range(i, max(0, i-5), -1):
                    if df['close'].iloc[j] < df['open'].iloc[j]:  # Bougie baissière
                        ob = OrderBlock(
                            date=df.index[j],
                            high=df['high'].iloc[j],
                            low=df['low'].iloc[j],
                            is_bullish=True,
                            is_mitigated=current_price < df['low'].iloc[j],
                        )
                        order_blocks.append(ob)
                        break

            # Mouvement impulsif baissier
            move_down = df['close'].iloc[i-1] - df['close'].iloc[i+1]
            if move_down > impulse_threshold:
                # Chercher la dernière bougie haussière avant le mouvement
                for j in range(i, max(0, i-5), -1):
                    if df['close'].iloc[j] > df['open'].iloc[j]:  # Bougie haussière
                        ob = OrderBlock(
                            date=df.index[j],
                            high=df['high'].iloc[j],
                            low=df['low'].iloc[j],
                            is_bullish=False,
                            is_mitigated=current_price > df['high'].iloc[j],
                        )
                        order_blocks.append(ob)
                        break

        # Garder les 10 derniers
        return order_blocks[-10:]

    def _find_nearest_level(
        self,
        levels: List[float],
        current_price: float,
        above: bool = True
    ) -> Optional[float]:
        """Trouve le niveau le plus proche au-dessus ou en-dessous du prix."""
        if not levels:
            return None

        if above:
            above_levels = [l for l in levels if l > current_price]
            return min(above_levels) if above_levels else None
        else:
            below_levels = [l for l in levels if l < current_price]
            return max(below_levels) if below_levels else None


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_market_structure_analyzer(swing_strength: int = 3) -> MarketStructureAnalyzer:
    """Factory function pour créer l'analyseur de structure."""
    return MarketStructureAnalyzer(swing_strength=swing_strength)
