"""
Service de gestion des actualités.

Ce service orchestre:
- La récupération des news depuis Finnhub
- Le cache en base de données
- L'analyse de sentiment
- L'agrégation des données

UTILISATION:
    from src.application.services.news_service import NewsService

    service = NewsService()
    news = await service.get_news_for_ticker("AAPL")
"""

import logging
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from src.infrastructure.providers.finnhub_provider import (
    FinnhubProvider,
    get_finnhub_provider,
    FinnhubNews,
)
from src.infrastructure.database.repositories.news_repository import (
    NewsRepository,
    NewsArticle,
    Sentiment,
)

logger = logging.getLogger(__name__)


class NewsService:
    """
    Service métier pour les actualités.

    Coordonne le provider Finnhub et le cache SQLite
    pour une gestion efficace des actualités.
    """

    # Durée de cache en heures
    CACHE_DURATION_HOURS = 1

    def __init__(
        self,
        finnhub: Optional[FinnhubProvider] = None,
        news_repo: Optional[NewsRepository] = None,
    ):
        """
        Initialise le service.

        Args:
            finnhub: Provider Finnhub.
            news_repo: Repository des news.
        """
        self._finnhub = finnhub or get_finnhub_provider()
        self._news_repo = news_repo or NewsRepository()

    def _convert_to_article(self, news: FinnhubNews, ticker: str) -> NewsArticle:
        """Convertit une news Finnhub en article pour le cache."""
        # Déterminer le sentiment basé sur des mots clés simples
        headline_lower = news.headline.lower()
        summary_lower = news.summary.lower()
        text = headline_lower + " " + summary_lower

        positive_words = ["surge", "gain", "rise", "jump", "beat", "strong", "bullish", "upgrade"]
        negative_words = ["drop", "fall", "miss", "weak", "bearish", "downgrade", "plunge", "crash"]

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        if pos_count > neg_count:
            sentiment = Sentiment.POSITIVE
            sentiment_score = 0.3 + (pos_count * 0.1)
        elif neg_count > pos_count:
            sentiment = Sentiment.NEGATIVE
            sentiment_score = -0.3 - (neg_count * 0.1)
        else:
            sentiment = Sentiment.NEUTRAL
            sentiment_score = 0.0

        return NewsArticle(
            id=news.id,
            ticker=ticker.upper(),
            headline=news.headline,
            summary=news.summary,
            source=news.source,
            url=news.url,
            image_url=news.image_url,
            sentiment=sentiment,
            sentiment_score=max(-1, min(1, sentiment_score)),
            published_at=news.published_at,
        )

    async def get_news_for_ticker(
        self,
        ticker: str,
        limit: int = 20,
        force_refresh: bool = False,
    ) -> List[NewsArticle]:
        """
        Récupère les actualités pour un ticker.

        Utilise le cache si disponible et frais.

        Args:
            ticker: Symbole du ticker
            limit: Nombre maximum d'articles
            force_refresh: Forcer le rafraîchissement du cache

        Returns:
            Liste d'articles
        """
        ticker = ticker.upper()

        # Vérifier le cache
        if not force_refresh:
            is_fresh = await self._news_repo.is_cache_fresh(
                ticker, self.CACHE_DURATION_HOURS
            )
            if is_fresh:
                articles = await self._news_repo.get_by_ticker(
                    ticker, limit, max_age_hours=24
                )
                if articles:
                    logger.debug(f"Cache hit for {ticker}: {len(articles)} articles")
                    return articles

        # Récupérer depuis Finnhub
        if not self._finnhub.is_configured:
            logger.warning("Finnhub not configured, returning cached data")
            return await self._news_repo.get_by_ticker(ticker, limit)

        try:
            news_list = await self._finnhub.get_company_news(ticker)

            if news_list:
                # Convertir et sauvegarder en cache
                articles = [self._convert_to_article(n, ticker) for n in news_list]
                await self._news_repo.save_many(articles)
                logger.info(f"Fetched {len(articles)} news for {ticker} from Finnhub")
                return articles[:limit]

        except Exception as e:
            logger.error(f"Error fetching news from Finnhub for {ticker}: {e}")

        # Fallback sur le cache
        return await self._news_repo.get_by_ticker(ticker, limit)

    async def get_market_news(
        self,
        category: str = "general",
        limit: int = 30,
    ) -> List[NewsArticle]:
        """
        Récupère les actualités générales du marché.

        Args:
            category: Catégorie (general, forex, crypto, merger)
            limit: Nombre maximum d'articles

        Returns:
            Liste d'articles
        """
        if not self._finnhub.is_configured:
            logger.warning("Finnhub not configured")
            return []

        try:
            news_list = await self._finnhub.get_market_news(category)

            articles = []
            for news in news_list[:limit]:
                # Pour les news générales, utiliser le premier ticker lié
                ticker = news.related_tickers[0] if news.related_tickers else "MARKET"
                articles.append(self._convert_to_article(news, ticker))

            return articles

        except Exception as e:
            logger.error(f"Error fetching market news: {e}")
            return []

    async def get_sentiment(self, ticker: str) -> Dict[str, Any]:
        """
        Récupère l'analyse de sentiment pour un ticker.

        Combine le sentiment Finnhub et l'analyse locale.

        Args:
            ticker: Symbole du ticker

        Returns:
            Données de sentiment
        """
        ticker = ticker.upper()

        # Sentiment du cache local
        local_sentiment = await self._news_repo.get_sentiment_summary(ticker)

        # Sentiment Finnhub si disponible
        finnhub_sentiment = None
        if self._finnhub.is_configured:
            try:
                finnhub_sentiment = await self._finnhub.get_sentiment(ticker)
            except Exception as e:
                logger.error(f"Error fetching Finnhub sentiment for {ticker}: {e}")

        result = {
            "ticker": ticker,
            "local": local_sentiment,
        }

        if finnhub_sentiment:
            result["finnhub"] = {
                "buzz_articles": finnhub_sentiment.buzz_articles,
                "buzz_weekly_avg": finnhub_sentiment.buzz_weekly_avg,
                "sentiment_score": finnhub_sentiment.sentiment_score,
                "sentiment_label": finnhub_sentiment.sentiment_label,
                "company_news_score": finnhub_sentiment.company_news_score,
            }

            # Score combiné
            local_score = local_sentiment.get("score", 0)
            finnhub_score = finnhub_sentiment.sentiment_score - 0.5  # Normaliser à -0.5, +0.5
            result["combined_score"] = round((local_score + finnhub_score) / 2, 3)
        else:
            result["combined_score"] = local_sentiment.get("score", 0)

        return result

    async def get_news_summary(
        self,
        tickers: List[str],
        limit_per_ticker: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Récupère un résumé des news pour plusieurs tickers.

        Args:
            tickers: Liste de symboles
            limit_per_ticker: Nombre d'articles par ticker

        Returns:
            Dictionnaire ticker -> articles
        """
        result = {}

        for ticker in tickers:
            articles = await self.get_news_for_ticker(ticker, limit=limit_per_ticker)
            result[ticker.upper()] = [a.to_dict() for a in articles]

        return result

    async def cleanup_old_cache(self, max_age_hours: int = 72) -> int:
        """
        Nettoie le cache des articles anciens.

        Args:
            max_age_hours: Âge maximum en heures

        Returns:
            Nombre d'articles supprimés
        """
        return await self._news_repo.cleanup_old(max_age_hours)

    async def search_news(
        self,
        query: str,
        limit: int = 20,
    ) -> List[NewsArticle]:
        """
        Recherche dans le cache des news.

        Args:
            query: Terme de recherche
            limit: Nombre maximum de résultats

        Returns:
            Articles correspondants
        """
        # Pour l'instant, recherche simple dans le cache récent
        recent = await self._news_repo.get_recent(limit=100, hours=48)

        query_lower = query.lower()
        matches = [
            a for a in recent
            if query_lower in a.headline.lower() or
               (a.summary and query_lower in a.summary.lower())
        ]

        return matches[:limit]
