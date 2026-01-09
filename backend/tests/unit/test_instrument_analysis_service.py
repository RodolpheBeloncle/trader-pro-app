"""
Tests unitaires pour le service d'analyse d'instrument.

Ces tests verifient:
- L'analyse technique d'un instrument
- L'analyse de sentiment
- Le calcul des niveaux de trading
- La generation de recommandations
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from src.application.services.instrument_analysis_service import (
    InstrumentAnalysisService,
    InstrumentInfo,
    PriceData,
    TechnicalAnalysis,
    SentimentAnalysis,
    TradingLevels,
    BuyRecommendation,
    InstrumentAnalysis,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_yahoo_provider():
    """Mock du provider Yahoo Finance."""
    provider = MagicMock()
    provider.get_metadata = AsyncMock()
    provider.get_current_quote = AsyncMock()
    provider.get_historical_data = AsyncMock()
    return provider


@pytest.fixture
def mock_technical_calculator():
    """Mock du calculateur technique."""
    calc = MagicMock()
    calc.calculate_all = AsyncMock()
    return calc


@pytest.fixture
def mock_news_service():
    """Mock du service de news."""
    service = MagicMock()
    service.get_news_for_ticker = AsyncMock()
    return service


@pytest.fixture
def mock_structure_analyzer():
    """Mock de l'analyseur de structure."""
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock()
    return analyzer


@pytest.fixture
def sample_metadata():
    """Metadata de test."""
    meta = MagicMock()
    meta.name = "Apple Inc."
    meta.currency = "USD"
    meta.exchange = "NASDAQ"
    meta.sector = "Technology"
    meta.industry = "Consumer Electronics"
    meta.market_cap = 3000000000000
    return meta


@pytest.fixture
def sample_quote():
    """Quote de test."""
    quote = MagicMock()
    quote.price = 185.50
    quote.change = 2.50
    quote.change_percent = 1.37
    return quote


@pytest.fixture
def sample_historical():
    """Donnees historiques de test."""
    data = []
    base_price = 150.0
    for i in range(365):
        date = datetime.now() - timedelta(days=365 - i)
        price = base_price * (1 + 0.15 * (i / 365))  # +15% sur l'annee
        point = MagicMock()
        point.date = date
        point.open = price * 0.99
        point.high = price * 1.02
        point.low = price * 0.98
        point.close = price
        point.volume = 1000000 + i * 1000
        data.append(point)
    return data


@pytest.fixture
def sample_indicators():
    """Indicateurs techniques de test."""
    indicators = MagicMock()

    # RSI
    indicators.rsi = MagicMock()
    indicators.rsi.value = 55.0

    # MACD
    indicators.macd = MagicMock()
    indicators.macd.macd_line = 1.5
    indicators.macd.signal_line = 1.2
    indicators.macd.histogram = 0.3

    # Moving Averages
    indicators.moving_averages = MagicMock()
    indicators.moving_averages.current_price = 185.50
    indicators.moving_averages.sma_20 = 180.0
    indicators.moving_averages.sma_50 = 175.0
    indicators.moving_averages.sma_200 = 160.0
    indicators.moving_averages.ema_12 = 182.0
    indicators.moving_averages.ema_26 = 178.0

    # Bollinger
    indicators.bollinger = MagicMock()
    indicators.bollinger.upper_band = 195.0
    indicators.bollinger.middle_band = 180.0
    indicators.bollinger.lower_band = 165.0
    indicators.bollinger.current_price = 185.50
    indicators.bollinger.percent_b = 0.68

    # ATR
    indicators.atr = 3.5
    indicators.atr_percent = 1.9

    return indicators


@pytest.fixture
def sample_news():
    """News de test."""
    articles = []
    for i in range(5):
        article = MagicMock()
        article.headline = f"Apple News Article {i+1}"
        article.source = "Reuters"
        article.sentiment_score = 0.3 if i < 3 else -0.1
        articles.append(article)
    return articles


@pytest.fixture
def analysis_service(
    mock_yahoo_provider,
    mock_technical_calculator,
    mock_news_service,
    mock_structure_analyzer,
):
    """Service d'analyse avec mocks."""
    return InstrumentAnalysisService(
        yahoo_provider=mock_yahoo_provider,
        technical_calculator=mock_technical_calculator,
        news_service=mock_news_service,
        structure_analyzer=mock_structure_analyzer,
    )


