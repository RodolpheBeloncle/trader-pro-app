"""
Use Case : Analyse d'un stock.

Orchestre l'analyse complète d'un ticker:
- Récupération des données historiques
- Calcul des performances sur plusieurs périodes
- Calcul de la volatilité
- Détermination de la résilience
- Génération des données pour graphiques

ARCHITECTURE:
- Dépend uniquement des interfaces (StockDataProvider)
- Retourne des DTOs ou entités du domaine
- Pas de dépendance vers l'infrastructure

UTILISATION:
    use_case = AnalyzeStockUseCase(yahoo_provider)
    result = await use_case.execute("AAPL")
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from src.application.interfaces.stock_data_provider import (
    StockDataProvider,
    HistoricalDataPoint,
)
from src.config.constants import (
    PERIOD_3_MONTHS_DAYS,
    PERIOD_6_MONTHS_DAYS,
    PERIOD_1_YEAR_DAYS,
    PERIOD_3_YEARS_DAYS,
    PERIOD_5_YEARS_DAYS,
    HIGH_VOLATILITY_THRESHOLD,
    MEDIUM_VOLATILITY_THRESHOLD,
    VolatilityLevel,
)
from src.domain.entities.stock import (
    StockAnalysis,
    StockInfo,
    PerformanceData,
    ChartDataPoint,
)
from src.domain.exceptions import (
    TickerNotFoundError,
    DataFetchError,
    AnalysisError,
)
from src.domain.value_objects.ticker import Ticker
from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage

logger = logging.getLogger(__name__)


@dataclass
class AnalyzeStockResult:
    """Résultat de l'analyse d'un stock."""

    analysis: Optional[StockAnalysis]
    error: Optional[str]
    ticker: str

    @property
    def is_success(self) -> bool:
        """Indique si l'analyse a réussi."""
        return self.analysis is not None and self.error is None


