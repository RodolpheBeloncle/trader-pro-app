"""
Strategie SMA Crossover - Croisement de moyennes mobiles.

Signal d'achat: SMA courte croise au-dessus de la SMA longue
Signal de vente: SMA courte croise en-dessous de la SMA longue
"""

from typing import List, Dict, Any

from src.backtesting.data_loader import OHLCV
from src.backtesting.strategies.base import (
    Strategy,
    Signal,
    SignalType,
    calculate_sma,
)


class SMACrossover(Strategy):
    """
    Strategie de croisement de moyennes mobiles simples.

    Parametres:
    - short_period: Periode de la SMA courte (defaut: 20)
    - long_period: Periode de la SMA longue (defaut: 50)
    """

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "short_period": 20,
            "long_period": 50,
        }

    def generate_signals(self, data: List[OHLCV]) -> List[Signal]:
        """Genere les signaux de croisement SMA."""
        signals = []

        short_period = self.get_param("short_period", 20)
        long_period = self.get_param("long_period", 50)

        if len(data) < long_period:
            return signals

        # Calculer les SMAs
        closes = [bar.close for bar in data]
        short_sma = calculate_sma(closes, short_period)
        long_sma = calculate_sma(closes, long_period)

        # Detecter les croisements
        for i in range(1, len(data)):
            if short_sma[i] is None or long_sma[i] is None:
                continue
            if short_sma[i-1] is None or long_sma[i-1] is None:
                continue

            # Golden Cross (SMA courte croise au-dessus)
            if short_sma[i-1] <= long_sma[i-1] and short_sma[i] > long_sma[i]:
                signals.append(Signal(
                    date=data[i].date,
                    signal_type=SignalType.BUY,
                    price=data[i].close,
                    strength=1.0,
                    reason=f"Golden Cross: SMA{short_period} > SMA{long_period}",
                ))

            # Death Cross (SMA courte croise en-dessous)
            elif short_sma[i-1] >= long_sma[i-1] and short_sma[i] < long_sma[i]:
                signals.append(Signal(
                    date=data[i].date,
                    signal_type=SignalType.SELL,
                    price=data[i].close,
                    strength=1.0,
                    reason=f"Death Cross: SMA{short_period} < SMA{long_period}",
                ))

        return signals