# =============================================================================
# TESTS - TradingLevels Calculation
# =============================================================================

class TestTradingLevelsCalculation:
    """Tests pour le calcul des niveaux de trading."""

    def test_calculate_trading_levels_basic(self, analysis_service):
        """Test calcul des niveaux SL/TP de base."""
        technical = TechnicalAnalysis(
            rsi=55.0,
            rsi_signal="neutral",
            macd_line=1.5,
            macd_signal=1.2,
            macd_histogram=0.3,
            macd_trend="bullish",
            trend="uptrend",
            trend_strength="moderate",
            sma_20=180.0,
            sma_50=175.0,
            sma_200=160.0,
            ema_12=182.0,
            ema_26=178.0,
            price_vs_sma50="above",
            price_vs_sma200="above",
            bollinger_upper=195.0,
            bollinger_middle=180.0,
            bollinger_lower=165.0,
            bollinger_position="middle",
            percent_b=0.68,
            atr=3.5,
            atr_percent=1.9,
            support_levels=[170.0, 165.0],
            resistance_levels=[190.0, 200.0],
        )

        levels = analysis_service._calculate_trading_levels(185.50, technical)

        assert levels.entry_price == 185.50
        assert levels.suggested_stop_loss < levels.entry_price
        assert levels.suggested_take_profit_1 > levels.entry_price
        assert levels.suggested_take_profit_2 > levels.suggested_take_profit_1
        assert levels.risk_reward_ratio >= 2.0

    def test_trading_levels_with_support(self, analysis_service):
        """Test que le SL respecte les supports."""
        technical = TechnicalAnalysis(
            rsi=55.0,
            rsi_signal="neutral",
            macd_line=1.5,
            macd_signal=1.2,
            macd_histogram=0.3,
            macd_trend="bullish",
            trend="uptrend",
            trend_strength="moderate",
            sma_20=180.0,
            sma_50=175.0,
            sma_200=160.0,
            ema_12=182.0,
            ema_26=178.0,
            price_vs_sma50="above",
            price_vs_sma200="above",
            bollinger_upper=195.0,
            bollinger_middle=180.0,
            bollinger_lower=165.0,
            bollinger_position="middle",
            percent_b=0.68,
            atr=3.5,
            atr_percent=1.9,
            support_levels=[180.0, 175.0],  # Support proche
            resistance_levels=[190.0],
        )

        levels = analysis_service._calculate_trading_levels(185.50, technical)

        # SL devrait etre proche du support
        assert levels.suggested_stop_loss >= 185.50 * 0.90  # Max 10% de perte


# =============================================================================
# TESTS - Recommendation Generation
# =============================================================================

