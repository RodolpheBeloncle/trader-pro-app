"""
Outils MCP pour les actualités financières.

Ces outils permettent à Claude Desktop de:
- Récupérer les actualités d'un ticker
- Analyser le sentiment
- Obtenir les news générales du marché
"""

import json
import logging

from src.application.services.news_service import NewsService

logger = logging.getLogger(__name__)


async def get_news_tool(ticker: str, limit: int = 10) -> str:
    """
    Récupère les actualités pour un ticker.

    Args:
        ticker: Symbole du ticker
        limit: Nombre maximum d'articles

    Returns:
        JSON avec les actualités
    """
    try:
        service = NewsService()
        articles = await service.get_news_for_ticker(
            ticker=ticker.upper(),
            limit=limit,
        )

        result = {
            "success": True,
            "ticker": ticker.upper(),
            "count": len(articles),
            "articles": [
                {
                    "headline": a.headline,
                    "summary": a.summary[:200] + "..." if a.summary and len(a.summary) > 200 else a.summary,
                    "source": a.source,
                    "sentiment": a.sentiment.value if a.sentiment else None,
                    "published_at": a.published_at,
                    "age_hours": round(a.age_hours, 1),
                    "url": a.url,
                }
                for a in articles
            ]
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting news for {ticker}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_sentiment_tool(ticker: str) -> str:
    """
    Analyse le sentiment des actualités pour un ticker.

    Args:
        ticker: Symbole du ticker

    Returns:
        JSON avec l'analyse de sentiment
    """
    try:
        service = NewsService()
        sentiment = await service.get_sentiment(ticker.upper())

        # Ajouter une interprétation
        score = sentiment.get("combined_score", 0)
        if score > 0.3:
            interpretation = "Sentiment très positif - potentiel haussier"
        elif score > 0.1:
            interpretation = "Sentiment légèrement positif"
        elif score < -0.3:
            interpretation = "Sentiment très négatif - prudence recommandée"
        elif score < -0.1:
            interpretation = "Sentiment légèrement négatif"
        else:
            interpretation = "Sentiment neutre"

        result = {
            "success": True,
            "ticker": ticker.upper(),
            "sentiment": sentiment,
            "interpretation": interpretation,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting sentiment for {ticker}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_market_news_tool(category: str = "general", limit: int = 15) -> str:
    """
    Récupère les actualités générales du marché.

    Args:
        category: Catégorie (general, forex, crypto, merger)
        limit: Nombre maximum d'articles

    Returns:
        JSON avec les actualités
    """
    try:
        service = NewsService()
        articles = await service.get_market_news(category=category, limit=limit)

        # Grouper par sentiment
        positive = [a for a in articles if a.sentiment and a.sentiment.value == "positive"]
        negative = [a for a in articles if a.sentiment and a.sentiment.value == "negative"]
        neutral = [a for a in articles if not a.sentiment or a.sentiment.value == "neutral"]

        result = {
            "success": True,
            "category": category,
            "total": len(articles),
            "sentiment_breakdown": {
                "positive": len(positive),
                "negative": len(negative),
                "neutral": len(neutral),
            },
            "articles": [
                {
                    "headline": a.headline,
                    "source": a.source,
                    "sentiment": a.sentiment.value if a.sentiment else "neutral",
                    "ticker": a.ticker,
                }
                for a in articles[:limit]
            ]
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting market news: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_news_summary_tool(tickers: str, limit_per_ticker: int = 3) -> str:
    """
    Récupère un résumé des actualités pour plusieurs tickers.

    Args:
        tickers: Liste de tickers séparés par virgule
        limit_per_ticker: Nombre d'articles par ticker

    Returns:
        JSON avec le résumé
    """
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

        if not ticker_list:
            return json.dumps({
                "success": False,
                "error": "Aucun ticker fourni"
            }, ensure_ascii=False)

        if len(ticker_list) > 10:
            ticker_list = ticker_list[:10]

        service = NewsService()
        summary = await service.get_news_summary(
            tickers=ticker_list,
            limit_per_ticker=limit_per_ticker,
        )

        # Calculer le sentiment global
        all_sentiments = []
        for ticker_news in summary.values():
            for article in ticker_news:
                if article.get("sentiment_score"):
                    all_sentiments.append(article["sentiment_score"])

        avg_sentiment = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0

        result = {
            "success": True,
            "tickers_count": len(ticker_list),
            "overall_sentiment": round(avg_sentiment, 3),
            "summary": {
                ticker: [
                    {
                        "headline": a.get("headline", ""),
                        "sentiment": a.get("sentiment"),
                    }
                    for a in articles
                ]
                for ticker, articles in summary.items()
            }
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting news summary: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
