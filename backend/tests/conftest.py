"""
Fixtures pytest partagees pour les tests Stock Analyzer.

Ce fichier contient:
- Configuration globale des tests
- Fixtures reutilisables (mocks, donnees de test)
- Helpers pour les tests async

UTILISATION:
    Les fixtures sont automatiquement disponibles dans tous les tests.
    Exemple:
        def test_something(mock_provider):
            result = mock_provider.get_data()
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from decimal import Decimal
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ajouter le repertoire backend au path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.application.interfaces.stock_data_provider import (
    StockDataProvider,
    HistoricalDataPoint,
    StockMetadata,
    StockQuote,
)
from src.config.constants import AssetType


# =============================================================================
# FIXTURES POUR LES VALUE OBJECTS
# =============================================================================

@pytest.fixture
def valid_tickers() -> List[str]:
    """
    Liste de tickers valides pour les tests.

    Couvre differents formats:
    - US stocks (AAPL)
    - Avec exchange (0700.HK, MC.PA)
    - Index (^GSPC)
    - Crypto (BTC-USD)
    """
    return [
        "AAPL",
        "MSFT",
        "GOOGL",
        "0700.HK",
        "MC.PA",
        "^GSPC",
        "^DJI",
        "BTC-USD",
        "ETH-USD",
        "BRK.A",
        "BRK.B",
    ]


@pytest.fixture
def invalid_tickers() -> List[str]:
    """
    Liste de tickers invalides pour les tests.

    Couvre differents cas d'erreur:
    - Vide
    - Trop long
    - Caracteres invalides
    """
    return [
        "",
        "   ",
        "A" * 15,  # Trop long (>12)
        "AAPL$",   # Caractere $ invalide
        "AAP L",   # Espace invalide
        "@AAPL",   # @ invalide
    ]


@pytest.fixture
def sample_money_amounts() -> List[dict]:
    """Exemples de montants pour tester Money."""
    return [
        {"amount": 100.50, "currency": "USD"},
        {"amount": 0, "currency": "EUR"},
        {"amount": -50.25, "currency": "GBP"},
        {"amount": 1000000, "currency": "CHF"},
        {"amount": 0.01, "currency": "JPY"},
    ]


@pytest.fixture
def sample_percentages() -> List[float]:
    """Exemples de pourcentages en decimal pour tester Percentage."""
    return [0.15, -0.05, 0, 1.0, -0.5, 0.001]


# =============================================================================
# FIXTURES POUR LES DONNEES HISTORIQUES
# =============================================================================

@pytest.fixture
def mock_historical_data() -> List[HistoricalDataPoint]:
    """
    Donnees historiques mock pour les tests d'analyse.

    Genere 5 ans de donnees quotidiennes avec une tendance haussiere.
    """
    data = []
    base_date = datetime.now()
    base_price = 100.0

    for i in range(1825):  # ~5 ans
        date = base_date - timedelta(days=1825 - i)
        # Prix avec tendance haussiere + bruit
        price = base_price * (1 + 0.1 * (i / 365))  # +10% par an
        noise = (i % 7 - 3) * 0.5  # Bruit periodique
        close = price + noise

        data.append(HistoricalDataPoint(
            date=date,
            open=close * 0.99,
            high=close * 1.02,
            low=close * 0.98,
            close=close,
            volume=1000000 + i * 100,
        ))

    return data


@pytest.fixture
def mock_resilient_data() -> List[HistoricalDataPoint]:
    """
    Donnees mock pour un stock resilient (toutes performances positives).
    """
    data = []
    base_date = datetime.now()
    base_price = 100.0

    for i in range(1825):
        date = base_date - timedelta(days=1825 - i)
        # Prix strictement croissant
        price = base_price * (1 + 0.15 * (i / 365))  # +15% par an

        data.append(HistoricalDataPoint(
            date=date,
            open=price * 0.99,
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=1000000,
        ))

    return data


@pytest.fixture
def mock_non_resilient_data() -> List[HistoricalDataPoint]:
    """
    Donnees mock pour un stock non resilient (performance negative recente).
    """
    data = []
    base_date = datetime.now()
    base_price = 100.0

    for i in range(1825):
        date = base_date - timedelta(days=1825 - i)

        # Prix croissant puis baissier sur les 6 derniers mois
        if i < 1645:  # Avant les 6 derniers mois
            price = base_price * (1 + 0.10 * (i / 365))
        else:
            # Baisse de 20% sur les 6 derniers mois
            progress = (i - 1645) / 180
            price = base_price * 1.5 * (1 - 0.20 * progress)

        data.append(HistoricalDataPoint(
            date=date,
            open=price * 0.99,
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=1000000,
        ))

    return data


# =============================================================================
# MOCK PROVIDER
# =============================================================================

@pytest.fixture
def mock_stock_metadata() -> StockMetadata:
    """Metadata mock pour un stock."""
    return StockMetadata(
        ticker="AAPL",
        name="Apple Inc.",
        currency="USD",
        exchange="NASDAQ",
        sector="Technology",
        industry="Consumer Electronics",
        asset_type=AssetType.STOCK,
        market_cap=3000000000000,
        dividend_yield=0.5,
    )


@pytest.fixture
def mock_stock_quote() -> StockQuote:
    """Quote mock pour un stock."""
    return StockQuote(
        ticker="AAPL",
        price=185.50,
        currency="USD",
        timestamp=datetime.now(),
        change=2.50,
        change_percent=1.37,
    )


@pytest.fixture
def mock_provider(
    mock_historical_data,
    mock_stock_metadata,
    mock_stock_quote,
) -> StockDataProvider:
    """
    Provider mock pour les tests.

    Given: Un provider qui retourne des donnees predefinies
    When: On appelle ses methodes
    Then: Il retourne les mocks
    """
    provider = AsyncMock(spec=StockDataProvider)

    # Configurer les retours
    provider.get_historical_data.return_value = mock_historical_data
    provider.get_metadata.return_value = mock_stock_metadata
    provider.get_current_quote.return_value = mock_stock_quote
    provider.calculate_volatility.return_value = 25.0  # 25% volatilite

    return provider


@pytest.fixture
def mock_provider_resilient(
    mock_resilient_data,
    mock_stock_metadata,
    mock_stock_quote,
) -> StockDataProvider:
    """Provider mock pour un stock resilient."""
    provider = AsyncMock(spec=StockDataProvider)

    provider.get_historical_data.return_value = mock_resilient_data
    provider.get_metadata.return_value = mock_stock_metadata
    provider.get_current_quote.return_value = mock_stock_quote
    provider.calculate_volatility.return_value = 15.0  # Faible volatilite

    return provider


@pytest.fixture
def mock_provider_not_found() -> StockDataProvider:
    """Provider mock qui leve TickerNotFoundError."""
    from src.domain.exceptions import TickerNotFoundError

    provider = AsyncMock(spec=StockDataProvider)
    provider.get_metadata.side_effect = TickerNotFoundError("INVALID")

    return provider


# =============================================================================
# FIXTURES POUR LES TESTS D'INTEGRATION
# =============================================================================

@pytest.fixture
def test_client():
    """
    Client de test FastAPI.

    Utilise pour les tests d'integration des routes.
    """
    from fastapi.testclient import TestClient
    from src.api.app import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def async_client():
    """
    Client de test async FastAPI.

    Pour les tests qui necessitent un client async.
    """
    import httpx
    from src.api.app import create_app

    app = create_app()
    return httpx.AsyncClient(app=app, base_url="http://test")


# =============================================================================
# HELPERS
# =============================================================================

def assert_percentage_close(actual: float, expected: float, tolerance: float = 0.1):
    """
    Verifie qu'un pourcentage est proche de la valeur attendue.

    Args:
        actual: Valeur reelle
        expected: Valeur attendue
        tolerance: Tolerance absolue (defaut: 0.1%)
    """
    assert abs(actual - expected) < tolerance, (
        f"Pourcentage {actual:.2f}% pas assez proche de {expected:.2f}% "
        f"(tolerance: {tolerance}%)"
    )
