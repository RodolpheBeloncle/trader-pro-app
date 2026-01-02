"""
Routes API pour les actualités financières.

Endpoints:
- GET /news                    - Actualités générales du marché
- GET /news/{ticker}           - Actualités pour un ticker
- GET /news/{ticker}/sentiment - Analyse de sentiment
- GET /news/summary            - Résumé pour plusieurs tickers
- POST /news/cleanup           - Nettoyage du cache
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.services.news_service import NewsService
from src.infrastructure.database.repositories.news_repository import NewsArticle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


# =============================================================================
# SCHEMAS
# =============================================================================

class NewsArticleResponse(BaseModel):
    """Réponse avec un article."""
    id: str
    ticker: str
    headline: str
    summary: Optional[str]
    source: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    sentiment: Optional[str]
    sentiment_score: Optional[float]
    published_at: Optional[str]
    age_hours: float

    @classmethod
    def from_entity(cls, article: NewsArticle) -> "NewsArticleResponse":
        return cls(
            id=article.id,
            ticker=article.ticker,
            headline=article.headline,
            summary=article.summary,
            source=article.source,
            url=article.url,
            image_url=article.image_url,
            sentiment=article.sentiment.value if article.sentiment else None,
            sentiment_score=article.sentiment_score,
            published_at=article.published_at,
            age_hours=article.age_hours,
        )


class SentimentResponse(BaseModel):
    """Réponse avec l'analyse de sentiment."""
    ticker: str
    combined_score: float
    local: dict
    finnhub: Optional[dict] = None


class SummaryRequest(BaseModel):
    """Requête pour le résumé multi-tickers."""
    tickers: List[str] = Field(..., min_length=1, max_length=10)
    limit_per_ticker: int = Field(5, ge=1, le=20)


# =============================================================================
# SERVICE
# =============================================================================

def get_news_service() -> NewsService:
    """Factory pour le service de news."""
    return NewsService()


# =============================================================================
# ROUTES
# =============================================================================

@router.get("", response_model=List[NewsArticleResponse])
async def get_market_news(
    category: str = Query("general", description="Catégorie: general, forex, crypto, merger"),
    limit: int = Query(30, ge=1, le=100),
):
    """
    Récupère les actualités générales du marché.

    Catégories disponibles:
    - **general**: Actualités générales
    - **forex**: Marché des changes
    - **crypto**: Cryptomonnaies
    - **merger**: Fusions et acquisitions
    """
    service = get_news_service()

    try:
        articles = await service.get_market_news(category=category, limit=limit)
        return [NewsArticleResponse.from_entity(a) for a in articles]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching market news: {e}")
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")


@router.get("/{ticker}", response_model=List[NewsArticleResponse])
async def get_ticker_news(
    ticker: str,
    limit: int = Query(20, ge=1, le=50),
    refresh: bool = Query(False, description="Forcer le rafraîchissement du cache"),
):
    """
    Récupère les actualités pour un ticker spécifique.

    Les actualités sont mises en cache pendant 1 heure.
    Utilisez `refresh=true` pour forcer un rafraîchissement.
    """
    service = get_news_service()

    try:
        articles = await service.get_news_for_ticker(
            ticker=ticker.upper(),
            limit=limit,
            force_refresh=refresh,
        )
        return [NewsArticleResponse.from_entity(a) for a in articles]
    except Exception as e:
        logger.exception(f"Error fetching news for {ticker}: {e}")
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")


@router.get("/{ticker}/sentiment", response_model=SentimentResponse)
async def get_ticker_sentiment(ticker: str):
    """
    Analyse le sentiment des actualités pour un ticker.

    Combine:
    - L'analyse locale basée sur les articles en cache
    - Les données de sentiment social Finnhub (si disponible)

    Le score combiné va de -1 (très négatif) à +1 (très positif).
    """
    service = get_news_service()

    try:
        sentiment = await service.get_sentiment(ticker.upper())
        return SentimentResponse(**sentiment)
    except Exception as e:
        logger.exception(f"Error fetching sentiment for {ticker}: {e}")
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")


@router.post("/summary")
async def get_news_summary(request: SummaryRequest):
    """
    Récupère un résumé des actualités pour plusieurs tickers.

    Maximum 10 tickers par requête.
    """
    service = get_news_service()

    try:
        summary = await service.get_news_summary(
            tickers=request.tickers,
            limit_per_ticker=request.limit_per_ticker,
        )
        return summary
    except Exception as e:
        logger.exception(f"Error fetching news summary: {e}")
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")


@router.get("/search/query")
async def search_news(
    q: str = Query(..., min_length=2, description="Terme de recherche"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Recherche dans les actualités en cache.

    Recherche dans les titres et résumés des articles récents.
    """
    service = get_news_service()

    try:
        articles = await service.search_news(query=q, limit=limit)
        return [NewsArticleResponse.from_entity(a) for a in articles]
    except Exception as e:
        logger.exception(f"Error searching news: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la recherche")


@router.post("/cleanup")
async def cleanup_news_cache(
    max_age_hours: int = Query(72, ge=24, le=720, description="Âge maximum en heures"),
):
    """
    Nettoie le cache des articles anciens.

    Supprime les articles plus anciens que `max_age_hours` heures.
    Par défaut: 72 heures (3 jours).
    """
    service = get_news_service()

    try:
        deleted = await service.cleanup_old_cache(max_age_hours)
        return {"deleted": deleted, "message": f"{deleted} articles supprimés du cache"}
    except Exception as e:
        logger.exception(f"Error cleaning up news cache: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du nettoyage")
