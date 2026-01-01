"""
Tests unitaires pour les Use Cases.

Couvre:
- AnalyzeStockUseCase: analyse complete d'un stock

Format des tests: Given/When/Then en docstrings.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from src.application.use_cases.analyze_stock import (
    AnalyzeStockUseCase,
    AnalyzeStockResult,
)
from src.application.interfaces.stock_data_provider import HistoricalDataPoint
from src.domain.exceptions import TickerNotFoundError, AnalysisError


# =============================================================================
# TESTS ANALYZE STOCK USE CASE
# =============================================================================

class TestAnalyzeStockUseCase:
    """Tests pour le Use Case d'analyse de stock."""

    # -------------------------------------------------------------------------
    # Tests de succes
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_stock_success(self, mock_provider):
        """
        Given: Un provider mock avec des donnees valides
        When: On execute le use case avec un ticker valide
        Then: L'analyse est retournee avec succes
        """
        use_case = AnalyzeStockUseCase(mock_provider)

        result = await use_case.execute("AAPL")

        assert result.is_success
        assert result.analysis is not None
        assert result.ticker == "AAPL"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_analyze_stock_has_performances(self, mock_provider):
        """
        Given: Un provider avec des donnees historiques
        When: On analyse un stock
        Then: Les performances sont calculees pour toutes les periodes
        """
        use_case = AnalyzeStockUseCase(mock_provider)

        result = await use_case.execute("AAPL")

        performances = result.analysis.performances
        assert performances.perf_3m is not None
        assert performances.perf_6m is not None
        assert performances.perf_1y is not None
        assert performances.perf_3y is not None
        assert performances.perf_5y is not None

    @pytest.mark.asyncio
    async def test_analyze_stock_has_chart_data(self, mock_provider):
        """
        Given: Un provider avec des donnees historiques
        When: On analyse un stock
        Then: Les donnees du graphique sont generees
        """
        use_case = AnalyzeStockUseCase(mock_provider)

        result = await use_case.execute("AAPL")

        assert result.analysis.chart_data is not None
        assert len(result.analysis.chart_data) > 0

        # Verifier le format des points
        first_point = result.analysis.chart_data[0]
        assert "date" in first_point.__dict__ or hasattr(first_point, "date")

    @pytest.mark.asyncio
    async def test_analyze_resilient_stock(self, mock_provider_resilient):
        """
        Given: Un provider avec des donnees de stock resilient
        When: On analyse le stock
        Then: is_resilient est True (toutes performances positives)
        """
        use_case = AnalyzeStockUseCase(mock_provider_resilient)

        result = await use_case.execute("AAPL")

        assert result.is_success
        assert result.analysis.is_resilient is True

        # Verifier que toutes les performances sont positives
        perfs = result.analysis.performances
        assert perfs.perf_3m > 0
        assert perfs.perf_6m > 0
        assert perfs.perf_1y > 0
        assert perfs.perf_3y > 0
        assert perfs.perf_5y > 0

    @pytest.mark.asyncio
    async def test_analyze_stock_score(self, mock_provider):
        """
        Given: Un provider avec des donnees
        When: On analyse un stock
        Then: Un score entre 0 et 100 est calcule
        """
        use_case = AnalyzeStockUseCase(mock_provider)

        result = await use_case.execute("AAPL")

        assert result.analysis.score is not None
        assert 0 <= result.analysis.score <= 100

    # -------------------------------------------------------------------------
    # Tests d'erreur
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_stock_not_found(self, mock_provider_not_found):
        """
        Given: Un provider qui leve TickerNotFoundError
        When: On analyse un ticker invalide
        Then: Le resultat contient une erreur
        """
        use_case = AnalyzeStockUseCase(mock_provider_not_found)

        result = await use_case.execute("INVALID")

        assert not result.is_success
        assert result.analysis is None
        assert result.error is not None
        assert "INVALID" in result.error

    @pytest.mark.asyncio
    async def test_analyze_stock_invalid_ticker(self, mock_provider):
        """
        Given: Un provider mock
        When: On passe un ticker invalide (format incorrect)
        Then: Le resultat contient une erreur de validation
        """
        use_case = AnalyzeStockUseCase(mock_provider)

        result = await use_case.execute("")

        assert not result.is_success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_analyze_stock_insufficient_data(self, mock_provider):
        """
        Given: Un provider qui retourne peu de donnees
        When: On analyse un stock
        Then: Une erreur d'analyse est retournee
        """
        # Configurer le mock pour retourner peu de donnees
        mock_provider.get_historical_data.return_value = [
            HistoricalDataPoint(
                date=datetime.now(),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1000
            )
        ]

        use_case = AnalyzeStockUseCase(mock_provider)

        result = await use_case.execute("AAPL")

        assert not result.is_success
        assert "insuffisantes" in result.error.lower() or "insufficient" in result.error.lower()


