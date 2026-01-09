"""
Repository pour les entrées de journal de trading.

Gère le CRUD des analyses pré/post trade avec support pour:
- Analyse de marché et setup
- Suivi émotionnel
- Leçons apprises
- Score de qualité de trade
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum

from src.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ExecutionQuality(str, Enum):
    """Qualité d'exécution du trade."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"


class EmotionalState(str, Enum):
    """État émotionnel pendant le trade."""
    CALM = "calm"
    CONFIDENT = "confident"
    ANXIOUS = "anxious"
    FOMO = "fomo"
    REVENGE = "revenge"


class ProcessCompliance(str, Enum):
    """Respect du processus de trading."""
    FOLLOWED = "followed"
    DEVIATED = "deviated"
    IGNORED = "ignored"


@dataclass
class JournalEntry:
    """
    Entrée de journal pour un trade.

    Attributs:
        id: Identifiant unique
        trade_id: ID du trade associé

        # Analyse pré-trade
        market_regime: Régime de marché (trending, ranging, volatile)
        market_bias: Biais de marché (bullish, bearish, neutral)
        setup_type: Type de setup (breakout, pullback, reversal, etc.)
        timeframe: Timeframe principal (1m, 5m, 1h, 4h, D)
        trade_thesis: Thèse du trade en texte libre
        confluence_factors: Facteurs de confluence (JSON array)

        # Exécution
        execution_quality: Qualité d'exécution
        emotional_state: État émotionnel

        # Analyse post-trade
        process_compliance: Respect du processus
        mistakes: Erreurs commises (JSON array)
        what_went_well: Ce qui a bien fonctionné (JSON array)
        what_to_improve: Points d'amélioration (JSON array)
        lessons_learned: Leçons apprises
        trade_quality_score: Score de qualité (1-10)
    """

    id: str
    trade_id: str

    # Pré-trade
    market_regime: Optional[str] = None
    market_bias: Optional[str] = None
    setup_type: Optional[str] = None
    timeframe: Optional[str] = None
    trade_thesis: Optional[str] = None
    confluence_factors: List[str] = field(default_factory=list)

    # Exécution
    execution_quality: Optional[ExecutionQuality] = None
    emotional_state: Optional[EmotionalState] = None

    # Post-trade
    process_compliance: Optional[ProcessCompliance] = None
    mistakes: List[str] = field(default_factory=list)
    what_went_well: List[str] = field(default_factory=list)
    what_to_improve: List[str] = field(default_factory=list)
    lessons_learned: Optional[str] = None
    trade_quality_score: Optional[int] = None

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def has_pre_trade_analysis(self) -> bool:
        """Vérifie si l'analyse pré-trade est complète."""
        return bool(self.setup_type and self.trade_thesis)

    @property
    def has_post_trade_analysis(self) -> bool:
        """Vérifie si l'analyse post-trade est complète."""
        return self.trade_quality_score is not None


