"""
Strategie Momentum - Trading sur la force du mouvement.

Achete quand le momentum est fort et positif.
Vend quand le momentum faiblit ou devient negatif.
"""

from typing import List, Dict, Any

from src.backtesting.data_loader import OHLCV
from src.backtesting.strategies.base import (
    Strategy,
    Signal,
    SignalType,
    calculate_sma,
)


class MomentumStrategy(Strategy):
    """
    Strategie basee sur le momentum (Rate of Change).

    Parametres:
    - lookback: Periode de calcul du momentum (defaut: 20)
    - threshold: Seuil de declenchement en % (defaut: 5)
    - sma_filter: Periode SMA pour filtrer (defaut: 50, 0 pour desactiver)
    """

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "lookback": 20,
            "threshold": 5.0,
            "sma_filter": 50,
        }

    def generate_signals(self, data: List[OHLCV]) -> List[Signal]:
        """Genere les signaux momentum."""
        signals = []

        lookback = self.get_param("lookback", 20)
        threshold = self.get_param("threshold", 5.0)
        sma_period = self.get_param("sma_filter", 50)

        if len(data) < max(lookback, sma_period) + 1:
            return signals

        closes = [bar.close for bar in data]

        # Calculer le momentum (Rate of Change)
        momentum = []
        for i in range(len(closes)):
            if i < lookback:
                momentum.append(None)
            else:
                roc = ((closes[i] - closes[i - lookback]) / closes[i - lookback]) * 100
                momentum.append(roc)

        # Calculer SMA si active
        sma = None
        if sma_period > 0:
            sma = calculate_sma(closes, sma_period)

        # Generer les signaux
        in_position = False

        for i in range(1, len(data)):
            if momentum[i] is None:
                continue

            current_mom = momentum[i]
            prev_mom = momentum[i-1] if momentum[i-1] is not None else 0

            # Filtre SMA (si active): n'acheter que si prix > SMA
            if sma and sma[i] is not None:
                above_sma = closes[i] > sma[i]
            else:
                above_sma = True

            # Signal d'achat: momentum depasse le seuil positif
            if not in_position and current_mom > threshold and above_sma:
                # Verifier que le momentum accelere
                if current_mom > prev_mom:
                    signals.append(Signal(
                        date=data[i].date,
                        signal_type=SignalType.BUY,
                        price=data[i].close,
                        strength=min(1.0, current_mom / (threshold * 2)),
                        reason=f"Momentum breakout: {current_mom:.1f}%",
                    ))
                    in_position = True

            # Signal de vente: momentum passe negatif ou chute fortement
            elif in_position:
                if current_mom < 0 or (current_mom < prev_mom * 0.5 and current_mom < threshold / 2):
                    signals.append(Signal(
                        date=data[i].date,
                        signal_type=SignalType.SELL,
                        price=data[i].close,
                        strength=1.0,
                        reason=f"Momentum fading: {current_mom:.1f}%",
                    ))
                    in_position = False

        return signals
