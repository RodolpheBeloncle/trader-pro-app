"""
Outils MCP pour simulation Monte Carlo.

Outils disponibles:
- monte_carlo_price_simulation: Simulation de trajectoires de prix
- monte_carlo_portfolio_risk: VaR/CVaR du portefeuille
- get_portfolio_analysis: Analyse enrichie du portefeuille Saxo

UTILISATION:
    from src.infrastructure.mcp.tools.monte_carlo_tool import (
        monte_carlo_price_simulation_tool,
        monte_carlo_portfolio_risk_tool,
        get_portfolio_analysis_tool,
    )
"""

import json
import logging
from typing import Optional

import numpy as np

from src.domain.services.monte_carlo import (
    MonteCarloEngine,
    interpret_simulation,
    interpret_portfolio_risk,
)
from src.infrastructure.providers.yahoo_finance_provider import (
    YahooFinanceProvider,
    get_yahoo_provider,
)
from src.domain.value_objects.ticker import Ticker

logger = logging.getLogger(__name__)


class NumpyEncoder(json.JSONEncoder):
    """Encoder JSON pour les types numpy."""

    def default(self, obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


async def monte_carlo_price_simulation_tool(
    ticker: str,
    time_horizon_days: int = 30,
    num_simulations: int = 10000,
) -> str:
    """
    Simulation Monte Carlo des trajectoires de prix.

    Utilise le mouvement Brownien geometrique (GBM) pour simuler
    l'evolution future du prix et calculer les intervalles de confiance.

    Args:
        ticker: Symbole de l'actif (ex: AAPL, MSFT)
        time_horizon_days: Horizon de simulation en jours (defaut 30)
        num_simulations: Nombre de trajectoires simulees (defaut 10000)

    Returns:
        JSON avec les resultats de simulation et interpretation
    """
    try:
        ticker = ticker.upper().strip()

        if not ticker:
            return json.dumps({
                "success": False,
                "error": "Ticker requis"
            }, indent=2)

        # Recuperer les donnees historiques
        provider = get_yahoo_provider()
        ticker_obj = Ticker(ticker)

        logger.info(f"Monte Carlo simulation pour {ticker}, horizon={time_horizon_days}j")

        historical_data = await provider.get_historical_data(ticker_obj, days=365)

        if len(historical_data) < 100:
            return json.dumps({
                "success": False,
                "error": f"Donnees insuffisantes pour {ticker}",
                "data_points": len(historical_data),
                "minimum_required": 100,
            }, indent=2, cls=NumpyEncoder)

        # Calculer les rendements historiques
        prices = np.array([d.close for d in historical_data])
        returns = np.diff(prices) / prices[:-1]

        current_price = historical_data[-1].close

        # Lancer la simulation
        engine = MonteCarloEngine()
        result = engine.simulate_single_asset(
            ticker=ticker,
            current_price=current_price,
            historical_returns=returns,
            time_horizon_days=time_horizon_days,
            num_simulations=num_simulations,
        )

        # Construire la reponse
        output = {
            "success": True,
            "ticker": ticker,
            "simulation": result.to_dict(),
            "interpretation": interpret_simulation(result),
            "trading_signals": _generate_trading_signals(result),
        }

        # Retirer les donnees volumineuses pour economiser les tokens
        if "price_distribution" in output["simulation"]:
            del output["simulation"]["price_distribution"]
        if "sample_paths" in output["simulation"]:
            del output["simulation"]["sample_paths"]

        return json.dumps(output, indent=2, cls=NumpyEncoder, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erreur Monte Carlo {ticker}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


async def monte_carlo_portfolio_risk_tool(
    positions: str,
    time_horizon_days: int = 1,
    num_simulations: int = 10000,
) -> str:
    """
    Calcul du risque portefeuille par Monte Carlo.

    Calcule:
    - VaR (Value at Risk) a 99%, 95%, 90%
    - CVaR/Expected Shortfall
    - Attribution du risque par position
    - Ratio de diversification

    Args:
        positions: JSON array des positions [{"symbol": "AAPL", "market_value": 10000}, ...]
        time_horizon_days: Horizon du VaR en jours (defaut 1)
        num_simulations: Nombre de simulations

    Returns:
        JSON avec VaR, CVaR, et metriques de risque
    """
    try:
        # Parser les positions
        try:
            positions_list = json.loads(positions)
        except json.JSONDecodeError:
            return json.dumps({
                "success": False,
                "error": "Format JSON invalide pour les positions"
            }, indent=2)

        if not positions_list:
            return json.dumps({
                "success": False,
                "error": "Aucune position fournie"
            }, indent=2)

        logger.info(f"Calcul VaR portefeuille: {len(positions_list)} positions")

        # Recuperer les donnees historiques pour chaque position
        provider = get_yahoo_provider()
        historical_returns = {}

        for pos in positions_list:
            symbol = pos.get("symbol", "").upper()
            if not symbol:
                continue

            try:
                ticker_obj = Ticker(symbol)
                data = await provider.get_historical_data(ticker_obj, days=365)

                if len(data) >= 100:
                    prices = np.array([d.close for d in data])
                    returns = np.diff(prices) / prices[:-1]
                    historical_returns[symbol] = returns
                else:
                    # Volatilite par defaut si donnees insuffisantes
                    logger.warning(f"Donnees insuffisantes pour {symbol}, utilisation volatilite par defaut")
                    historical_returns[symbol] = np.random.normal(0, 0.02, 252)

            except Exception as e:
                logger.warning(f"Erreur donnees {symbol}: {e}")
                historical_returns[symbol] = np.random.normal(0, 0.02, 252)

        # Calculer le risque
        engine = MonteCarloEngine()
        result = engine.calculate_portfolio_var(
            positions=[{
                "symbol": p["symbol"].upper(),
                "market_value": float(p.get("market_value", 0)),
            } for p in positions_list],
            historical_returns=historical_returns,
            time_horizon_days=time_horizon_days,
            num_simulations=num_simulations,
        )

        output = {
            "success": True,
            "risk_analysis": result.to_dict(),
            "interpretation": interpret_portfolio_risk(result),
            "risk_recommendations": _generate_risk_recommendations(result),
        }

        return json.dumps(output, indent=2, cls=NumpyEncoder, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erreur calcul VaR: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


async def get_portfolio_analysis_tool() -> str:
    """
    Analyse enrichie du portefeuille Saxo.

    Recupere le portefeuille Saxo et l'enrichit avec:
    - Analyse technique par position (RSI, MACD, trend)
    - News et sentiment
    - Metriques de risque (poids, SL/TP suggeres)
    - Recommandations (BUY/SELL/HOLD)

    Returns:
        JSON avec le portefeuille enrichi
    """
    try:
        from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth
        from src.infrastructure.brokers.saxo.saxo_api_client import SaxoApiClient
        from src.config.settings import get_settings
        from src.application.services.portfolio_analysis_service import PortfolioAnalysisService

        # Verifier la connexion Saxo
        auth = get_saxo_auth()
        token = auth.get_valid_token()

        if not token:
            return json.dumps({
                "success": False,
                "error": "Non connecte a Saxo. Connectez-vous d'abord via l'interface web.",
                "action_required": "Ouvrez l'application web et connectez-vous a Saxo"
            }, indent=2, ensure_ascii=False)

        # Recuperer le portefeuille
        settings = get_settings()
        client = SaxoApiClient(settings)

        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            return json.dumps({
                "success": False,
                "error": "Client Saxo non trouve"
            }, indent=2)

        accounts = client.get_accounts(token.access_token, client_key)
        account_key = accounts[0].get("AccountKey") if accounts else None

        positions_data = client.get_net_positions(token.access_token, client_key)

        if not positions_data:
            return json.dumps({
                "success": True,
                "message": "Portefeuille vide",
                "positions": [],
                "summary": {
                    "total_positions": 0,
                    "total_value": 0,
                    "total_pnl": 0,
                }
            }, indent=2)

        # Construire les positions
        positions = []
        total_value = 0
        total_pnl = 0

        for pos in positions_data:
            base = pos.get("NetPositionBase", {})
            display = pos.get("DisplayAndFormat", {})

            pnl = base.get("ProfitLossOnTrade", 0) or 0
            value = base.get("MarketValue", 0) or 0
            avg_price = base.get("AverageOpenPrice", 0) or 0
            current_price = base.get("CurrentPrice", 0) or 0
            quantity = base.get("Amount", 0) or 0

            pnl_percent = 0
            if avg_price > 0 and quantity != 0:
                pnl_percent = ((current_price - avg_price) / avg_price) * 100

            positions.append({
                "symbol": display.get("Symbol", base.get("AssetType", "N/A")),
                "description": display.get("Description", ""),
                "quantity": quantity,
                "current_price": current_price,
                "average_price": avg_price,
                "market_value": value,
                "pnl": pnl,
                "pnl_percent": round(pnl_percent, 2),
                "currency": display.get("Currency", "EUR"),
                "asset_type": base.get("AssetType", "Stock"),
                "uic": base.get("Uic"),
            })

            total_value += value
            total_pnl += pnl

        # Analyser le portefeuille
        logger.info(f"Analyse enrichie de {len(positions)} positions")
        analysis_service = PortfolioAnalysisService()
        enhanced_positions = await analysis_service.analyze_portfolio(
            positions=positions,
            portfolio_total_value=total_value,
        )

        total_pnl_percent = (total_pnl / total_value * 100) if total_value > 0 else 0

        # Generer le resume
        actions_summary = _summarize_actions(enhanced_positions)

        return json.dumps({
            "success": True,
            "positions": [p.to_dict() for p in enhanced_positions],
            "summary": {
                "total_positions": len(positions),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round(total_pnl_percent, 2),
            },
            "actions_summary": actions_summary,
            "account_key": account_key,
        }, indent=2, cls=NumpyEncoder, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erreur analyse portefeuille: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


async def set_portfolio_alerts_tool(
    tickers: Optional[str] = None,
    stop_loss_percent: float = 8.0,
    take_profit_percent: float = 24.0,
) -> str:
    """
    Configure les alertes stop loss et take profit pour les positions.

    Args:
        tickers: Liste de tickers separes par virgule (vide = toutes les positions)
        stop_loss_percent: Pourcentage de stop loss sous le prix d'entree (defaut 8%)
        take_profit_percent: Pourcentage de take profit au-dessus (defaut 24%)

    Returns:
        JSON avec les alertes creees
    """
    try:
        from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth
        from src.infrastructure.brokers.saxo.saxo_api_client import SaxoApiClient
        from src.config.settings import get_settings
        from src.application.services.alert_service import AlertService

        # Verifier connexion Saxo
        auth = get_saxo_auth()
        token = auth.get_valid_token()

        if not token:
            return json.dumps({
                "success": False,
                "error": "Non connecte a Saxo"
            }, indent=2)

        # Recuperer les positions
        settings = get_settings()
        client = SaxoApiClient(settings)

        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        positions_data = client.get_net_positions(token.access_token, client_key)

        if not positions_data:
            return json.dumps({
                "success": False,
                "error": "Aucune position dans le portefeuille"
            }, indent=2)

        # Filtrer par tickers si specifie
        target_tickers = None
        if tickers:
            target_tickers = [t.strip().upper() for t in tickers.split(",")]

        # Creer les alertes
        alert_service = AlertService()
        created_alerts = []

        for pos in positions_data:
            base = pos.get("NetPositionBase", {})
            display = pos.get("DisplayAndFormat", {})

            symbol = display.get("Symbol", "").upper()
            if target_tickers and symbol not in target_tickers:
                continue

            entry_price = base.get("AverageOpenPrice", 0)
            if entry_price <= 0:
                continue

            # Calculer les niveaux
            sl_price = entry_price * (1 - stop_loss_percent / 100)
            tp_price = entry_price * (1 + take_profit_percent / 100)

            # Creer alerte stop loss
            try:
                sl_alert = await alert_service.create_alert(
                    ticker=symbol,
                    alert_type="stop_loss",
                    target_value=sl_price,
                    notes=f"Stop loss auto: {stop_loss_percent}% sous entree ({entry_price:.2f})",
                )
                created_alerts.append({
                    "ticker": symbol,
                    "type": "stop_loss",
                    "level": round(sl_price, 2),
                    "alert_id": sl_alert.id,
                })
            except Exception as e:
                logger.warning(f"Erreur creation SL {symbol}: {e}")

            # Creer alerte take profit
            try:
                tp_alert = await alert_service.create_alert(
                    ticker=symbol,
                    alert_type="take_profit",
                    target_value=tp_price,
                    notes=f"Take profit auto: {take_profit_percent}% au-dessus entree ({entry_price:.2f})",
                )
                created_alerts.append({
                    "ticker": symbol,
                    "type": "take_profit",
                    "level": round(tp_price, 2),
                    "alert_id": tp_alert.id,
                })
            except Exception as e:
                logger.warning(f"Erreur creation TP {symbol}: {e}")

        return json.dumps({
            "success": True,
            "message": f"{len(created_alerts)} alertes creees",
            "alerts": created_alerts,
            "parameters": {
                "stop_loss_percent": stop_loss_percent,
                "take_profit_percent": take_profit_percent,
            }
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erreur creation alertes: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


# =============================================================================
# HELPERS
# =============================================================================

def _generate_trading_signals(result) -> dict:
    """Genere des signaux de trading bases sur la simulation."""
    prob_loss = result.probability_of_loss
    prob_gain_10 = result.probability_of_gain_10pct
    expected_return = result.expected_return_percent

    signals = []

    if prob_loss > 0.55:
        signals.append({
            "signal": "PRUDENCE",
            "reason": f"Probabilite de baisse elevee ({prob_loss*100:.0f}%)",
            "action": "Considerer reduire la position ou placer un stop loss serre"
        })

    if prob_gain_10 > 0.4:
        signals.append({
            "signal": "OPPORTUNITE",
            "reason": f"Probabilite de gain >10% = {prob_gain_10*100:.0f}%",
            "action": "Position favorable pour maintenir ou renforcer"
        })

    if result.risk_level == "ELEVE":
        signals.append({
            "signal": "RISQUE ELEVE",
            "reason": f"Volatilite elevee ({result.annual_volatility*100:.0f}%/an)",
            "action": "Reduire la taille de position"
        })

    return {
        "signals": signals,
        "summary": f"Rendement attendu: {expected_return:+.1f}%, Risque: {result.risk_level}",
    }


def _generate_risk_recommendations(result) -> list:
    """Genere des recommandations de gestion de risque."""
    recommendations = []

    var_pct = result.var_99_percent

    if var_pct > 10:
        recommendations.append({
            "priority": "HAUTE",
            "action": "Reduire l'exposition",
            "detail": f"VaR 99% de {var_pct:.1f}% trop eleve pour un portefeuille diversifie"
        })

    if not result.is_well_diversified:
        recommendations.append({
            "priority": "MOYENNE",
            "action": "Ameliorer la diversification",
            "detail": f"Correlation moyenne de {result.average_correlation:.0%} trop elevee"
        })

    # Identifier les contributeurs de risque majeurs
    for symbol, contrib in result.position_risk_contributions.items():
        if contrib > 0.3:  # 30% du risque
            recommendations.append({
                "priority": "MOYENNE",
                "action": f"Surveiller {symbol}",
                "detail": f"Contribue a {contrib*100:.0f}% du risque total"
            })

    if not recommendations:
        recommendations.append({
            "priority": "BASSE",
            "action": "Maintenir la strategie",
            "detail": "Portefeuille bien equilibre"
        })

    return recommendations


def _summarize_actions(enhanced_positions) -> dict:
    """Resume les actions recommandees."""
    buy = []
    sell = []
    hold = []

    for pos in enhanced_positions:
        if pos.recommendation:
            action = pos.recommendation.action
            symbol = pos.symbol
            confidence = pos.recommendation.confidence

            if action in ("BUY", "ADD"):
                buy.append({"symbol": symbol, "action": action, "confidence": confidence})
            elif action in ("SELL", "REDUCE"):
                sell.append({"symbol": symbol, "action": action, "confidence": confidence})
            else:
                hold.append({"symbol": symbol, "action": action, "confidence": confidence})

    return {
        "buy_signals": buy,
        "sell_signals": sell,
        "hold": hold,
        "summary": f"{len(buy)} achats, {len(sell)} ventes, {len(hold)} hold"
    }
