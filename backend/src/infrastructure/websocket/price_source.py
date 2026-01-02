"""
Interface abstraite pour les sources de prix en temps reel.

Permet de supporter plusieurs sources (Yahoo, Saxo, etc.)
avec une interface unifiee.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Awaitable


@dataclass
class PriceQuote:
    """
    Quote de prix unifie pour toutes les sources.

    Attributes:
        ticker: Symbole du ticker
        price: Prix actuel
        bid: Prix d'achat (optionnel)
        ask: Prix de vente (optionnel)
        change: Variation absolue
        change_percent: Variation en %
        volume: Volume du jour
        timestamp: Horodatage
        source: Source des donnees (yahoo, saxo, etc.)
    """
    ticker: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    timestamp: str = ""
    source: str = "unknown"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dict pour WebSocket."""
        return {
            "type": "price_update",
            "ticker": self.ticker,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "change": self.change,
            "change_percent": self.change_percent,
            "volume": self.volume,
            "timestamp": self.timestamp,
            "source": self.source,
        }


# Type pour callback de prix
PriceCallback = Callable[[PriceQuote], Awaitable[None]]


class PriceSource(ABC):
    """
    Interface abstraite pour une source de prix.

    Chaque implementation (Yahoo, Saxo, etc.) doit implementer:
    - subscribe: S'abonner a un ticker
    - unsubscribe: Se desabonner
    - is_available: Verifier la disponibilite
    """

    @abstractmethod
    async def subscribe(
        self,
        ticker: str,
        callback: PriceCallback
    ) -> bool:
        """
        S'abonne aux mises a jour de prix pour un ticker.

        Args:
            ticker: Symbole du ticker
            callback: Fonction appelee lors des mises a jour

        Returns:
            True si l'abonnement a reussi
        """
        pass

    @abstractmethod
    async def unsubscribe(self, ticker: str) -> bool:
        """
        Se desabonne d'un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            True si le desabonnement a reussi
        """
        pass

    @abstractmethod
    async def get_current_price(self, ticker: str) -> Optional[PriceQuote]:
        """
        Recupere le prix actuel d'un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            PriceQuote ou None si erreur
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Verifie si la source est disponible.

        Returns:
            True si la source peut fournir des prix
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Nom de la source (yahoo, saxo, etc.)."""
        pass

    @property
    @abstractmethod
    def is_realtime(self) -> bool:
        """True si la source est temps reel (WebSocket), False si polling."""
        pass
