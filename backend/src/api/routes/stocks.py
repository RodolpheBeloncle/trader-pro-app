"""
Routes API pour l'analyse des stocks.

Endpoints:
- GET /api/stocks/analyze?ticker=AAPL - Analyse un stock
- POST /api/stocks/analyze/batch - Analyse plusieurs stocks
- GET /api/stocks/export - Exporte les analyses en CSV

ARCHITECTURE:
- Validation avec Pydantic schemas
- Injection de dépendances via Depends
- Transformation des résultats en réponses HTTP
"""

import csv
from io import StringIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.application.use_cases import (
    AnalyzeStockUseCase,
    AnalyzeBatchUseCase,
    AnalyzeStockResult,
    BatchResult,
)
from src.domain.exceptions import (
    TickerNotFoundError,
    DataFetchError,
    AnalysisError,
)

router = APIRouter(prefix="/stocks", tags=["stocks"])


# =============================================================================
# SCHEMAS
# =============================================================================

class PerformanceResponse(BaseModel):
    """Performances sur toutes les périodes."""

    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_1y: Optional[float] = None
    perf_3y: Optional[float] = None
    perf_5y: Optional[float] = None


class StockInfoResponse(BaseModel):
    """Informations du stock."""

    name: str
    currency: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    asset_type: str
    dividend_yield: Optional[float] = None


class ChartDataPointResponse(BaseModel):
    """Point de données pour graphique."""

    date: str
    price: float


class StockAnalysisResponse(BaseModel):
    """Réponse d'analyse complète d'un stock."""

    ticker: str
    info: StockInfoResponse
    performances: PerformanceResponse
    current_price: Optional[float] = None
    currency: str
    volatility: Optional[float] = None
    is_resilient: bool
    volatility_level: str
    score: int
    chart_data: List[ChartDataPointResponse]
    analyzed_at: str


class StockErrorResponse(BaseModel):
    """Réponse d'erreur pour un stock."""

    ticker: str
    error: str


class BatchAnalyzeRequest(BaseModel):
    """Requête d'analyse batch."""

    tickers: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Liste des tickers à analyser",
    )


class BatchAnalyzeResponse(BaseModel):
    """Réponse d'analyse batch."""

    results: List[StockAnalysisResponse]
    errors: List[StockErrorResponse]
    success_count: int
    error_count: int


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

# Ces fonctions seront remplacées par l'injection depuis dependencies.py
async def get_analyze_use_case() -> AnalyzeStockUseCase:
    """Placeholder - sera injecté depuis dependencies.py."""
    # Import ici pour éviter les imports circulaires
    from src.api.dependencies import get_analyze_stock_use_case
    return await get_analyze_stock_use_case()


async def get_batch_use_case() -> AnalyzeBatchUseCase:
    """Placeholder - sera injecté depuis dependencies.py."""
    from src.api.dependencies import get_analyze_batch_use_case
    return await get_analyze_batch_use_case()


# =============================================================================
# ROUTES
# =============================================================================

@router.get(
    "/analyze",
    response_model=StockAnalysisResponse,
    responses={
        404: {"description": "Ticker non trouvé"},
        422: {"description": "Erreur de validation"},
        500: {"description": "Erreur serveur"},
    },
)
async def analyze_stock(
    ticker: str = Query(
        ...,
        min_length=1,
        max_length=10,
        description="Symbole du ticker (ex: AAPL)",
    ),
    use_case: AnalyzeStockUseCase = Depends(get_analyze_use_case),
):
    """
    Analyse un stock selon la méthodologie "trader writer".

    Calcule les performances sur 5 périodes (3m, 6m, 1y, 3y, 5y)
    et détermine si le stock est "résilient" (positif sur toutes).
    """
    result = await use_case.execute(ticker.upper())

    if not result.is_success:
        if "non trouvé" in result.error or "not found" in result.error.lower():
            raise HTTPException(status_code=404, detail=result.error)
        raise HTTPException(status_code=400, detail=result.error)

    analysis = result.analysis

    return StockAnalysisResponse(
        ticker=analysis.ticker,
        info=StockInfoResponse(
            name=analysis.info.name,
            currency=analysis.info.currency,
            exchange=analysis.info.exchange,
            sector=analysis.info.sector,
            industry=analysis.info.industry,
            asset_type=analysis.info.asset_type,
            dividend_yield=analysis.info.dividend_yield,
        ),
        performances=PerformanceResponse(
            perf_3m=analysis.performances.perf_3m,
            perf_6m=analysis.performances.perf_6m,
            perf_1y=analysis.performances.perf_1y,
            perf_3y=analysis.performances.perf_3y,
            perf_5y=analysis.performances.perf_5y,
        ),
        current_price=analysis.current_price,
        currency=analysis.currency,
        volatility=analysis.volatility,
        is_resilient=analysis.is_resilient,
        volatility_level=analysis.volatility_level,
        score=analysis.score,
        chart_data=[
            ChartDataPointResponse(date=p.date, price=p.price)
            for p in analysis.chart_data
        ],
        analyzed_at=analysis.analyzed_at,
    )


