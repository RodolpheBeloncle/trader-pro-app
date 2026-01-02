"""
Strategie RSI - Trading sur niveaux de surachat/survente.

Signal d'achat: RSI descend sous oversold puis remonte
Signal de vente: RSI monte au-dessus de overbought puis redescend
"""

from typing import List, Dict, Any

from src.backtesting.data_loader import OHLCV
from src.backtesting.strategies.base import (
    Strategy,
    Signal,
    SignalType,
    calculate_rsi,
)


class RSIStrategy(Strategy):
    """
    Strategie basee sur le RSI (Relative Strength Index).

    Parametres:
    - period: Periode du RSI (defaut: 14)
    - oversold: Niveau de survente (defaut: 30)
    - overbought: Niveau de surachat (defaut: 70)
    """

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "period": 14,
            "oversold": 30,
            "overbought": 70,
        }

    def generate_signals(self, data: List[OHLCV]) -> List[Signal]:
        """Genere les signaux RSI."""
        signals = []

        period = self.get_param("period", 14)
        oversold = self.get_param("oversold", 30)
        overbought = self.get_param("overbought", 70)

        if len(data) < period + 2:
            return signals

        # Calculer le RSI
        closes = [bar.close for bar in data]
        rsi = calculate_rsi(closes, period)

        # Tracker l'etat
        was_oversold = False
        was_overbought = False

        for i in range(1, len(data)):
            if rsi[i] is None:
                continue

            current_rsi = rsi[i]
            prev_rsi = rsi[i-1] if rsi[i-1] is not None else current_rsi

            # Entree en zone de survente
            if current_rsi < oversold:
                was_oversold = True

            # Entree en zone de surachat
            if current_rsi > overbought:
                was_overbought = True

            # Signal d'achat: sortie de survente
            if was_oversold and prev_rsi < oversold and current_rsi >= oversold:
                signals.append(Signal(
                    date=data[i].date,
                    signal_type=SignalType.BUY,
                    price=data[i].close,
                    strength=min(1.0, (oversold - prev_rsi) / 10),  # Plus fort si RSI etait bas
                    reason=f"RSI exiting oversold (RSI={current_rsi:.1f})",
                ))
                was_oversold = False

            # Signal de vente: sortie de surachat
            if was_overbought and prev_rsi > overbought and current_rsi <= overbought:
                signals.append(Signal(
                    date=data[i].date,
                    signal_type=SignalType.SELL,
                    price=data[i].close,
                    strength=min(1.0, (prev_rsi - overbought) / 10),  # Plus fort si RSI etait haut
                    reason=f"RSI exiting overbought (RSI={current_rsi:.1f})",
                ))
                was_overbought = False

        return signals
