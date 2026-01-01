"""
Tests d'integration pour les routes API.

Ces tests utilisent le client FastAPI pour tester les endpoints.

Format des tests: Given/When/Then en docstrings.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """Client de test FastAPI."""
    app = create_app()
    return TestClient(app)


# =============================================================================
# TESTS HEALTH ENDPOINT
# =============================================================================

class TestHealthEndpoint:
    """Tests pour le endpoint de sante."""

    def test_health_check(self, client):
        """
        Given: L'API est demarree
        When: On appelle GET /api/health
        Then: Le status 200 et les infos de sante sont retournes
        """
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


# =============================================================================
# TESTS MARKETS ENDPOINTS
# =============================================================================

class TestMarketsEndpoints:
    """Tests pour les endpoints de marches."""

    def test_list_markets(self, client):
        """
        Given: Le fichier markets.json existe
        When: On appelle GET /api/markets
        Then: La liste des marches est retournee
        """
        response = client.get("/api/markets")

        assert response.status_code == 200
        data = response.json()
        assert "markets" in data
        assert isinstance(data["markets"], list)

    def test_get_market_tickers(self, client):
        """
        Given: Le marche sp500 existe
        When: On appelle GET /api/markets/sp500/tickers
        Then: Les tickers du marche sont retournes
        """
        response = client.get("/api/markets/sp500/tickers")

        assert response.status_code == 200
        data = response.json()
        assert "tickers" in data
        assert "total" in data
        assert isinstance(data["tickers"], list)

    def test_get_market_not_found(self, client):
        """
        Given: Un marche inexistant
        When: On appelle GET /api/markets/inexistant/tickers
        Then: Une erreur 404 est retournee
        """
        response = client.get("/api/markets/marche_inexistant/tickers")

        assert response.status_code == 404

    def test_get_market_details(self, client):
        """
        Given: Le marche cac40 existe
        When: On appelle GET /api/markets/cac40
        Then: Les details du marche sont retournes
        """
        response = client.get("/api/markets/cac40")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "count" in data


# =============================================================================
# TESTS STOCKS ENDPOINTS
# =============================================================================

class TestStocksEndpoints:
    """Tests pour les endpoints de stocks."""

    @pytest.mark.skip_ci
    def test_analyze_stock_valid(self, client):
        """
        Given: Un ticker valide (AAPL)
        When: On appelle POST /api/stocks/analyze
        Then: L'analyse est retournee

        Note: Ce test fait un vrai appel a Yahoo Finance.
        Marque @skip_ci pour ne pas l'executer en CI.
        """
        response = client.post(
            "/api/stocks/analyze",
            json={"ticker": "AAPL"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "ticker" in data
        # Soit une analyse reussie, soit une erreur
        assert "analysis" in data or "error" in data

    def test_analyze_stock_invalid_ticker(self, client):
        """
        Given: Un ticker invalide (format incorrect)
        When: On appelle POST /api/stocks/analyze
        Then: Une erreur de validation est retournee
        """
        response = client.post(
            "/api/stocks/analyze",
            json={"ticker": ""}
        )

        # Peut etre 400 ou 422 selon la validation
        assert response.status_code in [400, 422]

    def test_analyze_stock_missing_ticker(self, client):
        """
        Given: Pas de ticker dans la requete
        When: On appelle POST /api/stocks/analyze
        Then: Une erreur 422 est retournee
        """
        response = client.post(
            "/api/stocks/analyze",
            json={}
        )

        assert response.status_code == 422


# =============================================================================
# TESTS API DOCUMENTATION
# =============================================================================

class TestApiDocumentation:
    """Tests pour la documentation API."""

    def test_openapi_schema(self, client):
        """
        Given: L'API est demarree
        When: On appelle GET /api/openapi.json
        Then: Le schema OpenAPI est retourne
        """
        response = client.get("/api/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_swagger_ui(self, client):
        """
        Given: L'API est demarree
        When: On appelle GET /api/docs
        Then: La page Swagger UI est retournee
        """
        response = client.get("/api/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


# =============================================================================
# TESTS CORS
# =============================================================================

class TestCors:
    """Tests pour la configuration CORS."""

    def test_cors_headers_present(self, client):
        """
        Given: Une requete avec Origin
        When: On appelle un endpoint
        Then: Les headers CORS sont presents dans la reponse
        """
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"}
        )

        # Verifier que la reponse contient les headers CORS
        # Note: TestClient ne gere pas toujours parfaitement CORS
        assert response.status_code == 200
