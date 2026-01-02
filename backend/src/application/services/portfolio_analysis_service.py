"""
Service d'analyse complete du portefeuille.

Combine pour chaque position:
- Analyse technique (RSI, MACD, support/resistance, trend)
- News & Sentiment (Finnhub)
- Metriques de risque (poids, concentration, SL/TP suggeres)
- Recommandation MCP Trader Pro (BUY/SELL/HOLD)

UTILISATION:
    from src.application.services.portfolio_analysis_service import PortfolioAnalysisService

    service = PortfolioAnalysisService()
    enhanced_positions = await service.analyze_portfolio(positions, total_value)
"""

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.application.services.technical_calculator import TechnicalCalculator
from src.application.services.news_service import NewsService
from src.application.services.market_structure_analyzer import MarketStructureAnalyzer
from src.infrastructure.providers.yahoo_finance_provider import (
    YahooFinanceProvider,
    get_yahoo_provider,
)
from src.domain.value_objects.ticker import Ticker

logger = logging.getLogger(__name__)


@dataclass
class PositionTechnicalAnalysis:
    """Analyse technique pour une position."""
    symbol: str
    rsi: float
    rsi_signal: str  # "overbought", "oversold", "neutral"
    macd_line: float
    macd_signal: float
    macd_histogram: float
    macd_trend: str  # "bullish", "bearish", "neutral"
    trend: str  # "uptrend", "downtrend", "sideways"
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    atr: float = 0.0
    atr_percent: float = 0.0
    bollinger_position: str = ""  # "above_upper", "below_lower", "middle"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PositionSentiment:
    """Sentiment et news pour une position."""
    symbol: str
    sentiment_score: float  # -1 (bearish) a +1 (bullish)
    sentiment_label: str  # "bullish", "bearish", "neutral"
    news_count: int
    recent_headlines: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PositionRiskMetrics:
    """Metriques de risque pour une position."""
    symbol: str
    portfolio_weight: float  # % du portefeuille
    concentration_risk: str  # "low", "medium", "high"
    entry_price: float
    current_price: float
    suggested_stop_loss: float
    suggested_take_profit: float
    stop_loss_distance_pct: float
    take_profit_distance_pct: float
    risk_reward_ratio: float
    max_loss_amount: float  # Perte si SL touche

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PositionRecommendation:
    """Recommandation MCP Trader Pro."""
    symbol: str
    action: str  # "BUY", "SELL", "HOLD", "REDUCE", "ADD"
    confidence: float  # 0-100
    reasoning: List[str] = field(default_factory=list)
    invalidation_level: Optional[float] = None
    target_price: Optional[float] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EnhancedPosition:
    """Position enrichie avec toutes les analyses."""
    # Donnees de base
    symbol: str
    description: str
    quantity: float
    current_price: float
    average_price: float
    market_value: float
    pnl: float
    pnl_percent: float
    currency: str
    asset_type: str
    uic: Optional[int] = None

    # Analyses enrichies
    technical: Optional[PositionTechnicalAnalysis] = None
    sentiment: Optional[PositionSentiment] = None
    risk: Optional[PositionRiskMetrics] = None
    recommendation: Optional[PositionRecommendation] = None

    # Metadata
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "description": self.description,
            "quantity": self.quantity,
            "current_price": round(self.current_price, 2),
            "average_price": round(self.average_price, 2),
            "market_value": round(self.market_value, 2),
            "pnl": round(self.pnl, 2),
            "pnl_percent": round(self.pnl_percent, 2),
            "currency": self.currency,
            "asset_type": self.asset_type,
            "uic": self.uic,
            "technical": self.technical.to_dict() if self.technical else None,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
            "analyzed_at": self.analyzed_at,
        }


