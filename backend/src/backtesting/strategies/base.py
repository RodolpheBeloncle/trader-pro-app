"""
Classe de base abstraite pour les strategies de trading.

Chaque strategie doit implementer:
- generate_signals: Genere les signaux de trading
- default_params: Retourne les parametres par defaut
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional

from src.backtesting.data_loader import OHLCV


class SignalType(Enum):
    """Type de signal."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """
    Signal de trading genere par une strategie.

    Attributes:
        date: Date du signal
        signal_type: Type (buy, sell, hold)
        price: Prix au moment du signal
        strength: Force du signal (0-1)
        reason: Raison du signal
    """
    date: datetime
    signal_type: SignalType
    price: float
    strength: float = 1.0
    reason: str = ""

    @property
    def is_buy(self) -> bool:
        return self.signal_type == SignalType.BUY

    @property
    def is_sell(self) -> bool:
        return self.signal_type == SignalType.SELL


class Strategy(ABC):
    """
    Classe de base abstraite pour les strategies.

    Chaque strategie concrete doit implementer:
    - generate_signals(): Analyse les donnees et genere des signaux
    - default_params(): Retourne les parametres par defaut
    """

    def __init__(self, **params):
        """
        Initialise la strategie avec des parametres.

        Args:
            **params: Parametres specifiques a la strategie
        """
        self.params = params

    @property
    def name(self) -> str:
        """Nom de la strategie."""
        return self.__class__.__name__

    @abstractmethod
    def generate_signals(self, data: List[OHLCV]) -> List[Signal]:
        """
        Genere les signaux de trading.

        Args:
            data: Donnees OHLCV historiques

        Returns:
            Liste de signaux
        """
        pass

    @classmethod
    @abstractmethod
    def default_params(cls) -> Dict[str, Any]:
        """
        Retourne les parametres par defaut de la strategie.

        Returns:
            Dict des parametres avec valeurs par defaut
        """
        pass

    def get_param(self, name: str, default: Any = None) -> Any:
        """
        Recupere un parametre ou sa valeur par defaut.

        Args:
            name: Nom du parametre
            default: Valeur par defaut

        Returns:
            Valeur du parametre
        """
        return self.params.get(name, default)

    def __repr__(self) -> str:
        params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.name}({params_str})"


def calculate_sma(data: List[float], period: int) -> List[Optional[float]]:
    """
    Calcule une moyenne mobile simple.

    Args:
        data: Liste de valeurs
        period: Periode de la moyenne

    Returns:
        Liste de moyennes (None pour les premieres valeurs)
    """
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            avg = sum(data[i - period + 1:i + 1]) / period
            result.append(avg)
    return result


def calculate_ema(data: List[float], period: int) -> List[Optional[float]]:
    """
    Calcule une moyenne mobile exponentielle.

    Args:
        data: Liste de valeurs
        period: Periode de la moyenne

    Returns:
        Liste de moyennes
    """
    result = []
    multiplier = 2 / (period + 1)

    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            # Premiere EMA = SMA
            sma = sum(data[i - period + 1:i + 1]) / period
            result.append(sma)
        else:
            ema = (data[i] - result[-1]) * multiplier + result[-1]
            result.append(ema)

    return result


def calculate_rsi(data: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calcule le RSI (Relative Strength Index).

    Args:
        data: Liste de prix de cloture
        period: Periode du RSI

    Returns:
        Liste de valeurs RSI (0-100)
    """
    if len(data) < period + 1:
        return [None] * len(data)

    # Calculer les variations
    deltas = [data[i] - data[i-1] for i in range(1, len(data))]

    # Separer gains et pertes
    gains = [max(0, d) for d in deltas]
    losses = [abs(min(0, d)) for d in deltas]

    result = [None] * period

    # Premiere moyenne
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        result.append(rsi)

        # Mise a jour des moyennes (smooth)
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    # Ajouter None pour la premiere valeur
    result.insert(0, None)

    return result
