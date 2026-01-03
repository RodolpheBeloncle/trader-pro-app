"""
Provider de signaux de régime de marché.

Analyse les indicateurs macro pour déterminer le régime de marché:
- Risk-On: Conditions favorables pour les actifs risqués
- Risk-Off: Conditions défavorables, préférer les actifs défensifs
- Neutral: Signaux mixtes

Basé sur les signaux du repo IncomeShield:
- HYG/LQD ratio (crédit)
- VIX (volatilité)
- SPY trend et drawdown
- Yield curve (10Y-2Y)

ARCHITECTURE:
- Utilise YahooFinance pour les données de marché
- Implémente la logique anti-whipsaw (filtres temporels)
- Fournit des recommandations d'allocation

UTILISATION:
    provider = MarketRegimeProvider()
    regime = await provider.calculate_market_regime()
    print(regime.regime)  # "risk_on", "risk_off", "neutral"
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional
from enum import Enum

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


class RegimeType(str, Enum):
    """Types de régime de marché."""
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    NEUTRAL = "neutral"
    HIGH_UNCERTAINTY = "high_uncertainty"


@dataclass
class MarketSignals:
    """
    Signaux de marché individuels.

    Chaque signal indique une condition de stress ou de calme.
    """
    credit_stress: bool = False
    """HYG/LQD ratio en dessous de sa SMA(50)."""

    vix_elevated: bool = False
    """VIX > 25 ou VIX > SMA(20)."""

    spy_below_sma200: bool = False
    """SPY en dessous de sa SMA(200) - bear market signal."""

    spy_drawdown_alert: bool = False
    """SPY drawdown > -10% depuis le plus haut."""

    yield_curve_inverted: bool = False
    """Courbe des taux inversée (10Y - 2Y < 0)."""

    vix_spike: bool = False
    """VIX > 30 - spike de volatilité."""

    # Valeurs brutes pour affichage
    hyg_lqd_ratio: Optional[float] = None
    hyg_lqd_sma50: Optional[float] = None
    vix_level: Optional[float] = None
    vix_sma20: Optional[float] = None
    spy_price: Optional[float] = None
    spy_sma200: Optional[float] = None
    spy_drawdown: Optional[float] = None
    yield_spread_10y_2y: Optional[float] = None

    @property
    def stress_count(self) -> int:
        """Nombre de signaux de stress actifs."""
        return sum([
            self.credit_stress,
            self.vix_elevated,
            self.spy_below_sma200,
            self.spy_drawdown_alert,
            self.yield_curve_inverted,
        ])

    @property
    def is_high_stress(self) -> bool:
        """3+ signaux de stress = conditions très défavorables."""
        return self.stress_count >= 3

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation JSON."""
        return {
            "credit_stress": self.credit_stress,
            "vix_elevated": self.vix_elevated,
            "spy_below_sma200": self.spy_below_sma200,
            "spy_drawdown_alert": self.spy_drawdown_alert,
            "yield_curve_inverted": self.yield_curve_inverted,
            "vix_spike": self.vix_spike,
            "stress_count": self.stress_count,
            "raw_values": {
                "hyg_lqd_ratio": round(self.hyg_lqd_ratio, 4) if self.hyg_lqd_ratio else None,
                "hyg_lqd_sma50": round(self.hyg_lqd_sma50, 4) if self.hyg_lqd_sma50 else None,
                "vix_level": round(self.vix_level, 2) if self.vix_level else None,
                "vix_sma20": round(self.vix_sma20, 2) if self.vix_sma20 else None,
                "spy_price": round(self.spy_price, 2) if self.spy_price else None,
                "spy_sma200": round(self.spy_sma200, 2) if self.spy_sma200 else None,
                "spy_drawdown": round(self.spy_drawdown * 100, 2) if self.spy_drawdown else None,
                "yield_spread_10y_2y": round(self.yield_spread_10y_2y, 3) if self.yield_spread_10y_2y else None,
            }
        }


