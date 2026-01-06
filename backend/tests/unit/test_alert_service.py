"""
Tests unitaires pour les services d'alertes.

Ces tests vérifient:
- La création d'alertes avec différents types
- La vérification des alertes actives
- Le calcul des prix SL/TP
- La gestion des erreurs
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.application.services.alert_service import AlertService
from src.application.services.technical_alert_service import TechnicalAlertService, TechnicalSignal
from src.infrastructure.database.repositories.alert_repository import Alert, AlertType
from src.domain.value_objects.ticker import Ticker


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_alert_repo():
    """Mock du repository d'alertes."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_active = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_ticker = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.mark_triggered = AsyncMock()
    repo.mark_notification_sent = AsyncMock()
    repo.get_stats = AsyncMock()
    return repo


@pytest.fixture
def mock_price_provider():
    """Mock du provider de prix."""
    provider = MagicMock()
    provider.get_current_quote = AsyncMock()
    provider.get_historical_data = AsyncMock()
    return provider


@pytest.fixture
def mock_telegram():
    """Mock du service Telegram."""
    telegram = MagicMock()
    telegram.is_configured = True
    telegram.send_alert = AsyncMock(return_value=True)
    telegram.send_message = AsyncMock(return_value=True)
    return telegram


@pytest.fixture
def alert_service(mock_alert_repo, mock_price_provider, mock_telegram):
    """Service d'alertes avec mocks."""
    service = AlertService(
        alert_repo=mock_alert_repo,
        price_provider=mock_price_provider,
    )
    service._telegram = mock_telegram
    return service


@pytest.fixture
def sample_alert():
    """Alerte de test."""
    return Alert(
        id="test-alert-001",
        ticker="AAPL",
        alert_type=AlertType.PRICE_ABOVE,
        target_value=200.0,
        current_value=150.0,
        is_active=True,
        is_triggered=False,
        notes="Test alert",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )


# =============================================================================
# TESTS - AlertService.create_alert
# =============================================================================

class TestAlertServiceCreate:
    """Tests pour la création d'alertes."""

    @pytest.mark.asyncio
    async def test_create_alert_price_above(self, alert_service, mock_alert_repo, sample_alert):
        """Test création alerte prix au-dessus."""
        mock_alert_repo.create.return_value = sample_alert

        result = await alert_service.create_alert(
            ticker="AAPL",
            alert_type="price_above",
            target_value=200.0,
            notes="Test"
        )

        assert result.ticker == "AAPL"
        assert result.target_value == 200.0
        mock_alert_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_alert_price_below(self, alert_service, mock_alert_repo, sample_alert):
        """Test création alerte prix en-dessous."""
        sample_alert.alert_type = AlertType.PRICE_BELOW
        sample_alert.target_value = 100.0
        mock_alert_repo.create.return_value = sample_alert

        result = await alert_service.create_alert(
            ticker="AAPL",
            alert_type="price_below",
            target_value=100.0
        )

        assert result.alert_type == AlertType.PRICE_BELOW
        assert result.target_value == 100.0

    @pytest.mark.asyncio
    async def test_create_alert_invalid_type(self, alert_service):
        """Test erreur avec type d'alerte invalide."""
        with pytest.raises(ValueError, match="Type d'alerte invalide"):
            await alert_service.create_alert(
                ticker="AAPL",
                alert_type="invalid_type",
                target_value=200.0
            )


# =============================================================================
# TESTS - AlertService.check_alert
# =============================================================================

class TestAlertServiceCheck:
    """Tests pour la vérification des alertes."""

    @pytest.mark.asyncio
    async def test_check_alert_triggers_price_above(
        self, alert_service, mock_price_provider, mock_alert_repo, mock_telegram, sample_alert
    ):
        """Test déclenchement alerte prix au-dessus."""
        # Prix actuel au-dessus de la cible
        mock_quote = MagicMock()
        mock_quote.price = 210.0  # Au-dessus de 200.0
        mock_price_provider.get_current_quote.return_value = mock_quote

        result = await alert_service.check_alert(sample_alert)

        assert result is True
        mock_alert_repo.mark_triggered.assert_called_once_with(sample_alert.id)
        mock_telegram.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_alert_no_trigger_price_not_reached(
        self, alert_service, mock_price_provider, sample_alert
    ):
        """Test pas de déclenchement si prix pas atteint."""
        mock_quote = MagicMock()
        mock_quote.price = 190.0  # En-dessous de 200.0
        mock_price_provider.get_current_quote.return_value = mock_quote

        result = await alert_service.check_alert(sample_alert)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_alert_already_triggered(self, alert_service, sample_alert):
        """Test pas de vérification si déjà déclenchée."""
        sample_alert.is_triggered = True

        result = await alert_service.check_alert(sample_alert)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_alert_inactive(self, alert_service, sample_alert):
        """Test pas de vérification si inactive."""
        sample_alert.is_active = False

        result = await alert_service.check_alert(sample_alert)

        assert result is False