class TestRecommendationGeneration:
    """Tests pour la generation de recommandations."""

    def test_buy_recommendation_uptrend_oversold(self, analysis_service):
        """Test recommandation BUY en tendance haussiere avec RSI bas."""
        price = PriceData(
            current_price=185.50,
            open=183.0,
            high=186.0,
            low=182.0,
            previous_close=183.0,
            change=2.50,
            change_percent=1.37,
            volume=50000000,
            avg_volume=45000000,
            week_52_high=200.0,
            week_52_low=120.0,
        )

        technical = TechnicalAnalysis(
            rsi=28.0,  # Survendu
            rsi_signal="oversold",
            macd_line=1.5,
            macd_signal=1.2,
            macd_histogram=0.3,
            macd_trend="bullish",
            trend="uptrend",
            trend_strength="strong",
            sma_20=180.0,
            sma_50=175.0,
            sma_200=160.0,
            ema_12=182.0,
            ema_26=178.0,
            price_vs_sma50="above",
            price_vs_sma200="above",
            bollinger_upper=195.0,
            bollinger_middle=180.0,
            bollinger_lower=165.0,
            bollinger_position="below_lower",  # Survente Bollinger
            percent_b=0.1,
            atr=3.5,
            atr_percent=1.9,
            support_levels=[170.0],
            resistance_levels=[190.0],
        )

        sentiment = SentimentAnalysis(
            sentiment_score=0.3,
            sentiment_label="bullish",
            news_count=5,
            recent_headlines=[],
        )

        trading_levels = TradingLevels(
            entry_price=185.50,
            suggested_stop_loss=175.0,
            suggested_take_profit_1=195.0,
            suggested_take_profit_2=205.0,
            stop_loss_distance_pct=5.7,
            take_profit_1_distance_pct=5.1,
            take_profit_2_distance_pct=10.5,
            risk_reward_ratio=2.0,
            invalidation_level=165.0,
        )

        recommendation = analysis_service._generate_recommendation(
            "AAPL", price, technical, sentiment, trading_levels
        )

        assert recommendation.action == "BUY"
        assert recommendation.confidence > 40
        assert recommendation.rating >= 4
        assert len(recommendation.pros) > 0

    def test_avoid_recommendation_downtrend_overbought(self, analysis_service):
        """Test recommandation AVOID en tendance baissiere avec RSI eleve."""
        price = PriceData(
            current_price=185.50,
            open=188.0,
            high=189.0,
            low=184.0,
            previous_close=188.0,
            change=-2.50,
            change_percent=-1.33,
            volume=60000000,
            avg_volume=45000000,
            week_52_high=200.0,
            week_52_low=120.0,
        )

        technical = TechnicalAnalysis(
            rsi=78.0,  # Surchauffe
            rsi_signal="overbought",
            macd_line=-1.5,
            macd_signal=-1.2,
            macd_histogram=-0.3,
            macd_trend="bearish",
            trend="downtrend",
            trend_strength="strong",
            sma_20=190.0,
            sma_50=195.0,
            sma_200=200.0,
            ema_12=188.0,
            ema_26=192.0,
            price_vs_sma50="below",
            price_vs_sma200="below",
            bollinger_upper=195.0,
            bollinger_middle=185.0,
            bollinger_lower=175.0,
            bollinger_position="above_upper",  # Surachat Bollinger
            percent_b=0.95,
            atr=5.0,
            atr_percent=2.7,
            support_levels=[170.0],
            resistance_levels=[190.0],
        )

        sentiment = SentimentAnalysis(
            sentiment_score=-0.3,
            sentiment_label="bearish",
            news_count=5,
            recent_headlines=[],
        )

        trading_levels = TradingLevels(
            entry_price=185.50,
            suggested_stop_loss=175.0,
            suggested_take_profit_1=195.0,
            suggested_take_profit_2=205.0,
            stop_loss_distance_pct=5.7,
            take_profit_1_distance_pct=5.1,
            take_profit_2_distance_pct=10.5,
            risk_reward_ratio=2.0,
            invalidation_level=175.0,
        )

        recommendation = analysis_service._generate_recommendation(
            "AAPL", price, technical, sentiment, trading_levels
        )

        assert recommendation.action == "AVOID"
        assert recommendation.rating <= 2
        assert len(recommendation.cons) > 0

    def test_wait_recommendation_neutral(self, analysis_service):
        """Test recommandation WAIT en conditions neutres."""
        price = PriceData(
            current_price=185.50,
            open=185.0,
            high=186.0,
            low=184.0,
            previous_close=185.0,
            change=0.50,
            change_percent=0.27,
            volume=45000000,
            avg_volume=45000000,
            week_52_high=200.0,
            week_52_low=150.0,
        )

        technical = TechnicalAnalysis(
            rsi=50.0,  # Neutre
            rsi_signal="neutral",
            macd_line=0.1,
            macd_signal=0.1,
            macd_histogram=0.0,
            macd_trend="neutral",
            trend="sideways",
            trend_strength="weak",
            sma_20=185.0,
            sma_50=184.0,
            sma_200=180.0,
            ema_12=185.0,
            ema_26=184.0,
            price_vs_sma50="above",
            price_vs_sma200="above",
            bollinger_upper=190.0,
            bollinger_middle=185.0,
            bollinger_lower=180.0,
            bollinger_position="middle",
            percent_b=0.5,
            atr=2.5,
            atr_percent=1.4,
            support_levels=[180.0],
            resistance_levels=[190.0],
        )

        sentiment = SentimentAnalysis(
            sentiment_score=0.0,
            sentiment_label="neutral",
            news_count=3,
            recent_headlines=[],
        )

        trading_levels = TradingLevels(
            entry_price=185.50,
            suggested_stop_loss=178.0,
            suggested_take_profit_1=193.0,
            suggested_take_profit_2=200.0,
            stop_loss_distance_pct=4.0,
            take_profit_1_distance_pct=4.0,
            take_profit_2_distance_pct=7.8,
            risk_reward_ratio=2.0,
            invalidation_level=180.0,
        )

        recommendation = analysis_service._generate_recommendation(
            "AAPL", price, technical, sentiment, trading_levels
        )

        assert recommendation.action == "WAIT"
        assert recommendation.rating == 3


