"""
Calcul des metriques de performance pour le backtesting.

Metriques incluses:
- Total Return
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Win Rate
- Profit Factor
- Average Trade
- Calmar Ratio
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import numpy as np


@dataclass
class PerformanceMetrics:
    """
    Metriques de performance d'un backtest.

    Attributes:
        total_return: Rendement total en %
        annualized_return: Rendement annualise
        sharpe_ratio: Ratio de Sharpe (risk-adjusted return)
        sortino_ratio: Ratio de Sortino (downside risk)
        max_drawdown: Drawdown maximum en %
        max_drawdown_duration: Duree du max drawdown en jours
        win_rate: Taux de trades gagnants
        profit_factor: Gains / Pertes
        avg_win: Gain moyen
        avg_loss: Perte moyenne
        total_trades: Nombre total de trades
        winning_trades: Nombre de trades gagnants
        losing_trades: Nombre de trades perdants
        avg_trade_return: Rendement moyen par trade
        calmar_ratio: Rendement annualise / Max Drawdown
        volatility: Volatilite annualisee
    """
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_return: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    # Donnees supplementaires
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour JSON."""
        return {
            "total_return": round(self.total_return, 2),
            "annualized_return": round(self.annualized_return, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_duration": self.max_drawdown_duration,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_return": round(self.avg_trade_return, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "volatility": round(self.volatility, 2),
        }


@dataclass
class Trade:
    """Represente un trade complete."""
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    direction: str  # 'long' or 'short'
    size: int
    pnl: float
    pnl_percent: float


def calculate_metrics(
    equity_curve: List[float],
    trades: List[Trade],
    initial_capital: float,
    trading_days: int = 252,
    risk_free_rate: float = 0.02,
) -> PerformanceMetrics:
    """
    Calcule toutes les metriques de performance.

    Args:
        equity_curve: Liste des valeurs de l'equity dans le temps
        trades: Liste des trades executes
        initial_capital: Capital initial
        trading_days: Nombre de jours de trading par an
        risk_free_rate: Taux sans risque annuel

    Returns:
        PerformanceMetrics avec toutes les metriques
    """
    if not equity_curve or len(equity_curve) < 2:
        return PerformanceMetrics(equity_curve=equity_curve)

    equity = np.array(equity_curve)
    final_equity = equity[-1]

    # Total Return
    total_return = ((final_equity - initial_capital) / initial_capital) * 100

    # Daily Returns
    daily_returns = np.diff(equity) / equity[:-1]

    # Volatility (annualized)
    volatility = np.std(daily_returns) * np.sqrt(trading_days) * 100

    # Annualized Return
    days = len(equity_curve)
    years = days / trading_days
    if years > 0 and final_equity > 0 and initial_capital > 0:
        annualized_return = ((final_equity / initial_capital) ** (1 / years) - 1) * 100
    else:
        annualized_return = 0

    # Sharpe Ratio
    if volatility > 0:
        excess_return = annualized_return - (risk_free_rate * 100)
        sharpe_ratio = excess_return / volatility
    else:
        sharpe_ratio = 0

    # Sortino Ratio (downside deviation)
    negative_returns = daily_returns[daily_returns < 0]
    if len(negative_returns) > 0:
        downside_deviation = np.std(negative_returns) * np.sqrt(trading_days) * 100
        if downside_deviation > 0:
            sortino_ratio = (annualized_return - (risk_free_rate * 100)) / downside_deviation
        else:
            sortino_ratio = 0
    else:
        sortino_ratio = 0

    # Max Drawdown
    peak = equity[0]
    max_dd = 0
    dd_curve = []
    current_dd_duration = 0
    max_dd_duration = 0

    for value in equity:
        if value > peak:
            peak = value
            current_dd_duration = 0
        dd = ((peak - value) / peak) * 100
        dd_curve.append(dd)
        if dd > max_dd:
            max_dd = dd
        if dd > 0:
            current_dd_duration += 1
            max_dd_duration = max(max_dd_duration, current_dd_duration)

    # Calmar Ratio
    calmar_ratio = annualized_return / max_dd if max_dd > 0 else 0

    # Trade Statistics
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t.pnl > 0])
    losing_trades = len([t for t in trades if t.pnl < 0])

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [abs(t.pnl) for t in trades if t.pnl < 0]

    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    total_wins = sum(wins)
    total_losses = sum(losses)
    profit_factor = total_wins / total_losses if total_losses > 0 else 0

    all_pnl = [t.pnl for t in trades]
    avg_trade_return = sum(all_pnl) / len(all_pnl) if all_pnl else 0

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_duration,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_trade_return=avg_trade_return,
        calmar_ratio=calmar_ratio,
        volatility=volatility,
        equity_curve=equity_curve,
        drawdown_curve=dd_curve,
    )