# =============================================================================
# TESTS - Ticker conversion
# =============================================================================

class TestTickerConversion:
    """Tests pour la conversion des tickers."""

    def test_ticker_valid_simple(self):
        """Test ticker simple valide."""
        ticker = Ticker("AAPL")
        assert ticker.value == "AAPL"

    def test_ticker_valid_with_exchange(self):
        """Test ticker avec exchange."""
        ticker = Ticker("VUSA:XMIL")
        assert ticker.value == "VUSA:XMIL"

    def test_ticker_normalized_to_uppercase(self):
        """Test normalisation en majuscules."""
        ticker = Ticker("aapl")
        assert ticker.value == "AAPL"

    def test_ticker_with_colon_valid(self):
        """Test ticker avec deux-points valide."""
        ticker = Ticker("JEPI:XMIL")
        assert ticker.value == "JEPI:XMIL"


# =============================================================================
# TESTS - Alert.should_trigger
# =============================================================================

class TestAlertShouldTrigger:
    """Tests pour la méthode should_trigger."""

    def test_should_trigger_price_above(self, sample_alert):
        """Test déclenchement prix au-dessus."""
        sample_alert.alert_type = AlertType.PRICE_ABOVE
        sample_alert.target_value = 200.0

        assert sample_alert.should_trigger(210.0) is True
        assert sample_alert.should_trigger(200.0) is True
        assert sample_alert.should_trigger(190.0) is False

    def test_should_trigger_price_below(self, sample_alert):
        """Test déclenchement prix en-dessous."""
        sample_alert.alert_type = AlertType.PRICE_BELOW
        sample_alert.target_value = 100.0

        assert sample_alert.should_trigger(90.0) is True
        assert sample_alert.should_trigger(100.0) is True
        assert sample_alert.should_trigger(110.0) is False

    def test_should_not_trigger_if_inactive(self, sample_alert):
        """Test pas de déclenchement si inactive."""
        sample_alert.is_active = False
        assert sample_alert.should_trigger(210.0) is False

    def test_should_not_trigger_if_already_triggered(self, sample_alert):
        """Test pas de déclenchement si déjà déclenchée."""
        sample_alert.is_triggered = True
        assert sample_alert.should_trigger(210.0) is False


# =============================================================================
# TESTS - TechnicalAlertService
# =============================================================================

