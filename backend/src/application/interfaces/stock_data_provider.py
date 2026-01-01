"""
Interface StockDataProvider - Abstraction pour les sources de données de stocks.

Cette interface définit le contrat que doit respecter tout fournisseur
de données boursières (Yahoo Finance, Alpha Vantage, Bloomberg, etc.).

ARCHITECTURE:
- Couche APPLICATION (port/interface)
- Implémentée par la couche INFRASTRUCTURE (adapters)
- Permet de changer de source de données sans modifier les use cases

PATTERN: Repository / Port (Hexagonal Architecture)

UTILISATION DANS UN USE CASE:
    class AnalyzeStockUseCase:
        def __init__(self, stock_provider: StockDataProvider):
            self._provider = stock_provider

        async def execute(self, ticker: str):
            data = await self._provider.get_historical_data(ticker, days=365)
            # ... calculs ...
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.domain.value_objects.ticker import Ticker


@dataclass
class HistoricalDataPoint:
    """
    Un point de données historiques (OHLCV).

    Attributs:
        date: Date du point
        open: Prix d'ouverture
        high: Prix le plus haut
        low: Prix le plus bas
        close: Prix de clôture
        volume: Volume échangé
        adj_close: Prix de clôture ajusté (dividendes, splits)
    """

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: Optional[float] = None


@dataclass
class StockQuote:
    """
    Citation actuelle d'un stock.

    Attributs:
        ticker: Symbole boursier
        price: Prix actuel
        previous_close: Prix de clôture précédent
        change: Variation en valeur absolue
        change_percent: Variation en pourcentage
        currency: Devise
        timestamp: Horodatage de la citation
        volume: Volume du jour (optionnel)
    """

    ticker: str
    price: float
    previous_close: float
    change: float
    change_percent: float
    currency: str
    timestamp: datetime
    volume: Optional[int] = None

    @property
    def is_up(self) -> bool:
        """Le prix est-il en hausse?"""
        return self.change >= 0


@dataclass
class StockMetadata:
    """
    Métadonnées d'un stock.

    Informations statiques qui ne changent pas souvent.
    """

    ticker: str
    name: str
    currency: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    asset_type: Optional[Any] = None  # AssetType enum
    market_cap: Optional[float] = None
    dividend_yield: Optional[float] = None
    description: Optional[str] = None


class StockDataProvider(ABC):
    """
    Interface abstraite pour les fournisseurs de données boursières.

    Toute implémentation (Yahoo Finance, Alpha Vantage, etc.) doit
    respecter ce contrat.

    Méthodes requises:
        - get_historical_data: Données historiques OHLCV
        - get_current_quote: Prix actuel
        - get_metadata: Informations sur le stock
        - search: Recherche de tickers
    """

    @abstractmethod
    async def get_historical_data(
        self,
        ticker: Ticker,
        days: int = 365,
        interval: str = "1d"
    ) -> List[HistoricalDataPoint]:
        """
        Récupère les données historiques d'un stock.

        Args:
            ticker: Symbole boursier
            days: Nombre de jours d'historique (défaut: 365)
            interval: Intervalle entre les points ("1d", "1wk", "1mo")

        Returns:
            Liste de HistoricalDataPoint triée par date croissante

        Raises:
            TickerNotFoundError: Si le ticker n'existe pas
            InsufficientDataError: Si pas assez de données disponibles
        """
        pass

    @abstractmethod
    async def get_current_quote(self, ticker: Ticker) -> StockQuote:
        """
        Récupère la citation actuelle d'un stock.

        Args:
            ticker: Symbole boursier

        Returns:
            StockQuote avec le prix actuel et la variation

        Raises:
            TickerNotFoundError: Si le ticker n'existe pas
        """
        pass

    @abstractmethod
    async def get_metadata(self, ticker: Ticker) -> StockMetadata:
        """
        Récupère les métadonnées d'un stock.

        Args:
            ticker: Symbole boursier

        Returns:
            StockMetadata avec les informations du stock

        Raises:
            TickerNotFoundError: Si le ticker n'existe pas
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[StockMetadata]:
        """
        Recherche des stocks par nom ou symbole.

        Args:
            query: Terme de recherche (nom ou symbole partiel)
            limit: Nombre maximum de résultats

        Returns:
            Liste de StockMetadata correspondant à la recherche
        """
        pass

    @abstractmethod
    async def is_valid_ticker(self, ticker: Ticker) -> bool:
        """
        Vérifie si un ticker existe.

        Args:
            ticker: Symbole boursier

        Returns:
            True si le ticker existe et a des données
        """
        pass

    async def get_multiple_quotes(
        self,
        tickers: List[Ticker]
    ) -> Dict[str, StockQuote]:
        """
        Récupère les citations de plusieurs stocks.

        Implémentation par défaut qui appelle get_current_quote en boucle.
        Les implémentations peuvent surcharger pour optimiser.

        Args:
            tickers: Liste de symboles boursiers

        Returns:
            Dictionnaire ticker -> StockQuote
        """
        import asyncio
        results = {}
        tasks = [self.get_current_quote(t) for t in tickers]
        quotes = await asyncio.gather(*tasks, return_exceptions=True)

        for ticker, quote in zip(tickers, quotes):
            if isinstance(quote, StockQuote):
                results[str(ticker)] = quote

        return results
