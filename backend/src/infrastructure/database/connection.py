"""
Gestionnaire de connexion SQLite async avec pattern singleton.

Ce module gère:
- Connexion unique à la base de données SQLite
- Pool de connexions via aiosqlite
- Transactions et gestion des erreurs
- Initialisation automatique au démarrage

UTILISATION:
    from src.infrastructure.database.connection import get_database

    db = get_database()
    async with db.connection() as conn:
        await conn.execute("SELECT * FROM alerts")
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, AsyncGenerator

import aiosqlite

from src.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Gestionnaire de connexion SQLite async.

    Pattern Singleton pour garantir une seule instance.
    Thread-safe grâce à aiosqlite.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le gestionnaire.

        Args:
            db_path: Chemin vers la base de données. Par défaut depuis settings.
        """
        self._db_path = Path(db_path or settings.DATABASE_PATH)
        self._connection: Optional[aiosqlite.Connection] = None
        self._initialized = False

        # Créer le répertoire parent si nécessaire
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        """Retourne le chemin de la base de données."""
        return self._db_path

    @property
    def is_initialized(self) -> bool:
        """Vérifie si la base est initialisée."""
        return self._initialized

    async def connect(self) -> aiosqlite.Connection:
        """
        Ouvre une connexion à la base de données.

        Returns:
            Connection aiosqlite
        """
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                self._db_path,
                check_same_thread=False
            )
            # Activer les clés étrangères
            await self._connection.execute("PRAGMA foreign_keys = ON")
            # Mode WAL pour de meilleures performances concurrentes
            await self._connection.execute("PRAGMA journal_mode = WAL")
            # Timeout pour éviter les erreurs "database is locked" (5 secondes)
            await self._connection.execute("PRAGMA busy_timeout = 5000")
            # Row factory pour accès par nom de colonne
            self._connection.row_factory = aiosqlite.Row

            logger.info(f"Connexion SQLite ouverte: {self._db_path}")

        return self._connection

    async def disconnect(self) -> None:
        """Ferme la connexion à la base de données."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Connexion SQLite fermée")

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Context manager pour obtenir une connexion.

        Usage:
            async with db.connection() as conn:
                await conn.execute(...)

        Yields:
            Connection aiosqlite
        """
        conn = await self.connect()
        try:
            yield conn
        finally:
            pass  # La connexion reste ouverte (singleton)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Context manager pour une transaction avec commit/rollback automatique.

        Usage:
            async with db.transaction() as conn:
                await conn.execute(...)
                # Commit automatique si pas d'exception

        Yields:
            Connection aiosqlite avec transaction
        """
        conn = await self.connect()
        try:
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Transaction rollback: {e}")
            raise

    async def execute(
        self,
        query: str,
        parameters: tuple = ()
    ) -> aiosqlite.Cursor:
        """
        Exécute une requête SQL.

        Args:
            query: Requête SQL
            parameters: Paramètres de la requête

        Returns:
            Cursor avec les résultats
        """
        conn = await self.connect()
        cursor = await conn.execute(query, parameters)
        await conn.commit()
        return cursor

    async def execute_many(
        self,
        query: str,
        parameters: list[tuple]
    ) -> None:
        """
        Exécute une requête SQL avec plusieurs jeux de paramètres.

        Args:
            query: Requête SQL
            parameters: Liste de tuples de paramètres
        """
        conn = await self.connect()
        await conn.executemany(query, parameters)
        await conn.commit()

    async def fetch_one(
        self,
        query: str,
        parameters: tuple = ()
    ) -> Optional[aiosqlite.Row]:
        """
        Exécute une requête et retourne une seule ligne.

        Args:
            query: Requête SQL
            parameters: Paramètres de la requête

        Returns:
            Row ou None
        """
        conn = await self.connect()
        cursor = await conn.execute(query, parameters)
        return await cursor.fetchone()

    async def fetch_all(
        self,
        query: str,
        parameters: tuple = ()
    ) -> list[aiosqlite.Row]:
        """
        Exécute une requête et retourne toutes les lignes.

        Args:
            query: Requête SQL
            parameters: Paramètres de la requête

        Returns:
            Liste de Rows
        """
        conn = await self.connect()
        cursor = await conn.execute(query, parameters)
        return await cursor.fetchall()

    def mark_initialized(self) -> None:
        """Marque la base comme initialisée."""
        self._initialized = True


# Instance singleton
_database: Optional[DatabaseConnection] = None


def get_database() -> DatabaseConnection:
    """
    Retourne l'instance singleton de la base de données.

    Returns:
        DatabaseConnection initialisée
    """
    global _database
    if _database is None:
        _database = DatabaseConnection()
    return _database


async def init_database() -> DatabaseConnection:
    """
    Initialise la base de données et exécute les migrations.

    À appeler au démarrage de l'application.

    Returns:
        DatabaseConnection initialisée avec schéma
    """
    from src.infrastructure.database.migrations import run_migrations

    db = get_database()
    await db.connect()
    await run_migrations(db)
    db.mark_initialized()

    logger.info("Base de données initialisée")
    return db


async def close_database() -> None:
    """Ferme la connexion à la base de données."""
    global _database
    if _database is not None:
        await _database.disconnect()
        _database = None
