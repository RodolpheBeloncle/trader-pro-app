"""
Service d'analyse d'instrument AVANT achat.

Fournit les memes analyses que pour le portefeuille mais pour
un instrument qu'on souhaite potentiellement acheter.

Inclut:
- Prix actuel et donnees de marche
- Analyse technique complete (RSI, MACD, Bollinger, tendance)
- Sentiment et news recentes
- Niveaux SL/TP suggeres pour un achat
- Recommandation BUY/HOLD/AVOID avec niveau de confiance

UTILISATION:
    from src.application.services.instrument_analysis_service import InstrumentAnalysisService

    service = InstrumentAnalysisService()
    analysis = await service.analyze_instrument("AAPL")
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
class InstrumentInfo:
    """Informations de base sur l'instrument."""
    symbol: str
    name: str
    currency: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PriceData:
    """Donnees de prix actuelles."""
    current_price: float
    open: float
    high: float
    low: float
    previous_close: float
    change: float
    change_percent: float
    volume: int
    avg_volume: Optional[int] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TechnicalAnalysis:
    """Analyse technique complete."""
    # RSI
    rsi: float
    rsi_signal: str  # "overbought", "oversold", "neutral"

    # MACD
    macd_line: float
    macd_signal: float
    macd_histogram: float
    macd_trend: str  # "bullish", "bearish", "neutral"

    # Tendance
    trend: str  # "uptrend", "downtrend", "sideways"
    trend_strength: str  # "strong", "moderate", "weak"

    # Moving Averages
    sma_20: float
    sma_50: float
    sma_200: float
    ema_12: float
    ema_26: float
    price_vs_sma50: str  # "above", "below"
    price_vs_sma200: str  # "above", "below"

    # Bollinger Bands
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    bollinger_position: str  # "above_upper", "below_lower", "middle"
    percent_b: float

    # Volatilite
    atr: float
    atr_percent: float

    # Support/Resistance
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SentimentAnalysis:
    """Analyse du sentiment marche."""
    sentiment_score: float  # -1 (bearish) a +1 (bullish)
    sentiment_label: str  # "bullish", "bearish", "neutral"
    news_count: int
    recent_headlines: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TradingLevels:
    """Niveaux de trading suggeres pour un achat."""
    entry_price: float
    suggested_stop_loss: float
    suggested_take_profit_1: float  # Target conservatif (2:1)
    suggested_take_profit_2: float  # Target agressif (3:1)
    stop_loss_distance_pct: float
    take_profit_1_distance_pct: float
    take_profit_2_distance_pct: float
    risk_reward_ratio: float
    invalidation_level: float  # Niveau qui invalide le setup

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BuyRecommendation:
    """Recommandation d'achat."""
    action: str  # "BUY", "WAIT", "AVOID"
    confidence: float  # 0-100
    rating: int  # 1-5 etoiles
    reasoning: List[str] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class InstrumentAnalysis:
    """Analyse complete d'un instrument."""
    info: InstrumentInfo
    price: PriceData
    technical: TechnicalAnalysis
    sentiment: SentimentAnalysis
    trading_levels: TradingLevels
    recommendation: BuyRecommendation
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "info": self.info.to_dict(),
            "price": self.price.to_dict(),
            "technical": self.technical.to_dict(),
            "sentiment": self.sentiment.to_dict(),
            "trading_levels": self.trading_levels.to_dict(),
            "recommendation": self.recommendation.to_dict(),
            "analyzed_at": self.analyzed_at,
        }


