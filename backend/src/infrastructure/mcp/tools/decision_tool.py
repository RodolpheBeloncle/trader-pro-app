"""
Outil MCP pour l'aide a la decision d'investissement.

Fournit des recommandations professionnelles basees sur:
- Analyse technique avancee (RSI, MACD, Bollinger, MAs)
- Scoring multi-facteurs
- Detection de tendances et momentum
- Calcul d'objectifs de prix

OUTILS:
    - get_recommendation: Recommandation complete pour un ticker
    - screen_opportunities: Screener pour trouver les meilleures opportunites
    - get_technical_analysis: Analyse technique detaillee
    - get_portfolio_advice: Conseils pour construire un portefeuille
"""

import json
import logging
from typing import List

from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
from src.application.services.technical_calculator import TechnicalCalculator
from src.application.services.recommendation_engine import RecommendationEngine
from src.domain.value_objects.ticker import Ticker
from src.config.constants import PERIOD_5_YEARS_DAYS

logger = logging.getLogger(__name__)


async def get_recommendation_tool(ticker: str) -> str:
    """
    Genere une recommandation d'investissement complete pour un ticker.

    Args:
        ticker: Symbole boursier (ex: AAPL, MSFT)

    Returns:
        JSON avec la recommandation detaillee
    """
    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()
        engine = RecommendationEngine(provider, calculator)

        recommendation = await engine.analyze_and_recommend(ticker)

        if not recommendation:
            return json.dumps({
                "error": f"Impossible d'analyser {ticker}",
                "suggestion": "Verifiez que le ticker est valide"
            }, indent=2, ensure_ascii=False)

        result = recommendation.to_dict()

        # Ajouter un resume executif
        result["executive_summary"] = _generate_executive_summary(recommendation)

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error getting recommendation for {ticker}: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def screen_opportunities_tool(
    tickers: List[str],
    min_score: int = 50,
) -> str:
    """
    Screene une liste d'actifs pour trouver les meilleures opportunites.

    Args:
        tickers: Liste de symboles a analyser
        min_score: Score minimum pour inclusion (0-100)

    Returns:
        JSON avec les meilleures opportunites classees
    """
    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()
        engine = RecommendationEngine(provider, calculator)

        results = await engine.screen_market(tickers, min_score=min_score)

        output = results.to_dict()

        # Ajouter un resume
        output["summary"] = {
            "total_analyzed": results.total_analyzed,
            "opportunities_found": results.buy_count,
            "to_avoid": results.sell_count,
            "market_bias": "haussier" if results.buy_count > results.sell_count else "baissier" if results.sell_count > results.buy_count else "neutre",
        }

        # Simplifier pour la lisibilite
        output["top_picks"] = [
            {
                "ticker": r.ticker,
                "name": r.name,
                "score": round(r.overall_score, 1),
                "recommendation": r.recommendation.value,
                "category": r.category.value,
                "risk": r.risk_level.value,
                "short_outlook": r.short_term_outlook,
            }
            for r in results.best_overall[:10]
        ]

        return json.dumps(output, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error screening opportunities: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def get_technical_analysis_tool(ticker: str) -> str:
    """
    Fournit une analyse technique detaillee pour un ticker.

    Args:
        ticker: Symbole boursier

    Returns:
        JSON avec tous les indicateurs techniques
    """
    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()

        ticker_obj = Ticker(ticker)
        historical_data = await provider.get_historical_data(ticker_obj, PERIOD_5_YEARS_DAYS)

        if len(historical_data) < 50:
            return json.dumps({
                "error": f"Donnees insuffisantes pour {ticker}",
                "data_points": len(historical_data),
                "minimum_required": 50,
            }, indent=2)

        indicators = await calculator.calculate_all(ticker, historical_data)

        if not indicators:
            return json.dumps({
                "error": f"Impossible de calculer les indicateurs pour {ticker}"
            }, indent=2)

        result = indicators.to_dict()

        # Ajouter un resume lisible
        result["readable_summary"] = {
            "signal_global": indicators.overall_signal.value.upper(),
            "tendance": indicators.overall_trend.value,
            "confiance": indicators.confidence_level,
            "rsi_interpretation": indicators.rsi.interpretation,
            "macd_interpretation": indicators.macd.interpretation,
            "bollinger_interpretation": indicators.bollinger.interpretation,
            "ma_interpretation": indicators.moving_averages.interpretation,
            "volume_interpretation": indicators.volume.interpretation,
        }

        # Niveaux cles
        result["key_levels"] = {
            "supports": indicators.moving_averages.support_levels,
            "resistances": indicators.moving_averages.resistance_levels,
            "bollinger_upper": round(indicators.bollinger.upper_band, 2),
            "bollinger_lower": round(indicators.bollinger.lower_band, 2),
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error getting technical analysis for {ticker}: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def get_portfolio_advice_tool(tickers: List[str]) -> str:
    """
    Genere des conseils pour construire un portefeuille optimal.

    Args:
        tickers: Liste d'actifs a considerer

    Returns:
        JSON avec les recommandations de portefeuille
    """
    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()
        engine = RecommendationEngine(provider, calculator)

        portfolio_rec = await engine.get_portfolio_recommendations(tickers)

        result = portfolio_rec.to_dict()

        # Ajouter des conseils synthetiques
        result["action_plan"] = _generate_action_plan(portfolio_rec)

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error getting portfolio advice: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def find_best_etfs_tool(category: str = "all") -> str:
    """
    Trouve les meilleurs ETFs par categorie.

    Args:
        category: Categorie d'ETF (tech, world, dividend, emerging, bond, all)

    Returns:
        JSON avec les meilleurs ETFs et leurs analyses
    """
    # ETFs populaires par categorie
    etf_categories = {
        "tech": ["QQQ", "XLK", "VGT", "ARKK", "SMH"],
        "world": ["VT", "ACWI", "IWDA.AS", "VWCE.DE", "VTI"],
        "dividend": ["VYM", "SCHD", "DVY", "HDV", "SPYD"],
        "emerging": ["VWO", "EEM", "IEMG", "SCHE", "DEM"],
        "bond": ["BND", "AGG", "TLT", "LQD", "HYG"],
        "sp500": ["SPY", "VOO", "IVV", "SPLG", "RSP"],
        "europe": ["VGK", "EZU", "FEZ", "IEUR", "HEDJ"],
        "crypto": ["BITO", "GBTC", "ETHE"],
        "gold": ["GLD", "IAU", "SGOL", "GLDM"],
        "realestate": ["VNQ", "SCHH", "IYR", "XLRE", "RWR"],
    }

    if category == "all":
        # Combiner les top 3 de chaque categorie
        tickers = []
        for cat_tickers in etf_categories.values():
            tickers.extend(cat_tickers[:3])
    else:
        tickers = etf_categories.get(category, etf_categories["world"])

    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()
        engine = RecommendationEngine(provider, calculator)

        results = await engine.screen_market(tickers, min_score=0)

        # Formater les resultats
        etf_results = []
        for rec in results.best_overall:
            etf_results.append({
                "ticker": rec.ticker,
                "name": rec.name,
                "score": round(rec.overall_score, 1),
                "recommendation": rec.recommendation.value,
                "category": rec.category.value,
                "risk": rec.risk_level.value,
                "short_term": rec.short_term_outlook,
                "medium_term": rec.medium_term_outlook,
                "long_term": rec.long_term_outlook,
                "strengths": rec.score_breakdown.strengths,
                "entry_strategy": rec.entry_strategy,
            })

        output = {
            "category_searched": category,
            "total_analyzed": len(tickers),
            "etfs_ranked": etf_results,
            "top_pick": etf_results[0] if etf_results else None,
            "allocation_tip": _get_allocation_tip(category),
        }

        return json.dumps(output, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error finding best ETFs: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def compare_assets_tool(tickers: List[str]) -> str:
    """
    Compare plusieurs actifs cote a cote.

    Args:
        tickers: Liste de symboles a comparer (max 10)

    Returns:
        JSON avec la comparaison detaillee
    """
    tickers = tickers[:10]  # Limiter a 10

    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()
        engine = RecommendationEngine(provider, calculator)

        comparisons = []
        for ticker in tickers:
            rec = await engine.analyze_and_recommend(ticker)
            if rec:
                comparisons.append({
                    "ticker": rec.ticker,
                    "name": rec.name,
                    "score_global": round(rec.overall_score, 1),
                    "scores": {
                        "performance": round(rec.score_breakdown.performance_score, 1),
                        "technique": round(rec.score_breakdown.technical_score, 1),
                        "momentum": round(rec.score_breakdown.momentum_score, 1),
                        "volatilite": round(rec.score_breakdown.volatility_score, 1),
                        "fondamentaux": round(rec.score_breakdown.fundamental_score, 1),
                        "timing": round(rec.score_breakdown.timing_score, 1),
                    },
                    "recommendation": rec.recommendation.value,
                    "risk": rec.risk_level.value,
                    "strengths": rec.score_breakdown.strengths,
                    "weaknesses": rec.score_breakdown.weaknesses,
                })

        # Trier par score
        comparisons.sort(key=lambda x: x["score_global"], reverse=True)

        # Determiner le meilleur choix
        best = comparisons[0] if comparisons else None
        verdict = ""
        if best:
            verdict = f"{best['ticker']} est le meilleur choix avec un score de {best['score_global']}/100"

        output = {
            "comparison": comparisons,
            "ranking": [c["ticker"] for c in comparisons],
            "best_choice": best["ticker"] if best else None,
            "verdict": verdict,
        }

        return json.dumps(output, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error comparing assets: {e}")
        return json.dumps({"error": str(e)}, indent=2)


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def _generate_executive_summary(recommendation) -> str:
    """Genere un resume executif de la recommandation."""
    rec = recommendation.recommendation.value.upper().replace("_", " ")
    score = round(recommendation.overall_score, 1)
    risk = recommendation.risk_level.value.upper().replace("_", " ")
    conf = round(recommendation.confidence, 0)

    summary = f"""
=== RESUME EXECUTIF ===
Ticker: {recommendation.ticker} ({recommendation.name})
Recommandation: {rec}
Score Global: {score}/100
Niveau de Risque: {risk}
Confiance: {conf}%

Verdict: {recommendation.action_summary}

Points Forts:
{chr(10).join('  - ' + s for s in recommendation.score_breakdown.strengths)}

Risques Identifies:
{chr(10).join('  - ' + r for r in recommendation.risks)}

Objectifs de Prix:
  - Court terme: {recommendation.price_targets['short_term'].target_price:.2f} ({recommendation.price_targets['short_term'].potential_return:+.1f}%)
  - Moyen terme: {recommendation.price_targets['medium_term'].target_price:.2f} ({recommendation.price_targets['medium_term'].potential_return:+.1f}%)
  - Long terme: {recommendation.price_targets['long_term'].target_price:.2f} ({recommendation.price_targets['long_term'].potential_return:+.1f}%)

Strategie d'Entree: {recommendation.entry_strategy}
"""
    return summary.strip()


def _generate_action_plan(portfolio_rec) -> List[str]:
    """Genere un plan d'action pour le portefeuille."""
    actions = []

    # Actions a acheter
    if portfolio_rec.top_momentum:
        top = portfolio_rec.top_momentum[0]
        actions.append(f"ACHETER {top.ticker} - Fort momentum, score {top.overall_score:.0f}/100")

    if portfolio_rec.top_growth:
        top = portfolio_rec.top_growth[0]
        if top.ticker not in [a.split()[1] for a in actions]:
            actions.append(f"CONSIDERER {top.ticker} - Croissance, score {top.overall_score:.0f}/100")

    if portfolio_rec.top_dividend:
        top = portfolio_rec.top_dividend[0]
        actions.append(f"REVENU: {top.ticker} - Dividende stable")

    if portfolio_rec.top_defensive:
        top = portfolio_rec.top_defensive[0]
        actions.append(f"DEFENSIF: {top.ticker} - Protection contre la volatilite")

    # Actifs a eviter
    for ticker in portfolio_rec.avoid_list[:3]:
        actions.append(f"EVITER {ticker} - Signaux negatifs")

    # Allocation
    actions.append(f"ALLOCATION SUGGEREE: {portfolio_rec.suggested_allocation}")

    # Sentiment
    actions.append(f"SENTIMENT MARCHE: {portfolio_rec.market_sentiment}")

    return actions


def _get_allocation_tip(category: str) -> str:
    """Retourne un conseil d'allocation pour une categorie."""
    tips = {
        "tech": "Les ETFs tech offrent une forte croissance mais volatilite elevee. Limiter a 20-30% du portefeuille.",
        "world": "Les ETFs monde sont ideaux comme base de portefeuille. Peuvent representer 40-60% du total.",
        "dividend": "Les ETFs dividendes conviennent pour le revenu passif. Allocation de 15-25% recommandee.",
        "emerging": "Les emergents sont volatils mais offrent une diversification. Limiter a 10-15%.",
        "bond": "Les ETFs obligataires stabilisent le portefeuille. 20-40% selon l'age et le profil de risque.",
        "sp500": "Le S&P 500 est un pilier classique. Peut representer 30-50% d'un portefeuille actions.",
        "europe": "L'Europe offre une diversification geographique. 15-25% du portefeuille actions.",
        "crypto": "Les ETFs crypto sont tres speculatifs. Maximum 5% du portefeuille total.",
        "gold": "L'or est une protection contre l'inflation. 5-10% du portefeuille.",
        "realestate": "L'immobilier offre revenus et diversification. 10-15% recommande.",
        "all": "Un portefeuille equilibre combine plusieurs categories. Diversifiez selon votre horizon.",
    }
    return tips.get(category, tips["all"])
