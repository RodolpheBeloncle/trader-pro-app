"""
Moteur de backtesting event-driven.

Execute une strategie sur des donnees historiques
et calcule les performances.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from src.backtesting.data_loader import BacktestDataLoader, OHLCV
from src.backtesting.strategies.base import Strategy, Signal, SignalType
from src.backtesting.metrics import (
    calculate_metrics,
    PerformanceMetrics,
    Trade,
)

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position ouverte."""
    ticker: str
    direction: str  # 'long' or 'short'
    entry_date: datetime
    entry_price: float
    size: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class BacktestResult:
    """
    Resultat d'un backtest.

    Attributes:
        ticker: Symbole du ticker
        strategy_name: Nom de la strategie
        strategy_params: Parametres de la strategie
        start_date: Date de debut
        end_date: Date de fin
        initial_capital: Capital initial
        final_capital: Capital final
        metrics: Metriques de performance
        trades: Liste des trades executes
        equity_curve: Courbe d'equity
    """
    ticker: str
    strategy_name: str
    strategy_params: Dict[str, Any]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour JSON/DB."""
        return {
            "ticker": self.ticker,
            "strategy_name": self.strategy_name,
            "strategy_params": self.strategy_params,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "metrics": self.metrics.to_dict(),
            "trades_count": len(self.trades),
            "equity_curve": self.equity_curve[:100],  # Limiter pour JSON
            "created_at": self.created_at,
        }


class BacktestEngine:
    """
    Moteur de backtesting.

    Features:
    - Execution de strategies sur donnees historiques
    - Calcul des commissions
    - Gestion des positions
    - Stop loss / Take profit
    - Calcul des metriques de performance
    """

    def __init__(
        self,
        initial_capital: float = 10000,
        commission: float = 0.001,  # 0.1%
        slippage: float = 0.0005,   # 0.05%
    ):
        """
        Args:
            initial_capital: Capital de depart
            commission: Commission par trade en %
            slippage: Slippage par trade en %
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.data_loader = BacktestDataLoader()

    async def run(
        self,
        ticker: str,
        strategy: Strategy,
        start_date: str,
        end_date: str,
        position_size_pct: float = 100,  # % du capital par trade
    ) -> BacktestResult:
        """
        Execute un backtest.

        Args:
            ticker: Symbole du ticker
            strategy: Strategie a tester
            start_date: Date de debut (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)
            position_size_pct: % du capital par position

        Returns:
            BacktestResult avec les performances
        """
        logger.info(f"Running backtest: {ticker} with {strategy.name}")

        # Charger les donnees
        data = await self.data_loader.load(ticker, start_date, end_date)

        if not data:
            raise ValueError(f"No data available for {ticker}")

        # Generer les signaux
        signals = strategy.generate_signals(data)
        logger.info(f"Generated {len(signals)} signals")

        # Simuler le trading
        result = self._simulate(
            ticker=ticker,
            data=data,
            signals=signals,
            position_size_pct=position_size_pct,
        )

        # Construire le resultat
        return BacktestResult(
            ticker=ticker,
            strategy_name=strategy.name,
            strategy_params=strategy.params,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=result["final_capital"],
            metrics=result["metrics"],
            trades=result["trades"],
            equity_curve=result["equity_curve"],
        )

    def _simulate(
        self,
        ticker: str,
        data: List[OHLCV],
        signals: List[Signal],
        position_size_pct: float,
    ) -> Dict[str, Any]:
        """
        Simule l'execution des signaux.

        Returns:
            Dict avec final_capital, metrics, trades, equity_curve
        """
        capital = self.initial_capital
        position: Optional[Position] = None
        trades: List[Trade] = []
        equity_curve: List[float] = []
        equity_dates: List[datetime] = []

        # Indexer les signaux par date
        signal_map = {s.date.date(): s for s in signals}

        for bar in data:
            current_date = bar.date.date()

            # Calculer l'equity actuelle
            current_equity = capital
            if position:
                # P&L non realise
                if position.direction == "long":
                    unrealized = (bar.close - position.entry_price) * position.size
                else:
                    unrealized = (position.entry_price - bar.close) * position.size
                current_equity += unrealized

            equity_curve.append(current_equity)
            equity_dates.append(bar.date)

            # Verifier si on a un signal
            signal = signal_map.get(current_date)

            if signal:
                if signal.is_buy and position is None:
                    # Ouvrir une position long
                    position = self._open_position(
                        ticker=ticker,
                        direction="long",
                        bar=bar,
                        capital=capital,
                        position_size_pct=position_size_pct,
                    )
                    capital -= position.entry_price * position.size * (1 + self.commission + self.slippage)

                elif signal.is_sell and position is not None:
                    # Fermer la position
                    trade = self._close_position(position, bar)
                    trades.append(trade)

                    # Mettre a jour le capital
                    exit_value = trade.exit_price * position.size
                    commission_cost = exit_value * self.commission
                    capital += exit_value - commission_cost + (position.entry_price * position.size)

                    position = None

        # Fermer la position ouverte a la fin
        if position and data:
            last_bar = data[-1]
            trade = self._close_position(position, last_bar)
            trades.append(trade)

            exit_value = trade.exit_price * position.size
            commission_cost = exit_value * self.commission
            capital += exit_value - commission_cost + (position.entry_price * position.size)

        # Calculer les metriques
        metrics = calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=self.initial_capital,
        )

        # Formater la courbe d'equity pour JSON
        equity_curve_json = [
            {
                "time": int(equity_dates[i].timestamp()),
                "value": round(equity_curve[i], 2),
            }
            for i in range(0, len(equity_curve), max(1, len(equity_curve) // 100))  # Max 100 points
        ]

        return {
            "final_capital": capital,
            "metrics": metrics,
            "trades": trades,
            "equity_curve": equity_curve_json,
        }

    def _open_position(
        self,
        ticker: str,
        direction: str,
        bar: OHLCV,
        capital: float,
        position_size_pct: float,
    ) -> Position:
        """Ouvre une nouvelle position."""
        # Calculer la taille de position
        position_value = capital * (position_size_pct / 100)
        entry_price = bar.close * (1 + self.slippage)  # Slippage
        size = int(position_value / entry_price)

        if size < 1:
            size = 1

        return Position(
            ticker=ticker,
            direction=direction,
            entry_date=bar.date,
            entry_price=entry_price,
            size=size,
        )

    def _close_position(self, position: Position, bar: OHLCV) -> Trade:
        """Ferme une position et retourne le trade."""
        exit_price = bar.close * (1 - self.slippage)  # Slippage

        if position.direction == "long":
            pnl = (exit_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - exit_price) * position.size

        pnl_percent = (pnl / (position.entry_price * position.size)) * 100

        return Trade(
            entry_date=position.entry_date,
            exit_date=bar.date,
            entry_price=position.entry_price,
            exit_price=exit_price,
            direction=position.direction,
            size=position.size,
            pnl=pnl,
            pnl_percent=pnl_percent,
        )
