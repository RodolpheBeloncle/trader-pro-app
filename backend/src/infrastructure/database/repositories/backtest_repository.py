"""
Repository pour les résultats de backtests.

Gère le CRUD des résultats avec support pour:
- Sauvegarde des résultats complets
- Comparaison de stratégies
- Historique des backtests
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Any, Dict

from src.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass
class EquityPoint:
    """Point de la courbe d'equity."""
    date: str
    equity: float
    drawdown: float = 0.0


@dataclass
class BacktestTrade:
    """Trade simulé dans un backtest."""
    entry_date: str
    exit_date: str
    direction: str  # 'long' ou 'short'
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float


@dataclass
class BacktestResult:
    """
    Résultat complet d'un backtest.

    Attributs:
        id: Identifiant unique
        strategy_name: Nom de la stratégie
        ticker: Symbole du ticker testé

        # Période
        start_date: Date de début
        end_date: Date de fin

        # Capital
        initial_capital: Capital initial
        final_capital: Capital final

        # Métriques de performance
        total_return: Rendement total en %
        annualized_return: Rendement annualisé en %
        sharpe_ratio: Ratio de Sharpe
        sortino_ratio: Ratio de Sortino
        max_drawdown: Drawdown maximum en %
        max_drawdown_duration: Durée du drawdown max en jours

        # Statistiques de trades
        total_trades: Nombre total de trades
        winning_trades: Nombre de trades gagnants
        losing_trades: Nombre de trades perdants
        win_rate: Taux de réussite en %
        avg_win: Gain moyen
        avg_loss: Perte moyenne
        profit_factor: Facteur de profit
        expectancy: Espérance mathématique

        # Données détaillées
        parameters: Paramètres de la stratégie (JSON)
        equity_curve: Courbe d'equity (JSON)
        trades_data: Détail des trades (JSON)
    """

    id: str
    strategy_name: str
    ticker: str

    # Période
    start_date: str
    end_date: str

    # Capital
    initial_capital: float
    final_capital: Optional[float] = None

    # Métriques de performance
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_duration: Optional[int] = None

    # Statistiques de trades
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy: Optional[float] = None

    # Données détaillées
    parameters: Dict[str, Any] = field(default_factory=dict)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    trades_data: List[BacktestTrade] = field(default_factory=list)

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_profitable(self) -> bool:
        """Vérifie si le backtest est rentable."""
        return self.total_return is not None and self.total_return > 0

    @property
    def risk_adjusted_return(self) -> Optional[float]:
        """Calcule le rendement ajusté au risque."""
        if self.total_return is None or self.max_drawdown is None or self.max_drawdown == 0:
            return None
        return self.total_return / abs(self.max_drawdown)

    def to_summary(self) -> Dict[str, Any]:
        """Retourne un résumé pour l'API."""
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "ticker": self.ticker,
            "period": f"{self.start_date} to {self.end_date}",
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "profit_factor": self.profit_factor,
            "is_profitable": self.is_profitable,
            "created_at": self.created_at,
        }


