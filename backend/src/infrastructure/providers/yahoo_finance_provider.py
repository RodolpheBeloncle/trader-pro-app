"""
Provider de données Yahoo Finance.

Implémente l'interface StockDataProvider en utilisant yfinance.
Adapte les données yfinance au format attendu par le domaine.

ARCHITECTURE:
- Pattern Adapter : adapte yfinance à notre interface
- Encapsule toute la logique spécifique à yfinance
- Facilement remplaçable par un autre provider

UTILISATION:
    provider = YahooFinanceProvider()
    data = await provider.get_historical_data(Ticker("AAPL"), days=365)
    quote = await provider.get_current_quote(Ticker("AAPL"))
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import yfinance as yf

from src.application.interfaces.stock_data_provider import (
    StockDataProvider,
    HistoricalDataPoint,
    StockQuote,
    StockMetadata,
)
from src.config.constants import (
    ANNUALIZATION_FACTOR,
    AssetType,
)
from src.domain.exceptions import (
    TickerNotFoundError,
    DataFetchError,
)
from src.domain.value_objects.ticker import Ticker

logger = logging.getLogger(__name__)


class YahooFinanceProvider(StockDataProvider):
    """
    Implémentation du provider de données utilisant Yahoo Finance.

    Utilise la bibliothèque yfinance pour récupérer les données boursières.
    Thread-safe et sans état interne (stateless).

    Attributes:
        _cache_ttl: Durée de vie du cache en secondes (futur usage)
    """

    def __init__(self, cache_ttl: int = 300):
        """
        Initialise le provider Yahoo Finance.

        Args:
            cache_ttl: TTL du cache en secondes (préparé pour futur cache Redis)
        """
        self._cache_ttl = cache_ttl

    async def get_historical_data(
        self,
        ticker: Ticker,
        days: int = 365,
        interval: str = "1d",
    ) -> List[HistoricalDataPoint]:
        """
        Récupère les données historiques depuis Yahoo Finance.

        Args:
            ticker: Ticker de l'instrument
            days: Nombre de jours d'historique

        Returns:
            Liste de points de données historiques

        Raises:
            TickerNotFoundError: Si le ticker n'existe pas
            DataFetchError: Si une erreur survient lors de la récupération
        """
        try:
            logger.debug(f"Fetching {days} days of data for {ticker.value}")

            yf_ticker = yf.Ticker(ticker.value)
            end_date = datetime.today()
            start_date = end_date - timedelta(days=days)

            # Récupération des données historiques
            hist = yf_ticker.history(start=start_date, end=end_date)

            if hist.empty:
                raise TickerNotFoundError(
                    ticker.value,
                    f"Aucune donnée disponible pour {ticker.value}"
                )

            # Conversion au format attendu
            data_points: List[HistoricalDataPoint] = []
            for date, row in hist.iterrows():
                point = HistoricalDataPoint(
                    date=date.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                )
                data_points.append(point)

            logger.debug(f"Retrieved {len(data_points)} data points for {ticker.value}")
            return data_points

        except TickerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker.value}: {e}")
            raise DataFetchError(
                f"Erreur lors de la récupération des données pour {ticker.value}: {str(e)}"
            )

    async def get_current_quote(self, ticker: Ticker) -> StockQuote:
        """
        Récupère le cours actuel d'un instrument.

        Args:
            ticker: Ticker de l'instrument

        Returns:
            Quote avec prix actuel et métadonnées

        Raises:
            TickerNotFoundError: Si le ticker n'existe pas
            DataFetchError: Si une erreur survient
        """
        try:
            logger.debug(f"Fetching current quote for {ticker.value}")

            yf_ticker = yf.Ticker(ticker.value)

            # Récupérer les derniers jours pour avoir le prix actuel
            hist = yf_ticker.history(period="5d")

            if hist.empty:
                raise TickerNotFoundError(
                    ticker.value,
                    f"Aucune donnée disponible pour {ticker.value}"
                )

            current_price = float(hist['Close'].iloc[-1])
            previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price

            # Récupérer les infos supplémentaires
            info = self._get_ticker_info(yf_ticker)

            quote = StockQuote(
                ticker=ticker.value,
                price=current_price,
                previous_close=previous_close,
                change=current_price - previous_close,
                change_percent=((current_price - previous_close) / previous_close * 100)
                if previous_close != 0
                else 0.0,
                currency=info.get('currency', 'USD'),
                timestamp=datetime.now(),
            )

            logger.debug(f"Quote for {ticker.value}: {current_price} {quote.currency}")
            return quote

        except TickerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching quote for {ticker.value}: {e}")
            raise DataFetchError(
                f"Erreur lors de la récupération du cours pour {ticker.value}: {str(e)}"
            )

    async def get_metadata(self, ticker: Ticker) -> StockMetadata:
        """
        Récupère les métadonnées d'un instrument.

        Args:
            ticker: Ticker de l'instrument

        Returns:
            Métadonnées complètes du stock

        Raises:
            TickerNotFoundError: Si le ticker n'existe pas
            DataFetchError: Si une erreur survient
        """
        try:
            logger.debug(f"Fetching metadata for {ticker.value}")

            yf_ticker = yf.Ticker(ticker.value)
            info = self._get_ticker_info(yf_ticker)

            if not info:
                raise TickerNotFoundError(
                    ticker.value,
                    f"Aucune information disponible pour {ticker.value}"
                )

            # Déterminer le type d'actif
            quote_type = info.get('quoteType', '').upper()
            asset_type = self._map_quote_type_to_asset_type(quote_type)

            # Extraire le dividend yield
            dividend_yield = self._extract_dividend_yield(info)

            metadata = StockMetadata(
                ticker=ticker.value,
                name=info.get('shortName') or info.get('longName') or ticker.value,
                currency=info.get('currency', 'USD'),
                exchange=info.get('exchange'),
                sector=info.get('sector'),
                industry=info.get('industry'),
                asset_type=asset_type,
                market_cap=info.get('marketCap'),
                dividend_yield=dividend_yield,
            )

            logger.debug(f"Metadata for {ticker.value}: {metadata.name}, {metadata.asset_type}")
            return metadata

        except TickerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching metadata for {ticker.value}: {e}")
            raise DataFetchError(
                f"Erreur lors de la récupération des métadonnées pour {ticker.value}: {str(e)}"
            )

    async def calculate_volatility(
        self,
        ticker: Ticker,
        days: int = 252,
    ) -> Optional[float]:
        """
        Calcule la volatilité annualisée d'un instrument.

        Utilise l'écart-type des rendements quotidiens, annualisé
        par la racine carrée du nombre de jours de trading.

        Args:
            ticker: Ticker de l'instrument
            days: Nombre de jours pour le calcul (défaut: 252 jours de trading)

        Returns:
            Volatilité annualisée en pourcentage, ou None si insuffisant de données
        """
        try:
            # Récupérer l'historique
            data = await self.get_historical_data(ticker, days)

            if len(data) < 20:  # Minimum de données pour un calcul fiable
                logger.warning(f"Insufficient data for volatility calculation: {len(data)} points")
                return None

            # Extraire les prix de clôture
            closes = [point.close for point in data]

            # Calculer les rendements quotidiens
            returns = np.diff(closes) / closes[:-1]

            # Calculer la volatilité annualisée
            daily_volatility = np.std(returns)
            annualized_volatility = daily_volatility * np.sqrt(ANNUALIZATION_FACTOR) * 100

            return round(annualized_volatility, 2)

        except Exception as e:
            logger.warning(f"Error calculating volatility for {ticker.value}: {e}")
            return None

    async def is_valid_ticker(self, ticker: Ticker) -> bool:
        """
        Vérifie si un ticker est valide sur Yahoo Finance.

        Args:
            ticker: Ticker à vérifier

        Returns:
            True si le ticker existe et a des données
        """
        try:
            yf_ticker = yf.Ticker(ticker.value)
            hist = yf_ticker.history(period="5d")
            return not hist.empty
        except Exception:
            return False

    async def search(self, query: str, limit: int = 10) -> List[StockMetadata]:
        """
        Recherche des stocks par nom ou symbole.

        Note: Yahoo Finance n'a pas d'API de recherche native dans yfinance.
        Cette implémentation tente de valider le ticker directement.

        Args:
            query: Terme de recherche (symbole)
            limit: Nombre maximum de résultats

        Returns:
            Liste de StockMetadata si le ticker est trouvé
        """
        try:
            # yfinance n'a pas de vrai search - on essaie le ticker directement
            ticker = Ticker(query.upper())
            if await self.is_valid_ticker(ticker):
                metadata = await self.get_metadata(ticker)
                return [metadata]
            return []
        except Exception as e:
            logger.warning(f"Search failed for {query}: {e}")
            return []

    # =========================================================================
    # MÉTHODES PRIVÉES
    # =========================================================================

    def _get_ticker_info(self, yf_ticker: yf.Ticker) -> dict:
        """
        Récupère les informations d'un ticker avec gestion d'erreur.

        Args:
            yf_ticker: Instance yfinance Ticker

        Returns:
            Dictionnaire d'informations (peut être vide)
        """
        try:
            info = yf_ticker.info
            return info if info else {}
        except Exception as e:
            logger.warning(f"Could not fetch ticker info: {e}")
            return {}

    def _map_quote_type_to_asset_type(self, quote_type: str) -> AssetType:
        """
        Mappe le type de quote Yahoo Finance vers notre AssetType.

        Args:
            quote_type: Type de quote Yahoo Finance

        Returns:
            AssetType correspondant
        """
        mapping = {
            'EQUITY': AssetType.STOCK,
            'ETF': AssetType.ETF,
            'CRYPTOCURRENCY': AssetType.CRYPTO,
            'MUTUALFUND': AssetType.ETF,  # Traité comme ETF
            'INDEX': AssetType.STOCK,  # Indices traités comme stocks
        }
        return mapping.get(quote_type, AssetType.STOCK)

    def _extract_dividend_yield(self, info: dict) -> Optional[float]:
        """
        Extrait le rendement du dividende des infos Yahoo Finance.

        Args:
            info: Dictionnaire d'informations Yahoo Finance

        Returns:
            Dividend yield en pourcentage ou None
        """
        try:
            # Essayer différentes clés (Yahoo Finance n'est pas consistant)
            dividend_yield = info.get('dividendYield')
            if dividend_yield is not None:
                return float(dividend_yield) * 100

            # Fallback sur trailing yield
            trailing_yield = info.get('trailingAnnualDividendYield')
            if trailing_yield is not None:
                return float(trailing_yield) * 100

            return None
        except (TypeError, ValueError):
            return None


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_yahoo_provider(cache_ttl: int = 300) -> YahooFinanceProvider:
    """
    Factory function pour créer un YahooFinanceProvider.

    Args:
        cache_ttl: Durée de vie du cache en secondes

    Returns:
        Instance configurée de YahooFinanceProvider
    """
    return YahooFinanceProvider(cache_ttl=cache_ttl)
