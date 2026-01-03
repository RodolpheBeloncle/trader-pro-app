"""
Moteur de backtest multi-assets avec mode Risk-Off.

Implémente la logique de backtest style IncomeShield:
- Allocation multi-assets
- Mode Risk-Off automatique basé sur les signaux macro
- Anti-Whipsaw (filtres temporels)
- Frais réalistes (FX, slippage, commissions)
- Rebalancement périodique
- Suivi des dividendes

ARCHITECTURE:
- Service de domaine
- Logique métier pure (pas d'appels externes)
- Utilise les données historiques fournies

UTILISATION:
    engine = PortfolioBacktestEngine()
    config = BacktestConfig(...)
    result = await engine.run_backtest(config, historical_data)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

from src.domain.entities.income_portfolio import (
    BacktestConfig,
    BacktestResult,
    RiskOffPeriod,
    EquityPoint,
    TradeRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class HistoricalBar:
    """Une barre de données historiques."""
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    adj_close: Optional[float] = None
    dividend: float = 0.0


@dataclass
class Position:
    """Une position dans le portefeuille."""
    ticker: str
    shares: float
    avg_cost: float
    current_price: float = 0.0

    @property
    def value(self) -> float:
        """Valeur actuelle de la position."""
        return self.shares * self.current_price

    @property
    def pnl(self) -> float:
        """P&L non réalisé."""
        return (self.current_price - self.avg_cost) * self.shares

    @property
    def pnl_percent(self) -> float:
        """P&L en pourcentage."""
        if self.avg_cost == 0:
            return 0
        return ((self.current_price / self.avg_cost) - 1) * 100


@dataclass
class SignalData:
    """Données de signal pour le mode Risk-Off."""
    hyg_close: Optional[float] = None
    lqd_close: Optional[float] = None
    hyg_lqd_ratio: Optional[float] = None
    hyg_lqd_sma50: Optional[float] = None
    vix_close: Optional[float] = None
    vix_sma20: Optional[float] = None
    spy_close: Optional[float] = None
    spy_sma200: Optional[float] = None
    spy_drawdown: Optional[float] = None

    @property
    def credit_stress(self) -> bool:
        """Signal de stress crédit."""
        if self.hyg_lqd_ratio and self.hyg_lqd_sma50:
            return self.hyg_lqd_ratio < self.hyg_lqd_sma50
        return False

    @property
    def vix_elevated(self) -> bool:
        """Signal VIX élevé."""
        if self.vix_close:
            if self.vix_close > 25:
                return True
            if self.vix_sma20 and self.vix_close > self.vix_sma20:
                return True
        return False

    @property
    def spy_weak(self) -> bool:
        """Signal SPY faible."""
        if self.spy_close and self.spy_sma200:
            return self.spy_close < self.spy_sma200
        return False

    @property
    def drawdown_alert(self) -> bool:
        """Alerte de drawdown."""
        if self.spy_drawdown:
            return self.spy_drawdown < -0.10
        return False


class PortfolioBacktestEngine:
    """
    Moteur de backtest multi-assets avec mode Risk-Off.

    Fonctionnalités:
    - Backtest sur période longue (10+ ans)
    - Mode Risk-Off automatique
    - Anti-Whipsaw (confirmation temporelle)
    - Rebalancement périodique
    - Suivi des dividendes
    - Frais réalistes
    """

    # Configuration par défaut
    DEFAULT_RISK_OFF_ALLOCATION = {
        "SGOV": 40,
        "BIL": 30,
        "AGG": 20,
        "BND": 10,
    }

    def __init__(self):
        """Initialise le moteur."""
        self._positions: Dict[str, Position] = {}
        self._cash: float = 0
        self._trades: List[TradeRecord] = []
        self._equity_curve: List[EquityPoint] = []
        self._risk_off_periods: List[RiskOffPeriod] = []
        self._is_risk_off: bool = False
        self._days_in_risk_off_signal: int = 0
        self._days_in_risk_on_signal: int = 0
        self._total_dividends: float = 0
        self._total_fees: float = 0

    async def run_backtest(
        self,
        config: BacktestConfig,
        historical_data: Dict[str, List[HistoricalBar]],
        signal_data: Optional[Dict[date, SignalData]] = None,
    ) -> BacktestResult:
        """
        Exécute le backtest.

        Args:
            config: Configuration du backtest
            historical_data: Données historiques par ticker {ticker: [bars]}
            signal_data: Données de signal par date {date: SignalData}

        Returns:
            BacktestResult avec toutes les métriques
        """
        try:
            # Reset de l'état
            self._reset()
            self._cash = config.initial_capital

            # Validation
            warnings = self._validate_data(config, historical_data)

            # Générer les dates de trading
            all_dates = self._get_trading_dates(config, historical_data)

            if not all_dates:
                return self._create_empty_result(config, ["Aucune date de trading"])

            logger.info(
                f"Running backtest from {all_dates[0]} to {all_dates[-1]} "
                f"({len(all_dates)} trading days)"
            )

            # Variables de suivi
            last_rebalance_date: Optional[date] = None
            current_risk_off_period: Optional[RiskOffPeriod] = None
            rolling_max = config.initial_capital
            monthly_values: List[Tuple[date, float]] = []

            # Boucle principale
            for current_date in all_dates:
                # Mettre à jour les prix
                self._update_prices(current_date, historical_data)

                # Calculer la valeur du portfolio
                portfolio_value = self._calculate_portfolio_value()

                # Collecter les dividendes
                if config.include_dividends:
                    self._collect_dividends(current_date, historical_data)

                # Contribution mensuelle (premier jour du mois)
                if config.monthly_contribution > 0:
                    if current_date.day <= 5:  # Début du mois
                        if not last_rebalance_date or current_date.month != last_rebalance_date.month:
                            self._cash += config.monthly_contribution

                # Vérifier les signaux Risk-Off
                if config.risk_off_enabled and signal_data:
                    signals = signal_data.get(current_date)
                    if signals:
                        should_be_risk_off = self._check_risk_off_trigger(
                            signals, config.risk_off_trigger
                        )

                        # Anti-Whipsaw
                        new_is_risk_off = self._apply_anti_whipsaw(
                            should_be_risk_off,
                            config.risk_off_entry_days,
                            config.risk_off_exit_days,
                        )

                        # Transition
                        if new_is_risk_off != self._is_risk_off:
                            if new_is_risk_off:
                                # Entrer en Risk-Off
                                current_risk_off_period = RiskOffPeriod(
                                    start_date=current_date,
                                    trigger=config.risk_off_trigger,
                                )
                                self._switch_to_risk_off(
                                    current_date,
                                    config,
                                    historical_data,
                                )
                            else:
                                # Sortir de Risk-Off
                                if current_risk_off_period:
                                    current_risk_off_period.end_date = current_date
                                    current_risk_off_period.duration_days = (
                                        current_date - current_risk_off_period.start_date
                                    ).days
                                    self._risk_off_periods.append(current_risk_off_period)
                                    current_risk_off_period = None

                                self._switch_to_risk_on(
                                    current_date,
                                    config,
                                    historical_data,
                                )

                            self._is_risk_off = new_is_risk_off

                # Rebalancement périodique
                should_rebalance = self._should_rebalance(
                    current_date,
                    last_rebalance_date,
                    config.rebalance_frequency,
                )

                if should_rebalance:
                    target = config.allocation if not self._is_risk_off else (
                        config.risk_off_allocation or self.DEFAULT_RISK_OFF_ALLOCATION
                    )
                    self._rebalance(current_date, target, config, historical_data)
                    last_rebalance_date = current_date

                # Mettre à jour la valeur du portfolio
                portfolio_value = self._calculate_portfolio_value()

                # Calculer le drawdown
                rolling_max = max(rolling_max, portfolio_value)
                drawdown = (portfolio_value / rolling_max - 1) if rolling_max > 0 else 0

                # Enregistrer le point d'équité
                self._equity_curve.append(EquityPoint(
                    date=current_date,
                    portfolio_value=portfolio_value,
                    drawdown=drawdown,
                    is_risk_off=self._is_risk_off,
                ))

                # Suivi mensuel pour les rendements
                if not monthly_values or current_date.month != monthly_values[-1][0].month:
                    monthly_values.append((current_date, portfolio_value))

            # Fermer la période Risk-Off si toujours active
            if current_risk_off_period:
                current_risk_off_period.end_date = all_dates[-1]
                current_risk_off_period.duration_days = (
                    all_dates[-1] - current_risk_off_period.start_date
                ).days
                self._risk_off_periods.append(current_risk_off_period)

            # Calculer les métriques finales
            result = self._calculate_metrics(config, all_dates, monthly_values, warnings)

            return result

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return self._create_empty_result(config, [f"Erreur: {str(e)}"])

    def _reset(self):
        """Reset l'état du moteur."""
        self._positions = {}
        self._cash = 0
        self._trades = []
        self._equity_curve = []
        self._risk_off_periods = []
        self._is_risk_off = False
        self._days_in_risk_off_signal = 0
        self._days_in_risk_on_signal = 0
        self._total_dividends = 0
        self._total_fees = 0

    def _validate_data(
        self,
        config: BacktestConfig,
        historical_data: Dict[str, List[HistoricalBar]],
    ) -> List[str]:
        """Valide les données et retourne les warnings."""
        warnings = []

        for ticker in config.allocation.keys():
            if ticker not in historical_data:
                warnings.append(f"Données manquantes pour {ticker}")
            elif len(historical_data[ticker]) < 50:
                warnings.append(f"Historique court pour {ticker} ({len(historical_data[ticker])} jours)")

            # Vérifier si les données couvrent la période demandée
            if ticker in historical_data and historical_data[ticker]:
                first_date = historical_data[ticker][0].date
                if first_date > config.start_date:
                    warnings.append(
                        f"{ticker}: données disponibles à partir de {first_date} "
                        f"(demandé: {config.start_date})"
                    )

        return warnings

    def _get_trading_dates(
        self,
        config: BacktestConfig,
        historical_data: Dict[str, List[HistoricalBar]],
    ) -> List[date]:
        """Récupère toutes les dates de trading."""
        all_dates = set()
        for bars in historical_data.values():
            for bar in bars:
                if config.start_date <= bar.date <= config.end_date:
                    all_dates.add(bar.date)
        return sorted(all_dates)

    def _update_prices(
        self,
        current_date: date,
        historical_data: Dict[str, List[HistoricalBar]],
    ):
        """Met à jour les prix des positions."""
        for ticker, position in self._positions.items():
            if ticker in historical_data:
                bar = self._get_bar_for_date(historical_data[ticker], current_date)
                if bar:
                    position.current_price = bar.close

    def _get_bar_for_date(
        self,
        bars: List[HistoricalBar],
        target_date: date,
    ) -> Optional[HistoricalBar]:
        """Récupère la barre pour une date donnée."""
        for bar in bars:
            if bar.date == target_date:
                return bar
        return None

    def _calculate_portfolio_value(self) -> float:
        """Calcule la valeur totale du portfolio."""
        positions_value = sum(p.value for p in self._positions.values())
        return self._cash + positions_value

    def _collect_dividends(
        self,
        current_date: date,
        historical_data: Dict[str, List[HistoricalBar]],
    ):
        """Collecte les dividendes."""
        for ticker, position in self._positions.items():
            if ticker in historical_data:
                bar = self._get_bar_for_date(historical_data[ticker], current_date)
                if bar and bar.dividend > 0:
                    dividend_amount = bar.dividend * position.shares
                    self._cash += dividend_amount
                    self._total_dividends += dividend_amount

    def _check_risk_off_trigger(
        self,
        signals: SignalData,
        trigger_type: str,
    ) -> bool:
        """Vérifie si le trigger Risk-Off est activé."""
        if trigger_type == "hyg_lqd_below_sma50":
            return signals.credit_stress
        elif trigger_type == "vix_above_25":
            return signals.vix_elevated
        elif trigger_type == "spy_below_sma200":
            return signals.spy_weak
        elif trigger_type == "combined":
            # Au moins 2 signaux sur 4
            count = sum([
                signals.credit_stress,
                signals.vix_elevated,
                signals.spy_weak,
                signals.drawdown_alert,
            ])
            return count >= 2
        return False

    def _apply_anti_whipsaw(
        self,
        should_be_risk_off: bool,
        entry_days: int,
        exit_days: int,
    ) -> bool:
        """Applique le filtre anti-whipsaw."""
        if should_be_risk_off:
            self._days_in_risk_off_signal += 1
            self._days_in_risk_on_signal = 0
        else:
            self._days_in_risk_on_signal += 1
            self._days_in_risk_off_signal = 0

        # Décision
        if self._is_risk_off:
            # Pour sortir de Risk-Off
            return self._days_in_risk_on_signal < exit_days
        else:
            # Pour entrer en Risk-Off
            return self._days_in_risk_off_signal >= entry_days

    def _switch_to_risk_off(
        self,
        current_date: date,
        config: BacktestConfig,
        historical_data: Dict[str, List[HistoricalBar]],
    ):
        """Bascule vers l'allocation Risk-Off."""
        logger.info(f"Switching to Risk-Off mode on {current_date}")
        target = config.risk_off_allocation or self.DEFAULT_RISK_OFF_ALLOCATION
        self._rebalance(current_date, target, config, historical_data, reason="risk_off_entry")

    def _switch_to_risk_on(
        self,
        current_date: date,
        config: BacktestConfig,
        historical_data: Dict[str, List[HistoricalBar]],
    ):
        """Bascule vers l'allocation Risk-On."""
        logger.info(f"Switching to Risk-On mode on {current_date}")
        self._rebalance(
            current_date, config.allocation, config, historical_data, reason="risk_on_entry"
        )

    def _should_rebalance(
        self,
        current_date: date,
        last_rebalance: Optional[date],
        frequency: str,
    ) -> bool:
        """Vérifie si un rebalancement est nécessaire."""
        if last_rebalance is None:
            return True  # Premier rebalancement

        if frequency == "monthly":
            return current_date.month != last_rebalance.month
        elif frequency == "quarterly":
            current_quarter = (current_date.month - 1) // 3
            last_quarter = (last_rebalance.month - 1) // 3
            return current_quarter != last_quarter or current_date.year != last_rebalance.year
        elif frequency == "annual":
            return current_date.year != last_rebalance.year

        return False

    def _rebalance(
        self,
        current_date: date,
        target_allocation: Dict[str, float],
        config: BacktestConfig,
        historical_data: Dict[str, List[HistoricalBar]],
        reason: str = "rebalance",
    ):
        """Exécute le rebalancement."""
        portfolio_value = self._calculate_portfolio_value()

        # Vendre d'abord les positions non désirées
        for ticker in list(self._positions.keys()):
            if ticker not in target_allocation:
                position = self._positions[ticker]
                if position.shares > 0:
                    self._sell_position(
                        current_date, ticker, position.shares, config, reason
                    )

        # Calculer les cibles
        for ticker, weight in target_allocation.items():
            target_value = (weight / 100) * portfolio_value
            current_value = self._positions[ticker].value if ticker in self._positions else 0

            # Récupérer le prix actuel
            price = self._get_current_price(ticker, current_date, historical_data)
            if not price or price <= 0:
                continue

            diff_value = target_value - current_value

            if diff_value > 0:
                # Acheter
                shares = diff_value / price
                self._buy_position(current_date, ticker, shares, price, config, reason)
            elif diff_value < -50:  # Seuil minimum pour vendre
                # Vendre
                shares = abs(diff_value) / price
                if ticker in self._positions:
                    shares = min(shares, self._positions[ticker].shares)
                    if shares > 0:
                        self._sell_position(current_date, ticker, shares, config, reason)

    def _get_current_price(
        self,
        ticker: str,
        current_date: date,
        historical_data: Dict[str, List[HistoricalBar]],
    ) -> Optional[float]:
        """Récupère le prix courant d'un ticker."""
        if ticker in historical_data:
            bar = self._get_bar_for_date(historical_data[ticker], current_date)
            if bar:
                return bar.close
        return None

    def _buy_position(
        self,
        current_date: date,
        ticker: str,
        shares: float,
        price: float,
        config: BacktestConfig,
        reason: str,
    ):
        """Achète une position."""
        # Calculer les frais
        amount = shares * price
        slippage = amount * config.slippage
        fx_fee = amount * config.fx_fee
        commission = config.commission_per_trade
        total_fees = slippage + fx_fee + commission

        # Vérifier le cash disponible
        total_cost = amount + total_fees
        if total_cost > self._cash:
            # Ajuster les shares
            available = self._cash - total_fees
            if available <= 0:
                return
            shares = available / price
            amount = shares * price
            total_cost = amount + total_fees

        # Exécuter l'achat
        self._cash -= total_cost
        self._total_fees += total_fees

        if ticker in self._positions:
            # Moyenner le coût
            pos = self._positions[ticker]
            total_shares = pos.shares + shares
            avg_cost = (pos.shares * pos.avg_cost + shares * price) / total_shares
            pos.shares = total_shares
            pos.avg_cost = avg_cost
            pos.current_price = price
        else:
            self._positions[ticker] = Position(
                ticker=ticker,
                shares=shares,
                avg_cost=price,
                current_price=price,
            )

        # Enregistrer le trade
        self._trades.append(TradeRecord(
            date=current_date,
            ticker=ticker,
            action="buy",
            shares=shares,
            price=price,
            amount=amount,
            fees=total_fees,
            reason=reason,
        ))

    def _sell_position(
        self,
        current_date: date,
        ticker: str,
        shares: float,
        config: BacktestConfig,
        reason: str,
    ):
        """Vend une position."""
        if ticker not in self._positions:
            return

        position = self._positions[ticker]
        shares = min(shares, position.shares)
        if shares <= 0:
            return

        price = position.current_price
        amount = shares * price

        # Calculer les frais
        slippage = amount * config.slippage
        fx_fee = amount * config.fx_fee
        commission = config.commission_per_trade
        total_fees = slippage + fx_fee + commission

        # Exécuter la vente
        self._cash += amount - total_fees
        self._total_fees += total_fees

        position.shares -= shares
        if position.shares < 0.0001:
            del self._positions[ticker]

        # Enregistrer le trade
        self._trades.append(TradeRecord(
            date=current_date,
            ticker=ticker,
            action="sell",
            shares=shares,
            price=price,
            amount=amount,
            fees=total_fees,
            reason=reason,
        ))

    def _calculate_metrics(
        self,
        config: BacktestConfig,
        all_dates: List[date],
        monthly_values: List[Tuple[date, float]],
        warnings: List[str],
    ) -> BacktestResult:
        """Calcule les métriques finales."""
        if not self._equity_curve:
            return self._create_empty_result(config, warnings)

        # Valeurs de base
        initial_value = config.initial_capital
        final_value = self._equity_curve[-1].portfolio_value

        # Période
        total_days = (all_dates[-1] - all_dates[0]).days
        years = total_days / 365.25

        # Rendement total
        total_return = ((final_value / initial_value) - 1) * 100 if initial_value > 0 else 0

        # CAGR
        if years > 0 and initial_value > 0:
            cagr = (((final_value / initial_value) ** (1 / years)) - 1) * 100
        else:
            cagr = 0

        # Rendements mensuels
        monthly_returns = []
        for i in range(1, len(monthly_values)):
            prev_value = monthly_values[i - 1][1]
            curr_value = monthly_values[i][1]
            if prev_value > 0:
                monthly_returns.append(((curr_value / prev_value) - 1) * 100)

        # Volatilité
        if monthly_returns:
            volatility = np.std(monthly_returns) * np.sqrt(12)
        else:
            volatility = 0

        # Sharpe Ratio (risk-free = 0)
        if volatility > 0:
            avg_monthly_return = np.mean(monthly_returns) if monthly_returns else 0
            sharpe = (avg_monthly_return * 12) / volatility
        else:
            sharpe = 0

        # Sortino Ratio
        negative_returns = [r for r in monthly_returns if r < 0]
        if negative_returns:
            downside_vol = np.std(negative_returns) * np.sqrt(12)
            avg_monthly_return = np.mean(monthly_returns) if monthly_returns else 0
            sortino = (avg_monthly_return * 12) / downside_vol if downside_vol > 0 else 0
        else:
            sortino = sharpe

        # Max Drawdown
        max_drawdown = min(p.drawdown for p in self._equity_curve) * 100 if self._equity_curve else 0

        # Durée du drawdown max
        max_dd_duration = self._calculate_max_drawdown_duration()

        # Temps en Risk-Off
        risk_off_days = sum(p.duration_days for p in self._risk_off_periods)
        time_in_risk_off = (risk_off_days / total_days) * 100 if total_days > 0 else 0

        # Yield moyen
        if final_value > 0:
            dividend_yield_avg = (self._total_dividends / final_value) * 100 / years if years > 0 else 0
        else:
            dividend_yield_avg = 0

        return BacktestResult(
            final_value=final_value,
            cagr=cagr,
            total_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=abs(max_drawdown),
            max_drawdown_duration=max_dd_duration,
            volatility=volatility,
            total_dividends=self._total_dividends,
            dividend_yield_avg=dividend_yield_avg,
            time_in_risk_off=time_in_risk_off,
            risk_off_periods=self._risk_off_periods,
            total_fees=self._total_fees,
            trades=self._trades,
            equity_curve=self._equity_curve,
            monthly_returns=monthly_returns,
            config=config,
            warnings=warnings,
        )

    def _calculate_max_drawdown_duration(self) -> int:
        """Calcule la durée du plus long drawdown."""
        if not self._equity_curve:
            return 0

        max_duration = 0
        current_duration = 0
        peak_value = 0

        for point in self._equity_curve:
            if point.portfolio_value >= peak_value:
                peak_value = point.portfolio_value
                max_duration = max(max_duration, current_duration)
                current_duration = 0
            else:
                current_duration += 1

        return max(max_duration, current_duration)

    def _create_empty_result(
        self,
        config: BacktestConfig,
        warnings: List[str],
    ) -> BacktestResult:
        """Crée un résultat vide en cas d'erreur."""
        return BacktestResult(
            final_value=config.initial_capital,
            cagr=0,
            total_return=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            max_drawdown_duration=0,
            volatility=0,
            total_dividends=0,
            dividend_yield_avg=0,
            time_in_risk_off=0,
            risk_off_periods=[],
            total_fees=0,
            trades=[],
            equity_curve=[],
            monthly_returns=[],
            config=config,
            warnings=warnings,
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def fetch_historical_data_for_backtest(
    tickers: List[str],
    start_date: date,
    end_date: date,
) -> Dict[str, List[HistoricalBar]]:
    """
    Récupère les données historiques pour un backtest.

    Args:
        tickers: Liste des tickers
        start_date: Date de début
        end_date: Date de fin

    Returns:
        Dict[ticker, List[HistoricalBar]]
    """
    import yfinance as yf

    result = {}

    for ticker in tickers:
        try:
            yf_ticker = yf.Ticker(ticker)
            hist = yf_ticker.history(start=start_date, end=end_date)

            bars = []
            for idx, row in hist.iterrows():
                bar = HistoricalBar(
                    date=idx.date(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    dividend=float(row.get('Dividends', 0)),
                )
                bars.append(bar)

            result[ticker] = bars
            logger.info(f"Fetched {len(bars)} bars for {ticker}")

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            result[ticker] = []

    return result


async def fetch_signal_data_for_backtest(
    start_date: date,
    end_date: date,
) -> Dict[date, SignalData]:
    """
    Récupère les données de signal pour un backtest.

    Calcule les signaux macro (HYG/LQD, VIX, SPY) pour chaque date.

    Args:
        start_date: Date de début
        end_date: Date de fin

    Returns:
        Dict[date, SignalData]
    """
    import yfinance as yf
    import pandas as pd

    signal_tickers = ["HYG", "LQD", "^VIX", "SPY"]
    data = {}

    # Récupérer les données avec un buffer pour les SMA
    buffer_start = start_date - timedelta(days=250)

    try:
        for ticker in signal_tickers:
            yf_ticker = yf.Ticker(ticker)
            hist = yf_ticker.history(start=buffer_start, end=end_date)
            if not hist.empty:
                data[ticker] = hist['Close']
    except Exception as e:
        logger.error(f"Error fetching signal data: {e}")
        return {}

    # Calculer les signaux
    result = {}

    if "HYG" in data and "LQD" in data:
        hyg_lqd = data["HYG"] / data["LQD"]
        hyg_lqd_sma50 = hyg_lqd.rolling(window=50).mean()
    else:
        hyg_lqd = pd.Series()
        hyg_lqd_sma50 = pd.Series()

    if "^VIX" in data:
        vix_sma20 = data["^VIX"].rolling(window=20).mean()
    else:
        vix_sma20 = pd.Series()

    if "SPY" in data:
        spy_sma200 = data["SPY"].rolling(window=200).mean()
        spy_rolling_max = data["SPY"].cummax()
        spy_drawdown = (data["SPY"] / spy_rolling_max) - 1
    else:
        spy_sma200 = pd.Series()
        spy_drawdown = pd.Series()

    # Construire les SignalData pour chaque date
    for d in pd.date_range(start=start_date, end=end_date):
        current_date = d.date()

        signal = SignalData()

        try:
            if "HYG" in data and current_date in data["HYG"].index.date:
                idx = data["HYG"].index[data["HYG"].index.date == current_date][0]
                signal.hyg_close = float(data["HYG"].loc[idx])
            if "LQD" in data and current_date in data["LQD"].index.date:
                idx = data["LQD"].index[data["LQD"].index.date == current_date][0]
                signal.lqd_close = float(data["LQD"].loc[idx])
            if not hyg_lqd.empty and current_date in hyg_lqd.index.date:
                idx = hyg_lqd.index[hyg_lqd.index.date == current_date][0]
                signal.hyg_lqd_ratio = float(hyg_lqd.loc[idx])
                if not hyg_lqd_sma50.empty:
                    signal.hyg_lqd_sma50 = float(hyg_lqd_sma50.loc[idx])
            if "^VIX" in data and current_date in data["^VIX"].index.date:
                idx = data["^VIX"].index[data["^VIX"].index.date == current_date][0]
                signal.vix_close = float(data["^VIX"].loc[idx])
                if not vix_sma20.empty:
                    signal.vix_sma20 = float(vix_sma20.loc[idx])
            if "SPY" in data and current_date in data["SPY"].index.date:
                idx = data["SPY"].index[data["SPY"].index.date == current_date][0]
                signal.spy_close = float(data["SPY"].loc[idx])
                if not spy_sma200.empty:
                    signal.spy_sma200 = float(spy_sma200.loc[idx])
                if not spy_drawdown.empty:
                    signal.spy_drawdown = float(spy_drawdown.loc[idx])
        except Exception:
            pass

        result[current_date] = signal

    return result