# =============================================================================
# TESTS - Full Analysis
# =============================================================================

class TestFullAnalysis:
    """Tests pour l'analyse complete."""

    @pytest.mark.asyncio
    async def test_analyze_instrument_success(
        self,
        analysis_service,
        mock_yahoo_provider,
        mock_technical_calculator,
        mock_news_service,
        mock_structure_analyzer,
        sample_metadata,
        sample_quote,
        sample_historical,
        sample_indicators,
        sample_news,
    ):
        """Test analyse complete d'un instrument."""
        # Configurer les mocks
        mock_yahoo_provider.get_metadata.return_value = sample_metadata
        mock_yahoo_provider.get_current_quote.return_value = sample_quote
        mock_yahoo_provider.get_historical_data.return_value = sample_historical
        mock_technical_calculator.calculate_all.return_value = sample_indicators
        mock_news_service.get_news_for_ticker.return_value = sample_news
        mock_structure_analyzer.analyze.return_value = None

        # Executer l'analyse
        result = await analysis_service.analyze_instrument("AAPL")

        # Verifier le resultat
        assert result.info.symbol == "AAPL"
        assert result.info.name == "Apple Inc."
        assert result.price.current_price == 185.50
        assert result.technical is not None
        assert result.sentiment is not None
        assert result.trading_levels is not None
        assert result.recommendation is not None
        assert result.recommendation.action in ["BUY", "WAIT", "AVOID"]

    @pytest.mark.asyncio
    async def test_analyze_instrument_insufficient_data(
        self,
        analysis_service,
        mock_yahoo_provider,
        mock_technical_calculator,
        sample_metadata,
        sample_quote,
    ):
        """Test erreur avec donnees insuffisantes."""
        mock_yahoo_provider.get_metadata.return_value = sample_metadata
        mock_yahoo_provider.get_current_quote.return_value = sample_quote
        mock_yahoo_provider.get_historical_data.return_value = []  # Pas de donnees

        with pytest.raises(ValueError, match="donnees insuffisantes"):
            await analysis_service.analyze_instrument("AAPL")


# =============================================================================
# TESTS - Data Classes
# =============================================================================

class TestDataClasses:
    """Tests pour les dataclasses."""

    def test_instrument_info_to_dict(self):
        """Test serialisation InstrumentInfo."""
        info = InstrumentInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
            sector="Technology",
        )

        data = info.to_dict()

        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["currency"] == "USD"

    def test_price_data_to_dict(self):
        """Test serialisation PriceData."""
        price = PriceData(
            current_price=185.50,
            open=183.0,
            high=186.0,
            low=182.0,
            previous_close=183.0,
            change=2.50,
            change_percent=1.37,
            volume=50000000,
        )

        data = price.to_dict()

        assert data["current_price"] == 185.50
        assert data["change"] == 2.50

    def test_recommendation_to_dict(self):
        """Test serialisation BuyRecommendation."""
        rec = BuyRecommendation(
            action="BUY",
            confidence=75.0,
            rating=4,
            reasoning=["Tendance haussiere"],
            pros=["RSI bas", "MACD bullish"],
            cons=["Volatilite elevee"],
        )

        data = rec.to_dict()

        assert data["action"] == "BUY"
        assert data["confidence"] == 75.0
        assert data["rating"] == 4
        assert len(data["pros"]) == 2
        assert len(data["cons"]) == 1


# =============================================================================
# TESTS - Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests pour les cas limites."""

    def test_default_info(self, analysis_service):
        """Test info par defaut."""
        info = analysis_service._default_info("UNKNOWN")

        assert info.symbol == "UNKNOWN"
        assert info.name == "UNKNOWN"
        assert info.currency == "USD"

    def test_default_sentiment(self, analysis_service):
        """Test sentiment par defaut."""
        sentiment = analysis_service._default_sentiment("AAPL")

        assert sentiment.sentiment_score == 0.0
        assert sentiment.sentiment_label == "unknown"
        assert sentiment.news_count == 0
