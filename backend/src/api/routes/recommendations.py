"""
Routes API pour les recommandations d'investissement.

Endpoints:
- GET /api/recommendations/{ticker} - Recommandation complete pour un ticker
- POST /api/recommendations/screen - Screener d'opportunites
- GET /api/recommendations/technical/{ticker} - Analyse technique detaillee
- POST /api/recommendations/portfolio - Conseils de portefeuille
- POST /api/recommendations/compare - Comparaison d'actifs
- GET /api/recommendations/etfs/{category} - Meilleurs ETFs par categorie
- GET /api/recommendations/chart/{ticker} - Graphique interactif (HTML)

ARCHITECTURE:
- Utilise le moteur de recommandation RecommendationEngine
- Calculs d'indicateurs avec TechnicalCalculator
- Graphiques avec ChartGenerator
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
from src.application.services.technical_calculator import TechnicalCalculator
from src.application.services.recommendation_engine import RecommendationEngine
from src.application.services.chart_generator import ChartGenerator
from src.domain.value_objects.ticker import Ticker
from src.config.constants import PERIOD_5_YEARS_DAYS

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# =============================================================================
# SCHEMAS
# =============================================================================

class ScoreBreakdownResponse(BaseModel):
    """Decomposition du score."""
    performance_score: float
    technical_score: float
    momentum_score: float
    volatility_score: float
    fundamental_score: float
    timing_score: float
    total_score: float
    strengths: List[str]
    weaknesses: List[str]


class PriceTargetResponse(BaseModel):
    """Objectif de prix."""
    target_price: float
    current_price: float
    potential_return: float
    stop_loss: float
    risk_reward_ratio: float
    horizon: str
    upside_percent: float
    downside_percent: float


class RecommendationResponse(BaseModel):
    """Recommandation complete."""
    ticker: str
    name: str
    asset_type: str
    sector: Optional[str]
    score_breakdown: ScoreBreakdownResponse
    overall_score: float
    recommendation: str
    action_summary: str
    category: str
    risk_level: str
    confidence: float
    short_term_outlook: str
    medium_term_outlook: str
    long_term_outlook: str
    price_targets: Dict[str, PriceTargetResponse]
    key_insights: List[str]
    risks: List[str]
    catalysts: List[str]
    technical_summary: str
    entry_strategy: str
    generated_at: str


class ScreenRequest(BaseModel):
    """Requete de screening."""
    tickers: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Liste des tickers a analyser",
    )
    min_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Score minimum pour inclusion",
    )


class ScreenResultItem(BaseModel):
    """Resultat de screening pour un ticker."""
    ticker: str
    name: str
    score: float
    recommendation: str
    category: str
    risk: str
    short_outlook: str


class ScreenResponse(BaseModel):
    """Reponse de screening."""
    total_analyzed: int
    opportunities_found: int
    to_avoid: int
    market_bias: str
    top_picks: List[ScreenResultItem]
    strong_buy_count: int
    strong_sell_count: int


class TechnicalIndicatorResponse(BaseModel):
    """Indicateur technique."""
    value: Any
    signal: str
    interpretation: str


class TechnicalAnalysisResponse(BaseModel):
    """Analyse technique complete."""
    ticker: str
    rsi: TechnicalIndicatorResponse
    macd: Dict[str, Any]
    bollinger: Dict[str, Any]
    moving_averages: Dict[str, Any]
    volume: Dict[str, Any]
    atr: float
    atr_percent: float
    overall_signal: str
    overall_trend: str
    confidence_level: str
    key_levels: Dict[str, Any]


class PortfolioRequest(BaseModel):
    """Requete de conseils portefeuille."""
    tickers: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Liste des actifs a considerer",
    )


class PortfolioAdviceResponse(BaseModel):
    """Conseils de portefeuille."""
    suggested_allocation: Dict[str, float]
    market_sentiment: str
    market_trend: str
    avoid_list: List[str]
    top_growth: List[ScreenResultItem]
    top_momentum: List[ScreenResultItem]
    top_dividend: List[ScreenResultItem]
    top_defensive: List[ScreenResultItem]
    action_plan: List[str]


class CompareRequest(BaseModel):
    """Requete de comparaison."""
    tickers: List[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Liste des tickers a comparer",
    )


class CompareItemResponse(BaseModel):
    """Element de comparaison."""
    ticker: str
    name: str
    score_global: float
    scores: Dict[str, float]
    recommendation: str
    risk: str
    strengths: List[str]
    weaknesses: List[str]


class CompareResponse(BaseModel):
    """Reponse de comparaison."""
    comparison: List[CompareItemResponse]
    ranking: List[str]
    best_choice: Optional[str]
    verdict: str


class ETFResultItem(BaseModel):
    """Resultat ETF."""
    ticker: str
    name: str
    score: float
    recommendation: str
    category: str
    risk: str
    entry_strategy: str


class ETFResponse(BaseModel):
    """Reponse ETFs."""
    category_searched: str
    total_analyzed: int
    etfs_ranked: List[ETFResultItem]
    top_pick: Optional[ETFResultItem]
    allocation_tip: str


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_services():
    """Cree les services necessaires."""
    provider = YahooFinanceProvider()
    calculator = TechnicalCalculator()
    engine = RecommendationEngine(provider, calculator)
    chart_gen = ChartGenerator(theme="dark")
    return provider, calculator, engine, chart_gen


# =============================================================================
# ROUTES
# =============================================================================

@router.get(
    "/{ticker}",
    response_model=RecommendationResponse,
    summary="Obtenir une recommandation complete",
)
async def get_recommendation(
    ticker: str = Path(..., description="Symbole du ticker"),
):
    """
    Genere une recommandation d'investissement complete.

    Inclut:
    - Scoring multi-facteurs (performance, technique, momentum, etc.)
    - Analyse de tendance et momentum
    - Objectifs de prix par horizon (court, moyen, long terme)
    - Strategie d'entree recommandee
    - Niveau de risque et confiance
    """
    provider, calculator, engine, _ = get_services()

    recommendation = await engine.analyze_and_recommend(ticker.upper())

    if not recommendation:
        raise HTTPException(
            status_code=404,
            detail=f"Impossible d'analyser {ticker}. Verifiez que le ticker est valide."
        )

    # Convertir les price targets
    price_targets = {}
    for horizon, target in recommendation.price_targets.items():
        price_targets[horizon] = PriceTargetResponse(
            target_price=target.target_price,
            current_price=target.current_price,
            potential_return=target.potential_return,
            stop_loss=target.stop_loss,
            risk_reward_ratio=target.risk_reward_ratio,
            horizon=target.horizon.value,
            upside_percent=target.upside_percent,
            downside_percent=target.downside_percent,
        )

    return RecommendationResponse(
        ticker=recommendation.ticker,
        name=recommendation.name,
        asset_type=recommendation.asset_type,
        sector=recommendation.sector,
        score_breakdown=ScoreBreakdownResponse(
            performance_score=recommendation.score_breakdown.performance_score,
            technical_score=recommendation.score_breakdown.technical_score,
            momentum_score=recommendation.score_breakdown.momentum_score,
            volatility_score=recommendation.score_breakdown.volatility_score,
            fundamental_score=recommendation.score_breakdown.fundamental_score,
            timing_score=recommendation.score_breakdown.timing_score,
            total_score=recommendation.score_breakdown.total_score,
            strengths=recommendation.score_breakdown.strengths,
            weaknesses=recommendation.score_breakdown.weaknesses,
        ),
        overall_score=recommendation.overall_score,
        recommendation=recommendation.recommendation.value,
        action_summary=recommendation.action_summary,
        category=recommendation.category.value,
        risk_level=recommendation.risk_level.value,
        confidence=recommendation.confidence,
        short_term_outlook=recommendation.short_term_outlook,
        medium_term_outlook=recommendation.medium_term_outlook,
        long_term_outlook=recommendation.long_term_outlook,
        price_targets=price_targets,
        key_insights=recommendation.key_insights,
        risks=recommendation.risks,
        catalysts=recommendation.catalysts,
        technical_summary=recommendation.technical_summary,
        entry_strategy=recommendation.entry_strategy,
        generated_at=recommendation.generated_at.isoformat(),
    )


@router.post(
    "/screen",
    response_model=ScreenResponse,
    summary="Screener d'opportunites",
)
async def screen_opportunities(request: ScreenRequest):
    """
    Screene une liste d'actifs pour trouver les meilleures opportunites.

    Retourne les actifs classes par score avec leurs recommandations.
    """
    provider, calculator, engine, _ = get_services()

    results = await engine.screen_market(request.tickers, min_score=request.min_score)

    top_picks = [
        ScreenResultItem(
            ticker=r.ticker,
            name=r.name,
            score=round(r.overall_score, 1),
            recommendation=r.recommendation.value,
            category=r.category.value,
            risk=r.risk_level.value,
            short_outlook=r.short_term_outlook,
        )
        for r in results.best_overall[:20]
    ]

    return ScreenResponse(
        total_analyzed=results.total_analyzed,
        opportunities_found=results.buy_count,
        to_avoid=results.sell_count,
        market_bias="haussier" if results.buy_count > results.sell_count else "baissier" if results.sell_count > results.buy_count else "neutre",
        top_picks=top_picks,
        strong_buy_count=len(results.strong_buy_signals),
        strong_sell_count=len(results.strong_sell_signals),
    )


@router.get(
    "/technical/{ticker}",
    response_model=TechnicalAnalysisResponse,
    summary="Analyse technique detaillee",
)
async def get_technical_analysis(
    ticker: str = Path(..., description="Symbole du ticker"),
):
    """
    Fournit une analyse technique complete avec tous les indicateurs:
    RSI, MACD, Bollinger Bands, Moyennes Mobiles, Volume, ATR.
    """
    provider, calculator, _, _ = get_services()

    ticker_obj = Ticker(ticker.upper())
    historical_data = await provider.get_historical_data(ticker_obj, PERIOD_5_YEARS_DAYS)

    if len(historical_data) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Donnees insuffisantes pour {ticker}: {len(historical_data)} points (min 50)"
        )

    indicators = await calculator.calculate_all(ticker.upper(), historical_data)

    if not indicators:
        raise HTTPException(
            status_code=500,
            detail=f"Impossible de calculer les indicateurs pour {ticker}"
        )

    return TechnicalAnalysisResponse(
        ticker=indicators.ticker,
        rsi=TechnicalIndicatorResponse(
            value=indicators.rsi.value,
            signal=indicators.rsi.signal.value,
            interpretation=indicators.rsi.interpretation,
        ),
        macd=indicators.macd.to_dict(),
        bollinger=indicators.bollinger.to_dict(),
        moving_averages=indicators.moving_averages.to_dict(),
        volume=indicators.volume.to_dict(),
        atr=indicators.atr,
        atr_percent=indicators.atr_percent,
        overall_signal=indicators.overall_signal.value,
        overall_trend=indicators.overall_trend.value,
        confidence_level=indicators.confidence_level,
        key_levels={
            "supports": indicators.moving_averages.support_levels,
            "resistances": indicators.moving_averages.resistance_levels,
            "bollinger_upper": indicators.bollinger.upper_band,
            "bollinger_lower": indicators.bollinger.lower_band,
        },
    )


@router.post(
    "/portfolio",
    response_model=PortfolioAdviceResponse,
    summary="Conseils de portefeuille",
)
async def get_portfolio_advice(request: PortfolioRequest):
    """
    Genere des conseils pour construire un portefeuille optimal.

    Categorise les actifs, suggere une allocation, et identifie les opportunites.
    """
    provider, calculator, engine, _ = get_services()

    portfolio_rec = await engine.get_portfolio_recommendations(request.tickers)

    def to_screen_item(rec) -> ScreenResultItem:
        return ScreenResultItem(
            ticker=rec.ticker,
            name=rec.name,
            score=round(rec.overall_score, 1),
            recommendation=rec.recommendation.value,
            category=rec.category.value,
            risk=rec.risk_level.value,
            short_outlook=rec.short_term_outlook,
        )

    # Generer le plan d'action
    action_plan = []
    if portfolio_rec.top_momentum:
        top = portfolio_rec.top_momentum[0]
        action_plan.append(f"ACHETER {top.ticker} - Fort momentum, score {top.overall_score:.0f}/100")
    if portfolio_rec.top_growth:
        top = portfolio_rec.top_growth[0]
        action_plan.append(f"CROISSANCE: {top.ticker} - Score {top.overall_score:.0f}/100")
    if portfolio_rec.top_dividend:
        top = portfolio_rec.top_dividend[0]
        action_plan.append(f"REVENU: {top.ticker} - Dividende stable")
    for ticker in portfolio_rec.avoid_list[:3]:
        action_plan.append(f"EVITER {ticker}")
    action_plan.append(f"SENTIMENT: {portfolio_rec.market_sentiment}")

    return PortfolioAdviceResponse(
        suggested_allocation=portfolio_rec.suggested_allocation,
        market_sentiment=portfolio_rec.market_sentiment,
        market_trend=portfolio_rec.market_trend.value,
        avoid_list=portfolio_rec.avoid_list,
        top_growth=[to_screen_item(r) for r in portfolio_rec.top_growth[:5]],
        top_momentum=[to_screen_item(r) for r in portfolio_rec.top_momentum[:5]],
        top_dividend=[to_screen_item(r) for r in portfolio_rec.top_dividend[:5]],
        top_defensive=[to_screen_item(r) for r in portfolio_rec.top_defensive[:5]],
        action_plan=action_plan,
    )


@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Comparer des actifs",
)
async def compare_assets(request: CompareRequest):
    """
    Compare plusieurs actifs cote a cote avec scoring detaille.
    """
    provider, calculator, engine, _ = get_services()

    comparisons = []
    for ticker in request.tickers:
        rec = await engine.analyze_and_recommend(ticker.upper())
        if rec:
            comparisons.append(CompareItemResponse(
                ticker=rec.ticker,
                name=rec.name,
                score_global=round(rec.overall_score, 1),
                scores={
                    "performance": round(rec.score_breakdown.performance_score, 1),
                    "technique": round(rec.score_breakdown.technical_score, 1),
                    "momentum": round(rec.score_breakdown.momentum_score, 1),
                    "volatilite": round(rec.score_breakdown.volatility_score, 1),
                    "fondamentaux": round(rec.score_breakdown.fundamental_score, 1),
                    "timing": round(rec.score_breakdown.timing_score, 1),
                },
                recommendation=rec.recommendation.value,
                risk=rec.risk_level.value,
                strengths=rec.score_breakdown.strengths,
                weaknesses=rec.score_breakdown.weaknesses,
            ))

    # Trier par score
    comparisons.sort(key=lambda x: x.score_global, reverse=True)
    ranking = [c.ticker for c in comparisons]
    best = comparisons[0] if comparisons else None

    verdict = ""
    if best:
        verdict = f"{best.ticker} est le meilleur choix avec un score de {best.score_global}/100"

    return CompareResponse(
        comparison=comparisons,
        ranking=ranking,
        best_choice=best.ticker if best else None,
        verdict=verdict,
    )


@router.get(
    "/etfs/{category}",
    response_model=ETFResponse,
    summary="Meilleurs ETFs par categorie",
)
async def find_best_etfs(
    category: str = Path(
        ...,
        description="Categorie: tech, world, dividend, emerging, bond, sp500, europe, crypto, gold, realestate, all",
    ),
):
    """
    Trouve et analyse les meilleurs ETFs par categorie.
    """
    # ETFs populaires par categorie
    etf_categories = {
        "tech": ["QQQ", "XLK", "VGT", "ARKK", "SMH"],
        "world": ["VT", "ACWI", "VTI", "SPTM", "ITOT"],
        "dividend": ["VYM", "SCHD", "DVY", "HDV", "SPYD"],
        "emerging": ["VWO", "EEM", "IEMG", "SCHE", "DEM"],
        "bond": ["BND", "AGG", "TLT", "LQD", "HYG"],
        "sp500": ["SPY", "VOO", "IVV", "SPLG", "RSP"],
        "europe": ["VGK", "EZU", "FEZ", "IEUR", "HEDJ"],
        "crypto": ["BITO", "GBTC"],
        "gold": ["GLD", "IAU", "SGOL", "GLDM"],
        "realestate": ["VNQ", "SCHH", "IYR", "XLRE", "RWR"],
    }

    if category == "all":
        tickers = []
        for cat_tickers in etf_categories.values():
            tickers.extend(cat_tickers[:2])
    else:
        tickers = etf_categories.get(category.lower(), etf_categories["world"])

    provider, calculator, engine, _ = get_services()

    results = await engine.screen_market(tickers, min_score=0)

    etf_results = [
        ETFResultItem(
            ticker=r.ticker,
            name=r.name,
            score=round(r.overall_score, 1),
            recommendation=r.recommendation.value,
            category=r.category.value,
            risk=r.risk_level.value,
            entry_strategy=r.entry_strategy,
        )
        for r in results.best_overall
    ]

    allocation_tips = {
        "tech": "ETFs tech: forte croissance mais volatilite elevee. Limiter a 20-30%.",
        "world": "ETFs monde: ideal comme base de portefeuille. 40-60% du total.",
        "dividend": "ETFs dividendes: revenu passif. 15-25% recommande.",
        "emerging": "Emergents: volatils mais diversification. 10-15%.",
        "bond": "Obligataires: stabilisent le portefeuille. 20-40% selon profil.",
        "sp500": "S&P 500: pilier classique. 30-50% des actions.",
        "europe": "Europe: diversification geographique. 15-25%.",
        "crypto": "Crypto: tres speculatif. Maximum 5%.",
        "gold": "Or: protection inflation. 5-10%.",
        "realestate": "Immobilier: revenus et diversification. 10-15%.",
        "all": "Diversifiez selon votre horizon et profil de risque.",
    }

    return ETFResponse(
        category_searched=category,
        total_analyzed=len(tickers),
        etfs_ranked=etf_results,
        top_pick=etf_results[0] if etf_results else None,
        allocation_tip=allocation_tips.get(category.lower(), allocation_tips["all"]),
    )


@router.get(
    "/chart/{ticker}",
    response_class=HTMLResponse,
    summary="Graphique interactif",
)
async def get_chart(
    ticker: str = Path(..., description="Symbole du ticker"),
    show_bollinger: bool = Query(True, description="Afficher Bollinger Bands"),
    show_mas: bool = Query(True, description="Afficher moyennes mobiles"),
    show_volume: bool = Query(True, description="Afficher volume"),
):
    """
    Retourne un graphique technique interactif en HTML.

    Inclut chandeliers, indicateurs, et annotations.
    """
    provider, calculator, _, chart_gen = get_services()

    ticker_obj = Ticker(ticker.upper())
    historical_data = await provider.get_historical_data(ticker_obj, PERIOD_5_YEARS_DAYS)

    if len(historical_data) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Donnees insuffisantes pour {ticker}"
        )

    indicators = await calculator.calculate_all(ticker.upper(), historical_data)

    if not indicators:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur de calcul pour {ticker}"
        )

    fig = chart_gen.create_technical_chart(
        ticker=ticker.upper(),
        data=historical_data,
        indicators=indicators,
        show_bollinger=show_bollinger,
        show_mas=show_mas,
        show_volume=show_volume,
    )

    return HTMLResponse(content=fig.to_html(full_html=True, include_plotlyjs=True))


@router.get(
    "/chart/radar/{ticker}",
    response_class=HTMLResponse,
    summary="Graphique radar du scoring",
)
async def get_radar_chart(
    ticker: str = Path(..., description="Symbole du ticker"),
):
    """
    Retourne un graphique radar du scoring multi-facteurs.
    """
    provider, calculator, engine, chart_gen = get_services()

    recommendation = await engine.analyze_and_recommend(ticker.upper())

    if not recommendation:
        raise HTTPException(
            status_code=404,
            detail=f"Impossible d'analyser {ticker}"
        )

    fig = chart_gen.create_score_radar(recommendation)

    return HTMLResponse(content=fig.to_html(full_html=True, include_plotlyjs=True))
