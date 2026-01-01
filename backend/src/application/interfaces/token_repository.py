"""
Interface TokenRepository - Abstraction pour le stockage des tokens.

Cette interface définit le contrat pour le stockage des tokens OAuth.
Permet de changer d'implémentation (fichier → Redis → PostgreSQL)
sans modifier le reste de l'application.

ARCHITECTURE:
- Couche APPLICATION (port/interface)
- Implémentée par infrastructure/persistence/token_store.py
- Utilisée par les use cases d'authentification

PATTERN: Repository

IMPLÉMENTATIONS POSSIBLES:
- FileTokenStore: Fichier JSON chiffré (actuel)
- RedisTokenStore: Cache Redis (futur)
- PostgresTokenStore: Base de données (futur)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any


@dataclass
class Token:
    """
    Représentation d'un token OAuth stocké.

    Structure commune pour tous les types de stockage.
    """

    access_token: str
    """Token d'accès pour les appels API."""

    refresh_token: Optional[str]
    """Token pour rafraîchir l'access_token."""

    expires_at: datetime
    """Date d'expiration de l'access_token."""

    created_at: datetime
    """Date de création initiale."""

    last_refresh: Optional[datetime] = None
    """Date du dernier rafraîchissement."""

    broker: str = "unknown"
    """Nom du broker."""

    metadata: Optional[Dict[str, Any]] = None
    """Métadonnées additionnelles (user_agent, ip, etc.)."""

    @property
    def is_expired(self) -> bool:
        """Vérifie si le token a expiré."""
        return datetime.now() > self.expires_at

    @property
    def expires_soon(self, hours: int = 1) -> bool:
        """Vérifie si le token expire dans les N prochaines heures."""
        from datetime import timedelta
        return datetime.now() + timedelta(hours=hours) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "broker": self.broker,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Token":
        """Crée un Token depuis un dictionnaire."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            last_refresh=datetime.fromisoformat(data["last_refresh"]) if data.get("last_refresh") else None,
            broker=data.get("broker", "unknown"),
            metadata=data.get("metadata"),
        )


class TokenRepository(ABC):
    """
    Interface abstraite pour le stockage des tokens.

    Définit les opérations CRUD sur les tokens.
    """

    @abstractmethod
    async def save(
        self,
        user_id: str,
        broker: str,
        token: Token
    ) -> None:
        """
        Sauvegarde un token.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker (ex: "saxo")
            token: Token à sauvegarder

        Note:
            Si un token existe déjà pour cet user/broker, il est remplacé.
        """
        pass

    @abstractmethod
    async def get(
        self,
        user_id: str,
        broker: str
    ) -> Optional[Token]:
        """
        Récupère un token.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker

        Returns:
            Token ou None si non trouvé
        """
        pass

    @abstractmethod
    async def delete(
        self,
        user_id: str,
        broker: str
    ) -> bool:
        """
        Supprime un token.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker

        Returns:
            True si le token a été supprimé, False si non trouvé
        """
        pass

    @abstractmethod
    async def get_all_for_user(
        self,
        user_id: str
    ) -> Dict[str, Token]:
        """
        Récupère tous les tokens d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur

        Returns:
            Dictionnaire broker -> Token
        """
        pass

    @abstractmethod
    async def get_expiring(
        self,
        within_hours: int = 1
    ) -> List[Tuple[str, str, Token]]:
        """
        Récupère tous les tokens qui expirent bientôt.

        Utilisé par le job de refresh automatique.

        Args:
            within_hours: Fenêtre d'expiration en heures

        Returns:
            Liste de tuples (user_id, broker, Token)
        """
        pass

    @abstractmethod
    async def update_access_token(
        self,
        user_id: str,
        broker: str,
        new_access_token: str,
        new_expires_at: datetime,
        new_refresh_token: Optional[str] = None
    ) -> None:
        """
        Met à jour l'access token après un refresh.

        Plus efficace que save() pour une mise à jour partielle.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker
            new_access_token: Nouveau token d'accès
            new_expires_at: Nouvelle date d'expiration
            new_refresh_token: Nouveau refresh token (si fourni par l'API)

        Raises:
            TokenInvalidError: Si le token n'existe pas
        """
        pass

    async def exists(
        self,
        user_id: str,
        broker: str
    ) -> bool:
        """
        Vérifie si un token existe.

        Implémentation par défaut utilisant get().

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker

        Returns:
            True si le token existe
        """
        token = await self.get(user_id, broker)
        return token is not None

    async def is_valid(
        self,
        user_id: str,
        broker: str
    ) -> bool:
        """
        Vérifie si un token existe ET n'est pas expiré.

        Implémentation par défaut.

        Args:
            user_id: Identifiant de l'utilisateur
            broker: Nom du broker

        Returns:
            True si le token est valide
        """
        token = await self.get(user_id, broker)
        if token is None:
            return False
        return not token.is_expired
