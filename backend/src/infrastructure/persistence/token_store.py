"""
Stockage sécurisé des tokens OAuth dans un fichier JSON chiffré.

Ce module implémente le repository pattern pour les tokens.
Les tokens sont chiffrés avec Fernet avant d'être stockés.

ARCHITECTURE:
- Couche INFRASTRUCTURE
- Implémente l'interface TokenRepository (définie dans application/interfaces)
- Stocke les tokens dans backend/data/tokens.json

SÉCURITÉ:
- Tous les tokens sont chiffrés au repos
- Le fichier JSON contient uniquement des données chiffrées
- La clé de chiffrement est dans .env (ENCRYPTION_KEY)

ÉVOLUTION:
- Pour passer à Redis/PostgreSQL, créer une nouvelle implémentation
  de TokenRepository sans modifier le reste de l'application

UTILISATION:
    from src.infrastructure.persistence.token_store import FileTokenStore

    store = FileTokenStore()

    # Sauvegarder
    await store.save_token("user1", "saxo", token_data)

    # Récupérer
    token = await store.get_token("user1", "saxo")

    # Supprimer
    await store.delete_token("user1", "saxo")
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import asyncio
from filelock import FileLock

from src.config.settings import settings
from src.infrastructure.persistence.encryption import (
    EncryptionService,
    get_encryption_service,
    EncryptionError
)
from src.domain.exceptions import TokenExpiredError, TokenInvalidError

logger = logging.getLogger(__name__)


@dataclass
class StoredToken:
    """
    Structure d'un token stocké.

    Attributs:
        access_token: Token d'accès pour les appels API
        refresh_token: Token pour rafraîchir l'access_token
        expires_at: Date d'expiration de l'access_token (ISO format)
        created_at: Date de création du token
        last_refresh: Date du dernier refresh
        broker: Nom du broker (saxo, ib, etc.)
    """

    access_token: str
    refresh_token: Optional[str]
    expires_at: str  # ISO format datetime
    created_at: str
    last_refresh: Optional[str] = None
    broker: str = "unknown"

    @property
    def is_expired(self) -> bool:
        """Vérifie si le token a expiré."""
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(expires.tzinfo) > expires
        except (ValueError, AttributeError):
            return True

    @property
    def expires_soon(self) -> bool:
        """Vérifie si le token expire dans moins d'1 heure."""
        try:
            from datetime import timedelta
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            soon = datetime.now(expires.tzinfo) + timedelta(hours=1)
            return soon > expires
        except (ValueError, AttributeError):
            return True

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredToken":
        """Crée depuis un dictionnaire."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_refresh=data.get("last_refresh"),
            broker=data.get("broker", "unknown"),
        )


class FileTokenStore:
    """
    Stockage de tokens dans un fichier JSON chiffré.

    Le fichier a la structure suivante (après déchiffrement):
    {
        "user_id": {
            "broker_name": {
                "access_token": "...",
                "refresh_token": "...",
                "expires_at": "...",
                ...
            }
        }
    }

    Thread-safe grâce à FileLock.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        encryption_service: Optional[EncryptionService] = None
    ):
        """
        Initialise le store.

        Args:
            file_path: Chemin du fichier JSON. Par défaut: data/tokens.json
            encryption_service: Service de chiffrement. Par défaut: singleton global
        """
        self._file_path = Path(file_path or settings.tokens_path)
        self._encryption = encryption_service or get_encryption_service()
        self._lock_path = self._file_path.with_suffix(".lock")

        # Créer le répertoire data si nécessaire
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialiser le fichier s'il n'existe pas
        if not self._file_path.exists():
            self._write_data({})

    def _read_data(self) -> Dict[str, Dict[str, Dict]]:
        """
        Lit et déchiffre le fichier de tokens.

        Returns:
            Dictionnaire déchiffré ou {} si fichier vide/inexistant
        """
        try:
            if not self._file_path.exists():
                return {}

            with open(self._file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                return {}

            # Le fichier contient du JSON avec une clé "encrypted"
            file_data = json.loads(content)
            encrypted_data = file_data.get("encrypted", "")

            if not encrypted_data:
                return {}

            return self._encryption.decrypt_dict(encrypted_data)

        except json.JSONDecodeError as e:
            logger.error(f"Fichier tokens corrompu: {e}")
            return {}
        except EncryptionError as e:
            logger.error(f"Impossible de déchiffrer les tokens: {e}")
            return {}
        except Exception as e:
            logger.error(f"Erreur lecture tokens: {e}")
            return {}

    def _write_data(self, data: Dict[str, Dict[str, Dict]]) -> None:
        """
        Chiffre et écrit les données dans le fichier.

        Args:
            data: Dictionnaire à chiffrer et sauvegarder
        """
        try:
            # Chiffrer les données
            encrypted = self._encryption.encrypt_dict(data)

            # Écrire dans le fichier avec lock
            with FileLock(self._lock_path):
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "encrypted": encrypted,
                            "updated_at": datetime.now().isoformat(),
                        },
                        f,
                        indent=2
                    )

        except Exception as e:
            logger.error(f"Erreur écriture tokens: {e}")
            raise

    async def save_token(
        self,
        user_id: str,
        broker: str,
        token_data: Dict[str, Any]
    ) -> None:
        """
        Sauvegarde un token pour un utilisateur et un broker.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker (ex: "saxo")
            token_data: Données du token (access_token, refresh_token, etc.)
        """
        # Lecture avec lock
        with FileLock(self._lock_path):
            data = self._read_data()

            # Créer la structure si nécessaire
            if user_id not in data:
                data[user_id] = {}

            # Ajouter les métadonnées
            token_data["broker"] = broker
            token_data["created_at"] = token_data.get(
                "created_at",
                datetime.now().isoformat()
            )
            token_data["last_refresh"] = datetime.now().isoformat()

            # Sauvegarder
            data[user_id][broker] = token_data
            self._write_data(data)

        logger.info(f"Token sauvegardé pour {user_id}/{broker}")

    async def get_token(
        self,
        user_id: str,
        broker: str
    ) -> Optional[StoredToken]:
        """
        Récupère un token pour un utilisateur et un broker.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker

        Returns:
            StoredToken ou None si non trouvé
        """
        data = self._read_data()

        user_data = data.get(user_id, {})
        token_data = user_data.get(broker)

        if not token_data:
            return None

        return StoredToken.from_dict(token_data)

    async def delete_token(self, user_id: str, broker: str) -> bool:
        """
        Supprime un token.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker

        Returns:
            True si le token a été supprimé, False si non trouvé
        """
        with FileLock(self._lock_path):
            data = self._read_data()

            if user_id not in data or broker not in data[user_id]:
                return False

            del data[user_id][broker]

            # Supprimer l'utilisateur s'il n'a plus de tokens
            if not data[user_id]:
                del data[user_id]

            self._write_data(data)

        logger.info(f"Token supprimé pour {user_id}/{broker}")
        return True

    async def get_all_tokens(self, user_id: str) -> Dict[str, StoredToken]:
        """
        Récupère tous les tokens d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur

        Returns:
            Dictionnaire broker -> StoredToken
        """
        data = self._read_data()
        user_data = data.get(user_id, {})

        return {
            broker: StoredToken.from_dict(token_data)
            for broker, token_data in user_data.items()
        }

    async def get_expiring_tokens(
        self,
        within_hours: int = 1
    ) -> list[tuple[str, str, StoredToken]]:
        """
        Récupère tous les tokens qui expirent bientôt.

        Utilisé par le job de refresh automatique.

        Args:
            within_hours: Nombre d'heures avant expiration

        Returns:
            Liste de tuples (user_id, broker, StoredToken)
        """
        from datetime import timedelta

        expiring = []
        data = self._read_data()
        now = datetime.now()
        threshold = now + timedelta(hours=within_hours)

        for user_id, brokers in data.items():
            for broker, token_data in brokers.items():
                token = StoredToken.from_dict(token_data)
                try:
                    expires = datetime.fromisoformat(
                        token.expires_at.replace("Z", "+00:00")
                    )
                    # Comparer sans timezone pour simplifier
                    if expires.replace(tzinfo=None) < threshold:
                        expiring.append((user_id, broker, token))
                except (ValueError, AttributeError):
                    # Token avec date invalide = à rafraîchir
                    expiring.append((user_id, broker, token))

        return expiring

    async def update_access_token(
        self,
        user_id: str,
        broker: str,
        new_access_token: str,
        new_expires_at: str,
        new_refresh_token: Optional[str] = None
    ) -> None:
        """
        Met à jour l'access token après un refresh.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker
            new_access_token: Nouveau token d'accès
            new_expires_at: Nouvelle date d'expiration
            new_refresh_token: Nouveau refresh token (si fourni)
        """
        with FileLock(self._lock_path):
            data = self._read_data()

            if user_id not in data or broker not in data[user_id]:
                raise TokenInvalidError("Token non trouvé pour mise à jour")

            token_data = data[user_id][broker]
            token_data["access_token"] = new_access_token
            token_data["expires_at"] = new_expires_at
            token_data["last_refresh"] = datetime.now().isoformat()

            if new_refresh_token:
                token_data["refresh_token"] = new_refresh_token

            self._write_data(data)

        logger.info(f"Token rafraîchi pour {user_id}/{broker}")

    def clear_all(self) -> None:
        """
        Supprime tous les tokens (utile pour les tests).

        ATTENTION: Action irréversible!
        """
        self._write_data({})
        logger.warning("Tous les tokens ont été supprimés")


# Instance globale (singleton)
_token_store: Optional[FileTokenStore] = None


def get_token_store() -> FileTokenStore:
    """
    Retourne l'instance singleton du store de tokens.

    Returns:
        FileTokenStore initialisé
    """
    global _token_store
    if _token_store is None:
        _token_store = FileTokenStore()
    return _token_store