class AnalyzeStockUseCase:
    """
    Use Case pour analyser un stock.

    Implémente la méthodologie "trader writer":
    - Calcul des performances sur 5 périodes (3m, 6m, 1y, 3y, 5y)
    - Un stock est "résilient" si positif sur TOUTES les périodes
    - Calcul de la volatilité annualisée

    Attributes:
        provider: Fournisseur de données de marché
    """

    def __init__(self, provider: StockDataProvider):
        """
        Initialise le use case.

        Args:
            provider: Fournisseur de données (Yahoo, etc.)
        """
        self.provider = provider

    async def execute(self, ticker_str: str) -> AnalyzeStockResult:
        """
        Analyse un stock.

        Args:
            ticker_str: Symbole du ticker (ex: "AAPL")

        Returns:
            AnalyzeStockResult avec l'analyse ou l'erreur
        """
        try:
            # Valider le ticker
            ticker = Ticker(ticker_str)

            logger.info(f"Analyzing {ticker.value}...")

            # Récupérer les métadonnées
            metadata = await self.provider.get_metadata(ticker)

            # Récupérer 5 ans d'historique pour les calculs
            historical_data = await self.provider.get_historical_data(
                ticker,
                days=PERIOD_5_YEARS_DAYS + 30,  # Marge de sécurité
            )

            if len(historical_data) < 20:
                raise AnalysisError(
                    ticker.value,
                    "Données historiques insuffisantes pour l'analyse"
                )

            # Calculer les performances
            performances = self._calculate_performances(historical_data)

            # Calculer la volatilité
            volatility = await self.provider.calculate_volatility(ticker)

            # Déterminer le niveau de volatilité
            volatility_level = self._determine_volatility_level(volatility)

            # Récupérer le prix actuel
            quote = await self.provider.get_current_quote(ticker)

            # Générer les données du graphique (échantillonnage hebdomadaire)
            chart_data = self._generate_chart_data(historical_data)

            # Calculer le score
            score = self._calculate_score(performances, volatility)

            # Construire l'analyse
            # Convertir le dividend yield en Percentage si disponible
            dividend_yield_pct = None
            if metadata.dividend_yield is not None:
                dividend_yield_pct = Percentage.from_percent(metadata.dividend_yield)

            stock_info = StockInfo(
                name=metadata.name,
                currency=metadata.currency,
                exchange=metadata.exchange,
                sector=metadata.sector,
                industry=metadata.industry,
                asset_type=metadata.asset_type if metadata.asset_type else None,
                dividend_yield=dividend_yield_pct,
            )

            # Convertir les valeurs en Value Objects
            current_price_money = Money(quote.price, quote.currency)
            volatility_pct = Percentage.from_percent(volatility) if volatility else None

            analysis = StockAnalysis(
                ticker=ticker,
                info=stock_info,
                performances=performances,
                current_price=current_price_money,
                volatility=volatility_pct,
                chart_data=chart_data,
                analyzed_at=datetime.now(),
            )

            logger.info(
                f"Analysis complete for {ticker.value}: "
                f"resilient={analysis.is_resilient}, score={score}"
            )

            return AnalyzeStockResult(
                analysis=analysis,
                error=None,
                ticker=ticker.value,
            )

        except TickerNotFoundError as e:
            logger.warning(f"Ticker not found: {ticker_str}")
            return AnalyzeStockResult(
                analysis=None,
                error=str(e),
                ticker=ticker_str,
            )
        except (DataFetchError, AnalysisError) as e:
            logger.error(f"Analysis error for {ticker_str}: {e}")
            return AnalyzeStockResult(
                analysis=None,
                error=str(e),
                ticker=ticker_str,
            )
        except Exception as e:
            logger.exception(f"Unexpected error analyzing {ticker_str}")
            return AnalyzeStockResult(
                analysis=None,
                error=f"Erreur inattendue: {str(e)}",
                ticker=ticker_str,
            )

    def _calculate_performances(
        self,
        data: List[HistoricalDataPoint],
    ) -> PerformanceData:
        """
        Calcule les performances sur toutes les périodes.

        Méthodologie "trader writer":
        - Performance = ((prix_fin - prix_début) / prix_début) * 100

        Args:
            data: Données historiques triées par date

        Returns:
            PerformanceData avec toutes les performances
        """
        # S'assurer que les données sont triées par date
        sorted_data = sorted(data, key=lambda x: x.date)

        # Calculer chaque période
        perf_3m = self._calculate_period_performance(sorted_data, PERIOD_3_MONTHS_DAYS)
        perf_6m = self._calculate_period_performance(sorted_data, PERIOD_6_MONTHS_DAYS)
        perf_1y = self._calculate_period_performance(sorted_data, PERIOD_1_YEAR_DAYS)
        perf_3y = self._calculate_period_performance(sorted_data, PERIOD_3_YEARS_DAYS)
        perf_5y = self._calculate_period_performance(sorted_data, PERIOD_5_YEARS_DAYS)

        return PerformanceData(
            perf_3m=Percentage.from_percent(perf_3m) if perf_3m is not None else None,
            perf_6m=Percentage.from_percent(perf_6m) if perf_6m is not None else None,
            perf_1y=Percentage.from_percent(perf_1y) if perf_1y is not None else None,
            perf_3y=Percentage.from_percent(perf_3y) if perf_3y is not None else None,
            perf_5y=Percentage.from_percent(perf_5y) if perf_5y is not None else None,
        )

    def _calculate_period_performance(
        self,
        data: List[HistoricalDataPoint],
        days: int,
    ) -> Optional[float]:
        """
        Calcule la performance sur une période donnée.

        Args:
            data: Données historiques triées par date (croissant)
            days: Nombre de jours de la période

        Returns:
            Performance en pourcentage ou None si données insuffisantes
        """
        if len(data) < 2:
            return None

        # Prix de fin (dernier point)
        end_price = data[-1].close

        # Trouver le point de départ (environ N jours avant)
        target_date = data[-1].date - timedelta(days=days)

        # Trouver le point le plus proche de la date cible
        start_point = None
        for point in data:
            if point.date >= target_date:
                start_point = point
                break

        if not start_point:
            # Prendre le premier point disponible
            start_point = data[0]

        start_price = start_point.close

        if start_price == 0:
            return None

        performance = ((end_price - start_price) / start_price) * 100
        return round(performance, 2)

    def _determine_volatility_level(
        self,
        volatility: Optional[float],
    ) -> VolatilityLevel:
        """
        Détermine le niveau de volatilité.

        Args:
            volatility: Volatilité en pourcentage

        Returns:
            VolatilityLevel correspondant
        """
        if volatility is None:
            return VolatilityLevel.UNKNOWN

        if volatility >= HIGH_VOLATILITY_THRESHOLD * 100:
            return VolatilityLevel.HIGH
        elif volatility >= MEDIUM_VOLATILITY_THRESHOLD * 100:
            return VolatilityLevel.MEDIUM
        else:
            return VolatilityLevel.LOW

    def _generate_chart_data(
        self,
        data: List[HistoricalDataPoint],
        max_points: int = 260,
    ) -> List[ChartDataPoint]:
        """
        Génère les données pour le graphique.

        Échantillonne les données en points hebdomadaires pour
        réduire la quantité de données tout en gardant la tendance.

        Args:
            data: Données historiques
            max_points: Nombre maximum de points (défaut: ~5 ans de semaines)

        Returns:
            Liste de points pour le graphique
        """
        if not data:
            return []

        # Trier par date
        sorted_data = sorted(data, key=lambda x: x.date)

        # Échantillonner (prendre environ 1 point par semaine)
        step = max(1, len(sorted_data) // max_points)

        chart_points = []
        for i in range(0, len(sorted_data), step):
            point = sorted_data[i]
            chart_points.append(ChartDataPoint(
                date=point.date,
                price=round(point.close, 2),
            ))

        # S'assurer d'inclure le dernier point
        if sorted_data and chart_points[-1].date != sorted_data[-1].date:
            chart_points.append(ChartDataPoint(
                date=sorted_data[-1].date,
                price=round(sorted_data[-1].close, 2),
            ))

        return chart_points[-max_points:]  # Limiter au max

    def _calculate_score(
        self,
        performances: PerformanceData,
        volatility: Optional[float],
    ) -> int:
        """
        Calcule un score de qualité du stock (0-100).

        Critères:
        - Performances positives: +15 points par période positive
        - Performances fortes (>20%): +5 points bonus par période
        - Volatilité faible: +25 points si < 20%
        - Volatilité moyenne: +10 points si 20-30%

        Args:
            performances: Données de performance
            volatility: Volatilité annualisée

        Returns:
            Score de 0 à 100
        """
        score = 0

        # Points pour les performances
        perfs = [
            performances.perf_3m,
            performances.perf_6m,
            performances.perf_1y,
            performances.perf_3y,
            performances.perf_5y,
        ]

        for perf in perfs:
            if perf is not None and perf.is_positive:
                score += 15  # Performance positive
                if perf.as_percent > 20:
                    score += 5  # Bonus performance forte

        # Points pour la volatilité
        if volatility is not None:
            if volatility < 20:
                score += 25  # Faible volatilité
            elif volatility < 30:
                score += 10  # Volatilité moyenne

        return min(100, score)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_analyze_stock_use_case(
    provider: StockDataProvider,
) -> AnalyzeStockUseCase:
    """
    Factory function pour créer un AnalyzeStockUseCase.

    Args:
        provider: Fournisseur de données de marché

    Returns:
        Instance configurée du use case
    """
    return AnalyzeStockUseCase(provider)