class TestTechnicalAlertService:
    """Tests pour le service d'alertes techniques."""

    def test_calculate_rsi(self):
        """Test calcul RSI."""
        service = TechnicalAlertService()

        # Prix en hausse constante -> RSI élevé
        prices_up = [100 + i for i in range(20)]
        rsi = service._calculate_rsi(prices_up)
        assert rsi is not None
        assert rsi > 70  # Surachat

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI avec données insuffisantes."""
        service = TechnicalAlertService()

        prices = [100, 101, 102]  # Pas assez de données
        rsi = service._calculate_rsi(prices)
        assert rsi is None

    def test_check_rsi_signal_overbought(self):
        """Test signal RSI surachat."""
        service = TechnicalAlertService()

        signal = service._check_rsi_signal("AAPL", 150.0, 75.0)

        assert signal is not None
        assert signal.signal_type == "rsi_overbought"
        assert signal.ticker == "AAPL"

    def test_check_rsi_signal_oversold(self):
        """Test signal RSI survente."""
        service = TechnicalAlertService()

        signal = service._check_rsi_signal("AAPL", 150.0, 25.0)

        assert signal is not None
        assert signal.signal_type == "rsi_oversold"

    def test_check_rsi_signal_normal(self):
        """Test pas de signal RSI si normal."""
        service = TechnicalAlertService()

        signal = service._check_rsi_signal("AAPL", 150.0, 50.0)

        assert signal is None


# =============================================================================
# TESTS - Stop Loss / Take Profit Price Calculation
# =============================================================================

class TestSLTPCalculation:
    """Tests pour le calcul des prix SL/TP."""

    def test_stop_loss_price_calculation(self):
        """Test calcul prix stop loss."""
        current_price = 100.0
        stop_loss_percent = 8.0

        sl_price = current_price * (1 - stop_loss_percent / 100)

        assert sl_price == 92.0

    def test_take_profit_price_calculation(self):
        """Test calcul prix take profit."""
        current_price = 100.0
        take_profit_percent = 24.0

        tp_price = current_price * (1 + take_profit_percent / 100)

        assert tp_price == 124.0

    def test_sl_tp_with_real_values(self):
        """Test calcul SL/TP avec valeurs réelles."""
        # Cas d'utilisation réel
        current_price = 47.85  # Prix VUSA exemple
        sl_percent = 8.0
        tp_percent = 24.0

        sl_price = current_price * (1 - sl_percent / 100)
        tp_price = current_price * (1 + tp_percent / 100)

        assert round(sl_price, 2) == 44.02
        assert round(tp_price, 2) == 59.33


# =============================================================================
# TESTS - AlertType enum handling
# =============================================================================

class TestAlertTypeHandling:
    """Tests pour la gestion des types d'alertes."""

    def test_alert_type_from_string(self):
        """Test conversion string vers AlertType."""
        alert_type = AlertType("price_above")
        assert alert_type == AlertType.PRICE_ABOVE

    def test_alert_type_value(self):
        """Test valeur du type d'alerte."""
        assert AlertType.PRICE_ABOVE.value == "price_above"
        assert AlertType.PRICE_BELOW.value == "price_below"
        assert AlertType.PERCENT_CHANGE.value == "percent_change"

    def test_alert_type_has_value_attribute(self):
        """Test que AlertType a l'attribut value."""
        alert_type = AlertType.PRICE_ABOVE
        assert hasattr(alert_type, 'value')
        assert alert_type.value == "price_above"

    def test_string_does_not_have_value_attribute(self):
        """Test qu'une string n'a pas l'attribut value."""
        alert_type_str = "price_above"
        assert not hasattr(alert_type_str, 'value')


# =============================================================================
# TESTS - Saxo to Yahoo ticker conversion
# =============================================================================

class TestSaxoToYahooConversion:
    """Tests pour la conversion des tickers Saxo vers Yahoo Finance."""

    def test_convert_xmil_to_mi(self):
        """Test conversion Milan XMIL -> .MI"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("VUSA:XMIL") == "VUSA.MI"

    def test_convert_xetr_to_de(self):
        """Test conversion Frankfurt XETR -> .DE"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("SAP:XETR") == "SAP.DE"

    def test_convert_xpar_to_pa(self):
        """Test conversion Paris XPAR -> .PA"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("MC:XPAR") == "MC.PA"

    def test_convert_xnas_no_suffix(self):
        """Test conversion NASDAQ - pas de suffixe"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("AAPL:XNAS") == "AAPL"

    def test_convert_xnys_no_suffix(self):
        """Test conversion NYSE - pas de suffixe"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("IBM:XNYS") == "IBM"

    def test_no_conversion_simple_ticker(self):
        """Test pas de conversion pour ticker simple"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("AAPL") == "AAPL"

    def test_no_conversion_yahoo_format(self):
        """Test pas de conversion pour format Yahoo existant"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("VUSA.MI") == "VUSA.MI"

    def test_convert_lowercase_exchange(self):
        """Test conversion avec exchange en minuscules"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("VUSA:xmil") == "VUSA.MI"

    def test_convert_xlon_to_l(self):
        """Test conversion London XLON -> .L"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("VOD:XLON") == "VOD.L"

    def test_convert_xams_to_as(self):
        """Test conversion Amsterdam XAMS -> .AS"""
        from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
        provider = YahooFinanceProvider()
        assert provider._convert_saxo_to_yahoo_ticker("ASML:XAMS") == "ASML.AS"
