"""
Tests unitaires pour le service de refresh automatique des tokens Saxo.

Ces tests verifient:
- La strategie de refresh proactif
- La politique de retry avec backoff exponentiel
- Le service de refresh complet
- Les metriques et le health check
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

from src.services.token_refresh_service import (
    TokenRefreshService,
    ProactiveRefreshStrategy,
    RetryPolicy,
    TokenStatus,
    RefreshResult,
    TokenHealth,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock des settings avec Saxo configure."""
    settings = MagicMock()
    settings.is_saxo_configured = True
    settings.SAXO_ENVIRONMENT = "SIM"
    settings.saxo_auth_url = "https://sim.logonvalidation.net"
    return settings


@pytest.fixture
def mock_token():
    """Mock d'un token Saxo valide."""
    token = MagicMock()
    token.access_token = "test_access_token"
    token.refresh_token = "test_refresh_token"
    token.environment = "SIM"
    token.expires_in_seconds = 900  # 15 minutes
    token.is_expired = False
    return token


@pytest.fixture
def mock_token_expiring():
    """Mock d'un token proche de l'expiration."""
    token = MagicMock()
    token.access_token = "test_access_token"
    token.refresh_token = "test_refresh_token"
    token.environment = "SIM"
    token.expires_in_seconds = 300  # 5 minutes - doit declencher un refresh
    token.is_expired = False
    return token


@pytest.fixture
def mock_token_expired():
    """Mock d'un token expire."""
    token = MagicMock()
    token.access_token = "test_access_token"
    token.refresh_token = "test_refresh_token"
    token.environment = "SIM"
    token.expires_in_seconds = 0
    token.is_expired = True
    return token


@pytest.fixture
def mock_auth_service(mock_token):
    """Mock du service d'authentification Saxo."""
    auth = MagicMock()
    auth.environment = "SIM"
    auth.token_manager = MagicMock()
    auth.token_manager.get = MagicMock(return_value=mock_token)
    auth.refresh_token = MagicMock(return_value=mock_token)
    return auth


@pytest.fixture
def refresh_service():
    """Service de refresh avec configuration par defaut."""
    return TokenRefreshService()


# =============================================================================
# TESTS - ProactiveRefreshStrategy
# =============================================================================

class TestProactiveRefreshStrategy:
    """Tests pour la strategie de refresh proactif."""

    def test_should_refresh_access_token_expiring(self):
        """Test: refresh si access_token expire bientot."""
        strategy = ProactiveRefreshStrategy(
            access_threshold=600,   # 10 min
            refresh_threshold=1200  # 20 min
        )

        # Access token expire dans 5 minutes (< seuil de 10)
        assert strategy.should_refresh(
            access_expires_in=300,
            refresh_expires_in=2000
        ) is True

    def test_should_refresh_refresh_token_expiring(self):
        """Test: refresh si refresh_token expire bientot (prioritaire)."""
        strategy = ProactiveRefreshStrategy(
            access_threshold=600,
            refresh_threshold=1200
        )

        # Access OK mais refresh_token proche de l'expiration
        assert strategy.should_refresh(
            access_expires_in=900,   # 15 min - OK
            refresh_expires_in=600   # 10 min < seuil de 20 min
        ) is True

    def test_should_not_refresh_tokens_valid(self):
        """Test: pas de refresh si les tokens sont valides."""
        strategy = ProactiveRefreshStrategy(
            access_threshold=600,
            refresh_threshold=1200
        )

        # Les deux tokens sont bien valides
        assert strategy.should_refresh(
            access_expires_in=1500,  # 25 min > seuil
            refresh_expires_in=2000  # 33 min > seuil
        ) is False

    def test_get_refresh_interval_normal(self):
        """Test: calcul de l'intervalle optimal."""
        strategy = ProactiveRefreshStrategy()

        # Avec 20 minutes restantes, devrait rafraichir a 50%
        interval = strategy.get_refresh_interval(
            access_expires_in=1200,  # 20 min
            refresh_expires_in=2400  # 40 min
        )

        # 50% de 1200 = 600 secondes
        assert interval == 600

    def test_get_refresh_interval_minimum(self):
        """Test: intervalle minimum de 60 secondes."""
        strategy = ProactiveRefreshStrategy()

        # Avec 1 minute restante
        interval = strategy.get_refresh_interval(
            access_expires_in=60,
            refresh_expires_in=120
        )

        # Minimum 60 secondes
        assert interval >= 60


# =============================================================================
# TESTS - RetryPolicy
# =============================================================================

