"""
Moteur de recommandation d'investissement.

Ce module implémente l'algorithme principal d'aide à la décision
qui analyse les actifs et génère des recommandations professionnelles.

ALGORITHME DE SCORING (Méthode "Smart Alpha"):
=============================================

1. SCORE PERFORMANCE (25%)
   - Résilience multi-période (3M, 6M, 1Y, 3Y, 5Y)
   - Bonus si toutes périodes positives
   - Pénalité pour volatilité excessive

2. SCORE TECHNIQUE (20%)
   - RSI dans zone favorable
   - MACD avec signal positif
   - Position dans les bandes de Bollinger

3. SCORE MOMENTUM (15%)
   - Tendance des moyennes mobiles
   - Force relative du mouvement
   - Volume confirmant le mouvement

4. SCORE VOLATILITÉ (15%) - Inversé
   - Faible volatilité = score élevé
   - ATR raisonnable
   - Stabilité historique

5. SCORE FONDAMENTAL (15%)
   - Rendement dividende
   - Secteur porteur
   - Type d'actif

6. SCORE TIMING (10%)
   - Position par rapport aux supports/résistances
   - Signaux de retournement
   - Momentum court terme

UTILISATION:
    engine = RecommendationEngine(provider, calculator)
    recommendation = await engine.analyze_and_recommend("AAPL")
    screener_results = await engine.screen_market(["AAPL", "MSFT", "GOOGL"])
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

import numpy as np

from src.application.interfaces.stock_data_provider import StockDataProvider
from src.application.services.technical_calculator import TechnicalCalculator
from src.domain.entities.stock import StockAnalysis, PerformanceData
from src.domain.entities.technical_analysis import (
    Signal,
    Trend,
    TimeHorizon,
    TechnicalIndicators,
)
from src.domain.entities.investment_recommendation import (
    RecommendationType,
    InvestmentCategory,
    RiskLevel,
    ScoreBreakdown,
    PriceTarget,
    InvestmentRecommendation,
    PortfolioRecommendation,
    MarketScreenerResult,
)
from src.domain.value_objects.ticker import Ticker
from src.config.constants import (
    PERIOD_5_YEARS_DAYS,
    HIGH_VOLATILITY_THRESHOLD,
    LOW_VOLATILITY_THRESHOLD,
    AssetType,
)

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Moteur de recommandation d'investissement.

    Combine l'analyse fondamentale, technique et quantitative
    pour générer des recommandations professionnelles.
    """

    # Secteurs considérés comme porteurs (mise à jour régulièrement)
    BULLISH_SECTORS = [
        "Technology", "Healthcare", "Consumer Cyclical",
        "Communication Services", "Industrials"
    ]

    # Secteurs défensifs
    DEFENSIVE_SECTORS = [
        "Consumer Defensive", "Utilities", "Healthcare",
        "Real Estate"
    ]

    def __init__(
        self,
        data_provider: StockDataProvider,
        technical_calculator: TechnicalCalculator,
    ):
        """
        Initialise le moteur de recommandation.

        Args:
            data_provider: Provider de données boursières
            technical_calculator: Calculateur d'indicateurs techniques
        """
        self._provider = data_provider
        self._calculator = technical_calculator

    async def analyze_and_recommend(
        self,
        ticker: str,
        stock_analysis: Optional[StockAnalysis] = None,
    ) -> Optional[InvestmentRecommendation]:
        """
        Analyse un actif et génère une recommandation complète.

        Args:
            ticker: Symbole de l'actif
            stock_analysis: Analyse existante (optionnel)

        Returns:
            Recommandation complète ou None si erreur
        """
        try:
            logger.info(f"Analyzing {ticker} for investment recommendation")

            # 1. Récupérer les données historiques
            ticker_obj = Ticker(ticker)
            historical_data = await self._provider.get_historical_data(
                ticker_obj, PERIOD_5_YEARS_DAYS
            )

            if len(historical_data) < 50:
                logger.warning(f"Insufficient data for {ticker}")
                return None

            # 2. Récupérer les métadonnées
            metadata = await self._provider.get_metadata(ticker_obj)

            # 3. Calculer les indicateurs techniques
            technical = await self._calculator.calculate_all(ticker, historical_data)
            if not technical:
                logger.warning(f"Could not calculate technical indicators for {ticker}")
                return None

            # 4. Calculer les performances si non fournies
            if stock_analysis is None:
                performances = await self._calculate_performances(ticker_obj)
                volatility = await self._provider.calculate_volatility(ticker_obj)
            else:
                performances = stock_analysis.performances
                volatility = stock_analysis.volatility.as_decimal if stock_analysis.volatility else None

            # 5. Calculer le score breakdown
            score_breakdown = self._calculate_score_breakdown(
                performances=performances,
                technical=technical,
                volatility=volatility,
                dividend_yield=metadata.dividend_yield,
                sector=metadata.sector,
                asset_type=metadata.asset_type,
            )

            # 6. Déterminer la recommandation
            recommendation_type = self._determine_recommendation(
                score_breakdown.total_score,
                technical,
            )

            # 7. Catégoriser l'investissement
            category = self._categorize_investment(
                performances=performances,
                technical=technical,
                volatility=volatility,
                dividend_yield=metadata.dividend_yield,
                sector=metadata.sector,
            )

            # 8. Évaluer le risque
            risk_level = self._evaluate_risk(
                volatility=volatility,
                technical=technical,
                asset_type=metadata.asset_type,
            )

            # 9. Calculer les objectifs de prix
            current_price = historical_data[-1].close
            price_targets = self._calculate_price_targets(
                current_price=current_price,
                technical=technical,
                volatility=volatility or 0.2,
            )

            # 10. Générer les insights
            key_insights = self._generate_insights(
                technical=technical,
                performances=performances,
                score_breakdown=score_breakdown,
            )

            risks = self._identify_risks(
                technical=technical,
                volatility=volatility,
                performances=performances,
            )

            catalysts = self._identify_catalysts(
                technical=technical,
                sector=metadata.sector,
            )

            # 11. Générer les perspectives par horizon
            outlooks = self._generate_outlooks(technical, performances)

            # 12. Stratégie d'entrée
            entry_strategy = self._suggest_entry_strategy(
                technical=technical,
                current_price=current_price,
            )

            # Calculer la confiance
            confidence = self._calculate_confidence(
                score_breakdown=score_breakdown,
                technical=technical,
            )

            return InvestmentRecommendation(
                ticker=ticker,
                name=metadata.name,
                asset_type=metadata.asset_type.value,
                sector=metadata.sector,
                score_breakdown=score_breakdown,
                recommendation=recommendation_type,
                category=category,
                risk_level=risk_level,
                confidence=confidence,
                short_term_outlook=outlooks["short"],
                medium_term_outlook=outlooks["medium"],
                long_term_outlook=outlooks["long"],
                price_targets=price_targets,
                key_insights=key_insights,
                risks=risks,
                catalysts=catalysts,
                technical_summary=self._generate_technical_summary(technical),
                entry_strategy=entry_strategy,
            )

        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return None

    async def screen_market(
        self,
        tickers: List[str],
        min_score: float = 0,
    ) -> MarketScreenerResult:
        """
        Screen un ensemble d'actifs et retourne les meilleures opportunités.

        Args:
            tickers: Liste de symboles à analyser
            min_score: Score minimum pour inclusion

        Returns:
            Résultats du screening avec classements
        """
        logger.info(f"Screening {len(tickers)} tickers")

        recommendations: List[InvestmentRecommendation] = []
        buy_count = 0
        sell_count = 0
        neutral_count = 0

        for ticker in tickers:
            try:
                rec = await self.analyze_and_recommend(ticker)
                if rec and rec.overall_score >= min_score:
                    recommendations.append(rec)

                    # Compter les signaux
                    if rec.recommendation in [RecommendationType.STRONG_BUY, RecommendationType.BUY, RecommendationType.ACCUMULATE]:
                        buy_count += 1
                    elif rec.recommendation in [RecommendationType.STRONG_SELL, RecommendationType.SELL, RecommendationType.AVOID]:
                        sell_count += 1
                    else:
                        neutral_count += 1

            except Exception as e:
                logger.warning(f"Error screening {ticker}: {e}")
                continue

        # Trier par score global
        sorted_by_score = sorted(recommendations, key=lambda r: r.overall_score, reverse=True)

        # Trier par momentum
        sorted_by_momentum = sorted(
            recommendations,
            key=lambda r: r.score_breakdown.momentum_score,
            reverse=True
        )

        # Identifier les surventes (potentiels rebonds)
        oversold = [
            r for r in recommendations
            if r.score_breakdown.timing_score > 70
            and r.score_breakdown.momentum_score < 40
        ]

        # Identifier les candidats à la rupture (breakout)
        breakouts = [
            r for r in recommendations
            if r.score_breakdown.momentum_score > 70
            and r.score_breakdown.technical_score > 60
        ]

        # Signaux forts
        strong_buys = [r for r in recommendations if r.recommendation == RecommendationType.STRONG_BUY]
        strong_sells = [r for r in recommendations if r.recommendation == RecommendationType.STRONG_SELL]

        return MarketScreenerResult(
            best_overall=sorted_by_score[:20],
            best_momentum=sorted_by_momentum[:20],
            best_value=[r for r in sorted_by_score if r.category == InvestmentCategory.VALUE][:20],
            oversold_bounces=oversold[:10],
            breakout_candidates=breakouts[:10],
            strong_buy_signals=strong_buys,
            strong_sell_signals=strong_sells,
            total_analyzed=len(tickers),
            buy_count=buy_count,
            sell_count=sell_count,
            neutral_count=neutral_count,
        )

    async def get_portfolio_recommendations(
        self,
        tickers: List[str],
    ) -> PortfolioRecommendation:
        """
        Génère des recommandations pour construire un portefeuille optimal.

        Args:
            tickers: Liste d'actifs à analyser

        Returns:
            Recommandations de portefeuille
        """
        logger.info(f"Generating portfolio recommendations for {len(tickers)} tickers")

        recommendations: List[InvestmentRecommendation] = []

        for ticker in tickers:
            try:
                rec = await self.analyze_and_recommend(ticker)
                if rec:
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"Error analyzing {ticker}: {e}")

        # Catégoriser
        growth = [r for r in recommendations if r.category == InvestmentCategory.GROWTH]
        value = [r for r in recommendations if r.category == InvestmentCategory.VALUE]
        dividend = [r for r in recommendations if r.category == InvestmentCategory.DIVIDEND]
        momentum = [r for r in recommendations if r.category == InvestmentCategory.MOMENTUM]
        defensive = [r for r in recommendations if r.category == InvestmentCategory.DEFENSIVE]

        # Trier par score
        growth.sort(key=lambda r: r.overall_score, reverse=True)
        value.sort(key=lambda r: r.overall_score, reverse=True)
        dividend.sort(key=lambda r: r.overall_score, reverse=True)
        momentum.sort(key=lambda r: r.overall_score, reverse=True)
        defensive.sort(key=lambda r: r.overall_score, reverse=True)

        # Identifier les ETFs
        etfs: Dict[str, List[InvestmentRecommendation]] = {}
        for rec in recommendations:
            if rec.asset_type == "etf":
                sector = rec.sector or "General"
                if sector not in etfs:
                    etfs[sector] = []
                etfs[sector].append(rec)

        # Allocation suggérée basée sur le sentiment du marché
        avg_momentum = np.mean([r.score_breakdown.momentum_score for r in recommendations]) if recommendations else 50

        if avg_momentum > 60:
            # Marché haussier - plus agressif
            allocation = {
                "growth": 0.30,
                "momentum": 0.25,
                "value": 0.20,
                "dividend": 0.15,
                "defensive": 0.10,
            }
            market_sentiment = "Haussier - Favoriser la croissance et le momentum"
            market_trend = Trend.UPTREND
        elif avg_momentum < 40:
            # Marché baissier - plus défensif
            allocation = {
                "defensive": 0.30,
                "dividend": 0.25,
                "value": 0.25,
                "growth": 0.15,
                "momentum": 0.05,
            }
            market_sentiment = "Baissier - Privilégier les actifs défensifs"
            market_trend = Trend.DOWNTREND
        else:
            # Marché neutre - équilibré
            allocation = {
                "growth": 0.25,
                "value": 0.25,
                "dividend": 0.20,
                "defensive": 0.20,
                "momentum": 0.10,
            }
            market_sentiment = "Neutre - Allocation équilibrée recommandée"
            market_trend = Trend.SIDEWAYS

        # Liste à éviter
        avoid_list = [
            r.ticker for r in recommendations
            if r.recommendation in [RecommendationType.STRONG_SELL, RecommendationType.AVOID]
        ]

        # Opportunités émergentes
        emerging = []
        for rec in recommendations:
            if (rec.overall_score > 70 and
                rec.score_breakdown.momentum_score > 60 and
                rec.risk_level in [RiskLevel.MEDIUM, RiskLevel.LOW]):
                emerging.append({
                    "ticker": rec.ticker,
                    "name": rec.name,
                    "score": rec.overall_score,
                    "reason": "Score élevé avec momentum positif et risque maîtrisé",
                })

        return PortfolioRecommendation(
            top_growth=growth[:10],
            top_value=value[:10],
            top_dividend=dividend[:10],
            top_momentum=momentum[:10],
            top_defensive=defensive[:10],
            recommended_etfs=etfs,
            suggested_allocation=allocation,
            avoid_list=avoid_list,
            emerging_opportunities=emerging[:5],
            market_sentiment=market_sentiment,
            market_trend=market_trend,
        )

    # =========================================================================
    # MÉTHODES DE CALCUL PRIVÉES
    # =========================================================================

    async def _calculate_performances(self, ticker: Ticker) -> PerformanceData:
        """Calcule les performances sur différentes périodes."""
        from src.domain.value_objects.percentage import Percentage

        periods = [90, 180, 365, 1095, 1825]
        perfs = {}

        for days in periods:
            try:
                data = await self._provider.get_historical_data(ticker, days)
                if len(data) >= 2:
                    start_price = data[0].close
                    end_price = data[-1].close
                    perf = ((end_price - start_price) / start_price) * 100
                    perfs[days] = Percentage.from_percent(perf)
                else:
                    perfs[days] = None
            except Exception:
                perfs[days] = None

        return PerformanceData(
            perf_3m=perfs.get(90),
            perf_6m=perfs.get(180),
            perf_1y=perfs.get(365),
            perf_3y=perfs.get(1095),
            perf_5y=perfs.get(1825),
        )

    def _calculate_score_breakdown(
        self,
        performances: PerformanceData,
        technical: TechnicalIndicators,
        volatility: Optional[float],
        dividend_yield: Optional[float],
        sector: Optional[str],
        asset_type: AssetType,
    ) -> ScoreBreakdown:
        """Calcule le score détaillé."""

        # 1. Score Performance (0-100)
        performance_score = self._calc_performance_score(performances)

        # 2. Score Technique (0-100)
        technical_score = self._calc_technical_score(technical)

        # 3. Score Momentum (0-100)
        momentum_score = self._calc_momentum_score(technical, performances)

        # 4. Score Volatilité (0-100, inversé)
        volatility_score = self._calc_volatility_score(volatility)

        # 5. Score Fondamental (0-100)
        fundamental_score = self._calc_fundamental_score(
            dividend_yield, sector, asset_type
        )

        # 6. Score Timing (0-100)
        timing_score = self._calc_timing_score(technical)

        return ScoreBreakdown(
            performance_score=performance_score,
            technical_score=technical_score,
            momentum_score=momentum_score,
            volatility_score=volatility_score,
            fundamental_score=fundamental_score,
            timing_score=timing_score,
        )

    def _calc_performance_score(self, performances: PerformanceData) -> float:
        """Score basé sur les performances historiques."""
        score = 50.0  # Base neutre

        available = performances.available_periods
        if not available:
            return score

        # Bonus pour chaque période positive
        for period, perf in available.items():
            if perf.is_positive:
                score += 10
                # Bonus supplémentaire pour forte performance
                if perf.as_percent > 20:
                    score += 5
                elif perf.as_percent > 10:
                    score += 2
            else:
                score -= 5
                # Pénalité supplémentaire pour forte baisse
                if perf.as_percent < -20:
                    score -= 5

        # Bonus résilience (toutes périodes positives)
        if performances.all_positive:
            score += 15

        return max(0, min(100, score))

    def _calc_technical_score(self, technical: TechnicalIndicators) -> float:
        """Score basé sur les indicateurs techniques."""
        score = 50.0

        signal_scores = {
            Signal.STRONG_BUY: 20,
            Signal.BUY: 10,
            Signal.NEUTRAL: 0,
            Signal.SELL: -10,
            Signal.STRONG_SELL: -20,
        }

        # RSI
        score += signal_scores[technical.rsi.signal]

        # MACD
        score += signal_scores[technical.macd.signal]

        # Moyennes mobiles
        score += signal_scores[technical.moving_averages.signal]

        # Bollinger
        score += signal_scores[technical.bollinger.signal] * 0.5

        return max(0, min(100, score))

    def _calc_momentum_score(
        self,
        technical: TechnicalIndicators,
        performances: PerformanceData,
    ) -> float:
        """Score de momentum."""
        score = 50.0

        # Tendance des MAs
        trend = technical.moving_averages.trend
        trend_scores = {
            Trend.STRONG_UPTREND: 25,
            Trend.UPTREND: 15,
            Trend.SIDEWAYS: 0,
            Trend.DOWNTREND: -15,
            Trend.STRONG_DOWNTREND: -25,
        }
        score += trend_scores.get(trend, 0)

        # MACD histogram (momentum)
        if technical.macd.histogram > 0:
            score += 10
        else:
            score -= 10

        # RSI momentum (entre 50-70 = bon momentum)
        if 50 <= technical.rsi.value <= 70:
            score += 10
        elif technical.rsi.value > 70:
            score += 5  # Suracheté mais momentum fort
        elif technical.rsi.value < 30:
            score -= 5

        # Performance court terme
        if performances.perf_3m and performances.perf_3m.is_positive:
            score += 5

        return max(0, min(100, score))

    def _calc_volatility_score(self, volatility: Optional[float]) -> float:
        """Score de volatilité (inversé: faible vol = score élevé)."""
        if volatility is None:
            return 50.0

        # Volatilité en décimal (ex: 0.25 = 25%)
        if volatility < 0.15:
            return 90.0  # Très stable
        elif volatility < 0.20:
            return 75.0  # Stable
        elif volatility < 0.30:
            return 55.0  # Modéré
        elif volatility < 0.40:
            return 35.0  # Élevé
        else:
            return 15.0  # Très élevé

    def _calc_fundamental_score(
        self,
        dividend_yield: Optional[float],
        sector: Optional[str],
        asset_type: AssetType,
    ) -> float:
        """Score fondamental."""
        score = 50.0

        # Dividende
        if dividend_yield:
            if dividend_yield > 4:
                score += 15
            elif dividend_yield > 2:
                score += 10
            elif dividend_yield > 1:
                score += 5

        # Secteur porteur
        if sector in self.BULLISH_SECTORS:
            score += 10
        elif sector in self.DEFENSIVE_SECTORS:
            score += 5

        # Type d'actif
        if asset_type == AssetType.ETF:
            score += 5  # Diversification

        return max(0, min(100, score))

    def _calc_timing_score(self, technical: TechnicalIndicators) -> float:
        """Score de timing d'entrée."""
        score = 50.0

        # Position dans Bollinger
        percent_b = technical.bollinger.percent_b
        if percent_b <= 0.2:
            score += 25  # Près du support
        elif percent_b >= 0.8:
            score -= 15  # Près de la résistance
        elif 0.4 <= percent_b <= 0.6:
            score += 5  # Zone neutre, pas mauvais

        # RSI survendu = bon timing d'achat
        if technical.rsi.value <= 30:
            score += 20
        elif technical.rsi.value >= 70:
            score -= 10

        # Volume confirmant
        if technical.volume.volume_confirmation:
            score += 10

        return max(0, min(100, score))

    def _determine_recommendation(
        self,
        total_score: float,
        technical: TechnicalIndicators,
    ) -> RecommendationType:
        """Détermine le type de recommandation."""

        # Basé sur le score global
        if total_score >= 80:
            return RecommendationType.STRONG_BUY
        elif total_score >= 70:
            return RecommendationType.BUY
        elif total_score >= 60:
            return RecommendationType.ACCUMULATE
        elif total_score >= 45:
            return RecommendationType.HOLD
        elif total_score >= 35:
            return RecommendationType.REDUCE
        elif total_score >= 25:
            return RecommendationType.SELL
        elif total_score >= 15:
            return RecommendationType.STRONG_SELL
        else:
            return RecommendationType.AVOID

    def _categorize_investment(
        self,
        performances: PerformanceData,
        technical: TechnicalIndicators,
        volatility: Optional[float],
        dividend_yield: Optional[float],
        sector: Optional[str],
    ) -> InvestmentCategory:
        """Catégorise le type d'investissement."""

        # Momentum fort
        if (technical.moving_averages.trend in [Trend.STRONG_UPTREND, Trend.UPTREND] and
            technical.macd.histogram > 0):
            return InvestmentCategory.MOMENTUM

        # Dividende élevé
        if dividend_yield and dividend_yield > 3:
            return InvestmentCategory.DIVIDEND

        # Défensif (faible vol + secteur défensif)
        if volatility and volatility < 0.20 and sector in self.DEFENSIVE_SECTORS:
            return InvestmentCategory.DEFENSIVE

        # Growth (forte perf, secteur tech)
        if (performances.perf_1y and performances.perf_1y.as_percent > 20 and
            sector in ["Technology", "Healthcare"]):
            return InvestmentCategory.GROWTH

        # Value (survendu avec fondamentaux ok)
        if technical.rsi.value < 40 and performances.perf_5y and performances.perf_5y.is_positive:
            return InvestmentCategory.VALUE

        # Par défaut selon momentum
        if technical.moving_averages.trend == Trend.UPTREND:
            return InvestmentCategory.GROWTH
        elif technical.moving_averages.trend == Trend.DOWNTREND:
            return InvestmentCategory.VALUE

        return InvestmentCategory.VALUE

    def _evaluate_risk(
        self,
        volatility: Optional[float],
        technical: TechnicalIndicators,
        asset_type: AssetType,
    ) -> RiskLevel:
        """Évalue le niveau de risque."""

        risk_score = 50  # Base

        # Volatilité
        if volatility:
            if volatility > 0.40:
                risk_score += 30
            elif volatility > 0.30:
                risk_score += 20
            elif volatility > 0.20:
                risk_score += 10
            elif volatility < 0.15:
                risk_score -= 15

        # Type d'actif
        if asset_type == AssetType.CRYPTO:
            risk_score += 25
        elif asset_type == AssetType.ETF:
            risk_score -= 10

        # ATR élevé
        if technical.atr_percent > 5:
            risk_score += 15
        elif technical.atr_percent > 3:
            risk_score += 5

        # Classification
        if risk_score >= 80:
            return RiskLevel.VERY_HIGH
        elif risk_score >= 60:
            return RiskLevel.HIGH
        elif risk_score >= 40:
            return RiskLevel.MEDIUM
        elif risk_score >= 20:
            return RiskLevel.LOW
        return RiskLevel.VERY_LOW

    def _calculate_price_targets(
        self,
        current_price: float,
        technical: TechnicalIndicators,
        volatility: float,
    ) -> Dict[str, PriceTarget]:
        """Calcule les objectifs de prix par horizon."""

        targets = {}

        # Court terme (6 mois) - basé sur Bollinger et ATR
        short_target = technical.bollinger.upper_band
        short_stop = max(
            technical.bollinger.lower_band,
            current_price * (1 - volatility)
        )
        short_return = ((short_target - current_price) / current_price) * 100
        short_rr = abs(short_return) / abs((current_price - short_stop) / current_price * 100) if short_stop != current_price else 1

        targets["short_term"] = PriceTarget(
            target_price=short_target,
            current_price=current_price,
            potential_return=short_return,
            stop_loss=short_stop,
            risk_reward_ratio=short_rr,
            horizon=TimeHorizon.SHORT_TERM,
        )

        # Moyen terme (1-2 ans) - basé sur tendance + marge
        if technical.moving_averages.trend in [Trend.STRONG_UPTREND, Trend.UPTREND]:
            medium_target = current_price * 1.25  # +25%
        elif technical.moving_averages.trend in [Trend.DOWNTREND, Trend.STRONG_DOWNTREND]:
            medium_target = current_price * 1.10  # +10%
        else:
            medium_target = current_price * 1.15  # +15%

        medium_stop = current_price * (1 - min(volatility * 1.5, 0.20))
        medium_return = ((medium_target - current_price) / current_price) * 100
        medium_rr = abs(medium_return) / abs((current_price - medium_stop) / current_price * 100) if medium_stop != current_price else 1

        targets["medium_term"] = PriceTarget(
            target_price=medium_target,
            current_price=current_price,
            potential_return=medium_return,
            stop_loss=medium_stop,
            risk_reward_ratio=medium_rr,
            horizon=TimeHorizon.MEDIUM_TERM,
        )

        # Long terme (5 ans) - projection basée sur historique
        if technical.moving_averages.trend == Trend.STRONG_UPTREND:
            long_target = current_price * 2.0  # x2
        elif technical.moving_averages.trend == Trend.UPTREND:
            long_target = current_price * 1.6  # +60%
        else:
            long_target = current_price * 1.3  # +30%

        long_stop = current_price * 0.70  # -30% stop
        long_return = ((long_target - current_price) / current_price) * 100
        long_rr = abs(long_return) / abs((current_price - long_stop) / current_price * 100) if long_stop != current_price else 1

        targets["long_term"] = PriceTarget(
            target_price=long_target,
            current_price=current_price,
            potential_return=long_return,
            stop_loss=long_stop,
            risk_reward_ratio=long_rr,
            horizon=TimeHorizon.LONG_TERM,
        )

        return targets

    def _generate_insights(
        self,
        technical: TechnicalIndicators,
        performances: PerformanceData,
        score_breakdown: ScoreBreakdown,
    ) -> List[str]:
        """Génère les insights clés."""
        insights = []

        # Performance
        if performances.all_positive:
            insights.append("Actif résilient : performances positives sur toutes les périodes")

        if score_breakdown.total_score >= 70:
            insights.append(f"Score global excellent ({score_breakdown.total_score:.0f}/100)")

        # Technique
        if technical.overall_signal in [Signal.STRONG_BUY, Signal.BUY]:
            insights.append("Signaux techniques favorables alignés")

        if technical.moving_averages.trend == Trend.STRONG_UPTREND:
            insights.append("Tendance haussière forte confirmée par les MAs")

        # Timing
        if technical.bollinger.percent_b < 0.3:
            insights.append("Prix proche du support - point d'entrée potentiel")

        if technical.volume.volume_confirmation:
            insights.append("Volume confirme le mouvement actuel")

        return insights[:5]

    def _identify_risks(
        self,
        technical: TechnicalIndicators,
        volatility: Optional[float],
        performances: PerformanceData,
    ) -> List[str]:
        """Identifie les risques."""
        risks = []

        if volatility and volatility > HIGH_VOLATILITY_THRESHOLD:
            risks.append(f"Volatilité élevée ({volatility*100:.1f}%)")

        if technical.rsi.value > 70:
            risks.append("RSI suracheté - risque de correction")

        if technical.bollinger.percent_b > 0.95:
            risks.append("Prix au sommet des bandes de Bollinger")

        if technical.moving_averages.trend in [Trend.DOWNTREND, Trend.STRONG_DOWNTREND]:
            risks.append("Tendance baissière en cours")

        if not technical.volume.volume_confirmation:
            risks.append("Volume faible - manque de conviction")

        if performances.perf_3m and performances.perf_3m.as_percent < -10:
            risks.append("Performance court terme négative")

        return risks[:5]

    def _identify_catalysts(
        self,
        technical: TechnicalIndicators,
        sector: Optional[str],
    ) -> List[str]:
        """Identifie les catalyseurs potentiels."""
        catalysts = []

        if technical.macd.histogram > 0 and technical.macd.macd_line < 0:
            catalysts.append("Croisement MACD haussier en formation")

        if technical.rsi.value < 35:
            catalysts.append("RSI survendu - rebond technique possible")

        if technical.bollinger.bandwidth < 0.05:
            catalysts.append("Squeeze Bollinger - explosion de volatilité attendue")

        if sector in self.BULLISH_SECTORS:
            catalysts.append(f"Secteur {sector} en tendance positive")

        if technical.volume.on_balance_volume_trend == "rising":
            catalysts.append("Accumulation détectée (OBV en hausse)")

        return catalysts[:4]

    def _generate_outlooks(
        self,
        technical: TechnicalIndicators,
        performances: PerformanceData,
    ) -> Dict[str, str]:
        """Génère les perspectives par horizon."""

        # Court terme
        if technical.overall_signal == Signal.STRONG_BUY:
            short = "Très favorable - Momentum positif et signaux alignés"
        elif technical.overall_signal == Signal.BUY:
            short = "Favorable - Tendance positive à court terme"
        elif technical.overall_signal == Signal.SELL:
            short = "Défavorable - Pression vendeuse"
        elif technical.overall_signal == Signal.STRONG_SELL:
            short = "Très défavorable - Forte pression baissière"
        else:
            short = "Neutre - Consolidation probable"

        # Moyen terme
        trend = technical.moving_averages.trend
        if trend == Trend.STRONG_UPTREND:
            medium = "Excellent - Tendance haussière forte établie"
        elif trend == Trend.UPTREND:
            medium = "Positif - Tendance favorable maintenue"
        elif trend == Trend.DOWNTREND:
            medium = "Négatif - Tendance baissière en place"
        elif trend == Trend.STRONG_DOWNTREND:
            medium = "Très négatif - Tendance baissière prononcée"
        else:
            medium = "Incertain - Marché en consolidation"

        # Long terme
        if performances.all_positive:
            long = "Excellent - Historique de croissance solide"
        elif performances.perf_5y and performances.perf_5y.is_positive:
            long = "Positif - Performance long terme satisfaisante"
        elif performances.perf_5y and performances.perf_5y.as_percent < -20:
            long = "Prudence - Sous-performance historique"
        else:
            long = "Modéré - Performance mitigée sur le long terme"

        return {"short": short, "medium": medium, "long": long}

    def _generate_technical_summary(self, technical: TechnicalIndicators) -> str:
        """Génère un résumé technique."""
        parts = []

        parts.append(f"RSI: {technical.rsi.value:.0f} ({technical.rsi.interpretation})")
        parts.append(f"MACD: {technical.macd.interpretation}")
        parts.append(f"Tendance: {technical.moving_averages.trend.value}")
        parts.append(f"Volatilité: {technical.bollinger.volatility_state}")

        return " | ".join(parts)

    def _suggest_entry_strategy(
        self,
        technical: TechnicalIndicators,
        current_price: float,
    ) -> str:
        """Suggère une stratégie d'entrée."""

        if technical.bollinger.percent_b < 0.2:
            return f"Entrée agressive : Achat maintenant près du support ({current_price:.2f})"
        elif technical.bollinger.percent_b < 0.4:
            return f"Entrée standard : Achat progressif autour de {current_price:.2f}"
        elif technical.rsi.value < 40:
            support = technical.moving_averages.sma_50
            return f"Attendre : Acheter sur repli vers SMA50 ({support:.2f})"
        elif technical.rsi.value > 70:
            return "Patience : Attendre une correction pour entrer"
        else:
            entry_zone = technical.bollinger.middle_band
            return f"Entrée modérée : Acheter par tranches autour de {entry_zone:.2f}"

    def _calculate_confidence(
        self,
        score_breakdown: ScoreBreakdown,
        technical: TechnicalIndicators,
    ) -> float:
        """Calcule le niveau de confiance dans la recommandation."""

        confidence = 50.0

        # Plus les indicateurs sont alignés, plus la confiance est haute
        if technical.confidence_level == "Haute":
            confidence += 25
        elif technical.confidence_level == "Moyenne":
            confidence += 10

        # Score total élevé ou très bas = plus de confiance
        total = score_breakdown.total_score
        if total > 75 or total < 25:
            confidence += 15
        elif total > 65 or total < 35:
            confidence += 5

        # Peu de faiblesses = confiance
        if len(score_breakdown.weaknesses) == 0:
            confidence += 10
        elif len(score_breakdown.weaknesses) >= 3:
            confidence -= 10

        return max(30, min(95, confidence))


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_recommendation_engine(
    data_provider: StockDataProvider,
    technical_calculator: TechnicalCalculator,
) -> RecommendationEngine:
    """Factory function pour créer le moteur de recommandation."""
    return RecommendationEngine(
        data_provider=data_provider,
        technical_calculator=technical_calculator,
    )
