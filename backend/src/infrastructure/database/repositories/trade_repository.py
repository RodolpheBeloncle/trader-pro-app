"""
Repository pour les trades du journal.

Gère le CRUD des trades avec support pour:
- Création/modification de trades
- Clôture avec calcul P&L
- Statistiques de performance
- Filtrage par statut, ticker, période
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Any, Dict
from enum import Enum

from src.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class TradeDirection(str, Enum):
    """Direction du trade."""
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    """Statut du trade."""
    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class Trade:
    """
    Entité Trade pour le journal de trading.

    Attributs:
        id: Identifiant unique
        ticker: Symbole du ticker
        direction: long ou short
        status: planned, active, closed, cancelled
        entry_price: Prix d'entrée
        exit_price: Prix de sortie
        stop_loss: Stop loss
        take_profit: Take profit
        position_size: Taille de position (nombre d'actions/contrats)
        entry_time: Date/heure d'entrée
        exit_time: Date/heure de sortie
        gross_pnl: P&L brut
        net_pnl: P&L net (après frais)
        fees: Frais de transaction
        r_multiple: Multiple de R (reward/risk)
    """

    id: str
    ticker: str
    direction: TradeDirection
    status: TradeStatus
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[int] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None
    fees: float = 0.0
    r_multiple: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_long(self) -> bool:
        """Vérifie si c'est un trade long."""
        return self.direction == TradeDirection.LONG

    @property
    def is_closed(self) -> bool:
        """Vérifie si le trade est clôturé."""
        return self.status == TradeStatus.CLOSED

    @property
    def is_winner(self) -> bool:
        """Vérifie si c'est un trade gagnant."""
        return self.net_pnl is not None and self.net_pnl > 0

    @property
    def risk_amount(self) -> Optional[float]:
        """Calcule le risque en valeur absolue."""
        if self.entry_price is None or self.stop_loss is None or self.position_size is None:
            return None
        return abs(self.entry_price - self.stop_loss) * self.position_size

    @property
    def reward_amount(self) -> Optional[float]:
        """Calcule le reward potentiel en valeur absolue."""
        if self.entry_price is None or self.take_profit is None or self.position_size is None:
            return None
        return abs(self.take_profit - self.entry_price) * self.position_size

    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """Calcule le ratio risk/reward."""
        risk = self.risk_amount
        reward = self.reward_amount
        if risk is None or reward is None or risk == 0:
            return None
        return reward / risk

    def calculate_pnl(self, exit_price: float, fees: float = 0.0) -> Dict[str, float]:
        """
        Calcule le P&L pour un prix de sortie donné.

        Args:
            exit_price: Prix de sortie
            fees: Frais de transaction

        Returns:
            Dictionnaire avec gross_pnl, net_pnl, r_multiple
        """
        if self.entry_price is None or self.position_size is None:
            return {"gross_pnl": 0, "net_pnl": 0, "r_multiple": 0}

        if self.is_long:
            gross_pnl = (exit_price - self.entry_price) * self.position_size
        else:
            gross_pnl = (self.entry_price - exit_price) * self.position_size

        net_pnl = gross_pnl - fees

        # Calcul du R-multiple
        risk = self.risk_amount
        r_multiple = net_pnl / risk if risk and risk > 0 else 0

        return {
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "r_multiple": round(r_multiple, 2),
        }


class TradeRepository(BaseRepository[Trade]):
    """Repository pour les trades du journal."""

    @property
    def table_name(self) -> str:
        return "trades"

    def _row_to_entity(self, row: Any) -> Trade:
        """Convertit une ligne SQLite en Trade."""
        return Trade(
            id=row["id"],
            ticker=row["ticker"],
            direction=TradeDirection(row["direction"]),
            status=TradeStatus(row["status"]),
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            position_size=row["position_size"],
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            gross_pnl=row["gross_pnl"],
            net_pnl=row["net_pnl"],
            fees=row["fees"] or 0.0,
            r_multiple=row["r_multiple"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _entity_to_dict(self, entity: Trade) -> Dict[str, Any]:
        """Convertit un Trade en dictionnaire."""
        return {
            "id": entity.id,
            "ticker": entity.ticker.upper(),
            "direction": entity.direction.value,
            "status": entity.status.value,
            "entry_price": entity.entry_price,
            "exit_price": entity.exit_price,
            "stop_loss": entity.stop_loss,
            "take_profit": entity.take_profit,
            "position_size": entity.position_size,
            "entry_time": entity.entry_time,
            "exit_time": entity.exit_time,
            "gross_pnl": entity.gross_pnl,
            "net_pnl": entity.net_pnl,
            "fees": entity.fees,
            "r_multiple": entity.r_multiple,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        }

    async def create(
        self,
        ticker: str,
        direction: TradeDirection,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[int] = None,
        status: TradeStatus = TradeStatus.PLANNED,
    ) -> Trade:
        """
        Crée un nouveau trade.

        Args:
            ticker: Symbole du ticker
            direction: Direction (long/short)
            entry_price: Prix d'entrée
            stop_loss: Stop loss
            take_profit: Take profit
            position_size: Taille de position
            status: Statut initial

        Returns:
            Trade créé
        """
        trade = Trade(
            id=self.generate_id(),
            ticker=ticker.upper(),
            direction=direction,
            status=status,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            entry_time=self.now_iso() if status == TradeStatus.ACTIVE else None,
        )

        data = self._entity_to_dict(trade)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])

        await self.db.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(data.values())
        )

        logger.info(f"Trade créé: {trade.ticker} {trade.direction.value}")
        return trade

    async def update(self, trade: Trade) -> Trade:
        """
        Met à jour un trade existant.

        Args:
            trade: Trade avec les nouvelles valeurs

        Returns:
            Trade mis à jour
        """
        data = self._entity_to_dict(trade)
        del data["id"]
        del data["created_at"]
        data["updated_at"] = self.now_iso()

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])

        await self.db.execute(
            f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
            tuple(data.values()) + (trade.id,)
        )

        return trade

    async def activate(self, trade_id: str, entry_price: float) -> Optional[Trade]:
        """
        Active un trade planifié.

        Args:
            trade_id: ID du trade
            entry_price: Prix d'entrée réel

        Returns:
            Trade activé ou None
        """
        now = self.now_iso()

        await self.db.execute(
            f"""
            UPDATE {self.table_name}
            SET status = ?, entry_price = ?, entry_time = ?, updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (TradeStatus.ACTIVE.value, entry_price, now, now, trade_id, TradeStatus.PLANNED.value)
        )

        return await self.get_by_id(trade_id)

    async def close(
        self,
        trade_id: str,
        exit_price: float,
        fees: float = 0.0
    ) -> Optional[Trade]:
        """
        Clôture un trade avec calcul du P&L.

        Args:
            trade_id: ID du trade
            exit_price: Prix de sortie
            fees: Frais de transaction

        Returns:
            Trade clôturé ou None
        """
        trade = await self.get_by_id(trade_id)
        if trade is None or trade.status != TradeStatus.ACTIVE:
            return None

        pnl = trade.calculate_pnl(exit_price, fees)
        now = self.now_iso()

        await self.db.execute(
            f"""
            UPDATE {self.table_name}
            SET status = ?, exit_price = ?, exit_time = ?,
                gross_pnl = ?, net_pnl = ?, fees = ?, r_multiple = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                TradeStatus.CLOSED.value,
                exit_price,
                now,
                pnl["gross_pnl"],
                pnl["net_pnl"],
                fees,
                pnl["r_multiple"],
                now,
                trade_id,
            )
        )

        logger.info(f"Trade clôturé: {trade.ticker} P&L={pnl['net_pnl']}")
        return await self.get_by_id(trade_id)

    async def cancel(self, trade_id: str) -> Optional[Trade]:
        """
        Annule un trade.

        Args:
            trade_id: ID du trade

        Returns:
            Trade annulé ou None
        """
        await self.db.execute(
            f"UPDATE {self.table_name} SET status = ?, updated_at = ? WHERE id = ?",
            (TradeStatus.CANCELLED.value, self.now_iso(), trade_id)
        )
        return await self.get_by_id(trade_id)

    async def get_by_status(self, status: TradeStatus) -> List[Trade]:
        """
        Récupère les trades par statut.

        Args:
            status: Statut recherché

        Returns:
            Liste des trades
        """
        rows = await self.db.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE status = ? ORDER BY created_at DESC",
            (status.value,)
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_by_ticker(self, ticker: str) -> List[Trade]:
        """
        Récupère les trades pour un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            Liste des trades
        """
        rows = await self.db.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE ticker = ? ORDER BY created_at DESC",
            (ticker.upper(),)
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_closed_between(
        self,
        start_date: date,
        end_date: date
    ) -> List[Trade]:
        """
        Récupère les trades clôturés dans une période.

        Args:
            start_date: Date de début
            end_date: Date de fin

        Returns:
            Liste des trades
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE status = ? AND DATE(exit_time) BETWEEN ? AND ?
            ORDER BY exit_time DESC
            """,
            (TradeStatus.CLOSED.value, start_date.isoformat(), end_date.isoformat())
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Calcule les statistiques globales de trading.

        Returns:
            Dictionnaire avec les métriques de performance
        """
        closed_trades = await self.get_by_status(TradeStatus.CLOSED)

        if not closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "avg_r_multiple": 0.0,
                "expectancy": 0.0,
            }

        winners = [t for t in closed_trades if t.is_winner]
        losers = [t for t in closed_trades if not t.is_winner]

        total_wins = sum(t.net_pnl for t in winners if t.net_pnl)
        total_losses = abs(sum(t.net_pnl for t in losers if t.net_pnl))

        avg_win = total_wins / len(winners) if winners else 0
        avg_loss = total_losses / len(losers) if losers else 0

        win_rate = len(winners) / len(closed_trades) if closed_trades else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        # Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        r_multiples = [t.r_multiple for t in closed_trades if t.r_multiple is not None]
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0

        return {
            "total_trades": len(closed_trades),
            "winning_trades": len(winners),
            "losing_trades": len(losers),
            "win_rate": round(win_rate * 100, 2),
            "total_pnl": round(total_wins - total_losses, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_r_multiple": round(avg_r, 2),
            "expectancy": round(expectancy, 2),
        }

    async def get_monthly_stats(self, year: int, month: int) -> Dict[str, Any]:
        """
        Calcule les statistiques pour un mois donné.

        Args:
            year: Année
            month: Mois (1-12)

        Returns:
            Statistiques mensuelles
        """
        from calendar import monthrange

        start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end = date(year, month, last_day)

        trades = await self.get_closed_between(start, end)

        if not trades:
            return {
                "year": year,
                "month": month,
                "trades": 0,
                "pnl": 0.0,
                "win_rate": 0.0,
            }

        total_pnl = sum(t.net_pnl for t in trades if t.net_pnl)
        winners = sum(1 for t in trades if t.is_winner)

        return {
            "year": year,
            "month": month,
            "trades": len(trades),
            "pnl": round(total_pnl, 2),
            "win_rate": round(winners / len(trades) * 100, 2),
        }
