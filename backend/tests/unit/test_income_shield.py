"""
Tests unitaires pour les fonctionnalites Income Shield.

Ce fichier teste:
- MarketRegimeProvider: Signaux macro et regime de marche
- Income domain models: IncomeCategory, YieldMetrics, etc.

Utilisation:
    pytest tests/unit/test_income_shield.py -v
    pytest tests/unit/test_income_shield.py -v -k "test_market_regime"
"""

import pytest
from datetime import date, datetime
from unittest.mock import patch
import numpy as np

# Domain models
from src.domain.entities.income_portfolio import (
    IncomeCategory,
    YieldMetrics,
    BacktestConfig,
    INCOME_ASSET_TICKERS,
    get_category_for_ticker,
    get_tickers_for_category,
)

# Providers
from src.infrastructure.providers.market_regime_provider import (
    MarketRegimeProvider,
    MarketSignals,
    MarketRegime,
    RegimeType,
    AntiWhipsawState,
)


# =============================================================================
# TESTS: Income Portfolio Domain Models
# =============================================================================

class TestIncomeCategory:
    """Tests pour l'enum IncomeCategory."""

    def test_income_category_values(self):
        """Verifie que toutes les categories sont definies."""
        assert IncomeCategory.BDC.value == "bdc"
        assert IncomeCategory.COVERED_CALL.value == "covered_call"
        assert IncomeCategory.CEF.value == "cef"
        assert IncomeCategory.MREIT.value == "mreit"
        assert IncomeCategory.CASH_LIKE.value == "cash_like"
        assert IncomeCategory.DIVIDEND_GROWTH.value == "dividend_growth"
        assert IncomeCategory.BONDS.value == "bonds"

    def test_income_asset_tickers_defined(self):
        """Verifie que les tickers sont definis pour chaque categorie."""
        for category in IncomeCategory:
            assert category in INCOME_ASSET_TICKERS
            assert len(INCOME_ASSET_TICKERS[category]) > 0

    def test_get_category_for_ticker(self):
        """Teste la recherche de categorie par ticker."""
        assert get_category_for_ticker("ARCC") == IncomeCategory.BDC
        assert get_category_for_ticker("JEPI") == IncomeCategory.COVERED_CALL
        assert get_category_for_ticker("BST") == IncomeCategory.CEF
        assert get_category_for_ticker("AGNC") == IncomeCategory.MREIT
        assert get_category_for_ticker("SGOV") == IncomeCategory.CASH_LIKE
        assert get_category_for_ticker("UNKNOWN") is None

    def test_get_tickers_for_category(self):
        """Teste la recuperation des tickers par categorie."""
        bdc_tickers = get_tickers_for_category(IncomeCategory.BDC)
        assert "ARCC" in bdc_tickers
        assert "MAIN" in bdc_tickers

        covered_call_tickers = get_tickers_for_category(IncomeCategory.COVERED_CALL)
        assert "JEPI" in covered_call_tickers


class TestYieldMetrics:
    """Tests pour YieldMetrics."""

    def test_yield_metrics_creation(self):
        """Teste la creation de YieldMetrics."""
        metrics = YieldMetrics(
            current_yield=7.5,
            trailing_12m_yield=7.2,
            sec_yield=7.0,
            monthly_income_per_1000=6.25,
        )

        assert metrics.current_yield == 7.5
        assert metrics.trailing_12m_yield == 7.2
        assert metrics.monthly_income_per_1000 == 6.25

    def test_yield_metrics_to_dict(self):
        """Teste la serialisation de YieldMetrics."""
        metrics = YieldMetrics(
            current_yield=7.5,
            trailing_12m_yield=7.2,
            monthly_income_per_1000=6.25,
        )

        data = metrics.to_dict()
        assert data["current_yield"] == 7.5
        assert data["monthly_income_per_1000"] == 6.25


