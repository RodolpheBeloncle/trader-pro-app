"""
Repository pour les alertes de prix.

Gère le CRUD des alertes avec support pour:
- Création/modification d'alertes
- Récupération des alertes actives
- Marquage comme déclenchée
- Filtrage par ticker
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum

from src.infrastructure.database.repositories.base import BaseRepository
from src.infrastructure.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types d'alertes supportés."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PERCENT_CHANGE = "percent_change"


@dataclass
class Alert:
    """
    Entité Alert pour les notifications de prix.

    Attributs:
        id: Identifiant unique
        ticker: Symbole du ticker (ex: AAPL)
        alert_type: Type d'alerte (price_above, price_below, percent_change)
        target_value: Valeur cible (prix ou pourcentage)
        current_value: Valeur actuelle au moment de la création
        is_active: Si l'alerte est active
        is_triggered: Si l'alerte a été déclenchée
        triggered_at: Date/heure de déclenchement
        notification_sent: Si la notification a été envoyée
        notes: Notes personnelles
        created_at: Date de création
        updated_at: Date de modification
    """

    id: str
    ticker: str
    alert_type: AlertType
    target_value: float
    current_value: Optional[float] = None
    is_active: bool = True
    is_triggered: bool = False
    triggered_at: Optional[str] = None
    notification_sent: bool = False
    notes: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_price_above(self) -> bool:
        """Vérifie si c'est une alerte prix au-dessus."""
        return self.alert_type == AlertType.PRICE_ABOVE

    @property
    def is_price_below(self) -> bool:
        """Vérifie si c'est une alerte prix en-dessous."""
        return self.alert_type == AlertType.PRICE_BELOW

    def should_trigger(self, current_price: float) -> bool:
        """
        Vérifie si l'alerte devrait être déclenchée.

        Args:
            current_price: Prix actuel du ticker

        Returns:
            True si l'alerte doit être déclenchée
        """
        if not self.is_active or self.is_triggered:
            return False

        if self.alert_type == AlertType.PRICE_ABOVE:
            return current_price >= self.target_value
        elif self.alert_type == AlertType.PRICE_BELOW:
            return current_price <= self.target_value
        elif self.alert_type == AlertType.PERCENT_CHANGE:
            if self.current_value is None or self.current_value == 0:
                return False
            change = ((current_price - self.current_value) / self.current_value) * 100
            return abs(change) >= abs(self.target_value)

        return False

    def format_message(self, current_price: float) -> str:
        """
        Formate le message de notification.

        Args:
            current_price: Prix actuel

        Returns:
            Message formaté pour Telegram
        """
        emoji = "🔔"
        if self.alert_type == AlertType.PRICE_ABOVE:
            emoji = "📈"
            condition = f"au-dessus de {self.target_value:.2f}"
        elif self.alert_type == AlertType.PRICE_BELOW:
            emoji = "📉"
            condition = f"en-dessous de {self.target_value:.2f}"
        else:
            emoji = "📊"
            change = ((current_price - self.current_value) / self.current_value) * 100
            condition = f"variation de {change:.2f}%"

        message = (
            f"{emoji} <b>Alerte {self.ticker}</b>\n\n"
            f"Prix actuel: <code>{current_price:.2f}</code>\n"
            f"Condition: {condition}\n"
        )

        if self.notes:
            message += f"\n📝 {self.notes}"

        return message