@dataclass
class AntiWhipsawState:
    """
    État du filtre anti-whipsaw.

    Évite les faux signaux en demandant une confirmation temporelle:
    - 7 jours pour entrer en risk-off
    - 14 jours pour sortir de risk-off
    """
    days_in_risk_off_signal: int = 0
    days_in_risk_on_signal: int = 0
    current_mode: str = "risk_on"  # Mode confirmé actuel

    # Seuils de confirmation
    ENTRY_CONFIRMATION_DAYS: int = 7
    EXIT_CONFIRMATION_DAYS: int = 14

    @property
    def risk_off_confirmed(self) -> bool:
        """Risk-off confirmé après X jours de signal."""
        return self.days_in_risk_off_signal >= self.ENTRY_CONFIRMATION_DAYS

    @property
    def risk_on_confirmed(self) -> bool:
        """Risk-on confirmé après X jours de signal."""
        return self.days_in_risk_on_signal >= self.EXIT_CONFIRMATION_DAYS

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "days_in_risk_off_signal": self.days_in_risk_off_signal,
            "days_in_risk_on_signal": self.days_in_risk_on_signal,
            "current_mode": self.current_mode,
            "entry_confirmed": self.risk_off_confirmed,
            "exit_confirmed": self.risk_on_confirmed,
            "entry_threshold_days": self.ENTRY_CONFIRMATION_DAYS,
            "exit_threshold_days": self.EXIT_CONFIRMATION_DAYS,
        }


@dataclass
class MarketRegime:
    """
    Régime de marché complet avec recommandations.
    """
    regime: RegimeType
    """Type de régime actuel."""

    signals: MarketSignals
    """Signaux individuels."""

    confidence: float
    """Niveau de confiance (0-100)."""

    recommended_allocation: Dict[str, float]
    """Allocation recommandée par catégorie."""

    anti_whipsaw: AntiWhipsawState = field(default_factory=AntiWhipsawState)
    """État du filtre anti-whipsaw."""

    timestamp: datetime = field(default_factory=datetime.now)
    """Horodatage de l'analyse."""

    interpretation: str = ""
    """Interprétation textuelle du régime."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation JSON."""
        return {
            "regime": self.regime.value,
            "signals": self.signals.to_dict(),
            "confidence": round(self.confidence, 1),
            "recommended_allocation": self.recommended_allocation,
            "anti_whipsaw": self.anti_whipsaw.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "interpretation": self.interpretation,
        }


