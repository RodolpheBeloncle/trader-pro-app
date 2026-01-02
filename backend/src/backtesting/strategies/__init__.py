"""
Strategies de trading pour le backtesting.

Strategies disponibles:
- SMAcrossover: Croisement de moyennes mobiles
- RSIStrategy: Trading sur RSI
- MomentumStrategy: Strategie momentum

UTILISATION:
    from src.backtesting.strategies import SMACrossover

    strategy = SMACrossover(short_period=20, long_period=50)
    signals = strategy.generate_signals(data)
"""

from src.backtesting.strategies.base import Strategy, Signal
from src.backtesting.strategies.sma_crossover import SMACrossover
from src.backtesting.strategies.rsi_strategy import RSIStrategy
from src.backtesting.strategies.momentum import MomentumStrategy

__all__ = [
    "Strategy",
    "Signal",
    "SMACrossover",
    "RSIStrategy",
    "MomentumStrategy",
]

# Registry des strategies disponibles
STRATEGY_REGISTRY = {
    "sma_crossover": SMACrossover,
    "rsi": RSIStrategy,
    "momentum": MomentumStrategy,
}


def get_strategy(name: str, **params) -> Strategy:
    """
    Factory pour creer une strategie par nom.

    Args:
        name: Nom de la strategie
        **params: Parametres de la strategie

    Returns:
        Instance de Strategy

    Raises:
        ValueError: Si la strategie n'existe pas
    """
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        raise ValueError(f"Unknown strategy: {name}. Available: {available}")

    return STRATEGY_REGISTRY[name](**params)


def list_strategies() -> list:
    """Liste toutes les strategies disponibles avec leurs parametres."""
    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        result.append({
            "name": name,
            "description": cls.__doc__ or "",
            "parameters": cls.default_params() if hasattr(cls, 'default_params') else {},
        })
    return result
