"""
Outils MCP pour le journal de trading.

Ces outils utilisent l'API HTTP du backend Docker pour garantir
que Claude Desktop et l'interface web partagent les mêmes données.

ARCHITECTURE:
    Claude Desktop MCP → HTTP API → Docker Backend → SQLite
    Web Frontend       → HTTP API → Docker Backend → SQLite
"""

import json
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

# URL de base de l'API (backend Docker)
API_BASE_URL = "http://localhost:8000/api"
HTTP_TIMEOUT = 30.0


async def _api_request(
    method: str,
    endpoint: str,
    data: Dict[str, Any] = None,
    params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Effectue une requête HTTP vers l'API backend.

    Args:
        method: GET, POST, PUT, DELETE
        endpoint: Chemin de l'endpoint (ex: /journal/trades)
        data: Données JSON pour POST/PUT
        params: Paramètres de query string

    Returns:
        Réponse JSON de l'API
    """
    url = f"{API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        if method.upper() == "GET":
            response = await client.get(url, params=params)
        elif method.upper() == "POST":
            response = await client.post(url, json=data)
        elif method.upper() == "PUT":
            response = await client.put(url, json=data)
        elif method.upper() == "DELETE":
            response = await client.delete(url, params=params)
        else:
            raise ValueError(f"Méthode HTTP non supportée: {method}")

        response.raise_for_status()
        return response.json()


async def log_trade_tool(
    ticker: str,
    direction: str,
    entry_price: float = 0,
    stop_loss: float = 0,
    take_profit: float = 0,
    position_size: int = 0,
    status: str = "planned",
    setup_type: str = "",
    trade_thesis: str = "",
    timeframe: str = "",
    confluence_factors: str = ""
) -> str:
    """
    Enregistre un nouveau trade dans le journal via l'API HTTP.

    Args:
        ticker: Symbole du ticker
        direction: long ou short
        entry_price: Prix d'entrée (optionnel si planned)
        stop_loss: Stop loss
        take_profit: Take profit
        position_size: Taille de position
        status: planned ou active
        setup_type: Type de setup (breakout, pullback, reversal...)
        trade_thesis: Thèse du trade
        timeframe: Timeframe (1m, 5m, 1h, 4h, D)
        confluence_factors: Facteurs de confluence séparés par virgule

    Returns:
        JSON avec le trade créé
    """
    try:
        # Construire le payload pour l'API
        payload = {
            "ticker": ticker.upper(),
            "direction": direction,
        }

        # Ajouter les champs optionnels
        if entry_price > 0:
            payload["entry_price"] = entry_price
        if stop_loss > 0:
            payload["stop_loss"] = stop_loss
        if take_profit > 0:
            payload["take_profit"] = take_profit
        if position_size > 0:
            payload["position_size"] = position_size
        if status:
            payload["status"] = status
        if setup_type:
            payload["setup_type"] = setup_type
        if trade_thesis:
            payload["trade_thesis"] = trade_thesis
        if timeframe:
            payload["timeframe"] = timeframe
        if confluence_factors:
            payload["confluence_factors"] = [f.strip() for f in confluence_factors.split(",") if f.strip()]

        # Appeler l'API
        trade = await _api_request("POST", "/journal/trades", data=payload)

        # Calculer le R/R ratio si possible
        rr_ratio = None
        if trade.get("entry_price") and trade.get("stop_loss") and trade.get("take_profit"):
            entry = trade["entry_price"]
            sl = trade["stop_loss"]
            tp = trade["take_profit"]
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            if risk > 0:
                rr_ratio = round(reward / risk, 2)

        result = {
            "success": True,
            "trade": {
                "id": trade.get("id"),
                "ticker": trade.get("ticker"),
                "direction": trade.get("direction"),
                "status": trade.get("status"),
                "entry_price": trade.get("entry_price"),
                "stop_loss": trade.get("stop_loss"),
                "take_profit": trade.get("take_profit"),
                "position_size": trade.get("position_size"),
                "risk_reward_ratio": rr_ratio,
            },
            "message": f"Trade {trade.get('ticker')} {trade.get('direction')} enregistré ({trade.get('status')})"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = "Erreur API"
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            error_detail = str(e)
        logger.error(f"HTTP error logging trade: {error_detail}")
        return json.dumps({
            "success": False,
            "error": error_detail
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error logging trade: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def close_trade_tool(
    trade_id: str,
    exit_price: float,
    fees: float = 0
) -> str:
    """
    Clôture un trade avec calcul du P&L via l'API HTTP.

    Args:
        trade_id: ID du trade à clôturer
        exit_price: Prix de sortie
        fees: Frais de transaction

    Returns:
        JSON avec le trade clôturé et le P&L
    """
    try:
        payload = {
            "exit_price": exit_price,
            "exit_reason": "manual"
        }
        if fees > 0:
            payload["fees"] = fees

        trade = await _api_request("POST", f"/journal/trades/{trade_id}/close", data=payload)

        result = {
            "success": True,
            "trade": {
                "id": trade.get("id"),
                "ticker": trade.get("ticker"),
                "direction": trade.get("direction"),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "gross_pnl": trade.get("gross_pnl"),
                "net_pnl": trade.get("net_pnl"),
                "r_multiple": trade.get("r_multiple"),
                "is_winner": trade.get("net_pnl", 0) > 0 if trade.get("net_pnl") is not None else None,
            },
            "message": f"Trade {trade.get('ticker')} clôturé: P&L = {trade.get('net_pnl', 0):+.2f}"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = "Trade non trouvé ou erreur"
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            pass
        return json.dumps({
            "success": False,
            "error": error_detail
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error closing trade: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_journal_stats_tool() -> str:
    """
    Retourne les statistiques globales du journal de trading via l'API HTTP.

    Returns:
        JSON avec les statistiques de performance
    """
    try:
        stats = await _api_request("GET", "/journal/stats")

        return json.dumps({
            "success": True,
            "stats": stats,
            "interpretation": _interpret_stats(stats)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting journal stats: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


def _interpret_stats(stats: Dict[str, Any]) -> Dict[str, str]:
    """Interprète les statistiques pour donner des conseils."""
    interpretation = {}

    # Win rate
    win_rate = stats.get("win_rate", 0) or 0
    if win_rate >= 60:
        interpretation["win_rate"] = "Excellent taux de réussite"
    elif win_rate >= 50:
        interpretation["win_rate"] = "Bon taux de réussite"
    elif win_rate >= 40:
        interpretation["win_rate"] = "Taux acceptable, mais peut être amélioré"
    else:
        interpretation["win_rate"] = "Taux faible - revoir les setups"

    # Profit factor
    pf = stats.get("profit_factor", 0) or 0
    if pf >= 2:
        interpretation["profit_factor"] = "Excellent profit factor"
    elif pf >= 1.5:
        interpretation["profit_factor"] = "Bon profit factor"
    elif pf >= 1:
        interpretation["profit_factor"] = "Rentable mais peut être optimisé"
    else:
        interpretation["profit_factor"] = "Non rentable - revoir la stratégie"

    # R-multiple moyen
    avg_r = stats.get("avg_r_multiple", 0) or 0
    if avg_r >= 1:
        interpretation["avg_r"] = "Excellent R moyen - bonne gestion R/R"
    elif avg_r >= 0.5:
        interpretation["avg_r"] = "Bon R moyen"
    elif avg_r > 0:
        interpretation["avg_r"] = "R moyen faible - améliorer les sorties"
    else:
        interpretation["avg_r"] = "R négatif - problème de money management"

    return interpretation


async def get_journal_dashboard_tool() -> str:
    """
    Retourne un dashboard complet du journal de trading via l'API HTTP.

    Inclut: stats, trades actifs, récents, erreurs et leçons.

    Returns:
        JSON avec le dashboard
    """
    try:
        dashboard = await _api_request("GET", "/journal/dashboard")

        return json.dumps({
            "success": True,
            "dashboard": dashboard
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting dashboard: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def list_trades_tool(
    status: str = "",
    ticker: str = "",
    limit: int = 10
) -> str:
    """
    Liste les trades du journal via l'API HTTP.

    Args:
        status: Filtrer par statut (planned, active, closed, cancelled)
        ticker: Filtrer par ticker
        limit: Nombre maximum de trades

    Returns:
        JSON avec la liste des trades
    """
    try:
        params = {"limit": limit}
        if status:
            params["status"] = status
        if ticker:
            params["ticker"] = ticker

        trades = await _api_request("GET", "/journal/trades", params=params)

        result = {
            "success": True,
            "count": len(trades),
            "trades": [
                {
                    "id": t.get("id"),
                    "ticker": t.get("ticker"),
                    "direction": t.get("direction"),
                    "status": t.get("status"),
                    "entry_price": t.get("entry_price"),
                    "exit_price": t.get("exit_price"),
                    "stop_loss": t.get("stop_loss"),
                    "take_profit": t.get("take_profit"),
                    "net_pnl": t.get("net_pnl"),
                    "r_multiple": t.get("r_multiple"),
                }
                for t in trades
            ]
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error listing trades: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def add_post_trade_analysis_tool(
    trade_id: str,
    execution_quality: str,
    emotional_state: str,
    process_compliance: str,
    trade_quality_score: int,
    mistakes: str = "",
    what_went_well: str = "",
    lessons_learned: str = ""
) -> str:
    """
    Ajoute une analyse post-trade à une entrée de journal via l'API HTTP.

    Args:
        trade_id: ID du trade
        execution_quality: excellent, good, average, poor
        emotional_state: calm, confident, anxious, fomo, revenge
        process_compliance: followed, deviated, ignored
        trade_quality_score: Score de 1 à 10
        mistakes: Erreurs commises (séparées par virgule)
        what_went_well: Ce qui a bien fonctionné (séparé par virgule)
        lessons_learned: Leçon principale

    Returns:
        JSON avec le résultat
    """
    try:
        payload = {
            "execution_quality": execution_quality,
            "emotional_state": emotional_state,
            "process_compliance": process_compliance,
            "trade_quality_score": trade_quality_score,
        }

        if mistakes:
            payload["mistakes"] = [m.strip() for m in mistakes.split(",") if m.strip()]
        if what_went_well:
            payload["what_went_well"] = [w.strip() for w in what_went_well.split(",") if w.strip()]
        if lessons_learned:
            payload["lessons_learned"] = lessons_learned

        await _api_request("POST", f"/journal/trades/{trade_id}/analysis", data=payload)

        return json.dumps({
            "success": True,
            "message": f"Analyse post-trade ajoutée (score: {trade_quality_score}/10)"
        }, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        error_detail = "Entrée de journal non trouvée"
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            pass
        return json.dumps({
            "success": False,
            "error": error_detail
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error adding post-trade analysis: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
