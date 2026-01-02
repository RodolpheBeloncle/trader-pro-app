"""
Repository pour le cache des actualités.

Gère le CRUD des news avec support pour:
- Cache des actualités Finnhub
- Expiration automatique
- Filtrage par ticker, date, sentiment
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict
from enum import Enum

from src.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class Sentiment(str, Enum):
    """Sentiment de l'actualité."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class NewsArticle:
    """
    Article d'actualité en cache.

    Attributs:
        id: Identifiant unique (hash de l'URL)
        ticker: Symbole du ticker concerné
        headline: Titre de l'article
        summary: Résumé
        source: Source (Reuters, Bloomberg, etc.)
        url: URL de l'article
        image_url: URL de l'image
        sentiment: Sentiment analysé
        sentiment_score: Score de sentiment (-1 à 1)
        published_at: Date de publication
        fetched_at: Date de récupération
    """

    id: str
    ticker: str
    headline: str
    summary: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    sentiment: Optional[Sentiment] = None
    sentiment_score: Optional[float] = None
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_positive(self) -> bool:
        """Vérifie si le sentiment est positif."""
        return self.sentiment == Sentiment.POSITIVE

    @property
    def is_negative(self) -> bool:
        """Vérifie si le sentiment est négatif."""
        return self.sentiment == Sentiment.NEGATIVE

    @property
    def age_hours(self) -> float:
        """Retourne l'âge de l'article en heures."""
        if not self.published_at:
            return 0
        try:
            published = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
            now = datetime.now(published.tzinfo) if published.tzinfo else datetime.now()
            return (now - published).total_seconds() / 3600
        except (ValueError, AttributeError):
            return 0

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour API."""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "headline": self.headline,
            "summary": self.summary,
            "source": self.source,
            "url": self.url,
            "image_url": self.image_url,
            "sentiment": self.sentiment.value if self.sentiment else None,
            "sentiment_score": self.sentiment_score,
            "published_at": self.published_at,
            "age_hours": round(self.age_hours, 1),
        }


class NewsRepository(BaseRepository[NewsArticle]):
    """Repository pour le cache des actualités."""

    # Durée de cache par défaut (24 heures)
    DEFAULT_CACHE_HOURS = 24

    @property
    def table_name(self) -> str:
        return "news_cache"

    def _row_to_entity(self, row: Any) -> NewsArticle:
        """Convertit une ligne SQLite en NewsArticle."""
        sentiment = None
        if row["sentiment"]:
            sentiment = Sentiment(row["sentiment"])

        return NewsArticle(
            id=row["id"],
            ticker=row["ticker"],
            headline=row["headline"],
            summary=row["summary"],
            source=row["source"],
            url=row["url"],
            image_url=row["image_url"],
            sentiment=sentiment,
            sentiment_score=row["sentiment_score"],
            published_at=row["published_at"],
            fetched_at=row["fetched_at"],
        )

    def _entity_to_dict(self, entity: NewsArticle) -> Dict[str, Any]:
        """Convertit une NewsArticle en dictionnaire."""
        return {
            "id": entity.id,
            "ticker": entity.ticker.upper(),
            "headline": entity.headline,
            "summary": entity.summary,
            "source": entity.source,
            "url": entity.url,
            "image_url": entity.image_url,
            "sentiment": entity.sentiment.value if entity.sentiment else None,
            "sentiment_score": entity.sentiment_score,
            "published_at": entity.published_at,
            "fetched_at": entity.fetched_at,
        }

    async def save(self, article: NewsArticle) -> NewsArticle:
        """
        Sauvegarde un article (insert ou update).

        Args:
            article: Article à sauvegarder

        Returns:
            Article sauvegardé
        """
        data = self._entity_to_dict(article)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        updates = ", ".join([f"{k} = excluded.{k}" for k in data.keys() if k != "id"])

        await self.db.execute(
            f"""
            INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {updates}
            """,
            tuple(data.values())
        )

        return article

    async def save_many(self, articles: List[NewsArticle]) -> int:
        """
        Sauvegarde plusieurs articles.

        Args:
            articles: Liste d'articles

        Returns:
            Nombre d'articles sauvegardés
        """
        count = 0
        for article in articles:
            await self.save(article)
            count += 1

        logger.info(f"{count} articles sauvegardés en cache")
        return count

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 20,
        max_age_hours: Optional[int] = None
    ) -> List[NewsArticle]:
        """
        Récupère les articles pour un ticker.

        Args:
            ticker: Symbole du ticker
            limit: Nombre maximum d'articles
            max_age_hours: Âge maximum en heures

        Returns:
            Liste des articles
        """
        if max_age_hours:
            cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            rows = await self.db.fetch_all(
                f"""
                SELECT * FROM {self.table_name}
                WHERE ticker = ? AND fetched_at > ?
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (ticker.upper(), cutoff, limit)
            )
        else:
            rows = await self.db.fetch_all(
                f"""
                SELECT * FROM {self.table_name}
                WHERE ticker = ?
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (ticker.upper(), limit)
            )

        return [self._row_to_entity(row) for row in rows]

    async def get_recent(
        self,
        limit: int = 50,
        hours: int = 24
    ) -> List[NewsArticle]:
        """
        Récupère les articles récents.

        Args:
            limit: Nombre maximum d'articles
            hours: Nombre d'heures à regarder en arrière

        Returns:
            Liste des articles récents
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE published_at > ?
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (cutoff, limit)
        )

        return [self._row_to_entity(row) for row in rows]

    async def get_by_sentiment(
        self,
        sentiment: Sentiment,
        limit: int = 20
    ) -> List[NewsArticle]:
        """
        Récupère les articles par sentiment.

        Args:
            sentiment: Sentiment recherché
            limit: Nombre maximum d'articles

        Returns:
            Liste des articles
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE sentiment = ?
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (sentiment.value, limit)
        )

        return [self._row_to_entity(row) for row in rows]

    async def is_cache_fresh(
        self,
        ticker: str,
        max_age_hours: int = 1
    ) -> bool:
        """
        Vérifie si le cache est encore frais.

        Args:
            ticker: Symbole du ticker
            max_age_hours: Âge maximum acceptable

        Returns:
            True si le cache est frais
        """
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()

        row = await self.db.fetch_one(
            f"""
            SELECT 1 FROM {self.table_name}
            WHERE ticker = ? AND fetched_at > ?
            LIMIT 1
            """,
            (ticker.upper(), cutoff)
        )

        return row is not None

    async def cleanup_old(self, max_age_hours: int = 72) -> int:
        """
        Supprime les articles anciens.

        Args:
            max_age_hours: Âge maximum avant suppression

        Returns:
            Nombre d'articles supprimés
        """
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()

        cursor = await self.db.execute(
            f"DELETE FROM {self.table_name} WHERE fetched_at < ?",
            (cutoff,)
        )

        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"{deleted} articles anciens supprimés du cache")

        return deleted

    async def get_sentiment_summary(self, ticker: str) -> Dict[str, Any]:
        """
        Calcule un résumé du sentiment pour un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            Résumé du sentiment
        """
        articles = await self.get_by_ticker(ticker, limit=50, max_age_hours=24)

        if not articles:
            return {
                "ticker": ticker,
                "total_articles": 0,
                "sentiment": "neutral",
                "score": 0.0,
                "breakdown": {"positive": 0, "negative": 0, "neutral": 0},
            }

        breakdown = {
            "positive": sum(1 for a in articles if a.is_positive),
            "negative": sum(1 for a in articles if a.is_negative),
            "neutral": sum(1 for a in articles if a.sentiment == Sentiment.NEUTRAL or a.sentiment is None),
        }

        scores = [a.sentiment_score for a in articles if a.sentiment_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Déterminer le sentiment global
        if breakdown["positive"] > breakdown["negative"] * 1.5:
            overall = "positive"
        elif breakdown["negative"] > breakdown["positive"] * 1.5:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "ticker": ticker,
            "total_articles": len(articles),
            "sentiment": overall,
            "score": round(avg_score, 3),
            "breakdown": breakdown,
        }
