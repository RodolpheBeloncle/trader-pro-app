"""
Routes API pour l'analyse des stocks.

Endpoints:
- GET /api/stocks/analyze?ticker=AAPL - Analyse un stock
- GET /api/stocks/search?query=... - Recherche par nom ou symbole
- POST /api/stocks/analyze/batch - Analyse plusieurs stocks
- GET /api/stocks/export - Exporte les analyses en CSV

ARCHITECTURE:
- Validation avec Pydantic schemas
- Injection de dépendances via Depends
- Transformation des résultats en réponses HTTP
"""

import csv
import logging

logger = logging.getLogger(__name__)
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


# =============================================================================
# RECHERCHE
# =============================================================================

class SearchResultItem(BaseModel):
    """Un résultat de recherche."""
    symbol: str
    name: str
    exchange: Optional[str] = None
    asset_type: Optional[str] = None


class SearchResponse(BaseModel):
    """Réponse de recherche."""
    query: str
    results: List[SearchResultItem]
    count: int


@router.get("/search", response_model=SearchResponse)
async def search_tickers(
    query: str = Query(
        ...,
        min_length=2,
        max_length=50,
        description="Terme de recherche (nom ou symbole)",
    ),
    asset_type: str = Query(
        "all",
        description="Type d'actif: stocks, etfs, crypto, all",
    ),
):
    """
    Recherche des tickers par nom ou symbole.

    Utilise Yahoo Finance pour trouver des correspondances.
    """
    import yfinance as yf

    try:
        # Yahoo Finance search via Ticker lookup
        results = []

        # Essayer d'abord comme un symbole direct
        try:
            ticker = yf.Ticker(query.upper())
            info = ticker.info
            if info and info.get('shortName'):
                results.append(SearchResultItem(
                    symbol=query.upper(),
                    name=info.get('shortName', query.upper()),
                    exchange=info.get('exchange'),
                    asset_type=info.get('quoteType', 'EQUITY'),
                ))
        except Exception:
            pass

        # Si pas de résultat direct, essayer avec des variations courantes pour ETFs
        if not results and len(query) > 3:
            # Essayer quelques variantes pour les ETFs populaires
            common_etf_tickers = {
                "ishares msci world": ["IWDA.AS", "URTH", "SWDA.L"],
                "ishares": ["IWDA.AS", "IVV", "AGG", "EEM"],
                "vanguard": ["VTI", "VOO", "VEA", "VWO"],
                "spdr": ["SPY", "GLD", "XLF"],
                "msci world": ["IWDA.AS", "URTH", "ACWI"],
                "s&p 500": ["SPY", "VOO", "IVV"],
                "nasdaq": ["QQQ", "TQQQ"],
            }

            query_lower = query.lower()
            for key, tickers in common_etf_tickers.items():
                if key in query_lower:
                    for t in tickers[:3]:  # Max 3 par catégorie
                        try:
                            ticker = yf.Ticker(t)
                            info = ticker.info
                            if info and info.get('shortName'):
                                results.append(SearchResultItem(
                                    symbol=t,
                                    name=info.get('shortName', t),
                                    exchange=info.get('exchange'),
                                    asset_type=info.get('quoteType', 'ETF'),
                                ))
                        except Exception:
                            pass
                    break

        # Filtrer par type d'actif si demandé
        if asset_type != "all" and results:
            type_mapping = {
                "stocks": ["EQUITY"],
                "etfs": ["ETF"],
                "crypto": ["CRYPTOCURRENCY"],
            }
            allowed_types = type_mapping.get(asset_type, [])
            if allowed_types:
                results = [r for r in results if r.asset_type in allowed_types]

        return SearchResponse(
            query=query,
            results=results[:10],  # Max 10 résultats
            count=len(results[:10]),
        )

    except Exception as e:
        logger.error(f"Search error for '{query}': {e}")
        return SearchResponse(query=query, results=[], count=0)


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


# =============================================================================
# TECHNICAL ANALYSIS
# =============================================================================

class TechnicalAnalysisResponse(BaseModel):
    """Reponse analyse technique."""
    ticker: str
    trend: str  # bullish, bearish, neutral
    rsi: float
    macd: dict
    moving_averages: dict
    support_resistance: dict
    volume_trend: str


