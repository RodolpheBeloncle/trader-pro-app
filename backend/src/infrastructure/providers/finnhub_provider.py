"""
Provider pour l'API Finnhub.

Ce module gère:
- Récupération des actualités par ticker
- Actualités générales du marché
- Analyse de sentiment
- Rate limiting (60 req/min tier gratuit)

CONFIGURATION:
    FINNHUB_API_KEY: Clé API Finnhub (gratuit sur finnhub.io)

UTILISATION:
    from src.infrastructure.providers.finnhub_provider import FinnhubProvider

    provider = FinnhubProvider()
    news = await provider.get_company_news("AAPL")
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import hashlib

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class FinnhubNews:
    """Article d'actualité Finnhub."""
    id: str
    headline: str
    summary: str
    source: str
    url: str
    image_url: Optional[str]
    category: str
    published_at: str
    related_tickers: List[str]

    @classmethod
    def from_api(cls, data: Dict[str, Any], ticker: str = "") -> "FinnhubNews":
        """Crée depuis la réponse API."""
        # Générer un ID unique basé sur l'URL
        url = data.get("url", "")
        id_hash = hashlib.md5(url.encode()).hexdigest()[:16]

        # Convertir le timestamp Unix
        timestamp = data.get("datetime", 0)
        if timestamp:
            published = datetime.fromtimestamp(timestamp).isoformat()
        else:
            published = datetime.now().isoformat()

        return cls(
            id=id_hash,
            headline=data.get("headline", ""),
            summary=data.get("summary", ""),
            source=data.get("source", ""),
            url=url,
            image_url=data.get("image", None),
            category=data.get("category", "general"),
            published_at=published,
            related_tickers=data.get("related", ticker).split(",") if data.get("related") else [ticker],
        )


@dataclass
class SentimentData:
    """Données de sentiment Finnhub."""
    ticker: str
    buzz_articles: int
    buzz_weekly_avg: float
    sentiment_score: float
    sentiment_label: str  # positive, negative, neutral
    company_news_score: float


class FinnhubProvider:
    """
    Provider pour l'API Finnhub.

    Implémente le rate limiting et la gestion des erreurs.
    Tier gratuit: 60 requêtes/minute.
    """

    BASE_URL = "https://finnhub.io/api/v1"
    RATE_LIMIT = 60  # requêtes par minute
    RATE_WINDOW = 60  # secondes

    def __init__(self, api_key: Optional[str] = None, timeout: float = 30.0):
        """
        Initialise le provider.

        Args:
            api_key: Clé API Finnhub. Par défaut depuis settings.
            timeout: Timeout des requêtes HTTP.
        """
        self._api_key = api_key or settings.FINNHUB_API_KEY
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._request_times: List[float] = []

    @property
    def is_configured(self) -> bool:
        """Vérifie si le provider est configuré."""
        return bool(self._api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Retourne le client HTTP (singleton)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"X-Finnhub-Token": self._api_key or ""}
            )
        return self._client

    async def close(self) -> None:
        """Ferme le client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self) -> None:
        """Applique le rate limiting."""
        now = asyncio.get_event_loop().time()

        # Nettoyer les anciennes requêtes
        self._request_times = [
            t for t in self._request_times
            if now - t < self.RATE_WINDOW
        ]

        # Attendre si nécessaire
        if len(self._request_times) >= self.RATE_LIMIT:
            wait_time = self.RATE_WINDOW - (now - self._request_times[0])
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """
        Effectue une requête à l'API Finnhub.

        Args:
            endpoint: Endpoint API (sans le base URL)
            params: Paramètres de requête

        Returns:
            Données JSON de la réponse
        """
        if not self.is_configured:
            raise ValueError("Finnhub API key not configured")

        await self._rate_limit()

        client = await self._get_client()
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = await client.get(url, params=params or {})

            if response.status_code == 429:
                logger.warning("Finnhub rate limit exceeded")
                await asyncio.sleep(60)
                return await self._request(endpoint, params)

            if response.status_code == 401:
                raise ValueError("Invalid Finnhub API key")

            if response.status_code == 403:
                raise ValueError("Finnhub API access forbidden")

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            logger.error(f"Finnhub request timeout: {endpoint}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Finnhub request error: {e}")
            raise

    async def get_company_news(
        self,
        ticker: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[FinnhubNews]:
        """
        Récupère les actualités pour une entreprise.

        Args:
            ticker: Symbole du ticker
            from_date: Date de début. Par défaut: 7 jours
            to_date: Date de fin. Par défaut: aujourd'hui

        Returns:
            Liste d'articles
        """
        if to_date is None:
            to_date = date.today()
        if from_date is None:
            from_date = to_date - timedelta(days=7)

        data = await self._request("company-news", {
            "symbol": ticker.upper(),
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        })

        if not isinstance(data, list):
            return []

        return [FinnhubNews.from_api(item, ticker) for item in data]

    async def get_market_news(self, category: str = "general") -> List[FinnhubNews]:
        """
        Récupère les actualités générales du marché.

        Args:
            category: Catégorie (general, forex, crypto, merger)

        Returns:
            Liste d'articles
        """
        data = await self._request("news", {"category": category})

        if not isinstance(data, list):
            return []

        return [FinnhubNews.from_api(item) for item in data]

    async def get_sentiment(self, ticker: str) -> Optional[SentimentData]:
        """
        Récupère les données de sentiment social.

        Args:
            ticker: Symbole du ticker

        Returns:
            Données de sentiment ou None
        """
        try:
            data = await self._request("news-sentiment", {"symbol": ticker.upper()})

            if not data:
                return None

            buzz = data.get("buzz", {})
            sentiment = data.get("sentiment", {})
            company = data.get("companyNewsScore", 0)

            # Déterminer le label
            score = sentiment.get("bullishPercent", 0.5)
            if score > 0.6:
                label = "positive"
            elif score < 0.4:
                label = "negative"
            else:
                label = "neutral"

            return SentimentData(
                ticker=ticker.upper(),
                buzz_articles=buzz.get("articlesInLastWeek", 0),
                buzz_weekly_avg=buzz.get("weeklyAverage", 0),
                sentiment_score=score,
                sentiment_label=label,
                company_news_score=company,
            )

        except Exception as e:
            logger.error(f"Error fetching sentiment for {ticker}: {e}")
            return None

    async def search_symbol(self, query: str) -> List[Dict[str, str]]:
        """
        Recherche des symboles.

        Args:
            query: Terme de recherche

        Returns:
            Liste de résultats
        """
        data = await self._request("search", {"q": query})

        if not data or "result" not in data:
            return []

        return [
            {
                "symbol": item.get("symbol", ""),
                "description": item.get("description", ""),
                "type": item.get("type", ""),
            }
            for item in data.get("result", [])
        ]

    async def get_basic_financials(self, ticker: str) -> Dict[str, Any]:
        """
        Récupère les métriques financières de base.

        Args:
            ticker: Symbole du ticker

        Returns:
            Métriques financières
        """
        data = await self._request("stock/metric", {
            "symbol": ticker.upper(),
            "metric": "all",
        })

        if not data:
            return {}

        return data.get("metric", {})


# Singleton
_finnhub_provider: Optional[FinnhubProvider] = None


def get_finnhub_provider() -> FinnhubProvider:
    """
    Retourne l'instance singleton du provider Finnhub.

    Returns:
        FinnhubProvider initialisé
    """
    global _finnhub_provider
    if _finnhub_provider is None:
        _finnhub_provider = FinnhubProvider()
    return _finnhub_provider