@router.post(
    "/analyze/batch",
    response_model=BatchAnalyzeResponse,
)
async def analyze_batch(
    request: BatchAnalyzeRequest,
    use_case: AnalyzeBatchUseCase = Depends(get_batch_use_case),
):
    """
    Analyse plusieurs stocks en parallèle.

    Limite: 50 tickers maximum par requête.
    """
    # Normaliser les tickers
    tickers = [t.upper() for t in request.tickers]

    batch_result = await use_case.execute(tickers)

    # Séparer succès et erreurs
    results = []
    errors = []

    for r in batch_result.results:
        if r.is_success and r.analysis:
            analysis = r.analysis
            results.append(StockAnalysisResponse(
                ticker=analysis.ticker,
                info=StockInfoResponse(
                    name=analysis.info.name,
                    currency=analysis.info.currency,
                    exchange=analysis.info.exchange,
                    sector=analysis.info.sector,
                    industry=analysis.info.industry,
                    asset_type=analysis.info.asset_type,
                    dividend_yield=analysis.info.dividend_yield,
                ),
                performances=PerformanceResponse(
                    perf_3m=analysis.performances.perf_3m,
                    perf_6m=analysis.performances.perf_6m,
                    perf_1y=analysis.performances.perf_1y,
                    perf_3y=analysis.performances.perf_3y,
                    perf_5y=analysis.performances.perf_5y,
                ),
                current_price=analysis.current_price,
                currency=analysis.currency,
                volatility=analysis.volatility,
                is_resilient=analysis.is_resilient,
                volatility_level=analysis.volatility_level,
                score=analysis.score,
                chart_data=[
                    ChartDataPointResponse(date=p.date, price=p.price)
                    for p in analysis.chart_data
                ],
                analyzed_at=analysis.analyzed_at,
            ))
        else:
            errors.append(StockErrorResponse(
                ticker=r.ticker,
                error=r.error or "Erreur inconnue",
            ))

    return BatchAnalyzeResponse(
        results=results,
        errors=errors,
        success_count=len(results),
        error_count=len(errors),
    )


@router.get("/export")
async def export_csv(
    tickers: str = Query(
        ...,
        description="Tickers séparés par des virgules (ex: AAPL,MSFT,GOOGL)",
    ),
    resilient_only: bool = Query(
        False,
        description="Exporter uniquement les stocks résilients",
    ),
    use_case: AnalyzeBatchUseCase = Depends(get_batch_use_case),
):
    """
    Exporte les analyses en CSV.

    Format compatible avec Excel (séparateur point-virgule).
    """
    # Parser les tickers
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if not ticker_list:
        raise HTTPException(status_code=400, detail="Aucun ticker fourni")

    if len(ticker_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 tickers")

    # Analyser
    batch_result = await use_case.execute(ticker_list)

    # Filtrer si demandé
    analyses = [
        r.analysis for r in batch_result.results
        if r.is_success and r.analysis
    ]

    if resilient_only:
        analyses = [a for a in analyses if a.is_resilient]

    if not analyses:
        return StreamingResponse(
            iter(["Aucun stock à exporter\n"]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=stocks.csv"},
        )

    # Générer le CSV
    output = StringIO()
    writer = csv.writer(output, delimiter=";")

    # Headers
    writer.writerow([
        "Ticker", "Nom", "Devise", "Prix",
        "Perf 3M", "Perf 6M", "Perf 1Y", "Perf 3Y", "Perf 5Y",
        "Volatilité", "Résilient", "Score", "Secteur",
    ])

    # Données
    for a in analyses:
        writer.writerow([
            a.ticker,
            a.info.name,
            a.currency,
            a.current_price or "",
            a.performances.perf_3m or "",
            a.performances.perf_6m or "",
            a.performances.perf_1y or "",
            a.performances.perf_3y or "",
            a.performances.perf_5y or "",
            a.volatility or "",
            "Oui" if a.is_resilient else "Non",
            a.score,
            a.info.sector or "",
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=stocks_analysis.csv",
        },
    )
