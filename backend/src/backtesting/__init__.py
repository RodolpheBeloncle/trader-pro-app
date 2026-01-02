"""
Module de backtesting pour tester des strategies de trading.

Ce module fournit:
- BacktestEngine: Moteur de backtesting event-driven
- Strategy: Classe de base pour les strategies
- Metrics: Calcul des metriques de performance
- DataLoader: Chargement des donnees historiques

UTILISATION:
    from src.backtesting import BacktestEngine, SMAStrategy

    engine = BacktestEngine(
        initial_capital=10000,
        commission=0.001,
    )
    result = await engine.run(
        ticker="AAPL",
        strategy=SMAStrategy(short=20, long=50),
        start_date="2023-01-01",
        end_date="2024-01-01",
    )
    print(result.total_return)
"""

from src.backtesting.engine import BacktestEngine, BacktestResult
from src.backtesting.metrics import calculate_metrics, PerformanceMetrics
from src.backtesting.data_loader import BacktestDataLoader
from src.backtesting.strategies.base import Strategy

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "Strategy",
    "calculate_metrics",
    "PerformanceMetrics",
    "BacktestDataLoader",
]