class TestBacktestConfig:
    """Tests pour BacktestConfig."""

    def test_backtest_config_defaults(self):
        """Teste les valeurs par defaut de BacktestConfig."""
        config = BacktestConfig(
            allocation={"JEPI": 50, "SCHD": 50},
            start_date=date(2020, 1, 1),
            end_date=date(2023, 12, 31),
        )

        assert config.initial_capital == 10000
        assert config.monthly_contribution == 0
        assert config.risk_off_enabled is True
        assert config.rebalance_frequency == "monthly"

    def test_backtest_config_custom(self):
        """Teste BacktestConfig avec valeurs personnalisees."""
        config = BacktestConfig(
            allocation={"JEPI": 30, "SCHD": 30, "SGOV": 40},
            start_date=date(2015, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=50000,
            monthly_contribution=1000,
            risk_off_enabled=False,
            rebalance_frequency="quarterly",
        )

        assert config.initial_capital == 50000
        assert config.monthly_contribution == 1000
        assert config.risk_off_enabled is False
        assert config.rebalance_frequency == "quarterly"


# =============================================================================
# TESTS: Market Regime Provider
# =============================================================================

class TestMarketSignals:
    """Tests pour MarketSignals."""

    def test_stress_count_no_stress(self):
        """Teste stress_count sans signaux actifs."""
        signals = MarketSignals()
        assert signals.stress_count == 0
        assert signals.is_high_stress is False

    def test_stress_count_partial_stress(self):
        """Teste stress_count avec quelques signaux."""
        signals = MarketSignals(
            credit_stress=True,
            vix_elevated=True,
        )
        assert signals.stress_count == 2
        assert signals.is_high_stress is False

    def test_stress_count_high_stress(self):
        """Teste stress_count avec plusieurs signaux."""
        signals = MarketSignals(
            credit_stress=True,
            vix_elevated=True,
            spy_below_sma200=True,
            spy_drawdown_alert=True,
        )
        assert signals.stress_count == 4
        assert signals.is_high_stress is True

    def test_signals_to_dict(self):
        """Teste la serialisation de MarketSignals."""
        signals = MarketSignals(
            credit_stress=True,
            vix_level=28.5,
            spy_price=420.0,
        )

        data = signals.to_dict()
        assert data["credit_stress"] is True
        assert data["stress_count"] == 1
        assert data["raw_values"]["vix_level"] == 28.5


class TestAntiWhipsawState:
    """Tests pour AntiWhipsawState."""

    def test_risk_off_not_confirmed_initially(self):
        """Teste que risk-off n'est pas confirme initialement."""
        state = AntiWhipsawState()
        assert state.risk_off_confirmed is False
        assert state.risk_on_confirmed is False

    def test_risk_off_confirmed_after_threshold(self):
        """Teste la confirmation risk-off apres le seuil."""
        state = AntiWhipsawState(days_in_risk_off_signal=7)
        assert state.risk_off_confirmed is True

    def test_risk_on_confirmed_after_threshold(self):
        """Teste la confirmation risk-on apres le seuil."""
        state = AntiWhipsawState(days_in_risk_on_signal=14)
        assert state.risk_on_confirmed is True

    def test_to_dict(self):
        """Teste la serialisation de AntiWhipsawState."""
        state = AntiWhipsawState(
            days_in_risk_off_signal=5,
            days_in_risk_on_signal=3,
            current_mode="risk_off",
        )
        data = state.to_dict()
        assert data["days_in_risk_off_signal"] == 5
        assert data["current_mode"] == "risk_off"


class TestMarketRegimeProvider:
    """Tests pour MarketRegimeProvider."""

    def test_provider_initialization(self):
        """Teste l'initialisation du provider."""
        provider = MarketRegimeProvider(cache_ttl=600)
        assert provider._cache_ttl == 600

    def test_determine_regime_risk_on(self):
        """Teste la determination du regime Risk-On."""
        provider = MarketRegimeProvider()
        signals = MarketSignals()  # Pas de stress

        regime = provider._determine_regime(signals)
        assert regime == RegimeType.RISK_ON

    def test_determine_regime_neutral(self):
        """Teste la determination du regime Neutral."""
        provider = MarketRegimeProvider()
        signals = MarketSignals(credit_stress=True)  # 1 signal

        regime = provider._determine_regime(signals)
        assert regime == RegimeType.NEUTRAL

    def test_determine_regime_risk_off(self):
        """Teste la determination du regime Risk-Off."""
        provider = MarketRegimeProvider()
        signals = MarketSignals(
            credit_stress=True,
            vix_elevated=True,
            spy_below_sma200=True,
        )  # 3 signaux

        regime = provider._determine_regime(signals)
        assert regime == RegimeType.RISK_OFF

    def test_determine_regime_high_uncertainty_vix_spike(self):
        """Teste High Uncertainty avec VIX spike."""
        provider = MarketRegimeProvider()
        signals = MarketSignals(vix_spike=True)

        regime = provider._determine_regime(signals)
        assert regime == RegimeType.HIGH_UNCERTAINTY

    def test_calculate_confidence_risk_on(self):
        """Teste le calcul de confiance en Risk-On."""
        provider = MarketRegimeProvider()
        signals = MarketSignals()

        confidence = provider._calculate_confidence(signals, RegimeType.RISK_ON)
        assert confidence == 100  # Max confidence sans stress

    def test_calculate_confidence_risk_off(self):
        """Teste le calcul de confiance en Risk-Off."""
        provider = MarketRegimeProvider()
        signals = MarketSignals(
            credit_stress=True,
            vix_elevated=True,
            spy_below_sma200=True,
        )

        confidence = provider._calculate_confidence(signals, RegimeType.RISK_OFF)
        assert confidence == 80  # 50 + (3 * 10)

    def test_allocations_defined_for_all_regimes(self):
        """Verifie que les allocations sont definies pour tous les regimes."""
        provider = MarketRegimeProvider()

        for regime in RegimeType:
            assert regime in provider.ALLOCATIONS
            allocation = provider.ALLOCATIONS[regime]
            assert sum(allocation.values()) == 100

    def test_generate_interpretation_risk_on(self):
        """Teste la generation d'interpretation pour Risk-On."""
        provider = MarketRegimeProvider()
        signals = MarketSignals()

        interpretation = provider._generate_interpretation(signals, RegimeType.RISK_ON)
        assert "favorables" in interpretation.lower()

    def test_generate_interpretation_risk_off(self):
        """Teste la generation d'interpretation pour Risk-Off."""
        provider = MarketRegimeProvider()
        signals = MarketSignals(credit_stress=True, vix_elevated=True)

        interpretation = provider._generate_interpretation(signals, RegimeType.RISK_OFF)
        # Note: accents francais - défavorables, défensifs
        assert "favorables" in interpretation.lower() or "fensifs" in interpretation.lower()

    def test_interpret_vix_low(self):
        """Teste l'interpretation VIX faible."""
        provider = MarketRegimeProvider()
        result = provider._interpret_vix(10)
        assert "complaisance" in result.lower()

    def test_interpret_vix_normal(self):
        """Teste l'interpretation VIX normal."""
        provider = MarketRegimeProvider()
        result = provider._interpret_vix(20)
        assert "normal" in result.lower()

    def test_interpret_vix_high(self):
        """Teste l'interpretation VIX eleve."""
        provider = MarketRegimeProvider()
        result = provider._interpret_vix(28)
        assert "prudence" in result.lower() or "eleve" in result.lower()

    def test_interpret_vix_extreme(self):
        """Teste l'interpretation VIX extreme."""
        provider = MarketRegimeProvider()
        result = provider._interpret_vix(35)
        assert "extreme" in result.lower() or "panique" in result.lower()


class TestMarketRegime:
    """Tests pour MarketRegime."""

    def test_market_regime_to_dict(self):
        """Teste la serialisation de MarketRegime."""
        signals = MarketSignals(credit_stress=True, vix_level=25.0)
        regime = MarketRegime(
            regime=RegimeType.NEUTRAL,
            signals=signals,
            confidence=65.0,
            recommended_allocation={"growth": 25, "income": 30, "defensive": 30, "cash": 15},
            interpretation="Signaux mixtes",
        )

        data = regime.to_dict()
        assert data["regime"] == "neutral"
        assert data["confidence"] == 65.0
        assert data["signals"]["credit_stress"] is True


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