class AlertRepository(BaseRepository[Alert]):
    """Repository pour les alertes de prix."""

    @property
    def table_name(self) -> str:
        return "alerts"

    def _row_to_entity(self, row: Any) -> Alert:
        """Convertit une ligne SQLite en Alert."""
        # Convertir alert_type en enum de manière defensive
        alert_type_raw = row["alert_type"]
        try:
            alert_type = AlertType(alert_type_raw) if isinstance(alert_type_raw, str) else alert_type_raw
        except ValueError:
            logger.warning(f"Unknown alert_type: {alert_type_raw}, defaulting to PRICE_ABOVE")
            alert_type = AlertType.PRICE_ABOVE

        return Alert(
            id=row["id"],
            ticker=row["ticker"],
            alert_type=alert_type,
            target_value=row["target_value"],
            current_value=row["current_value"],
            is_active=bool(row["is_active"]),
            is_triggered=bool(row["is_triggered"]),
            triggered_at=row["triggered_at"],
            notification_sent=bool(row["notification_sent"]),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _entity_to_dict(self, entity: Alert) -> Dict[str, Any]:
        """Convertit une Alert en dictionnaire."""
        alert_type_str = entity.alert_type.value if hasattr(entity.alert_type, 'value') else str(entity.alert_type)
        return {
            "id": entity.id,
            "ticker": entity.ticker.upper(),
            "alert_type": alert_type_str,
            "target_value": entity.target_value,
            "current_value": entity.current_value,
            "is_active": entity.is_active,
            "is_triggered": entity.is_triggered,
            "triggered_at": entity.triggered_at,
            "notification_sent": entity.notification_sent,
            "notes": entity.notes,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        }

    async def create(
        self,
        ticker: str,
        alert_type: AlertType,
        target_value: float,
        current_value: Optional[float] = None,
        notes: Optional[str] = None
    ) -> Alert:
        """
        Crée une nouvelle alerte.

        Args:
            ticker: Symbole du ticker
            alert_type: Type d'alerte
            target_value: Valeur cible
            current_value: Valeur actuelle (pour percent_change)
            notes: Notes personnelles

        Returns:
            Alert créée
        """
        alert = Alert(
            id=self.generate_id(),
            ticker=ticker.upper(),
            alert_type=alert_type,
            target_value=target_value,
            current_value=current_value,
            notes=notes,
        )

        data = self._entity_to_dict(alert)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])

        await self.db.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(data.values())
        )

        alert_type_str = alert.alert_type.value if hasattr(alert.alert_type, 'value') else str(alert.alert_type)
        logger.info(f"Alerte créée: {alert.ticker} {alert_type_str} {alert.target_value}")
        return alert

    async def update(self, alert: Alert) -> Alert:
        """
        Met à jour une alerte existante.

        Args:
            alert: Alert avec les nouvelles valeurs

        Returns:
            Alert mise à jour
        """
        data = self._entity_to_dict(alert)
        del data["id"]
        del data["created_at"]
        data["updated_at"] = self.now_iso()

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])

        await self.db.execute(
            f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
            tuple(data.values()) + (alert.id,)
        )

        return alert

    async def get_active(self) -> List[Alert]:
        """
        Récupère toutes les alertes actives non déclenchées.

        Returns:
            Liste des alertes actives
        """
        rows = await self.db.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE is_active = 1 AND is_triggered = 0"
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_by_ticker(self, ticker: str) -> List[Alert]:
        """
        Récupère les alertes pour un ticker.

        Args:
            ticker: Symbole du ticker

        Returns:
            Liste des alertes
        """
        rows = await self.db.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE ticker = ? ORDER BY created_at DESC",
            (ticker.upper(),)
        )
        return [self._row_to_entity(row) for row in rows]

    async def mark_triggered(
        self,
        alert_id: str,
        notification_sent: bool = False
    ) -> Optional[Alert]:
        """
        Marque une alerte comme déclenchée.

        Args:
            alert_id: ID de l'alerte
            notification_sent: Si la notification a été envoyée

        Returns:
            Alert mise à jour ou None
        """
        now = self.now_iso()

        await self.db.execute(
            f"""
            UPDATE {self.table_name}
            SET is_triggered = 1, triggered_at = ?, notification_sent = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, notification_sent, now, alert_id)
        )

        return await self.get_by_id(alert_id)

    async def mark_notification_sent(self, alert_id: str) -> None:
        """
        Marque la notification comme envoyée.

        Args:
            alert_id: ID de l'alerte
        """
        await self.db.execute(
            f"UPDATE {self.table_name} SET notification_sent = 1 WHERE id = ?",
            (alert_id,)
        )

    async def deactivate(self, alert_id: str) -> None:
        """
        Désactive une alerte.

        Args:
            alert_id: ID de l'alerte
        """
        await self.db.execute(
            f"UPDATE {self.table_name} SET is_active = 0, updated_at = ? WHERE id = ?",
            (self.now_iso(), alert_id)
        )

    async def get_triggered_not_sent(self) -> List[Alert]:
        """
        Récupère les alertes déclenchées mais non notifiées.

        Returns:
            Liste des alertes à notifier
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM {self.table_name}
            WHERE is_triggered = 1 AND notification_sent = 0
            """
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Retourne des statistiques sur les alertes.

        Returns:
            Dictionnaire de statistiques
        """
        total = await self.count()
        active = await self.count("is_active = 1 AND is_triggered = 0")
        triggered = await self.count("is_triggered = 1")

        return {
            "total": total,
            "active": active,
            "triggered": triggered,
            "inactive": total - active - triggered,
        }