class TestRetryPolicy:
    """Tests pour la politique de retry."""

    def test_get_delay_exponential_backoff(self):
        """Test: delai augmente exponentiellement."""
        policy = RetryPolicy(
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0
        )

        # Premiere tentative: 1s
        assert policy.get_delay(1) == 1.0

        # Deuxieme: 2s
        assert policy.get_delay(2) == 2.0

        # Troisieme: 4s
        assert policy.get_delay(3) == 4.0

        # Quatrieme: 8s
        assert policy.get_delay(4) == 8.0

    def test_get_delay_max_cap(self):
        """Test: delai plafonne au max."""
        policy = RetryPolicy(
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0
        )

        # Apres plusieurs tentatives, ne depasse pas max
        assert policy.get_delay(10) == 10.0

    def test_should_retry_under_max_attempts(self):
        """Test: retry autorise si sous le max."""
        policy = RetryPolicy(max_attempts=3)

        assert policy.should_retry(1, Exception("Network error")) is True
        assert policy.should_retry(2, Exception("Timeout")) is True

    def test_should_not_retry_at_max_attempts(self):
        """Test: pas de retry au max d'attempts."""
        policy = RetryPolicy(max_attempts=3)

        assert policy.should_retry(3, Exception("Error")) is False
        assert policy.should_retry(4, Exception("Error")) is False

    def test_should_not_retry_on_invalid_grant(self):
        """Test: pas de retry sur erreurs non-retryables."""
        policy = RetryPolicy(max_attempts=5)

        # invalid_grant = refresh token invalide, inutile de retry
        assert policy.should_retry(1, Exception("invalid_grant: token expired")) is False

        # unauthorized aussi
        assert policy.should_retry(1, Exception("unauthorized")) is False

    def test_should_retry_on_network_error(self):
        """Test: retry sur erreur reseau."""
        policy = RetryPolicy(max_attempts=3)

        assert policy.should_retry(1, Exception("Connection timeout")) is True
        assert policy.should_retry(1, Exception("Network unreachable")) is True


# =============================================================================
# TESTS - TokenRefreshService
# =============================================================================

class TestTokenRefreshService:
    """Tests pour le service de refresh."""

    def test_init_with_defaults(self):
        """Test: initialisation avec valeurs par defaut."""
        service = TokenRefreshService()

        assert service.strategy is not None
        assert service.retry_policy is not None
        assert service._consecutive_failures == 0
        assert service._total_refreshes == 0

    def test_init_with_custom_strategy(self):
        """Test: initialisation avec strategie custom."""
        strategy = ProactiveRefreshStrategy(
            access_threshold=300,
            refresh_threshold=600
        )
        service = TokenRefreshService(strategy=strategy)

        assert service.strategy.access_threshold == 300
        assert service.strategy.refresh_threshold == 600

    @patch('src.config.settings.get_settings')
    def test_check_and_refresh_not_configured(self, mock_get_settings):
        """Test: retourne MISSING si Saxo non configure."""
        settings = MagicMock()
        settings.is_saxo_configured = False
        mock_get_settings.return_value = settings

        service = TokenRefreshService()
        result = service.check_and_refresh()

        assert result.status == TokenStatus.MISSING
        assert "not configured" in result.error

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_check_and_refresh_no_token(self, mock_get_settings, mock_get_auth):
        """Test: retourne MISSING si pas de token."""
        settings = MagicMock()
        settings.is_saxo_configured = True
        mock_get_settings.return_value = settings

        auth = MagicMock()
        auth.token_manager.get.return_value = None
        mock_get_auth.return_value = auth

        service = TokenRefreshService()
        result = service.check_and_refresh()

        assert result.status == TokenStatus.MISSING

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_check_and_refresh_token_valid(self, mock_get_settings, mock_get_auth, mock_settings, mock_token):
        """Test: retourne VALID si token OK."""
        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token
        mock_get_auth.return_value = auth

        # Token avec 15 min restantes, au-dessus des seuils
        mock_token.expires_in_seconds = 1500  # 25 min

        service = TokenRefreshService()
        result = service.check_and_refresh()

        assert result.status == TokenStatus.VALID
        assert result.success is True

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_check_and_refresh_triggers_refresh(
        self, mock_get_settings, mock_get_auth, mock_settings, mock_token_expiring
    ):
        """Test: declenche refresh si token expire bientot."""
        mock_get_settings.return_value = mock_settings

        new_token = MagicMock()
        new_token.expires_in_seconds = 1200  # Nouveau token avec 20 min

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token_expiring
        auth.refresh_token.return_value = new_token
        mock_get_auth.return_value = auth

        service = TokenRefreshService()
        result = service.check_and_refresh()

        # Verifie que refresh_token a ete appele
        auth.refresh_token.assert_called_once_with(mock_token_expiring.refresh_token)

        assert result.success is True
        assert result.status == TokenStatus.VALID
        assert result.access_token_expires_in == 1200

    @patch('src.services.token_refresh_service.time.sleep')
    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_refresh_with_retry_on_failure(
        self, mock_get_settings, mock_get_auth, mock_sleep, mock_settings, mock_token_expiring
    ):
        """Test: retry avec backoff sur echec."""
        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token_expiring
        # Echoue 2 fois, reussit la 3eme
        new_token = MagicMock()
        new_token.expires_in_seconds = 1200
        auth.refresh_token.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            new_token
        ]
        mock_get_auth.return_value = auth

        service = TokenRefreshService(
            retry_policy=RetryPolicy(max_attempts=5, base_delay=0.1)
        )
        result = service.check_and_refresh()

        assert result.success is True
        assert result.attempts == 3
        assert mock_sleep.call_count == 2  # 2 sleeps pour les 2 retries

    @patch('src.services.token_refresh_service.time.sleep')
    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_refresh_fails_after_max_retries(
        self, mock_get_settings, mock_get_auth, mock_sleep, mock_settings, mock_token_expiring
    ):
        """Test: echec apres max retries."""
        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token_expiring
        auth.refresh_token.side_effect = Exception("Persistent error")
        mock_get_auth.return_value = auth

        service = TokenRefreshService(
            retry_policy=RetryPolicy(max_attempts=3, base_delay=0.01)
        )
        result = service.check_and_refresh()

        assert result.success is False
        assert result.status == TokenStatus.REFRESH_FAILED
        assert result.attempts == 3
        assert "Persistent error" in result.error

    def test_stats_tracking(self):
        """Test: suivi des statistiques."""
        service = TokenRefreshService()

        # Initialement a zero
        assert service.stats["total_refreshes"] == 0
        assert service.stats["total_failures"] == 0
        assert service.stats["success_rate"] == 1.0

        # Simuler des refreshes
        service._total_refreshes = 8
        service._total_failures = 2

        stats = service.stats
        assert stats["total_refreshes"] == 8
        assert stats["total_failures"] == 2
        assert stats["success_rate"] == 0.8  # 8/(8+2)


