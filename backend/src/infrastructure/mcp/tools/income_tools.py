"""
Outils MCP pour les portefeuilles orientés revenus (Income).

Contient les tools:
- get_market_regime: Signaux macro Risk-On/Off
- get_income_assets: Analyse des actifs income par catégorie
- get_income_recommendation: Scoring orienté revenus
- calculate_rebalancing: Calcul des ordres de rebalancement
- simulate_income_portfolio: Projection revenus passifs
- run_portfolio_backtest: Backtest multi-assets avec Risk-Off
- create_macro_alert: Alertes VIX, credit, recession
- get_dividend_calendar: Calendrier des dividendes

UTILISATION:
    result = await get_market_regime_tool()
    result = await get_income_assets_tool("covered_call")
"""

import json
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from src.infrastructure.providers.market_regime_provider import (
    get_market_regime_provider,
    MarketRegimeProvider,
)
from src.application.services.income_asset_service import (
    get_income_asset_service,
    IncomeAssetService,
)
from src.domain.entities.income_portfolio import (
    IncomeCategory,
    BacktestConfig,
    INCOME_ASSET_TICKERS,
    get_tickers_for_category,
)
from src.domain.services.portfolio_backtest_engine import (
    PortfolioBacktestEngine,
    fetch_historical_data_for_backtest,
    fetch_signal_data_for_backtest,
)
from src.application.services.alert_service import get_alert_service

logger = logging.getLogger(__name__)


# =============================================================================
# GET MARKET REGIME
# =============================================================================