class InstrumentAnalysisService:
    """
    Service d'analyse complete d'un instrument avant achat.

    Fournit toutes les informations necessaires pour prendre
    une decision d'achat eclairee.
    """

    def __init__(
        self,
        yahoo_provider: Optional[YahooFinanceProvider] = None,
        technical_calculator: Optional[TechnicalCalculator] = None,
        news_service: Optional[NewsService] = None,
        structure_analyzer: Optional[MarketStructureAnalyzer] = None,
    ):
        self._yahoo = yahoo_provider or get_yahoo_provider()
        self._tech_calc = technical_calculator or TechnicalCalculator()
        self._news_service = news_service or NewsService()
        self._structure = structure_analyzer or MarketStructureAnalyzer()

    async def analyze_instrument(self, symbol: str) -> InstrumentAnalysis:
        """
        Analyse complete d'un instrument.

        Args:
            symbol: Symbole de l'instrument (ex: "AAPL", "MSFT")

        Returns:
            InstrumentAnalysis avec toutes les donnees
        """
        ticker = Ticker(symbol)

        # Lancer toutes les analyses en parallele
        info_task = self._get_instrument_info(ticker)
        price_task = self._get_price_data(ticker)
        technical_task = self._get_technical_analysis(ticker)
        sentiment_task = self._get_sentiment_analysis(symbol)

        results = await asyncio.gather(
            info_task,
            price_task,
            technical_task,
            sentiment_task,
            return_exceptions=True,
        )

        info = results[0] if not isinstance(results[0], Exception) else self._default_info(symbol)
        price = results[1] if not isinstance(results[1], Exception) else None
        technical = results[2] if not isinstance(results[2], Exception) else None
        sentiment = results[3] if not isinstance(results[3], Exception) else self._default_sentiment(symbol)

        # Log des erreurs
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Erreur analyse {symbol} (task {i}): {result}")

        if price is None or technical is None:
            raise ValueError(f"Impossible d'analyser {symbol}: donnees insuffisantes")

        # Calculer les niveaux de trading
        trading_levels = self._calculate_trading_levels(price.current_price, technical)

        # Generer la recommandation
        recommendation = self._generate_recommendation(
            symbol, price, technical, sentiment, trading_levels
        )

        return InstrumentAnalysis(
            info=info,
            price=price,
            technical=technical,
            sentiment=sentiment,
            trading_levels=trading_levels,
            recommendation=recommendation,
        )

    async def _get_instrument_info(self, ticker: Ticker) -> InstrumentInfo:
        """Recupere les informations de base de l'instrument."""
        try:
            metadata = await self._yahoo.get_metadata(ticker)

            return InstrumentInfo(
                symbol=ticker.value,
                name=metadata.name or ticker.value,
                currency=metadata.currency or "USD",
                exchange=metadata.exchange,
                sector=metadata.sector,
                industry=metadata.industry,
                market_cap=metadata.market_cap,
            )
        except Exception as e:
            logger.warning(f"Metadata non disponible pour {ticker.value}: {e}")
            return self._default_info(ticker.value)

    async def _get_price_data(self, ticker: Ticker) -> PriceData:
        """Recupere les donnees de prix actuelles."""
        quote = await self._yahoo.get_current_quote(ticker)
        historical = await self._yahoo.get_historical_data(ticker, days=365)

        if not historical:
            raise ValueError(f"Donnees historiques non disponibles pour {ticker.value}")

        # Calculer les stats
        prices = [h.close for h in historical]
        week_52_high = max(prices) if prices else None
        week_52_low = min(prices) if prices else None
        volumes = [h.volume for h in historical[-20:]]  # 20 derniers jours
        avg_volume = int(sum(volumes) / len(volumes)) if volumes else None

        # Derniere bougie
        latest = historical[-1]
        prev_close = historical[-2].close if len(historical) > 1 else latest.close

        change = quote.price - prev_close
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0

        return PriceData(
            current_price=round(quote.price, 2),
            open=round(latest.open, 2),
            high=round(latest.high, 2),
            low=round(latest.low, 2),
            previous_close=round(prev_close, 2),
            change=round(change, 2),
            change_percent=round(change_pct, 2),
            volume=latest.volume,
            avg_volume=avg_volume,
            week_52_high=round(week_52_high, 2) if week_52_high else None,
            week_52_low=round(week_52_low, 2) if week_52_low else None,
        )

    async def _get_technical_analysis(self, ticker: Ticker) -> TechnicalAnalysis:
        """Calcule l'analyse technique complete."""
        historical = await self._yahoo.get_historical_data(ticker, days=365)

        if len(historical) < 50:
            raise ValueError(f"Donnees insuffisantes pour {ticker.value}: {len(historical)} points")

        indicators = await self._tech_calc.calculate_all(ticker.value, historical)

        if not indicators:
            raise ValueError(f"Indicateurs non calculables pour {ticker.value}")

        # RSI signal
        rsi = indicators.rsi.value
        if rsi > 70:
            rsi_signal = "overbought"
        elif rsi < 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"

        # MACD trend
        macd_hist = indicators.macd.histogram
        if macd_hist > 0 and indicators.macd.macd_line > indicators.macd.signal_line:
            macd_trend = "bullish"
        elif macd_hist < 0 and indicators.macd.macd_line < indicators.macd.signal_line:
            macd_trend = "bearish"
        else:
            macd_trend = "neutral"

        # Tendance et force
        ma = indicators.moving_averages
        if ma.current_price > ma.sma_50 > ma.sma_200:
            trend = "uptrend"
            trend_strength = "strong" if ma.current_price > ma.sma_20 else "moderate"
        elif ma.current_price < ma.sma_50 < ma.sma_200:
            trend = "downtrend"
            trend_strength = "strong" if ma.current_price < ma.sma_20 else "moderate"
        else:
            trend = "sideways"
            trend_strength = "weak"

        # Position vs MAs
        price_vs_sma50 = "above" if ma.current_price > ma.sma_50 else "below"
        price_vs_sma200 = "above" if ma.current_price > ma.sma_200 else "below"

        # Bollinger position
        bb = indicators.bollinger
        if bb.current_price > bb.upper_band:
            bb_position = "above_upper"
        elif bb.current_price < bb.lower_band:
            bb_position = "below_lower"
        else:
            bb_position = "middle"

        # Support/resistance
        support_levels = []
        resistance_levels = []
        try:
            structure = await self._structure.analyze(ticker.value, historical)
            if structure:
                support_levels = [round(z.lower, 2) for z in (structure.demand_zones or [])][:3]
                resistance_levels = [round(z.upper, 2) for z in (structure.supply_zones or [])][:3]
        except Exception:
            pass

        return TechnicalAnalysis(
            rsi=round(rsi, 2),
            rsi_signal=rsi_signal,
            macd_line=round(indicators.macd.macd_line, 4),
            macd_signal=round(indicators.macd.signal_line, 4),
            macd_histogram=round(macd_hist, 4),
            macd_trend=macd_trend,
            trend=trend,
            trend_strength=trend_strength,
            sma_20=round(ma.sma_20, 2),
            sma_50=round(ma.sma_50, 2),
            sma_200=round(ma.sma_200, 2),
            ema_12=round(ma.ema_12, 2),
            ema_26=round(ma.ema_26, 2),
            price_vs_sma50=price_vs_sma50,
            price_vs_sma200=price_vs_sma200,
            bollinger_upper=round(bb.upper_band, 2),
            bollinger_middle=round(bb.middle_band, 2),
            bollinger_lower=round(bb.lower_band, 2),
            bollinger_position=bb_position,
            percent_b=round(bb.percent_b, 2) if hasattr(bb, 'percent_b') else 0.5,
            atr=round(indicators.atr, 2),
            atr_percent=round(indicators.atr_percent, 2),
            support_levels=support_levels,
            resistance_levels=resistance_levels,
        )

    async def _get_sentiment_analysis(self, symbol: str) -> SentimentAnalysis:
        """Analyse du sentiment via les news."""
        try:
            news_articles = await self._news_service.get_news_for_ticker(symbol, limit=10)

            if not news_articles:
                return self._default_sentiment(symbol)

            scores = [a.sentiment_score for a in news_articles if hasattr(a, 'sentiment_score')]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            if avg_score > 0.2:
                label = "bullish"
            elif avg_score < -0.2:
                label = "bearish"
            else:
                label = "neutral"

            headlines = [
                {"headline": a.headline, "source": getattr(a, 'source', 'Unknown')}
                for a in news_articles[:5]
                if hasattr(a, 'headline')
            ]

            return SentimentAnalysis(
                sentiment_score=round(avg_score, 2),
                sentiment_label=label,
                news_count=len(news_articles),
                recent_headlines=headlines,
            )
        except Exception as e:
            logger.debug(f"Sentiment non disponible pour {symbol}: {e}")
            return self._default_sentiment(symbol)

    def _calculate_trading_levels(
        self,
        current_price: float,
        technical: TechnicalAnalysis,
    ) -> TradingLevels:
        """Calcule les niveaux de trading suggeres."""
        # Stop loss base sur ATR ou support
        atr_sl = current_price - (2 * technical.atr)  # 2 ATR sous le prix

        # Utiliser le support le plus proche si disponible
        if technical.support_levels:
            nearest_support = max(s for s in technical.support_levels if s < current_price)
            sl = min(atr_sl, nearest_support * 0.98)  # 2% sous le support
        else:
            sl = atr_sl

        # Ne pas mettre le SL trop loin (max 10%)
        sl = max(sl, current_price * 0.90)

        sl_distance_pct = ((current_price - sl) / current_price) * 100

        # Take profits bases sur Risk/Reward
        risk = current_price - sl
        tp1 = current_price + (2 * risk)  # 2:1 R/R
        tp2 = current_price + (3 * risk)  # 3:1 R/R

        tp1_distance_pct = ((tp1 - current_price) / current_price) * 100
        tp2_distance_pct = ((tp2 - current_price) / current_price) * 100

        # Niveau d'invalidation (proche de la bande Bollinger inferieure)
        invalidation = technical.bollinger_lower

        return TradingLevels(
            entry_price=round(current_price, 2),
            suggested_stop_loss=round(sl, 2),
            suggested_take_profit_1=round(tp1, 2),
            suggested_take_profit_2=round(tp2, 2),
            stop_loss_distance_pct=round(sl_distance_pct, 2),
            take_profit_1_distance_pct=round(tp1_distance_pct, 2),
            take_profit_2_distance_pct=round(tp2_distance_pct, 2),
            risk_reward_ratio=2.0,  # Target 2:1 minimum
            invalidation_level=round(invalidation, 2),
        )

    def _generate_recommendation(
        self,
        symbol: str,
        price: PriceData,
        technical: TechnicalAnalysis,
        sentiment: SentimentAnalysis,
        trading_levels: TradingLevels,
    ) -> BuyRecommendation:
        """Genere la recommandation d'achat."""
        score = 0
        reasoning = []
        pros = []
        cons = []

        # === Analyse RSI (20% du score) ===
        if technical.rsi < 30:
            score += 25
            pros.append(f"RSI survendu ({technical.rsi:.0f}) - opportunite d'achat")
        elif technical.rsi < 40:
            score += 10
            pros.append(f"RSI en zone basse ({technical.rsi:.0f})")
        elif technical.rsi > 70:
            score -= 25
            cons.append(f"RSI surchauffe ({technical.rsi:.0f}) - risque de correction")
        elif technical.rsi > 60:
            score -= 5
            cons.append(f"RSI eleve ({technical.rsi:.0f})")

        # === Analyse MACD (25% du score) ===
        if technical.macd_trend == "bullish":
            score += 20
            pros.append("MACD bullish - momentum positif")
        elif technical.macd_trend == "bearish":
            score -= 20
            cons.append("MACD bearish - momentum negatif")

        # Croisement MACD (signal fort)
        if technical.macd_histogram > 0 and abs(technical.macd_histogram) < 0.1:
            score += 10
            reasoning.append("Croisement MACD recent - signal d'achat")

        # === Analyse Tendance (30% du score) ===
        if technical.trend == "uptrend":
            score += 25
            pros.append(f"Tendance haussiere {technical.trend_strength}")
            if technical.price_vs_sma200 == "above":
                score += 10
                pros.append("Prix au-dessus de la SMA 200 - tendance long terme positive")
        elif technical.trend == "downtrend":
            score -= 25
            cons.append(f"Tendance baissiere {technical.trend_strength}")
            if technical.price_vs_sma200 == "below":
                score -= 10
                cons.append("Prix sous la SMA 200 - tendance long terme negative")
        else:
            reasoning.append("Tendance laterale - attendre une cassure")

        # === Analyse Bollinger (15% du score) ===
        if technical.bollinger_position == "below_lower":
            score += 15
            pros.append("Prix sous bande Bollinger inferieure - survente technique")
        elif technical.bollinger_position == "above_upper":
            score -= 15
            cons.append("Prix au-dessus bande Bollinger superieure - surachat")

        # === Analyse Sentiment (10% du score) ===
        if sentiment.sentiment_label == "bullish":
            score += 10
            pros.append(f"Sentiment marche positif ({sentiment.sentiment_score:.2f})")
        elif sentiment.sentiment_label == "bearish":
            score -= 10
            cons.append(f"Sentiment marche negatif ({sentiment.sentiment_score:.2f})")

        # === Proximite des niveaux cles ===
        if technical.support_levels:
            nearest_support = max((s for s in technical.support_levels if s < price.current_price), default=0)
            if nearest_support > 0:
                distance_to_support = ((price.current_price - nearest_support) / price.current_price) * 100
                if distance_to_support < 3:
                    score += 15
                    pros.append(f"Proche d'un support ({nearest_support:.2f}) - bon point d'entree")

        # === Volatilite ===
        if technical.atr_percent > 5:
            cons.append(f"Volatilite elevee (ATR {technical.atr_percent:.1f}%) - risque accru")
        elif technical.atr_percent < 2:
            reasoning.append(f"Faible volatilite (ATR {technical.atr_percent:.1f}%)")

        # === 52-week position ===
        if price.week_52_high and price.week_52_low:
            range_52w = price.week_52_high - price.week_52_low
            position_in_range = (price.current_price - price.week_52_low) / range_52w if range_52w > 0 else 0.5
            if position_in_range < 0.3:
                score += 10
                pros.append(f"Dans le bas de la fourchette 52 semaines ({position_in_range*100:.0f}%)")
            elif position_in_range > 0.9:
                score -= 10
                cons.append(f"Proche du plus haut 52 semaines ({position_in_range*100:.0f}%)")

        # === Determiner l'action finale ===
        confidence = min(abs(score), 100)

        if score >= 40:
            action = "BUY"
            rating = 5
            reasoning.insert(0, "Signal d'achat fort - conditions favorables")
        elif score >= 20:
            action = "BUY"
            rating = 4
            reasoning.insert(0, "Signal d'achat modere - bonnes conditions")
        elif score >= 0:
            action = "WAIT"
            rating = 3
            reasoning.insert(0, "Conditions mitigees - attendre une meilleure opportunite")
        elif score >= -20:
            action = "WAIT"
            rating = 2
            reasoning.insert(0, "Conditions defavorables - prudence recommandee")
        else:
            action = "AVOID"
            rating = 1
            reasoning.insert(0, "Conditions tres defavorables - eviter l'achat")

        return BuyRecommendation(
            action=action,
            confidence=confidence,
            rating=rating,
            reasoning=reasoning,
            pros=pros,
            cons=cons,
        )

    def _default_info(self, symbol: str) -> InstrumentInfo:
        """Info par defaut si non disponible."""
        return InstrumentInfo(
            symbol=symbol,
            name=symbol,
            currency="USD",
        )

    def _default_sentiment(self, symbol: str) -> SentimentAnalysis:
        """Sentiment par defaut si non disponible."""
        return SentimentAnalysis(
            sentiment_score=0.0,
            sentiment_label="unknown",
            news_count=0,
            recent_headlines=[],
        )


# Factory
def get_instrument_analysis_service() -> InstrumentAnalysisService:
    """Factory pour creer le service d'analyse."""
    return InstrumentAnalysisService()
