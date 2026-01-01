"""
Outils MCP pour l'analyse de stocks.

Fonctions:
- analyze_stock_tool: Analyse un ticker unique
- analyze_batch_tool: Analyse plusieurs tickers
"""

import json
import logging
from typing import List

from src.application.use_cases.analyze_stock import AnalyzeStockUseCase
from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider

logger = logging.getLogger(__name__)


async def analyze_stock_tool(ticker: str) -> str:
    """
    Analyse un ticker unique.

    Args:
        ticker: Symbole du ticker (ex: AAPL)

    Returns:
        String JSON avec l'analyse ou un message d'erreur
    """
    if not ticker or not ticker.strip():
        return json.dumps({"error": "Ticker requis"}, ensure_ascii=False)

    ticker = ticker.strip().upper()
    logger.info(f"Analyzing stock: {ticker}")

    try:
        # Creer le provider et le use case
        provider = YahooFinanceProvider()
        use_case = AnalyzeStockUseCase(provider)

        # Executer l'analyse
        result = await use_case.execute(ticker)

        if result.is_success and result.analysis:
            analysis = result.analysis

            # Formater le resultat avec conversion des Value Objects
            perf = analysis.performances
            output = {
                "ticker": str(analysis.ticker),
                "name": analysis.info.name,
                "current_price": analysis.current_price.as_float() if analysis.current_price else None,
                "currency": analysis.info.currency,
                "performances": {
                    "3_months": perf.perf_3m.as_percent if perf.perf_3m else None,
                    "6_months": perf.perf_6m.as_percent if perf.perf_6m else None,
                    "1_year": perf.perf_1y.as_percent if perf.perf_1y else None,
                    "3_years": perf.perf_3y.as_percent if perf.perf_3y else None,
                    "5_years": perf.perf_5y.as_percent if perf.perf_5y else None,
                },
                "is_resilient": analysis.is_resilient,
                "volatility": analysis.volatility.as_percent if analysis.volatility else None,
                "volatility_level": analysis.volatility_level,
                "score": analysis.score,
                "sector": analysis.info.sector,
                "industry": analysis.info.industry,
            }

            return json.dumps(output, ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": result.error or "Analyse echouee"}, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error analyzing {ticker}: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def analyze_batch_tool(tickers: List[str]) -> str:
    """
    Analyse plusieurs tickers en batch.

    Args:
        tickers: Liste des tickers a analyser

    Returns:
        String JSON avec les analyses ou les erreurs
    """
    if not tickers:
        return json.dumps({"error": "Liste de tickers requise"}, ensure_ascii=False)

    # Limiter le nombre de tickers
    max_tickers = 20
    if len(tickers) > max_tickers:
        tickers = tickers[:max_tickers]
        logger.warning(f"Limiting batch to {max_tickers} tickers")

    logger.info(f"Batch analyzing {len(tickers)} stocks")

    results = []
    errors = []

    try:
        provider = YahooFinanceProvider()
        use_case = AnalyzeStockUseCase(provider)

        for ticker in tickers:
            ticker = ticker.strip().upper()
            if not ticker:
                continue

            result = await use_case.execute(ticker)

            if result.is_success and result.analysis:
                analysis = result.analysis
                perf = analysis.performances
                results.append({
                    "ticker": str(analysis.ticker),
                    "name": analysis.info.name,
                    "price": analysis.current_price.as_float() if analysis.current_price else None,
                    "perf_3m": perf.perf_3m.as_percent if perf.perf_3m else None,
                    "perf_1y": perf.perf_1y.as_percent if perf.perf_1y else None,
                    "is_resilient": analysis.is_resilient,
                    "volatility": analysis.volatility.as_percent if analysis.volatility else None,
                    "score": analysis.score,
                })
            else:
                errors.append({
                    "ticker": ticker,
                    "error": result.error or "Analyse echouee",
                })

        output = {
            "total": len(results) + len(errors),
            "success_count": len(results),
            "error_count": len(errors),
            "resilient_count": sum(1 for r in results if r["is_resilient"]),
            "results": results,
            "errors": errors if errors else None,
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error in batch analysis: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