class BacktestRepository(BaseRepository[BacktestResult]):
    """Repository pour les résultats de backtests."""

    @property
    def table_name(self) -> str:
        return "backtest_results"

    def _row_to_entity(self, row: Any) -> BacktestResult:
        """Convertit une ligne SQLite en BacktestResult."""

        def parse_json(value: Optional[str], default: Any) -> Any:
            if not value:
                return default
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default

        parameters = parse_json(row["parameters"], {})
        equity_data = parse_json(row["equity_curve"], [])
        trades_data = parse_json(row["trades_data"], [])

        equity_curve = [
            EquityPoint(
                date=p.get("date", ""),
                equity=p.get("equity", 0),
                drawdown=p.get("drawdown", 0),
            )
            for p in equity_data
        ]

        trades = [
            BacktestTrade(
                entry_date=t.get("entry_date", ""),
                exit_date=t.get("exit_date", ""),
                direction=t.get("direction", "long"),
                entry_price=t.get("entry_price", 0),
                exit_price=t.get("exit_price", 0),
                pnl=t.get("pnl", 0),
                pnl_percent=t.get("pnl_percent", 0),
            )
            for t in trades_data
        ]

        return BacktestResult(
            id=row["id"],
            strategy_name=row["strategy_name"],
            ticker=row["ticker"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            initial_capital=row["initial_capital"],
            final_capital=row["final_capital"],
            total_return=row["total_return"],
            annualized_return=row["annualized_return"],
            sharpe_ratio=row["sharpe_ratio"],
            sortino_ratio=row["sortino_ratio"],
            max_drawdown=row["max_drawdown"],
            max_drawdown_duration=row["max_drawdown_duration"],
            total_trades=row["total_trades"] or 0,
            winning_trades=row["winning_trades"] or 0,
            losing_trades=row["losing_trades"] or 0,
            win_rate=row["win_rate"],
            avg_win=row["avg_win"],
            avg_loss=row["avg_loss"],
            profit_factor=row["profit_factor"],
            expectancy=row["expectancy"],
            parameters=parameters,
            equity_curve=equity_curve,
            trades_data=trades,
            created_at=row["created_at"],
        )

    def _entity_to_dict(self, entity: BacktestResult) -> Dict[str, Any]:
        """Convertit un BacktestResult en dictionnaire."""

        def equity_to_dict(ep: EquityPoint) -> Dict:
            return {"date": ep.date, "equity": ep.equity, "drawdown": ep.drawdown}

        def trade_to_dict(t: BacktestTrade) -> Dict:
            return {
                "entry_date": t.entry_date,
                "exit_date": t.exit_date,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
            }

        return {
            "id": entity.id,
            "strategy_name": entity.strategy_name,
            "ticker": entity.ticker.upper(),
            "start_date": entity.start_date,
            "end_date": entity.end_date,
            "initial_capital": entity.initial_capital,
            "final_capital": entity.final_capital,
            "total_return": entity.total_return,
            "annualized_return": entity.annualized_return,
            "sharpe_ratio": entity.sharpe_ratio,
            "sortino_ratio": entity.sortino_ratio,
            "max_drawdown": entity.max_drawdown,
            "max_drawdown_duration": entity.max_drawdown_duration,
            "total_trades": entity.total_trades,
            "winning_trades": entity.winning_trades,
            "losing_trades": entity.losing_trades,
            "win_rate": entity.win_rate,
            "avg_win": entity.avg_win,
            "avg_loss": entity.avg_loss,
            "profit_factor": entity.profit_factor,
            "expectancy": entity.expectancy,
            "parameters": json.dumps(entity.parameters),
            "equity_curve": json.dumps([equity_to_dict(ep) for ep in entity.equity_curve]),
            "trades_data": json.dumps([trade_to_dict(t) for t in entity.trades_data]),
            "created_at": entity.created_at,
        }

    async def save(self, result: BacktestResult) -> BacktestResult:
        """
        Sauvegarde un résultat de backtest.

        Args:
            result: Résultat à sauvegarder

        Returns:
            Résultat sauvegardé
        """
        data = self._entity_to_dict(result)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])

        await self.db.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(data.values())
        )

        logger.info(f"Backtest sauvegardé: {result.strategy_name} sur {result.ticker}")
        return result

    async def get_by_strategy(self, strategy_name: str) -> List[BacktestResult]:
        """
        Récupère les résultats pour une stratégie.

        Args:
            strategy_name: Nom de la stratégie

        Returns:
            Liste des résultats
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE strategy_name = ?
            ORDER BY created_at DESC
            """,
            (strategy_name,)
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_by_ticker(self, ticker: str) -> List[BacktestResult]:
        """
        Récupère les résultats pour un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            Liste des résultats
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE ticker = ?
            ORDER BY created_at DESC
            """,
            (ticker.upper(),)
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_best_by_metric(
        self,
        metric: str = "sharpe_ratio",
        limit: int = 10
    ) -> List[BacktestResult]:
        """
        Récupère les meilleurs résultats par métrique.

        Args:
            metric: Métrique de tri (sharpe_ratio, total_return, profit_factor)
            limit: Nombre maximum de résultats

        Returns:
            Liste des meilleurs résultats
        """
        allowed_metrics = ["sharpe_ratio", "total_return", "profit_factor", "win_rate", "expectancy"]
        if metric not in allowed_metrics:
            metric = "sharpe_ratio"

        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE {metric} IS NOT NULL
            ORDER BY {metric} DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [self._row_to_entity(row) for row in rows]

    async def compare_strategies(
        self,
        strategy_names: List[str],
        ticker: str
    ) -> List[Dict[str, Any]]:
        """
        Compare plusieurs stratégies sur un même ticker.

        Args:
            strategy_names: Noms des stratégies à comparer
            ticker: Symbole du ticker

        Returns:
            Comparaison des stratégies
        """
        results = []

        for strategy in strategy_names:
            rows = await self.db.fetch_all(
                f"""
                SELECT * FROM {self.table_name}
                WHERE strategy_name = ? AND ticker = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (strategy, ticker.upper())
            )

            if rows:
                result = self._row_to_entity(rows[0])
                results.append({
                    "strategy": strategy,
                    "total_return": result.total_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "profit_factor": result.profit_factor,
                    "total_trades": result.total_trades,
                })

        # Trier par Sharpe ratio
        return sorted(results, key=lambda x: x.get("sharpe_ratio") or 0, reverse=True)

    async def get_strategy_stats(self) -> List[Dict[str, Any]]:
        """
        Calcule les statistiques agrégées par stratégie.

        Returns:
            Statistiques par stratégie
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT
                strategy_name,
                COUNT(*) as backtest_count,
                AVG(total_return) as avg_return,
                AVG(sharpe_ratio) as avg_sharpe,
                AVG(max_drawdown) as avg_drawdown,
                AVG(win_rate) as avg_win_rate,
                SUM(CASE WHEN total_return > 0 THEN 1 ELSE 0 END) as profitable_count
            FROM {self.table_name}
            GROUP BY strategy_name
            ORDER BY avg_sharpe DESC
            """
        )

        return [
            {
                "strategy_name": row["strategy_name"],
                "backtest_count": row["backtest_count"],
                "avg_return": round(row["avg_return"] or 0, 2),
                "avg_sharpe": round(row["avg_sharpe"] or 0, 2),
                "avg_drawdown": round(row["avg_drawdown"] or 0, 2),
                "avg_win_rate": round(row["avg_win_rate"] or 0, 2),
                "profitable_ratio": round(
                    row["profitable_count"] / row["backtest_count"] * 100, 1
                ) if row["backtest_count"] > 0 else 0,
            }
            for row in rows
        ]
