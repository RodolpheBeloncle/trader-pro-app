"""
Outils MCP pour le backtesting.

Ces outils permettent a Claude Desktop de:
- Lancer des backtests de strategies
- Lister les strategies disponibles
- Consulter les resultats
"""

import json
import logging
from typing import Optional, Dict, Any

from src.backtesting.engine import BacktestEngine
from src.backtesting.strategies import get_strategy, list_strategies

logger = logging.getLogger(__name__)


async def run_backtest_tool(
    ticker: str,
    strategy: str,
    start_date: str = "",
    end_date: str = "",
    initial_capital: float = 10000,
    parameters: str = "",
) -> str:
    """
    Lance un backtest d'une strategie sur un ticker.

    Args:
        ticker: Symbole du ticker
        strategy: Nom de la strategie (sma_crossover, rsi, momentum)
        start_date: Date de debut (YYYY-MM-DD, defaut: 1 an)
        end_date: Date de fin (YYYY-MM-DD, defaut: aujourd'hui)
        initial_capital: Capital initial
        parameters: Parametres JSON de la strategie

    Returns:
        JSON avec les resultats du backtest
    """
    try:
        from datetime import datetime, timedelta

        # Dates par defaut
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Parser les parametres
        params = {}
        if parameters:
            try:
                params = json.loads(parameters)
            except json.JSONDecodeError:
                pass

        # Creer la strategie
        strat = get_strategy(strategy, **params)

        # Creer le moteur
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission=0.001,
            slippage=0.0005,
        )

        # Executer le backtest
        result = await engine.run(
            ticker=ticker.upper(),
            strategy=strat,
            start_date=start_date,
            end_date=end_date,
        )

        # Formater la reponse
        response = {
            "success": True,
            "ticker": result.ticker,
            "strategy": result.strategy_name,
            "parameters": result.strategy_params,
            "period": f"{start_date} to {end_date}",
            "initial_capital": initial_capital,
            "final_capital": round(result.final_capital, 2),
            "performance": {
                "total_return": f"{result.metrics.total_return:+.2f}%",
                "annualized_return": f"{result.metrics.annualized_return:+.2f}%",
                "sharpe_ratio": round(result.metrics.sharpe_ratio, 2),
                "sortino_ratio": round(result.metrics.sortino_ratio, 2),
                "max_drawdown": f"{result.metrics.max_drawdown:.2f}%",
                "volatility": f"{result.metrics.volatility:.2f}%",
            },
            "trades": {
                "total": result.metrics.total_trades,
                "winning": result.metrics.winning_trades,
                "losing": result.metrics.losing_trades,
                "win_rate": f"{result.metrics.win_rate:.1f}%",
                "profit_factor": round(result.metrics.profit_factor, 2),
                "avg_win": round(result.metrics.avg_win, 2),
                "avg_loss": round(result.metrics.avg_loss, 2),
            },
            "interpretation": _interpret_backtest(result.metrics),
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error running backtest: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


def _interpret_backtest(metrics) -> dict:
    """Interprete les resultats du backtest."""
    interpretation = {}

    # Performance globale
    if metrics.total_return > 20:
        interpretation["performance"] = "Excellente performance"
    elif metrics.total_return > 10:
        interpretation["performance"] = "Bonne performance"
    elif metrics.total_return > 0:
        interpretation["performance"] = "Performance positive mais modeste"
    else:
        interpretation["performance"] = "Performance negative - strategie a eviter"

    # Sharpe
    if metrics.sharpe_ratio > 2:
        interpretation["risk_adjusted"] = "Excellent ratio risque/rendement"
    elif metrics.sharpe_ratio > 1:
        interpretation["risk_adjusted"] = "Bon ratio risque/rendement"
    elif metrics.sharpe_ratio > 0:
        interpretation["risk_adjusted"] = "Ratio risque/rendement acceptable"
    else:
        interpretation["risk_adjusted"] = "Mauvais ratio risque/rendement"

    # Drawdown
    if metrics.max_drawdown < 10:
        interpretation["risk"] = "Risque faible"
    elif metrics.max_drawdown < 20:
        interpretation["risk"] = "Risque modere"
    elif metrics.max_drawdown < 30:
        interpretation["risk"] = "Risque eleve"
    else:
        interpretation["risk"] = "Risque tres eleve - drawdown important"

    # Win rate
    if metrics.win_rate > 60:
        interpretation["consistency"] = "Tres consistant"
    elif metrics.win_rate > 50:
        interpretation["consistency"] = "Consistant"
    else:
        interpretation["consistency"] = "Peu consistant - besoin de gros gains pour compenser"

    return interpretation


async def list_strategies_tool() -> str:
    """
    Liste toutes les strategies de backtesting disponibles.

    Returns:
        JSON avec les strategies et leurs parametres
    """
    try:
        strategies = list_strategies()

        response = {
            "success": True,
            "count": len(strategies),
            "strategies": [
                {
                    "name": s["name"],
                    "description": s["description"].strip().split("\n")[0] if s["description"] else "",
                    "parameters": s["parameters"],
                }
                for s in strategies
            ],
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error listing strategies: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