class JournalRepository(BaseRepository[JournalEntry]):
    """Repository pour les entrées de journal."""

    @property
    def table_name(self) -> str:
        return "journal_entries"

    def _row_to_entity(self, row: Any) -> JournalEntry:
        """Convertit une ligne SQLite en JournalEntry."""

        def parse_json_list(value: Optional[str]) -> List[str]:
            if not value:
                return []
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []

        execution_quality = None
        if row["execution_quality"]:
            execution_quality = ExecutionQuality(row["execution_quality"])

        emotional_state = None
        if row["emotional_state"]:
            emotional_state = EmotionalState(row["emotional_state"])

        process_compliance = None
        if row["process_compliance"]:
            process_compliance = ProcessCompliance(row["process_compliance"])

        return JournalEntry(
            id=row["id"],
            trade_id=row["trade_id"],
            market_regime=row["market_regime"],
            market_bias=row["market_bias"],
            setup_type=row["setup_type"],
            timeframe=row["timeframe"],
            trade_thesis=row["trade_thesis"],
            confluence_factors=parse_json_list(row["confluence_factors"]),
            execution_quality=execution_quality,
            emotional_state=emotional_state,
            process_compliance=process_compliance,
            mistakes=parse_json_list(row["mistakes"]),
            what_went_well=parse_json_list(row["what_went_well"]),
            what_to_improve=parse_json_list(row["what_to_improve"]),
            lessons_learned=row["lessons_learned"],
            trade_quality_score=row["trade_quality_score"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _entity_to_dict(self, entity: JournalEntry) -> Dict[str, Any]:
        """Convertit une JournalEntry en dictionnaire."""
        return {
            "id": entity.id,
            "trade_id": entity.trade_id,
            "market_regime": entity.market_regime,
            "market_bias": entity.market_bias,
            "setup_type": entity.setup_type,
            "timeframe": entity.timeframe,
            "trade_thesis": entity.trade_thesis,
            "confluence_factors": json.dumps(entity.confluence_factors) if entity.confluence_factors else None,
            "execution_quality": entity.execution_quality.value if entity.execution_quality else None,
            "emotional_state": entity.emotional_state.value if entity.emotional_state else None,
            "process_compliance": entity.process_compliance.value if entity.process_compliance else None,
            "mistakes": json.dumps(entity.mistakes) if entity.mistakes else None,
            "what_went_well": json.dumps(entity.what_went_well) if entity.what_went_well else None,
            "what_to_improve": json.dumps(entity.what_to_improve) if entity.what_to_improve else None,
            "lessons_learned": entity.lessons_learned,
            "trade_quality_score": entity.trade_quality_score,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        }

    async def create(
        self,
        trade_id: str,
        setup_type: Optional[str] = None,
        trade_thesis: Optional[str] = None,
        market_regime: Optional[str] = None,
        market_bias: Optional[str] = None,
        timeframe: Optional[str] = None,
        confluence_factors: Optional[List[str]] = None,
    ) -> JournalEntry:
        """
        Crée une nouvelle entrée de journal (pré-trade).

        Args:
            trade_id: ID du trade associé
            setup_type: Type de setup
            trade_thesis: Thèse du trade
            market_regime: Régime de marché
            market_bias: Biais de marché
            timeframe: Timeframe
            confluence_factors: Facteurs de confluence

        Returns:
            JournalEntry créée
        """
        entry = JournalEntry(
            id=self.generate_id(),
            trade_id=trade_id,
            setup_type=setup_type,
            trade_thesis=trade_thesis,
            market_regime=market_regime,
            market_bias=market_bias,
            timeframe=timeframe,
            confluence_factors=confluence_factors or [],
        )

        data = self._entity_to_dict(entry)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])

        await self.db.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(data.values())
        )

        logger.info(f"Entrée de journal créée pour trade {trade_id}")
        return entry

    async def update(self, entry: JournalEntry) -> JournalEntry:
        """
        Met à jour une entrée de journal.

        Args:
            entry: Entrée avec les nouvelles valeurs

        Returns:
            Entrée mise à jour
        """
        data = self._entity_to_dict(entry)
        del data["id"]
        del data["created_at"]
        data["updated_at"] = self.now_iso()

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])

        await self.db.execute(
            f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
            tuple(data.values()) + (entry.id,)
        )

        return entry

    async def get_by_trade_id(self, trade_id: str) -> Optional[JournalEntry]:
        """
        Récupère l'entrée de journal pour un trade.

        Args:
            trade_id: ID du trade

        Returns:
            JournalEntry ou None
        """
        row = await self.db.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE trade_id = ?",
            (trade_id,)
        )
        if row is None:
            return None
        return self._row_to_entity(row)

    async def delete_by_trade_id(self, trade_id: str) -> bool:
        """
        Supprime l'entrée de journal associée à un trade.

        Args:
            trade_id: ID du trade

        Returns:
            True si supprimé, False sinon
        """
        result = await self.db.execute(
            f"DELETE FROM {self.table_name} WHERE trade_id = ?",
            (trade_id,)
        )
        deleted = result.rowcount > 0 if hasattr(result, 'rowcount') else True
        if deleted:
            logger.info(f"Entrée de journal supprimée pour trade {trade_id}")
        return deleted

    async def add_post_trade_analysis(
        self,
        trade_id: str,
        execution_quality: ExecutionQuality,
        emotional_state: EmotionalState,
        process_compliance: ProcessCompliance,
        trade_quality_score: int,
        mistakes: Optional[List[str]] = None,
        what_went_well: Optional[List[str]] = None,
        what_to_improve: Optional[List[str]] = None,
        lessons_learned: Optional[str] = None,
    ) -> Optional[JournalEntry]:
        """
        Ajoute l'analyse post-trade à une entrée existante.

        Args:
            trade_id: ID du trade
            execution_quality: Qualité d'exécution
            emotional_state: État émotionnel
            process_compliance: Respect du processus
            trade_quality_score: Score de qualité (1-10)
            mistakes: Erreurs commises
            what_went_well: Ce qui a bien fonctionné
            what_to_improve: Points d'amélioration
            lessons_learned: Leçons apprises

        Returns:
            Entrée mise à jour ou None
        """
        entry = await self.get_by_trade_id(trade_id)
        if entry is None:
            return None

        entry.execution_quality = execution_quality
        entry.emotional_state = emotional_state
        entry.process_compliance = process_compliance
        entry.trade_quality_score = max(1, min(10, trade_quality_score))
        entry.mistakes = mistakes or []
        entry.what_went_well = what_went_well or []
        entry.what_to_improve = what_to_improve or []
        entry.lessons_learned = lessons_learned

        return await self.update(entry)

    async def get_by_setup_type(self, setup_type: str) -> List[JournalEntry]:
        """
        Récupère les entrées par type de setup.

        Args:
            setup_type: Type de setup

        Returns:
            Liste des entrées
        """
        rows = await self.db.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE setup_type = ? ORDER BY created_at DESC",
            (setup_type,)
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_lessons(self, limit: int = 20) -> List[str]:
        """
        Récupère les dernières leçons apprises.

        Args:
            limit: Nombre maximum de leçons

        Returns:
            Liste des leçons
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT lessons_learned FROM {self.table_name}
            WHERE lessons_learned IS NOT NULL AND lessons_learned != ''
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [row["lessons_learned"] for row in rows]

    async def get_common_mistakes(self) -> Dict[str, int]:
        """
        Analyse les erreurs les plus fréquentes.

        Returns:
            Dictionnaire erreur -> nombre d'occurrences
        """
        rows = await self.db.fetch_all(
            f"SELECT mistakes FROM {self.table_name} WHERE mistakes IS NOT NULL"
        )

        mistake_counts: Dict[str, int] = {}
        for row in rows:
            try:
                mistakes = json.loads(row["mistakes"])
                for mistake in mistakes:
                    mistake_counts[mistake] = mistake_counts.get(mistake, 0) + 1
            except json.JSONDecodeError:
                continue

        # Trier par fréquence
        return dict(sorted(mistake_counts.items(), key=lambda x: x[1], reverse=True))

    async def get_stats_by_setup(self) -> List[Dict[str, Any]]:
        """
        Calcule les statistiques par type de setup.

        Returns:
            Liste de stats par setup
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT
                j.setup_type,
                COUNT(*) as count,
                AVG(j.trade_quality_score) as avg_quality,
                SUM(CASE WHEN t.net_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(t.net_pnl) as total_pnl
            FROM {self.table_name} j
            JOIN trades t ON j.trade_id = t.id
            WHERE j.setup_type IS NOT NULL AND t.status = 'closed'
            GROUP BY j.setup_type
            ORDER BY total_pnl DESC
            """
        )

        return [
            {
                "setup_type": row["setup_type"],
                "count": row["count"],
                "avg_quality": round(row["avg_quality"] or 0, 1),
                "win_rate": round(row["wins"] / row["count"] * 100, 1) if row["count"] > 0 else 0,
                "total_pnl": round(row["total_pnl"] or 0, 2),
            }
            for row in rows
        ]

    async def get_emotional_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyse la performance par état émotionnel.

        Returns:
            Statistiques par état émotionnel
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT
                j.emotional_state,
                COUNT(*) as count,
                AVG(j.trade_quality_score) as avg_quality,
                SUM(CASE WHEN t.net_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(t.net_pnl) as total_pnl
            FROM {self.table_name} j
            JOIN trades t ON j.trade_id = t.id
            WHERE j.emotional_state IS NOT NULL AND t.status = 'closed'
            GROUP BY j.emotional_state
            """
        )

        return {
            row["emotional_state"]: {
                "count": row["count"],
                "avg_quality": round(row["avg_quality"] or 0, 1),
                "win_rate": round(row["wins"] / row["count"] * 100, 1) if row["count"] > 0 else 0,
                "total_pnl": round(row["total_pnl"] or 0, 2),
            }
            for row in rows
        }
