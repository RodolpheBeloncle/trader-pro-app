"""
Classe de base pour les repositories.

Fournit les méthodes communes de CRUD et la gestion de la connexion.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, TypeVar, Optional, List, Any, Dict

from src.infrastructure.database.connection import get_database, DatabaseConnection

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Classe de base abstraite pour tous les repositories.

    Fournit:
    - Accès à la base de données
    - Génération d'ID
    - Méthodes CRUD de base
    """

    def __init__(self, db: Optional[DatabaseConnection] = None):
        """
        Initialise le repository.

        Args:
            db: Instance DatabaseConnection. Par défaut: singleton global.
        """
        self._db = db or get_database()

    @property
    def db(self) -> DatabaseConnection:
        """Retourne la connexion à la base de données."""
        return self._db

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Nom de la table associée à ce repository."""
        pass

    @staticmethod
    def generate_id() -> str:
        """Génère un ID unique."""
        return str(uuid.uuid4())

    @staticmethod
    def now_iso() -> str:
        """Retourne la date/heure actuelle en ISO format."""
        return datetime.now().isoformat()

    @abstractmethod
    def _row_to_entity(self, row: Any) -> T:
        """
        Convertit une ligne de base de données en entité.

        Args:
            row: Ligne aiosqlite.Row

        Returns:
            Entité typée
        """
        pass

    @abstractmethod
    def _entity_to_dict(self, entity: T) -> Dict[str, Any]:
        """
        Convertit une entité en dictionnaire pour insertion.

        Args:
            entity: Entité à convertir

        Returns:
            Dictionnaire des valeurs
        """
        pass

    async def get_by_id(self, id: str) -> Optional[T]:
        """
        Récupère une entité par son ID.

        Args:
            id: Identifiant unique

        Returns:
            Entité ou None si non trouvée
        """
        row = await self.db.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE id = ?",
            (id,)
        )
        if row is None:
            return None
        return self._row_to_entity(row)

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC"
    ) -> List[T]:
        """
        Récupère toutes les entités avec pagination.

        Args:
            limit: Nombre maximum d'entités
            offset: Décalage pour la pagination
            order_by: Clause ORDER BY

        Returns:
            Liste d'entités
        """
        rows = await self.db.fetch_all(
            f"SELECT * FROM {self.table_name} ORDER BY {order_by} LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [self._row_to_entity(row) for row in rows]

    async def count(self, where: str = "1=1", params: tuple = ()) -> int:
        """
        Compte le nombre d'entités.

        Args:
            where: Clause WHERE
            params: Paramètres de la clause

        Returns:
            Nombre d'entités
        """
        row = await self.db.fetch_one(
            f"SELECT COUNT(*) as count FROM {self.table_name} WHERE {where}",
            params
        )
        return row["count"] if row else 0

    async def delete(self, id: str) -> bool:
        """
        Supprime une entité par son ID.

        Args:
            id: Identifiant unique

        Returns:
            True si supprimée, False si non trouvée
        """
        cursor = await self.db.execute(
            f"DELETE FROM {self.table_name} WHERE id = ?",
            (id,)
        )
        return cursor.rowcount > 0

    async def delete_all(self) -> int:
        """
        Supprime toutes les entités.

        Returns:
            Nombre d'entités supprimées
        """
        cursor = await self.db.execute(f"DELETE FROM {self.table_name}")
        return cursor.rowcount

    async def exists(self, id: str) -> bool:
        """
        Vérifie si une entité existe.

        Args:
            id: Identifiant unique

        Returns:
            True si existe
        """
        row = await self.db.fetch_one(
            f"SELECT 1 FROM {self.table_name} WHERE id = ? LIMIT 1",
            (id,)
        )
        return row is not None