@router.get(
    "/technical/{ticker}",
    response_model=TechnicalAnalysisResponse,
)
async def get_technical_analysis(ticker: str):
    """
    Retourne l'analyse technique d'un ticker.

    Indicateurs:
    - RSI (14 periodes)
    - MACD (12, 26, 9)
    - Moyennes mobiles (SMA 20, 50, 200)
    - Support/Resistance
    """
    import yfinance as yf
    import numpy as np

    try:
        symbol = ticker.upper()
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")

        if hist.empty:
            raise HTTPException(status_code=404, detail=f"Ticker {symbol} non trouve")

        close = hist['Close']

        # RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        # Moyennes mobiles
        sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
        sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None
        sma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else close.mean()

        current_price = close.iloc[-1]

        # Tendance
        if current_price > (sma_50 or current_price) and rsi > 50:
            trend = "bullish"
        elif current_price < (sma_50 or current_price) and rsi < 50:
            trend = "bearish"
        else:
            trend = "neutral"

        # Support/Resistance simples (min/max recents)
        recent = close.tail(30)
        support = float(recent.min())
        resistance = float(recent.max())

        # Volume trend
        vol = hist['Volume'].tail(10)
        vol_avg = hist['Volume'].tail(50).mean()
        if vol.mean() > vol_avg * 1.3:
            volume_trend = "high"
        elif vol.mean() < vol_avg * 0.7:
            volume_trend = "low"
        else:
            volume_trend = "normal"

        return TechnicalAnalysisResponse(
            ticker=symbol,
            trend=trend,
            rsi=round(float(rsi), 1) if not np.isnan(rsi) else 50,
            macd={
                "value": round(float(macd_line.iloc[-1]), 3),
                "signal": round(float(signal_line.iloc[-1]), 3),
                "histogram": round(float(histogram.iloc[-1]), 3)
            },
            moving_averages={
                "sma_20": round(float(sma_20), 2) if sma_20 else None,
                "sma_50": round(float(sma_50), 2) if sma_50 else None,
                "sma_200": round(float(sma_200), 2) if sma_200 else None
            },
            support_resistance={
                "support": round(support, 2),
                "resistance": round(resistance, 2)
            },
            volume_trend=volume_trend
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Technical analysis error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DECISION HELPER
# =============================================================================

class DecisionFactorResponse(BaseModel):
    """Facteur de decision."""
    name: str
    score: int
    description: Optional[str] = None


class DecisionResponse(BaseModel):
    """Reponse aide a la decision."""
    ticker: str
    decision: str  # strong_buy, buy, hold, monitor, review, sell
    confidence: int
    factors: List[DecisionFactorResponse]
    summary: str


@router.get(
    "/decision/{ticker}",
    response_model=DecisionResponse,
)
async def get_decision_help(ticker: str):
    """
    Fournit une aide a la decision pour un ticker.

    Analyse multi-facteurs:
    - Tendance technique
    - Momentum (RSI, MACD)
    - Volatilite
    - Performance recente
    """
    import yfinance as yf
    import numpy as np

    try:
        symbol = ticker.upper()
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1y")

        if hist.empty:
            raise HTTPException(status_code=404, detail=f"Ticker {symbol} non trouve")

        close = hist['Close']
        current_price = close.iloc[-1]

        # Calculs
        perf_1m = ((close.iloc[-1] / close.iloc[-22]) - 1) * 100 if len(close) > 22 else 0
        perf_3m = ((close.iloc[-1] / close.iloc[-66]) - 1) * 100 if len(close) > 66 else 0

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        if np.isnan(rsi):
            rsi = 50

        # Volatilite
        returns = close.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100

        # SMA trend
        sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else current_price
        trend_score = 70 if current_price > sma_50 else 30

        # Scoring
        factors = []

        # 1. Tendance
        if current_price > sma_50 * 1.05:
            factors.append(DecisionFactorResponse(name="Tendance", score=80, description="Au-dessus SMA50"))
        elif current_price > sma_50:
            factors.append(DecisionFactorResponse(name="Tendance", score=60, description="Legerement haussier"))
        elif current_price > sma_50 * 0.95:
            factors.append(DecisionFactorResponse(name="Tendance", score=40, description="Legerement baissier"))
        else:
            factors.append(DecisionFactorResponse(name="Tendance", score=20, description="Sous SMA50"))

        # 2. Momentum RSI
        if rsi > 70:
            factors.append(DecisionFactorResponse(name="RSI", score=30, description="Surachete"))
        elif rsi > 50:
            factors.append(DecisionFactorResponse(name="RSI", score=65, description="Momentum positif"))
        elif rsi > 30:
            factors.append(DecisionFactorResponse(name="RSI", score=45, description="Momentum faible"))
        else:
            factors.append(DecisionFactorResponse(name="RSI", score=70, description="Survendu - potentiel rebond"))

        # 3. Performance
        perf_score = max(20, min(80, 50 + perf_1m))
        factors.append(DecisionFactorResponse(
            name="Performance 1M",
            score=int(perf_score),
            description=f"{perf_1m:+.1f}%"
        ))

        # 4. Volatilite
        if volatility > 40:
            factors.append(DecisionFactorResponse(name="Volatilite", score=30, description="Tres volatile"))
        elif volatility > 25:
            factors.append(DecisionFactorResponse(name="Volatilite", score=50, description="Volatile"))
        else:
            factors.append(DecisionFactorResponse(name="Volatilite", score=70, description="Stable"))

        # Score global
        avg_score = sum(f.score for f in factors) / len(factors)

        # Decision
        if avg_score >= 70:
            decision = "strong_buy"
            summary = "Tous les indicateurs sont favorables. Opportunite d'achat."
        elif avg_score >= 60:
            decision = "buy"
            summary = "Indicateurs majoritairement positifs. Achat envisageable."
        elif avg_score >= 50:
            decision = "hold"
            summary = "Situation neutre. Maintenir la position si deja investi."
        elif avg_score >= 40:
            decision = "monitor"
            summary = "Signaux mixtes. A surveiller de pres."
        elif avg_score >= 30:
            decision = "review"
            summary = "Indicateurs defavorables. Reevaluer la position."
        else:
            decision = "sell"
            summary = "Signaux negatifs multiples. Considerer une sortie."

        confidence = min(95, max(40, int(avg_score + abs(avg_score - 50) * 0.5)))

        return DecisionResponse(
            ticker=symbol,
            decision=decision,
            confidence=confidence,
            factors=factors,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Decision analysis error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# OHLC DATA FOR TRADINGVIEW
# =============================================================================

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
