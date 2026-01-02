"""
Routes API pour le backtesting.

Endpoints:
- POST /api/backtest/run - Lancer un backtest
- GET /api/backtest/strategies - Lister les strategies
- GET /api/backtest/results - Lister les resultats sauvegardes
- GET /api/backtest/results/{id} - Details d'un resultat
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.backtesting.engine import BacktestEngine
from src.backtesting.strategies import get_strategy, list_strategies
from src.infrastructure.database.repositories.backtest_repository import (
    BacktestRepository,
    BacktestResult as DBBacktestResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])


# =============================================================================
# SCHEMAS
# =============================================================================

class BacktestRequest(BaseModel):
    """Requete de backtest."""
    ticker: str = Field(..., description="Symbole du ticker")
    strategy: str = Field(..., description="Nom de la strategie")
    start_date: Optional[str] = Field(None, description="Date de debut (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Date de fin (YYYY-MM-DD)")
    initial_capital: float = Field(10000, ge=100, description="Capital initial")
    position_size_pct: float = Field(100, ge=1, le=100, description="Taille position en %")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parametres de strategie")


class StrategyInfo(BaseModel):
    """Info sur une strategie."""
    name: str
    description: str
    parameters: Dict[str, Any]


class MetricsResponse(BaseModel):
    """Metriques de performance."""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    volatility: float


class BacktestResponse(BaseModel):
    """Reponse de backtest."""
    ticker: str
    strategy_name: str
    strategy_params: Dict[str, Any]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    metrics: MetricsResponse
    trades_count: int
    equity_curve: List[Dict[str, Any]]


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """
    Lance un backtest d'une strategie sur un ticker.

    Retourne les performances et la courbe d'equity.
    """
    try:
        # Dates par defaut (1 an)
        end_date = request.end_date or datetime.now().strftime("%Y-%m-%d")
        start_date = request.start_date or (
            datetime.now() - timedelta(days=365)
        ).strftime("%Y-%m-%d")

        # Creer la strategie
        params = request.parameters or {}
        strategy = get_strategy(request.strategy, **params)

        # Creer le moteur
        engine = BacktestEngine(
            initial_capital=request.initial_capital,
            commission=0.001,
            slippage=0.0005,
        )

        # Executer le backtest
        result = await engine.run(
            ticker=request.ticker.upper(),
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            position_size_pct=request.position_size_pct,
        )

        # Sauvegarder en base
        try:
            repo = BacktestRepository()
            await repo.save(
                strategy_name=result.strategy_name,
                ticker=result.ticker,
                start_date=start_date,
                end_date=end_date,
                initial_capital=result.initial_capital,
                final_capital=result.final_capital,
                total_return=result.metrics.total_return,
                sharpe_ratio=result.metrics.sharpe_ratio,
                max_drawdown=result.metrics.max_drawdown,
                win_rate=result.metrics.win_rate,
                total_trades=result.metrics.total_trades,
                parameters=result.strategy_params,
                equity_curve=[],
                trades=[],
            )
        except Exception as e:
            logger.warning(f"Could not save backtest result: {e}")

        return BacktestResponse(
            ticker=result.ticker,
            strategy_name=result.strategy_name,
            strategy_params=result.strategy_params,
            start_date=start_date,
            end_date=end_date,
            initial_capital=result.initial_capital,
            final_capital=result.final_capital,
            metrics=MetricsResponse(
                total_return=result.metrics.total_return,
                annualized_return=result.metrics.annualized_return,
                sharpe_ratio=result.metrics.sharpe_ratio,
                sortino_ratio=result.metrics.sortino_ratio,
                max_drawdown=result.metrics.max_drawdown,
                win_rate=result.metrics.win_rate,
                profit_factor=result.metrics.profit_factor,
                total_trades=result.metrics.total_trades,
                volatility=result.metrics.volatility,
            ),
            trades_count=len(result.trades),
            equity_curve=result.equity_curve,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/strategies", response_model=List[StrategyInfo])
async def get_strategies():
    """
    Liste toutes les strategies disponibles avec leurs parametres.
    """
    strategies = list_strategies()
    return [
        StrategyInfo(
            name=s["name"],
            description=s["description"].strip(),
            parameters=s["parameters"],
        )
        for s in strategies
    ]


@router.get("/results")
async def get_backtest_results(
    ticker: Optional[str] = Query(None, description="Filtrer par ticker"),
    strategy: Optional[str] = Query(None, description="Filtrer par strategie"),
    limit: int = Query(20, ge=1, le=100, description="Nombre max de resultats"),
):
    """
    Liste les resultats de backtests sauvegardes.
    """
    try:
        repo = BacktestRepository()
        results = await repo.get_all(
            ticker=ticker,
            strategy_name=strategy,
            limit=limit,
        )

        return {
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "ticker": r.ticker,
                    "strategy_name": r.strategy_name,
                    "start_date": r.start_date,
                    "end_date": r.end_date,
                    "total_return": round(r.total_return, 2),
                    "sharpe_ratio": round(r.sharpe_ratio, 2),
                    "max_drawdown": round(r.max_drawdown, 2),
                    "total_trades": r.total_trades,
                    "created_at": r.created_at,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.exception(f"Error listing backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{result_id}")
async def get_backtest_result(result_id: str):
    """
    Recupere les details d'un resultat de backtest.
    """
    try:
        repo = BacktestRepository()
        result = await repo.get_by_id(result_id)

        if not result:
            raise HTTPException(status_code=404, detail="Result not found")

        return {
            "id": result.id,
            "ticker": result.ticker,
            "strategy_name": result.strategy_name,
            "parameters": result.parameters,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "equity_curve": result.equity_curve,
            "created_at": result.created_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting backtest result: {e}")
        raise HTTPException(status_code=500, detail=str(e))
