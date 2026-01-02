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
from src.application.use_cases.get_ohlc_data import GetOHLCDataUseCase
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


class OHLCCandleResponse(BaseModel):
    """Un point de donnees candlestick."""

    time: int
    open: float
    high: float
    low: float
    close: float


class OHLCVolumeResponse(BaseModel):
    """Un point de donnees volume."""

    time: int
    value: int
    color: str


class OHLCDataResponse(BaseModel):
    """Reponse avec donnees OHLC pour TradingView."""

    ticker: str
    candles: List[OHLCCandleResponse]
    volume: List[OHLCVolumeResponse]


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

    # Extraire les valeurs primitives des Value Objects
    perf = analysis.performances

    return StockAnalysisResponse(
        ticker=analysis.ticker.value if hasattr(analysis.ticker, 'value') else str(analysis.ticker),
        info=StockInfoResponse(
            name=analysis.info.name,
            currency=analysis.info.currency,
            exchange=analysis.info.exchange,
            sector=analysis.info.sector,
            industry=analysis.info.industry,
            asset_type=analysis.info.asset_type.value if analysis.info.asset_type else None,
            dividend_yield=analysis.info.dividend_yield.as_percent if analysis.info.dividend_yield else None,
        ),
        performances=PerformanceResponse(
            perf_3m=perf.perf_3m.as_percent if perf.perf_3m else None,
            perf_6m=perf.perf_6m.as_percent if perf.perf_6m else None,
            perf_1y=perf.perf_1y.as_percent if perf.perf_1y else None,
            perf_3y=perf.perf_3y.as_percent if perf.perf_3y else None,
            perf_5y=perf.perf_5y.as_percent if perf.perf_5y else None,
        ),
        current_price=analysis.current_price.amount if hasattr(analysis.current_price, 'amount') else float(analysis.current_price),
        currency=analysis.current_price.currency if hasattr(analysis.current_price, 'currency') else analysis.info.currency,
        volatility=analysis.volatility.as_percent if analysis.volatility else None,
        is_resilient=analysis.is_resilient,
        volatility_level=analysis.volatility_level.value if hasattr(analysis.volatility_level, 'value') else analysis.volatility_level,
        score=analysis.score,
        chart_data=[
            ChartDataPointResponse(date=p.date.strftime("%Y-%m-%d") if hasattr(p.date, 'strftime') else p.date, price=p.price)
            for p in analysis.chart_data
        ],
        analyzed_at=analysis.analyzed_at.isoformat() if hasattr(analysis.analyzed_at, 'isoformat') else str(analysis.analyzed_at),
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
            perf = analysis.performances
            results.append(StockAnalysisResponse(
                ticker=analysis.ticker.value if hasattr(analysis.ticker, 'value') else str(analysis.ticker),
                info=StockInfoResponse(
                    name=analysis.info.name,
                    currency=analysis.info.currency,
                    exchange=analysis.info.exchange,
                    sector=analysis.info.sector,
                    industry=analysis.info.industry,
                    asset_type=analysis.info.asset_type.value if analysis.info.asset_type else None,
                    dividend_yield=analysis.info.dividend_yield.as_percent if analysis.info.dividend_yield else None,
                ),
                performances=PerformanceResponse(
                    perf_3m=perf.perf_3m.as_percent if perf.perf_3m else None,
                    perf_6m=perf.perf_6m.as_percent if perf.perf_6m else None,
                    perf_1y=perf.perf_1y.as_percent if perf.perf_1y else None,
                    perf_3y=perf.perf_3y.as_percent if perf.perf_3y else None,
                    perf_5y=perf.perf_5y.as_percent if perf.perf_5y else None,
                ),
                current_price=analysis.current_price.amount if hasattr(analysis.current_price, 'amount') else float(analysis.current_price),
                currency=analysis.current_price.currency if hasattr(analysis.current_price, 'currency') else analysis.info.currency,
                volatility=analysis.volatility.as_percent if analysis.volatility else None,
                is_resilient=analysis.is_resilient,
                volatility_level=analysis.volatility_level.value if hasattr(analysis.volatility_level, 'value') else analysis.volatility_level,
                score=analysis.score,
                chart_data=[
                    ChartDataPointResponse(date=p.date.strftime("%Y-%m-%d") if hasattr(p.date, 'strftime') else p.date, price=p.price)
                    for p in analysis.chart_data
                ],
                analyzed_at=analysis.analyzed_at.isoformat() if hasattr(analysis.analyzed_at, 'isoformat') else str(analysis.analyzed_at),
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


# =============================================================================
# OHLC DATA FOR TRADINGVIEW
# =============================================================================

async def get_ohlc_use_case() -> GetOHLCDataUseCase:
    """Factory pour le use case OHLC."""
    from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
    provider = YahooFinanceProvider()
    return GetOHLCDataUseCase(provider)


@router.get(
    "/ohlc/{ticker}",
    response_model=OHLCDataResponse,
    responses={
        404: {"description": "Ticker non trouve"},
        500: {"description": "Erreur serveur"},
    },
)
async def get_ohlc_data(
    ticker: str,
    days: int = Query(
        365,
        ge=30,
        le=1825,
        description="Nombre de jours d'historique (30-1825)",
    ),
    use_case: GetOHLCDataUseCase = Depends(get_ohlc_use_case),
):
    """
    Recupere les donnees OHLC pour un graphique candlestick.

    Retourne les donnees formatees pour TradingView lightweight-charts:
    - candles: Array de {time, open, high, low, close}
    - volume: Array de {time, value, color}

    Args:
        ticker: Symbole boursier (ex: AAPL, MSFT)
        days: Nombre de jours d'historique (30 a 1825)
    """
    try:
        result = await use_case.execute(ticker.upper(), days)

        if not result["candles"]:
            raise HTTPException(
                status_code=404,
                detail=f"Aucune donnee OHLC disponible pour {ticker}"
            )

        return OHLCDataResponse(
            ticker=result["ticker"],
            candles=[
                OHLCCandleResponse(**c) for c in result["candles"]
            ],
            volume=[
                OHLCVolumeResponse(**v) for v in result["volume"]
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la recuperation des donnees OHLC: {str(e)}"
        )