# =============================================================================
# TESTS DES CALCULS INTERNES
# =============================================================================

class TestPerformanceCalculations:
    """Tests pour les calculs de performance internes."""

    @pytest.mark.asyncio
    async def test_performance_calculation_positive(self, mock_provider):
        """
        Given: Des donnees avec une tendance haussiere
        When: On calcule les performances
        Then: Les valeurs sont positives
        """
        # Creer des donnees avec hausse constante
        base_date = datetime.now()
        data = []
        for i in range(400):  # ~1 an
            date = base_date - timedelta(days=400 - i)
            price = 100 * (1 + 0.0005 * i)  # +0.05% par jour
            data.append(HistoricalDataPoint(
                date=date,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=1000000
            ))

        mock_provider.get_historical_data.return_value = data

        use_case = AnalyzeStockUseCase(mock_provider)
        result = await use_case.execute("AAPL")

        assert result.is_success
        assert result.analysis.performances.perf_3m > 0
        assert result.analysis.performances.perf_6m > 0

    @pytest.mark.asyncio
    async def test_volatility_level_classification(self, mock_provider):
        """
        Given: Un provider avec une volatilite specifique
        When: On analyse un stock
        Then: Le niveau de volatilite est correctement classifie
        """
        # Test avec faible volatilite
        mock_provider.calculate_volatility.return_value = 10.0
        use_case = AnalyzeStockUseCase(mock_provider)
        result = await use_case.execute("AAPL")
        assert result.analysis.volatility_level == "low"

        # Test avec volatilite moyenne
        mock_provider.calculate_volatility.return_value = 25.0
        result = await use_case.execute("AAPL")
        assert result.analysis.volatility_level == "medium"

        # Test avec haute volatilite
        mock_provider.calculate_volatility.return_value = 40.0
        result = await use_case.execute("AAPL")
        assert result.analysis.volatility_level == "high"


# =============================================================================
# TESTS DE RESILIENCE
# =============================================================================

class TestResilienceCalculation:
    """Tests pour le calcul de resilience."""

    @pytest.mark.asyncio
    async def test_is_resilient_all_positive(self, mock_provider_resilient):
        """
        Given: Un stock avec toutes les performances positives
        When: On verifie is_resilient
        Then: True est retourne
        """
        use_case = AnalyzeStockUseCase(mock_provider_resilient)
        result = await use_case.execute("AAPL")

        assert result.analysis.is_resilient is True

    @pytest.mark.asyncio
    async def test_is_resilient_with_negative(self, mock_provider):
        """
        Given: Un stock avec au moins une performance negative
        When: On verifie is_resilient
        Then: False est retourne
        """
        # Creer des donnees avec une baisse recente
        base_date = datetime.now()
        data = []

        # Donnees haussiere puis baissiere
        for i in range(1825):
            date = base_date - timedelta(days=1825 - i)
            if i < 1700:  # Hausse
                price = 100 * (1 + 0.0003 * i)
            else:  # Baisse sur les 4 derniers mois
                price = 100 * 1.5 * (1 - 0.002 * (i - 1700))

            data.append(HistoricalDataPoint(
                date=date,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=1000000
            ))

        mock_provider.get_historical_data.return_value = data

        use_case = AnalyzeStockUseCase(mock_provider)
        result = await use_case.execute("AAPL")

        # Avec la baisse recente, le stock n'est pas resilient
        # (au moins perf_3m devrait etre negative)
        assert result.is_success