# =============================================================================
# TESTS - TokenRefreshService.get_health
# =============================================================================

class TestTokenRefreshServiceHealth:
    """Tests pour le health check."""

    @patch('src.config.settings.get_settings')
    def test_health_not_configured(self, mock_get_settings):
        """Test: None si Saxo non configure."""
        settings = MagicMock()
        settings.is_saxo_configured = False
        mock_get_settings.return_value = settings

        service = TokenRefreshService()
        health = service.get_health()

        assert health is None

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_health_no_token(self, mock_get_settings, mock_get_auth, mock_settings):
        """Test: health avec token missing."""
        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = None
        mock_get_auth.return_value = auth

        service = TokenRefreshService()
        health = service.get_health()

        assert health.status == TokenStatus.MISSING
        assert health.environment == "SIM"
        assert health.access_token_expires_in == 0

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_health_token_valid(self, mock_get_settings, mock_get_auth, mock_settings, mock_token):
        """Test: health avec token valide."""
        mock_get_settings.return_value = mock_settings
        mock_token.expires_in_seconds = 1500  # 25 min

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token
        mock_get_auth.return_value = auth

        service = TokenRefreshService()
        health = service.get_health()

        assert health.status == TokenStatus.VALID
        assert health.access_token_expires_in == 1500
        assert health.next_refresh_in > 0

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_health_token_expiring_soon(self, mock_get_settings, mock_get_auth, mock_settings, mock_token_expiring):
        """Test: health avec token expirant bientot."""
        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token_expiring
        mock_get_auth.return_value = auth

        service = TokenRefreshService()
        health = service.get_health()

        assert health.status == TokenStatus.EXPIRING_SOON

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_health_token_expired(self, mock_get_settings, mock_get_auth, mock_settings, mock_token_expired):
        """Test: health avec token expire."""
        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token_expired
        mock_get_auth.return_value = auth

        service = TokenRefreshService()
        health = service.get_health()

        assert health.status == TokenStatus.EXPIRED


# =============================================================================
# TESTS - Integration Job
# =============================================================================