class PortfolioAnalysisService:
    """
    Service d'analyse complete du portefeuille.

    Orchestre les differents services d'analyse pour enrichir
    chaque position avec des donnees professionnelles.
    """

    def __init__(
        self,
        yahoo_provider: Optional[YahooFinanceProvider] = None,
        technical_calculator: Optional[TechnicalCalculator] = None,
        news_service: Optional[NewsService] = None,
        structure_analyzer: Optional[MarketStructureAnalyzer] = None,
    ):
        """
        Initialise le service.

        Args:
            yahoo_provider: Provider de donnees de marche.
            technical_calculator: Calculateur d'indicateurs techniques.
            news_service: Service de news et sentiment.
            structure_analyzer: Analyseur de structure de marche.
        """
        self._yahoo = yahoo_provider or get_yahoo_provider()
        self._tech_calc = technical_calculator or TechnicalCalculator()
        self._news_service = news_service or NewsService()
        self._structure = structure_analyzer or MarketStructureAnalyzer()

    async def analyze_portfolio(
        self,
        positions: List[Dict[str, Any]],
        portfolio_total_value: float,
    ) -> List[EnhancedPosition]:
        """
        Analyse complete de toutes les positions du portefeuille.

        Args:
            positions: Liste des positions brutes
            portfolio_total_value: Valeur totale du portefeuille

        Returns:
            Liste des positions enrichies
        """
        if not positions:
            return []

        # Analyser toutes les positions en parallele
        tasks = [
            self.analyze_position(pos, portfolio_total_value)
            for pos in positions
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrer les erreurs
        enhanced_positions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erreur analyse position {positions[i].get('symbol')}: {result}")
                # Creer une position minimale
                enhanced_positions.append(self._create_minimal_position(positions[i]))
            else:
                enhanced_positions.append(result)

        return enhanced_positions

    async def analyze_position(
        self,
        position: Dict[str, Any],
        portfolio_total_value: float,
    ) -> EnhancedPosition:
        """
        Analyse complete d'une seule position.

        Args:
            position: Donnees de la position
            portfolio_total_value: Valeur totale du portefeuille

        Returns:
            Position enrichie avec toutes les analyses
        """
        symbol = position.get("symbol", "UNKNOWN")

        # Lancer les analyses en parallele
        tech_task = self._analyze_technical(symbol)
        sentiment_task = self._analyze_sentiment(symbol)
        risk_task = self._analyze_risk(position, portfolio_total_value)
        recommendation_task = self._get_recommendation(symbol, position)

        results = await asyncio.gather(
            tech_task,
            sentiment_task,
            risk_task,
            recommendation_task,
            return_exceptions=True,
        )

        technical = results[0] if not isinstance(results[0], Exception) else None
        sentiment = results[1] if not isinstance(results[1], Exception) else None
        risk = results[2] if not isinstance(results[2], Exception) else None
        recommendation = results[3] if not isinstance(results[3], Exception) else None

        if isinstance(results[0], Exception):
            logger.warning(f"Erreur technique {symbol}: {results[0]}")
        if isinstance(results[1], Exception):
            logger.warning(f"Erreur sentiment {symbol}: {results[1]}")
        if isinstance(results[2], Exception):
            logger.warning(f"Erreur risque {symbol}: {results[2]}")
        if isinstance(results[3], Exception):
            logger.warning(f"Erreur recommandation {symbol}: {results[3]}")

        return EnhancedPosition(
            symbol=symbol,
            description=position.get("description", ""),
            quantity=position.get("quantity", 0),
            current_price=position.get("current_price", 0),
            average_price=position.get("average_price", 0),
            market_value=position.get("market_value", 0),
            pnl=position.get("pnl", 0),
            pnl_percent=position.get("pnl_percent", 0),
            currency=position.get("currency", "EUR"),
            asset_type=position.get("asset_type", "Stock"),
            uic=position.get("uic"),
            technical=technical,
            sentiment=sentiment,
            risk=risk,
            recommendation=recommendation,
        )

    async def _analyze_technical(self, symbol: str) -> PositionTechnicalAnalysis:
        """Analyse technique d'une position."""
        ticker = Ticker(symbol)

        # Recuperer les donnees historiques (1 an)
        historical = await self._yahoo.get_historical_data(ticker, days=365)

        if len(historical) < 50:
            raise ValueError(f"Donnees insuffisantes pour {symbol}: {len(historical)} points")

        # Calculer les indicateurs
        indicators = await self._tech_calc.calculate_all(symbol, historical)

        if not indicators:
            raise ValueError(f"Impossible de calculer les indicateurs pour {symbol}")

        # Determiner les signaux
        rsi = indicators.rsi.value
        if rsi > 70:
            rsi_signal = "overbought"
        elif rsi < 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"

        # MACD trend
        macd_hist = indicators.macd.histogram
        if macd_hist > 0:
            macd_trend = "bullish"
        elif macd_hist < 0:
            macd_trend = "bearish"
        else:
            macd_trend = "neutral"

        # Trend general
        ma = indicators.moving_averages
        if ma.current_price > ma.sma_20 > ma.sma_50:
            trend = "uptrend"
        elif ma.current_price < ma.sma_20 < ma.sma_50:
            trend = "downtrend"
        else:
            trend = "sideways"

        # Bollinger position
        bb = indicators.bollinger
        if bb.current_price > bb.upper_band:
            bb_position = "above_upper"
        elif bb.current_price < bb.lower_band:
            bb_position = "below_lower"
        else:
            bb_position = "middle"

        # Support/resistance via structure de marche
        support_levels = []
        resistance_levels = []
        try:
            structure = await self._structure.analyze(symbol, historical)
            if structure:
                support_levels = [z.lower for z in (structure.demand_zones or [])][:3]
                resistance_levels = [z.upper for z in (structure.supply_zones or [])][:3]
        except Exception as e:
            logger.debug(f"Structure non disponible pour {symbol}: {e}")

        return PositionTechnicalAnalysis(
            symbol=symbol,
            rsi=round(rsi, 2),
            rsi_signal=rsi_signal,
            macd_line=round(indicators.macd.macd_line, 4),
            macd_signal=round(indicators.macd.signal_line, 4),
            macd_histogram=round(macd_hist, 4),
            macd_trend=macd_trend,
            trend=trend,
            support_levels=[round(s, 2) for s in support_levels],
            resistance_levels=[round(r, 2) for r in resistance_levels],
            atr=round(indicators.atr, 2),
            atr_percent=round(indicators.atr_percent, 2),
            bollinger_position=bb_position,
        )

    async def _analyze_sentiment(self, symbol: str) -> PositionSentiment:
        """Analyse sentiment via news Finnhub."""
        try:
            news_articles = await self._news_service.get_news_for_ticker(symbol, limit=10)

            if not news_articles:
                return PositionSentiment(
                    symbol=symbol,
                    sentiment_score=0.0,
                    sentiment_label="neutral",
                    news_count=0,
                    recent_headlines=[],
                )

            # Calculer le sentiment moyen
            scores = [a.sentiment_score for a in news_articles if hasattr(a, 'sentiment_score')]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            if avg_score > 0.2:
                label = "bullish"
            elif avg_score < -0.2:
                label = "bearish"
            else:
                label = "neutral"

            headlines = [a.headline for a in news_articles[:5] if hasattr(a, 'headline')]

            return PositionSentiment(
                symbol=symbol,
                sentiment_score=round(avg_score, 2),
                sentiment_label=label,
                news_count=len(news_articles),
                recent_headlines=headlines,
            )

        except Exception as e:
            logger.debug(f"News non disponibles pour {symbol}: {e}")
            return PositionSentiment(
                symbol=symbol,
                sentiment_score=0.0,
                sentiment_label="unknown",
                news_count=0,
                recent_headlines=[],
            )

    async def _analyze_risk(
        self,
        position: Dict[str, Any],
        portfolio_total_value: float,
    ) -> PositionRiskMetrics:
        """Calcule les metriques de risque."""
        symbol = position.get("symbol", "")
        market_value = position.get("market_value", 0)
        entry_price = position.get("average_price", 0)
        current_price = position.get("current_price", 0)
        quantity = position.get("quantity", 0)

        # Poids dans le portefeuille
        weight = (market_value / portfolio_total_value * 100) if portfolio_total_value > 0 else 0

        # Risque de concentration
        if weight > 25:
            concentration = "high"
        elif weight > 15:
            concentration = "medium"
        else:
            concentration = "low"

        # Stop loss suggere (8% sous le prix d'entree)
        suggested_sl = entry_price * 0.92 if entry_price > 0 else current_price * 0.92
        sl_distance_pct = 8.0

        # Take profit suggere (24% au-dessus = 3:1 R/R)
        suggested_tp = entry_price * 1.24 if entry_price > 0 else current_price * 1.24
        tp_distance_pct = 24.0

        # Ratio risque/reward
        risk = abs(entry_price - suggested_sl) if entry_price > 0 else abs(current_price - suggested_sl)
        reward = abs(suggested_tp - entry_price) if entry_price > 0 else abs(suggested_tp - current_price)
        rr_ratio = reward / risk if risk > 0 else 0

        # Perte maximale si SL touche
        max_loss = abs(quantity) * (entry_price - suggested_sl) if quantity != 0 and entry_price > 0 else 0

        return PositionRiskMetrics(
            symbol=symbol,
            portfolio_weight=round(weight, 2),
            concentration_risk=concentration,
            entry_price=round(entry_price, 2),
            current_price=round(current_price, 2),
            suggested_stop_loss=round(suggested_sl, 2),
            suggested_take_profit=round(suggested_tp, 2),
            stop_loss_distance_pct=round(sl_distance_pct, 2),
            take_profit_distance_pct=round(tp_distance_pct, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            max_loss_amount=round(abs(max_loss), 2),
        )

    async def _get_recommendation(
        self,
        symbol: str,
        position: Dict[str, Any],
    ) -> PositionRecommendation:
        """Genere une recommandation basee sur les analyses."""
        ticker = Ticker(symbol)

        try:
            # Recuperer les donnees
            historical = await self._yahoo.get_historical_data(ticker, days=365)

            if len(historical) < 50:
                return PositionRecommendation(
                    symbol=symbol,
                    action="HOLD",
                    confidence=0,
                    reasoning=["Donnees insuffisantes pour analyse"],
                )

            # Calculer les indicateurs
            indicators = await self._tech_calc.calculate_all(symbol, historical)

            if not indicators:
                return PositionRecommendation(
                    symbol=symbol,
                    action="HOLD",
                    confidence=0,
                    reasoning=["Indicateurs non disponibles"],
                )

            # Logique de recommandation basee sur les indicateurs
            reasoning = []
            score = 0  # -100 (SELL) a +100 (BUY)

            # RSI
            rsi = indicators.rsi.value
            if rsi > 80:
                score -= 30
                reasoning.append(f"RSI tres surchauffe ({rsi:.0f})")
            elif rsi > 70:
                score -= 15
                reasoning.append(f"RSI surchauffe ({rsi:.0f})")
            elif rsi < 20:
                score += 30
                reasoning.append(f"RSI tres survendu ({rsi:.0f})")
            elif rsi < 30:
                score += 15
                reasoning.append(f"RSI survendu ({rsi:.0f})")
            else:
                reasoning.append(f"RSI neutre ({rsi:.0f})")

            # MACD
            macd = indicators.macd
            if macd.histogram > 0 and macd.macd_line > macd.signal_line:
                score += 20
                reasoning.append("MACD bullish (au-dessus de la ligne signal)")
            elif macd.histogram < 0 and macd.macd_line < macd.signal_line:
                score -= 20
                reasoning.append("MACD bearish (sous la ligne signal)")

            # Tendance (Moving Averages)
            ma = indicators.moving_averages
            if ma.current_price > ma.sma_50 > ma.sma_200:
                score += 25
                reasoning.append("Tendance haussiere (prix > SMA50 > SMA200)")
            elif ma.current_price < ma.sma_50 < ma.sma_200:
                score -= 25
                reasoning.append("Tendance baissiere (prix < SMA50 < SMA200)")

            # Bollinger Bands
            bb = indicators.bollinger
            if bb.current_price < bb.lower_band:
                score += 15
                reasoning.append("Prix sous bande Bollinger inferieure (survente)")
            elif bb.current_price > bb.upper_band:
                score -= 15
                reasoning.append("Prix au-dessus bande Bollinger superieure (surachat)")

            # P&L actuel de la position
            pnl_pct = position.get("pnl_percent", 0)
            if pnl_pct > 30:
                score -= 10
                reasoning.append(f"Gain important (+{pnl_pct:.0f}%) - considerer prise de profits")
            elif pnl_pct < -15:
                score -= 5
                reasoning.append(f"Perte significative ({pnl_pct:.0f}%) - verifier le stop loss")

            # Determiner l'action
            confidence = min(abs(score), 100)
            if score > 40:
                action = "BUY"
            elif score > 20:
                action = "ADD"
            elif score < -40:
                action = "SELL"
            elif score < -20:
                action = "REDUCE"
            else:
                action = "HOLD"

            # Target price (resistance proche ou +15%)
            target = None
            if action in ("BUY", "ADD"):
                target = indicators.moving_averages.current_price * 1.15

            # Invalidation
            invalidation = indicators.bollinger.lower_band

            return PositionRecommendation(
                symbol=symbol,
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                invalidation_level=round(invalidation, 2) if invalidation else None,
                target_price=round(target, 2) if target else None,
            )

        except Exception as e:
            logger.error(f"Erreur recommandation {symbol}: {e}")
            return PositionRecommendation(
                symbol=symbol,
                action="HOLD",
                confidence=0,
                reasoning=[f"Erreur d'analyse: {str(e)}"],
            )

    def _create_minimal_position(self, position: Dict[str, Any]) -> EnhancedPosition:
        """Cree une position minimale en cas d'erreur."""
        return EnhancedPosition(
            symbol=position.get("symbol", "UNKNOWN"),
            description=position.get("description", ""),
            quantity=position.get("quantity", 0),
            current_price=position.get("current_price", 0),
            average_price=position.get("average_price", 0),
            market_value=position.get("market_value", 0),
            pnl=position.get("pnl", 0),
            pnl_percent=position.get("pnl_percent", 0),
            currency=position.get("currency", "EUR"),
            asset_type=position.get("asset_type", "Stock"),
            uic=position.get("uic"),
        )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_portfolio_analysis_service() -> PortfolioAnalysisService:
    """Factory function pour creer le service d'analyse."""
    return PortfolioAnalysisService()
