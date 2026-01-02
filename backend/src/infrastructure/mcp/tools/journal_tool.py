"""
Outils MCP pour le journal de trading.

Ces outils permettent à Claude Desktop de:
- Logger de nouveaux trades
- Clôturer des trades avec P&L
- Consulter les statistiques de performance
- Ajouter des analyses post-trade
"""

import json
import logging
from typing import Any, Dict, List, Optional

from src.application.services.journal_service import JournalService

logger = logging.getLogger(__name__)


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
    Enregistre un nouveau trade dans le journal.

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
        service = JournalService()

        # Parser les facteurs de confluence
        factors = [f.strip() for f in confluence_factors.split(",") if f.strip()] if confluence_factors else None

        trade = await service.create_trade(
            ticker=ticker.upper(),
            direction=direction,
            entry_price=entry_price if entry_price > 0 else None,
            stop_loss=stop_loss if stop_loss > 0 else None,
            take_profit=take_profit if take_profit > 0 else None,
            position_size=position_size if position_size > 0 else None,
            status=status,
            setup_type=setup_type if setup_type else None,
            trade_thesis=trade_thesis if trade_thesis else None,
            timeframe=timeframe if timeframe else None,
            confluence_factors=factors,
            notify=True,
        )

        result = {
            "success": True,
            "trade": {
                "id": trade.id,
                "ticker": trade.ticker,
                "direction": trade.direction.value,
                "status": trade.status.value,
                "entry_price": trade.entry_price,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "position_size": trade.position_size,
                "risk_reward_ratio": trade.risk_reward_ratio,
            },
            "message": f"Trade {trade.ticker} {trade.direction.value} enregistré ({trade.status.value})"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
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
    Clôture un trade avec calcul du P&L.

    Args:
        trade_id: ID du trade à clôturer
        exit_price: Prix de sortie
        fees: Frais de transaction

    Returns:
        JSON avec le trade clôturé et le P&L
    """
    try:
        service = JournalService()
        trade = await service.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            fees=fees,
            notify=True,
        )

        if trade is None:
            return json.dumps({
                "success": False,
                "error": "Trade non trouvé ou n'est pas actif"
            }, ensure_ascii=False)

        result = {
            "success": True,
            "trade": {
                "id": trade.id,
                "ticker": trade.ticker,
                "direction": trade.direction.value,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "gross_pnl": trade.gross_pnl,
                "net_pnl": trade.net_pnl,
                "r_multiple": trade.r_multiple,
                "is_winner": trade.is_winner,
            },
            "message": f"Trade {trade.ticker} clôturé: P&L = {trade.net_pnl:+.2f} ({trade.r_multiple:+.2f}R)"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error closing trade: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_journal_stats_tool() -> str:
    """
    Retourne les statistiques globales du journal de trading.

    Returns:
        JSON avec les statistiques de performance
    """
    try:
        service = JournalService()
        stats = await service.get_stats()

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
    win_rate = stats.get("win_rate", 0)
    if win_rate >= 60:
        interpretation["win_rate"] = "Excellent taux de réussite"
    elif win_rate >= 50:
        interpretation["win_rate"] = "Bon taux de réussite"
    elif win_rate >= 40:
        interpretation["win_rate"] = "Taux acceptable, mais peut être amélioré"
    else:
        interpretation["win_rate"] = "Taux faible - revoir les setups"

    # Profit factor
    pf = stats.get("profit_factor", 0)
    if pf >= 2:
        interpretation["profit_factor"] = "Excellent profit factor"
    elif pf >= 1.5:
        interpretation["profit_factor"] = "Bon profit factor"
    elif pf >= 1:
        interpretation["profit_factor"] = "Rentable mais peut être optimisé"
    else:
        interpretation["profit_factor"] = "Non rentable - revoir la stratégie"

    # R-multiple moyen
    avg_r = stats.get("avg_r_multiple", 0)
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
    Retourne un dashboard complet du journal de trading.

    Inclut: stats, trades actifs, récents, erreurs et leçons.

    Returns:
        JSON avec le dashboard
    """
    try:
        service = JournalService()
        dashboard = await service.get_dashboard()

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
    Liste les trades du journal.

    Args:
        status: Filtrer par statut (planned, active, closed, cancelled)
        ticker: Filtrer par ticker
        limit: Nombre maximum de trades

    Returns:
        JSON avec la liste des trades
    """
    try:
        service = JournalService()
        trades = await service.get_trades(
            status=status if status else None,
            ticker=ticker if ticker else None,
            limit=limit,
        )

        result = {
            "success": True,
            "count": len(trades),
            "trades": [
                {
                    "id": t.id,
                    "ticker": t.ticker,
                    "direction": t.direction.value,
                    "status": t.status.value,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "net_pnl": t.net_pnl,
                    "r_multiple": t.r_multiple,
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
    Ajoute une analyse post-trade à une entrée de journal.

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
        service = JournalService()

        mistakes_list = [m.strip() for m in mistakes.split(",") if m.strip()] if mistakes else None
        well_list = [w.strip() for w in what_went_well.split(",") if w.strip()] if what_went_well else None

        entry = await service.add_post_trade_analysis(
            trade_id=trade_id,
            execution_quality=execution_quality,
            emotional_state=emotional_state,
            process_compliance=process_compliance,
            trade_quality_score=trade_quality_score,
            mistakes=mistakes_list,
            what_went_well=well_list,
            lessons_learned=lessons_learned if lessons_learned else None,
        )

        if entry is None:
            return json.dumps({
                "success": False,
                "error": "Entrée de journal non trouvée pour ce trade"
            }, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "message": f"Analyse post-trade ajoutée (score: {trade_quality_score}/10)"
        }, ensure_ascii=False)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error adding post-trade analysis: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