class MarketRegimeProvider:
    """
    Provider pour l'analyse du régime de marché.

    Analyse les conditions macro pour déterminer si le marché
    est en mode Risk-On ou Risk-Off.

    Utilise les signaux:
    - HYG/LQD: Stress crédit (high yield vs investment grade)
    - VIX: Volatilité implicite
    - SPY: Tendance et drawdown du marché
    - Yield Curve: Spread 10Y-2Y (indicateur de récession)
    """

    # Tickers utilisés pour les signaux
    TICKERS = {
        "hyg": "HYG",      # High Yield Corporate Bonds
        "lqd": "LQD",      # Investment Grade Corporate Bonds
        "vix": "^VIX",     # Volatility Index
        "spy": "SPY",      # S&P 500 ETF
        "tnx": "^TNX",     # 10-Year Treasury Yield
        "irx": "^IRX",     # 13-Week Treasury Bill
        "tyx": "^TYX",     # 30-Year Treasury Yield
    }

    # Seuils pour les signaux
    VIX_ELEVATED_THRESHOLD = 25
    VIX_SPIKE_THRESHOLD = 30
    DRAWDOWN_ALERT_THRESHOLD = -0.10  # -10%

    # Allocations recommandées par régime
    ALLOCATIONS = {
        RegimeType.RISK_ON: {
            "growth": 40,
            "income": 35,
            "defensive": 15,
            "cash": 10,
        },
        RegimeType.NEUTRAL: {
            "growth": 25,
            "income": 30,
            "defensive": 30,
            "cash": 15,
        },
        RegimeType.RISK_OFF: {
            "growth": 10,
            "income": 20,
            "defensive": 40,
            "cash": 30,
        },
        RegimeType.HIGH_UNCERTAINTY: {
            "growth": 5,
            "income": 15,
            "defensive": 30,
            "cash": 50,
        },
    }

    def __init__(self, cache_ttl: int = 300):
        """
        Initialise le provider.

        Args:
            cache_ttl: TTL du cache en secondes
        """
        self._cache_ttl = cache_ttl
        self._whipsaw_state = AntiWhipsawState()

    async def calculate_market_regime(self) -> MarketRegime:
        """
        Calcule le régime de marché actuel.

        Returns:
            MarketRegime avec signaux, régime, et recommandations
        """
        try:
            # Récupérer tous les signaux
            signals = await self._fetch_all_signals()

            # Déterminer le régime
            regime_type = self._determine_regime(signals)

            # Calculer la confiance
            confidence = self._calculate_confidence(signals, regime_type)

            # Obtenir l'allocation recommandée
            allocation = self.ALLOCATIONS[regime_type]

            # Générer l'interprétation
            interpretation = self._generate_interpretation(signals, regime_type)

            regime = MarketRegime(
                regime=regime_type,
                signals=signals,
                confidence=confidence,
                recommended_allocation=allocation,
                anti_whipsaw=self._whipsaw_state,
                interpretation=interpretation,
            )

            logger.info(f"Market regime calculated: {regime_type.value} (confidence: {confidence:.1f}%)")
            return regime

        except Exception as e:
            logger.error(f"Error calculating market regime: {e}")
            # Retourner un régime neutre par défaut en cas d'erreur
            return MarketRegime(
                regime=RegimeType.NEUTRAL,
                signals=MarketSignals(),
                confidence=0,
                recommended_allocation=self.ALLOCATIONS[RegimeType.NEUTRAL],
                interpretation=f"Erreur lors de l'analyse: {str(e)}",
            )

    async def get_hyg_lqd_ratio(self, days: int = 100) -> Dict:
        """
        Calcule le ratio HYG/LQD et sa SMA.

        Le ratio HYG/LQD mesure le spread de crédit:
        - Ratio élevé = conditions de crédit faciles
        - Ratio en baisse = stress sur le crédit

        Args:
            days: Nombre de jours d'historique

        Returns:
            Dict avec ratio actuel, SMA, et signal
        """
        try:
            hyg_data = self._fetch_ticker_data(self.TICKERS["hyg"], days)
            lqd_data = self._fetch_ticker_data(self.TICKERS["lqd"], days)

            if hyg_data.empty or lqd_data.empty:
                return {"error": "Données insuffisantes"}

            # Aligner les dates
            combined = hyg_data.join(lqd_data, lsuffix='_hyg', rsuffix='_lqd', how='inner')

            # Calculer le ratio
            ratio = combined['Close_hyg'] / combined['Close_lqd']
            current_ratio = float(ratio.iloc[-1])
            sma_50 = float(ratio.rolling(window=50).mean().iloc[-1])

            credit_stress = current_ratio < sma_50

            return {
                "current_ratio": current_ratio,
                "sma_50": sma_50,
                "credit_stress": credit_stress,
                "interpretation": "Stress crédit" if credit_stress else "Crédit stable",
            }

        except Exception as e:
            logger.error(f"Error fetching HYG/LQD ratio: {e}")
            return {"error": str(e)}

    async def get_vix_data(self, days: int = 50) -> Dict:
        """
        Récupère les données VIX et analyse la volatilité.

        Args:
            days: Nombre de jours d'historique

        Returns:
            Dict avec niveau VIX, SMA, et signaux
        """
        try:
            vix_data = self._fetch_ticker_data(self.TICKERS["vix"], days)

            if vix_data.empty:
                return {"error": "Données VIX indisponibles"}

            current_vix = float(vix_data['Close'].iloc[-1])
            sma_20 = float(vix_data['Close'].rolling(window=20).mean().iloc[-1])

            vix_elevated = current_vix > self.VIX_ELEVATED_THRESHOLD or current_vix > sma_20
            vix_spike = current_vix > self.VIX_SPIKE_THRESHOLD

            return {
                "current_level": current_vix,
                "sma_20": sma_20,
                "elevated": vix_elevated,
                "spike": vix_spike,
                "interpretation": self._interpret_vix(current_vix),
            }

        except Exception as e:
            logger.error(f"Error fetching VIX data: {e}")
            return {"error": str(e)}

    async def get_spy_trend(self, days: int = 250) -> Dict:
        """
        Analyse la tendance SPY et le drawdown.

        Args:
            days: Nombre de jours d'historique (250 pour SMA200)

        Returns:
            Dict avec prix, SMA200, drawdown, et signaux
        """
        try:
            spy_data = self._fetch_ticker_data(self.TICKERS["spy"], days)

            if spy_data.empty or len(spy_data) < 200:
                return {"error": "Données SPY insuffisantes"}

            current_price = float(spy_data['Close'].iloc[-1])
            sma_200 = float(spy_data['Close'].rolling(window=200).mean().iloc[-1])

            # Calculer le drawdown depuis le plus haut
            rolling_max = spy_data['Close'].cummax()
            drawdown = (spy_data['Close'] / rolling_max - 1).iloc[-1]

            below_sma200 = current_price < sma_200
            drawdown_alert = drawdown < self.DRAWDOWN_ALERT_THRESHOLD

            return {
                "current_price": current_price,
                "sma_200": sma_200,
                "drawdown": float(drawdown),
                "below_sma200": below_sma200,
                "drawdown_alert": drawdown_alert,
                "trend": "Bearish" if below_sma200 else "Bullish",
                "interpretation": self._interpret_spy_trend(current_price, sma_200, drawdown),
            }

        except Exception as e:
            logger.error(f"Error fetching SPY trend: {e}")
            return {"error": str(e)}

    async def get_yield_curve(self) -> Dict:
        """
        Analyse la courbe des taux (10Y - 2Y spread).

        Une courbe inversée (spread négatif) est un signal de récession.

        Returns:
            Dict avec spread et signal d'inversion
        """
        try:
            # Note: Yahoo Finance n'a pas directement le 2Y
            # On utilise le 10Y et le 13-week comme proxy
            tnx_data = self._fetch_ticker_data(self.TICKERS["tnx"], 30)
            irx_data = self._fetch_ticker_data(self.TICKERS["irx"], 30)

            if tnx_data.empty or irx_data.empty:
                return {"error": "Données de taux indisponibles"}

            # TNX est en points (ex: 4.5 = 4.5%), IRX aussi
            yield_10y = float(tnx_data['Close'].iloc[-1])
            yield_3m = float(irx_data['Close'].iloc[-1])

            # Le spread 10Y-3M est aussi un bon indicateur de récession
            spread = yield_10y - yield_3m
            inverted = spread < 0

            return {
                "yield_10y": yield_10y,
                "yield_3m": yield_3m,
                "spread_10y_3m": spread,
                "inverted": inverted,
                "interpretation": "Courbe inversée - Signal de récession" if inverted else "Courbe normale",
            }

        except Exception as e:
            logger.error(f"Error fetching yield curve: {e}")
            return {"error": str(e)}

    # =========================================================================
    # MÉTHODES PRIVÉES
    # =========================================================================

    def _fetch_ticker_data(self, ticker: str, days: int) -> 'pd.DataFrame':
        """Récupère les données d'un ticker via yfinance."""
        try:
            yf_ticker = yf.Ticker(ticker)
            end_date = datetime.today()
            start_date = end_date - timedelta(days=days)
            data = yf_ticker.history(start=start_date, end=end_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            import pandas as pd
            return pd.DataFrame()

    async def _fetch_all_signals(self) -> MarketSignals:
        """Récupère tous les signaux de marché."""
        signals = MarketSignals()

        # HYG/LQD
        hyg_lqd = await self.get_hyg_lqd_ratio()
        if "error" not in hyg_lqd:
            signals.credit_stress = hyg_lqd.get("credit_stress", False)
            signals.hyg_lqd_ratio = hyg_lqd.get("current_ratio")
            signals.hyg_lqd_sma50 = hyg_lqd.get("sma_50")

        # VIX
        vix = await self.get_vix_data()
        if "error" not in vix:
            signals.vix_elevated = vix.get("elevated", False)
            signals.vix_spike = vix.get("spike", False)
            signals.vix_level = vix.get("current_level")
            signals.vix_sma20 = vix.get("sma_20")

        # SPY
        spy = await self.get_spy_trend()
        if "error" not in spy:
            signals.spy_below_sma200 = spy.get("below_sma200", False)
            signals.spy_drawdown_alert = spy.get("drawdown_alert", False)
            signals.spy_price = spy.get("current_price")
            signals.spy_sma200 = spy.get("sma_200")
            signals.spy_drawdown = spy.get("drawdown")

        # Yield Curve
        yc = await self.get_yield_curve()
        if "error" not in yc:
            signals.yield_curve_inverted = yc.get("inverted", False)
            signals.yield_spread_10y_2y = yc.get("spread_10y_3m")

        return signals

    def _determine_regime(self, signals: MarketSignals) -> RegimeType:
        """
        Détermine le régime basé sur les signaux.

        Logique:
        - 4+ signaux de stress: HIGH_UNCERTAINTY
        - 3 signaux de stress: RISK_OFF
        - 1-2 signaux: NEUTRAL
        - 0 signaux: RISK_ON
        """
        stress_count = signals.stress_count

        if signals.vix_spike:
            # VIX > 30 est toujours high uncertainty
            return RegimeType.HIGH_UNCERTAINTY

        if stress_count >= 4:
            return RegimeType.HIGH_UNCERTAINTY
        elif stress_count >= 3:
            return RegimeType.RISK_OFF
        elif stress_count >= 1:
            return RegimeType.NEUTRAL
        else:
            return RegimeType.RISK_ON

    def _calculate_confidence(self, signals: MarketSignals, regime: RegimeType) -> float:
        """Calcule le niveau de confiance du régime."""
        # Base confidence
        if regime == RegimeType.RISK_ON:
            # Plus il y a de signaux positifs, plus on est confiant
            confidence = 100 - (signals.stress_count * 15)
        elif regime == RegimeType.RISK_OFF:
            # Plus il y a de signaux de stress, plus on est confiant
            confidence = 50 + (signals.stress_count * 10)
        elif regime == RegimeType.HIGH_UNCERTAINTY:
            confidence = 80  # Haute confiance dans l'incertitude
        else:  # NEUTRAL
            confidence = 60  # Confiance modérée

        return max(0, min(100, confidence))

    def _generate_interpretation(self, signals: MarketSignals, regime: RegimeType) -> str:
        """Génère une interprétation textuelle du régime."""
        parts = []

        if regime == RegimeType.RISK_ON:
            parts.append("Conditions favorables pour les actifs risqués.")
        elif regime == RegimeType.RISK_OFF:
            parts.append("Conditions défavorables - privilégier les actifs défensifs.")
        elif regime == RegimeType.HIGH_UNCERTAINTY:
            parts.append("Incertitude élevée - réduire l'exposition et augmenter le cash.")
        else:
            parts.append("Signaux mixtes - allocation équilibrée recommandée.")

        # Détails des signaux actifs
        active_signals = []
        if signals.credit_stress:
            active_signals.append("stress crédit (HYG/LQD)")
        if signals.vix_elevated:
            active_signals.append(f"VIX élevé ({signals.vix_level:.1f})" if signals.vix_level else "VIX élevé")
        if signals.spy_below_sma200:
            active_signals.append("SPY sous SMA200")
        if signals.spy_drawdown_alert:
            active_signals.append(f"drawdown {signals.spy_drawdown*100:.1f}%" if signals.spy_drawdown else "drawdown")
        if signals.yield_curve_inverted:
            active_signals.append("courbe des taux inversée")

        if active_signals:
            parts.append(f"Signaux actifs: {', '.join(active_signals)}.")

        return " ".join(parts)

    def _interpret_vix(self, vix: float) -> str:
        """Interprète le niveau de VIX."""
        if vix < 12:
            return "Complaisance extrême"
        elif vix < 18:
            return "Volatilité faible - marché calme"
        elif vix < 25:
            return "Volatilité normale"
        elif vix < 30:
            return "Volatilité élevée - prudence"
        else:
            return "Volatilité extrême - panique"

    def _interpret_spy_trend(self, price: float, sma200: float, drawdown: float) -> str:
        """Interprète la tendance SPY."""
        parts = []

        if price > sma200:
            pct_above = ((price / sma200) - 1) * 100
            parts.append(f"Tendance haussière (+{pct_above:.1f}% vs SMA200)")
        else:
            pct_below = ((sma200 / price) - 1) * 100
            parts.append(f"Tendance baissière (-{pct_below:.1f}% vs SMA200)")

        if drawdown < -0.20:
            parts.append("Bear market")
        elif drawdown < -0.10:
            parts.append("Correction")
        elif drawdown < -0.05:
            parts.append("Pullback")

        return " - ".join(parts)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_market_regime_provider(cache_ttl: int = 300) -> MarketRegimeProvider:
    """
    Factory function pour créer un MarketRegimeProvider.

    Args:
        cache_ttl: Durée de vie du cache en secondes

    Returns:
        Instance configurée de MarketRegimeProvider
    """
    return MarketRegimeProvider(cache_ttl=cache_ttl)


# Singleton pour usage simple
_market_regime_provider: Optional[MarketRegimeProvider] = None


def get_market_regime_provider() -> MarketRegimeProvider:
    """
    Retourne une instance singleton du provider.

    Returns:
        MarketRegimeProvider partagé
    """
    global _market_regime_provider
    if _market_regime_provider is None:
        _market_regime_provider = create_market_regime_provider()
    return _market_regime_provider