class TestTokenRefreshJob:
    """Tests pour le job de refresh."""

    @patch('src.jobs.token_refresh.get_token_refresh_service')
    def test_refresh_job_success(self, mock_get_service):
        """Test: job retourne succes."""
        from src.jobs.token_refresh import refresh_saxo_token_job

        mock_service = MagicMock()
        mock_service.check_and_refresh.return_value = RefreshResult(
            success=True,
            status=TokenStatus.VALID,
            access_token_expires_in=1200,
        )
        mock_get_service.return_value = mock_service

        result = refresh_saxo_token_job()

        assert result.success is True
        assert result.status == TokenStatus.VALID

    @patch('src.jobs.token_refresh.get_token_refresh_service')
    def test_refresh_job_failure(self, mock_get_service):
        """Test: job retourne echec."""
        from src.jobs.token_refresh import refresh_saxo_token_job

        mock_service = MagicMock()
        mock_service.check_and_refresh.return_value = RefreshResult(
            success=False,
            status=TokenStatus.REFRESH_FAILED,
            error="Network error"
        )
        mock_get_service.return_value = mock_service

        result = refresh_saxo_token_job()

        assert result.success is False
        assert result.status == TokenStatus.REFRESH_FAILED

    @patch('src.jobs.token_refresh.get_token_refresh_service')
    def test_refresh_job_handles_exception(self, mock_get_service):
        """Test: job gere les exceptions."""
        from src.jobs.token_refresh import refresh_saxo_token_job

        mock_service = MagicMock()
        mock_service.check_and_refresh.side_effect = Exception("Unexpected error")
        mock_get_service.return_value = mock_service

        result = refresh_saxo_token_job()

        assert result.success is False
        assert result.status == TokenStatus.REFRESH_FAILED


# =============================================================================
# TESTS - Force Refresh
# =============================================================================

class TestForceRefreshToken:
    """Tests pour le refresh force."""

    @patch('src.config.settings.get_settings')
    def test_force_refresh_not_configured(self, mock_get_settings):
        """Test: erreur si non configure."""
        from src.jobs.token_refresh import force_refresh_token

        settings = MagicMock()
        settings.is_saxo_configured = False
        mock_get_settings.return_value = settings

        result = force_refresh_token()

        assert result["success"] is False
        assert "not configured" in result["error"]

    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_force_refresh_no_token(self, mock_get_settings, mock_get_auth, mock_settings):
        """Test: erreur si pas de token."""
        from src.jobs.token_refresh import force_refresh_token

        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.token_manager.get.return_value = None
        mock_get_auth.return_value = auth

        result = force_refresh_token()

        assert result["success"] is False
        assert "No token" in result["error"]

    @patch('src.jobs.token_refresh.get_token_refresh_service')
    @patch('src.infrastructure.brokers.saxo.saxo_auth.get_saxo_auth')
    @patch('src.config.settings.get_settings')
    def test_force_refresh_success(
        self, mock_get_settings, mock_get_auth, mock_get_service, mock_settings, mock_token
    ):
        """Test: force refresh reussit."""
        from src.jobs.token_refresh import force_refresh_token

        mock_get_settings.return_value = mock_settings

        auth = MagicMock()
        auth.environment = "SIM"
        auth.token_manager.get.return_value = mock_token
        mock_get_auth.return_value = auth

        mock_service = MagicMock()
        mock_service._do_refresh_with_retry.return_value = RefreshResult(
            success=True,
            status=TokenStatus.VALID,
            access_token_expires_in=1200,
            attempts=1,
        )
        mock_service.stats = {"total_refreshes": 1}
        mock_get_service.return_value = mock_service

        result = force_refresh_token()

        assert result["success"] is True
        assert result["environment"] == "SIM"
        assert result["expires_in_seconds"] == 1200


# =============================================================================
# TESTS - Get Token Health
# =============================================================================

class TestGetTokenHealth:
    """Tests pour la fonction get_token_health."""

    @patch('src.jobs.token_refresh.get_token_refresh_service')
    def test_get_health_not_configured(self, mock_get_service):
        """Test: retourne not_configured si pas de config."""
        from src.jobs.token_refresh import get_token_health

        mock_service = MagicMock()
        mock_service.get_health.return_value = None
        mock_get_service.return_value = mock_service

        result = get_token_health()

        assert result["status"] == "not_configured"

    @patch('src.jobs.token_refresh.get_token_refresh_service')
    def test_get_health_success(self, mock_get_service):
        """Test: retourne health complet."""
        from src.jobs.token_refresh import get_token_health

        mock_service = MagicMock()
        mock_service.get_health.return_value = TokenHealth(
            status=TokenStatus.VALID,
            environment="SIM",
            access_token_expires_in=1200,
            refresh_token_expires_in=2400,
            last_refresh=datetime.now(),
            consecutive_failures=0,
            next_refresh_in=600,
        )
        mock_service.stats = {"total_refreshes": 5, "success_rate": 1.0}
        mock_get_service.return_value = mock_service

        result = get_token_health()

        assert result["status"] == "valid"
        assert result["environment"] == "SIM"
        assert result["access_token"]["expires_in_seconds"] == 1200
        assert result["refresh_token"]["expires_in_seconds"] == 2400