async def get_market_regime_tool() -> str:
    """
    Analyse le régime de marché actuel (Risk-On/Off).

    Signaux analysés:
    - HYG/LQD ratio (stress crédit)
    - VIX (volatilité)
    - SPY trend et drawdown
    - Yield curve (10Y-2Y)

    Returns:
        JSON avec:
        - regime: "risk_on" | "risk_off" | "neutral" | "high_uncertainty"
        - signals: détail des signaux actifs
        - recommended_allocation: allocation recommandée
        - interpretation: explication textuelle
    """
    try:
        provider = get_market_regime_provider()
        regime = await provider.calculate_market_regime()

        return json.dumps(regime.to_dict(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting market regime: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# GET INCOME ASSETS
# =============================================================================

async def get_income_assets_tool(
    category: str = "all",
) -> str:
    """
    Analyse les actifs à revenus par catégorie.

    Args:
        category: "bdc" | "covered_call" | "cef" | "mreit" | "cash_like" | "all"

    Returns:
        JSON avec:
        - category: catégorie demandée
        - assets: liste des analyses
        - category_average_yield: rendement moyen
        - best_pick: meilleur actif de la catégorie
    """
    try:
        service = get_income_asset_service()

        if category.lower() == "all":
            # Toutes les catégories
            all_assets = await service.get_all_income_assets()

            result = {
                "category": "all",
                "categories": {},
                "total_assets": 0,
            }

            for cat_name, analyses in all_assets.items():
                assets_data = [a.to_dict() for a in analyses]
                avg_yield = sum(a.yield_metrics.current_yield for a in analyses) / len(analyses) if analyses else 0
                best = analyses[0] if analyses else None

                result["categories"][cat_name] = {
                    "assets": assets_data,
                    "count": len(assets_data),
                    "average_yield": round(avg_yield, 2),
                    "best_pick": best.ticker if best else None,
                }
                result["total_assets"] += len(assets_data)

            return json.dumps(result, ensure_ascii=False, indent=2)

        else:
            # Une catégorie spécifique
            try:
                cat = IncomeCategory(category.lower())
            except ValueError:
                return json.dumps({
                    "error": f"Catégorie invalide: {category}",
                    "valid_categories": [c.value for c in IncomeCategory],
                }, ensure_ascii=False)

            analyses = await service.get_category_assets(cat)

            if not analyses:
                return json.dumps({
                    "category": category,
                    "assets": [],
                    "message": "Aucun actif trouvé pour cette catégorie",
                }, ensure_ascii=False)

            assets_data = [a.to_dict() for a in analyses]
            avg_yield = sum(a.yield_metrics.current_yield for a in analyses) / len(analyses)
            best = analyses[0]

            result = {
                "category": category,
                "count": len(assets_data),
                "assets": assets_data,
                "category_average_yield": round(avg_yield, 2),
                "best_pick": {
                    "ticker": best.ticker,
                    "yield": best.yield_metrics.current_yield,
                    "score": best.overall_income_score,
                    "recommendation": best.recommendation,
                },
            }

            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting income assets: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# GET INCOME RECOMMENDATION
# =============================================================================

async def get_income_recommendation_tool(ticker: str) -> str:
    """
    Génère une recommandation orientée revenus pour un ticker.

    Scoring basé sur:
    - Dividend Yield: 25%
    - Dividend Growth (5Y): 20%
    - Payout Ratio: 15%
    - NAV Discount (CEF): 15%
    - Volatilité: 15%
    - Distribution Stability: 10%

    Args:
        ticker: Symbole du ticker

    Returns:
        JSON avec analyse complète et recommandation
    """
    try:
        if not ticker or not ticker.strip():
            return json.dumps({"error": "Ticker requis"}, ensure_ascii=False)

        ticker = ticker.upper().strip()
        service = get_income_asset_service()
        analysis = await service.analyze_income_asset(ticker)

        if not analysis:
            return json.dumps({
                "error": f"Impossible d'analyser {ticker}",
                "suggestion": "Vérifiez que le ticker est valide",
            }, ensure_ascii=False)

        result = analysis.to_dict()

        # Ajouter un résumé exécutif
        result["executive_summary"] = {
            "recommendation": analysis.recommendation,
            "yield": f"{analysis.yield_metrics.current_yield:.1f}%",
            "monthly_income_per_1000": f"${analysis.yield_metrics.monthly_income_per_1000:.2f}",
            "overall_score": analysis.overall_income_score,
            "risk_level": "Faible" if analysis.risk_score >= 70 else "Modéré" if analysis.risk_score >= 40 else "Élevé",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting income recommendation for {ticker}: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# CALCULATE REBALANCING
# =============================================================================

async def calculate_rebalancing_tool(
    current_positions: List[Dict],
    target_allocation: Dict[str, float],
    cash_available: float = 0,
    threshold_percent: float = 5.0,
) -> str:
    """
    Calcule les ordres de rebalancement.

    Args:
        current_positions: [{ticker, shares, value, avg_cost}]
        target_allocation: {ticker: weight_percent}
        cash_available: Cash disponible
        threshold_percent: Seuil de drift pour déclencher

    Returns:
        JSON avec:
        - needs_rebalancing: bool
        - drift_analysis: analyse du drift par position
        - sell_orders: ordres de vente
        - buy_orders: ordres d'achat
        - tax_loss_harvesting: opportunités fiscales
    """
    try:
        service = get_income_asset_service()
        result = await service.calculate_rebalancing(
            current_positions=current_positions,
            target_allocation=target_allocation,
            cash_available=cash_available,
            threshold_percent=threshold_percent,
        )

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error calculating rebalancing: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# SIMULATE INCOME PORTFOLIO
# =============================================================================

async def simulate_income_portfolio_tool(
    positions: List[Dict],
    monthly_contribution: float = 0,
    years: int = 10,
    reinvest_dividends: bool = True,
    withdrawal_rate: float = 0,
) -> str:
    """
    Simule l'évolution d'un portefeuille orienté revenus.

    Args:
        positions: [{ticker, shares} ou {ticker, value}]
        monthly_contribution: Contribution mensuelle
        years: Nombre d'années à simuler
        reinvest_dividends: Réinvestir les dividendes (DRIP)
        withdrawal_rate: Taux de retrait (ex: 4 pour 4%)

    Returns:
        JSON avec:
        - current_annual_income: Revenu annuel actuel
        - projected_value: Valeur projetée
        - projected_monthly_income: Revenu mensuel projeté
        - yield_on_cost: Rendement sur coût
        - yearly_projections: Projections année par année
    """
    try:
        service = get_income_asset_service()

        # Calculer les valeurs si pas fournies
        for pos in positions:
            if 'value' not in pos and 'shares' in pos:
                ticker = pos.get('ticker', '')
                analysis = await service.analyze_income_asset(ticker)
                if analysis:
                    pos['value'] = pos['shares'] * analysis.current_price

        result = await service.simulate_income_portfolio(
            positions=positions,
            monthly_contribution=monthly_contribution,
            years=years,
            reinvest_dividends=reinvest_dividends,
        )

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error simulating portfolio: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# RUN PORTFOLIO BACKTEST
# =============================================================================

async def run_portfolio_backtest_tool(
    allocation: Dict[str, float],
    start_date: str = "2015-01-01",
    initial_capital: float = 10000,
    monthly_contribution: float = 0,
    risk_off_enabled: bool = True,
    risk_off_trigger: str = "combined",
    rebalance_frequency: str = "monthly",
) -> str:
    """
    Exécute un backtest multi-assets avec mode Risk-Off.

    Args:
        allocation: {ticker: weight_percent}
        start_date: Date de début (YYYY-MM-DD)
        initial_capital: Capital initial
        monthly_contribution: Contribution mensuelle
        risk_off_enabled: Activer le mode Risk-Off
        risk_off_trigger: "hyg_lqd_below_sma50" | "vix_above_25" | "combined"
        rebalance_frequency: "monthly" | "quarterly" | "annual"

    Returns:
        JSON avec:
        - performance: CAGR, Sharpe, Max Drawdown, etc.
        - risk_off: temps en risk-off, périodes
        - dividends: total des dividendes
        - equity_curve: courbe d'équité (échantillonnée)
    """
    try:
        # Parser la date
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            return json.dumps({
                "error": f"Format de date invalide: {start_date}",
                "expected_format": "YYYY-MM-DD",
            }, ensure_ascii=False)

        end = date.today()

        # Créer la configuration
        config = BacktestConfig(
            allocation=allocation,
            start_date=start,
            end_date=end,
            initial_capital=initial_capital,
            monthly_contribution=monthly_contribution,
            risk_off_enabled=risk_off_enabled,
            risk_off_trigger=risk_off_trigger,
            rebalance_frequency=rebalance_frequency,
        )

        # Récupérer les données
        all_tickers = list(allocation.keys())
        if risk_off_enabled:
            # Ajouter les tickers défensifs
            defensive_tickers = ["SGOV", "BIL", "AGG", "BND"]
            all_tickers = list(set(all_tickers + defensive_tickers))

        logger.info(f"Fetching historical data for {len(all_tickers)} tickers...")
        historical_data = await fetch_historical_data_for_backtest(
            tickers=all_tickers,
            start_date=start,
            end_date=end,
        )

        signal_data = None
        if risk_off_enabled:
            logger.info("Fetching signal data...")
            signal_data = await fetch_signal_data_for_backtest(start, end)

        # Exécuter le backtest
        logger.info("Running backtest...")
        engine = PortfolioBacktestEngine()
        result = await engine.run_backtest(config, historical_data, signal_data)

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error running backtest: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# CREATE MACRO ALERT
# =============================================================================

async def create_macro_alert_tool(
    alert_type: str,
    notify_telegram: bool = True,
) -> str:
    """
    Crée une alerte macro (VIX, credit spread, recession).

    Args:
        alert_type: "credit_stress" | "vix_spike" | "correction" | "recession" | "risk_off"
        notify_telegram: Envoyer notification Telegram

    Returns:
        JSON avec confirmation de l'alerte créée
    """
    try:
        valid_types = ["credit_stress", "vix_spike", "correction", "recession", "risk_off"]
        if alert_type not in valid_types:
            return json.dumps({
                "error": f"Type d'alerte invalide: {alert_type}",
                "valid_types": valid_types,
            }, ensure_ascii=False)

        # Définir les conditions d'alerte
        alert_configs = {
            "credit_stress": {
                "description": "HYG/LQD ratio en dessous de SMA(50) pendant 5 jours",
                "ticker": "HYG",
                "condition": "ratio_below_sma",
            },
            "vix_spike": {
                "description": "VIX > 30",
                "ticker": "^VIX",
                "condition": "price_above",
                "threshold": 30,
            },
            "correction": {
                "description": "SPY drawdown > -5%",
                "ticker": "SPY",
                "condition": "drawdown_below",
                "threshold": -5,
            },
            "recession": {
                "description": "Yield curve inversée (10Y - 3M < 0)",
                "ticker": "^TNX",
                "condition": "yield_curve_inverted",
            },
            "risk_off": {
                "description": "Combinaison de signaux macro (2+ actifs)",
                "ticker": "MACRO",
                "condition": "combined_signals",
            },
        }

        config = alert_configs[alert_type]

        # Enregistrer l'alerte (via le service existant si disponible)
        try:
            alert_service = get_alert_service()
            # Pour les alertes macro, on utilise un format spécial
            alert_id = await alert_service.create_alert(
                ticker=config["ticker"],
                alert_type="macro_" + alert_type,
                target_value=config.get("threshold", 0),
                notify_telegram=notify_telegram,
            )

            result = {
                "success": True,
                "alert_id": alert_id,
                "alert_type": alert_type,
                "description": config["description"],
                "notify_telegram": notify_telegram,
                "message": f"Alerte macro '{alert_type}' créée avec succès",
            }

        except Exception as e:
            # Si le service d'alerte n'est pas disponible, retourner un avertissement
            result = {
                "success": False,
                "alert_type": alert_type,
                "description": config["description"],
                "error": f"Service d'alerte non disponible: {str(e)}",
                "suggestion": "Vérifiez la configuration du service d'alertes",
            }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error creating macro alert: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# GET DIVIDEND CALENDAR
# =============================================================================

async def get_dividend_calendar_tool(
    tickers: List[str],
    days_ahead: int = 30,
) -> str:
    """
    Récupère le calendrier des dividendes à venir.

    Args:
        tickers: Liste des tickers à surveiller
        days_ahead: Nombre de jours à regarder en avant

    Returns:
        JSON avec:
        - upcoming_dividends: [{ticker, ex_date, pay_date, amount, yield}]
        - total_expected_income: revenu total attendu
    """
    try:
        if not tickers:
            return json.dumps({
                "error": "Liste de tickers requise",
                "example": ["JEPI", "SCHD", "ARCC"],
            }, ensure_ascii=False)

        service = get_income_asset_service()
        upcoming = await service.get_dividend_calendar(tickers, days_ahead)

        # Calculer le revenu total attendu
        total_income = sum(
            d.get("amount", 0) or 0
            for d in upcoming
        )

        result = {
            "period_days": days_ahead,
            "tickers_checked": len(tickers),
            "upcoming_dividends": upcoming,
            "count": len(upcoming),
            "total_expected_income": round(total_income, 2) if total_income else "Non disponible",
            "note": "Les montants sont par action. Multipliez par vos positions pour le total.",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting dividend calendar: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# INCOME PORTFOLIO PRESET
# =============================================================================

def get_income_shield_preset() -> Dict:
    """
    Retourne le preset Income Shield Portfolio.

    Returns:
        Configuration du portefeuille Income Shield
    """
    return {
        "id": "income_shield",
        "name": "Income Shield Portfolio",
        "description": "Portefeuille orienté revenus avec protection Risk-Off automatique",
        "category": "income",
        "tickers": [
            # Covered Call ETFs (40%)
            "JEPI", "JEPQ", "DIVO", "XYLD",
            # BDC (25%)
            "ARCC", "MAIN", "HTGC", "OBDC",
            # CEF (15%)
            "BST", "UTF",
            # Cash-like défensif (10%)
            "SGOV", "BIL",
            # Obligations (10%)
            "AGG", "BND",
        ],
        "default_allocation": {
            "JEPI": 15, "JEPQ": 10, "DIVO": 10, "XYLD": 5,
            "ARCC": 8, "MAIN": 7, "HTGC": 5, "OBDC": 5,
            "BST": 8, "UTF": 7,
            "SGOV": 5, "BIL": 5,
            "AGG": 5, "BND": 5,
        },
        "risk_off_allocation": {
            "SGOV": 40, "BIL": 30, "AGG": 20, "BND": 10,
        },
        "expected_yield": "6-8%",
        "risk_level": "Modéré",
        "rebalance_frequency": "monthly",
    }
