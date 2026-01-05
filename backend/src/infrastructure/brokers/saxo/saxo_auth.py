"""
Service d'authentification OAuth2 simplifie pour Saxo Bank.

Architecture simple et fonctionnelle:
- Pas de PKCE (inutile pour les apps confidentielles avec secret)
- Token storage en memoire (singleton)
- Auto-refresh des tokens expires
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode
import threading

import requests

from src.config.settings import Settings

logger = logging.getLogger(__name__)

# Buffer de securite avant expiration (5 minutes)
TOKEN_EXPIRY_BUFFER = 300


@dataclass
class SaxoToken:
    """Token Saxo avec metadata."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    environment: str  # SIM ou LIVE

    @property
    def is_expired(self) -> bool:
        """Verifie si le token est expire (avec buffer)."""
        return datetime.now() >= self.expires_at

    @property
    def expires_in_seconds(self) -> int:
        """Secondes avant expiration."""
        delta = self.expires_at - datetime.now()
        return max(0, int(delta.total_seconds()))


class SaxoTokenManager:
    """
    Gestionnaire de tokens Saxo - Singleton avec persistance fichier.

    Stocke les tokens en memoire ET dans un fichier JSON pour partage
    entre processus (API web et serveur MCP).
    Thread-safe.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tokens: Dict[str, SaxoToken] = {}
                    cls._instance._init_file_path()
                    cls._instance._load_from_file()
        return cls._instance

    def _init_file_path(self) -> None:
        """Initialise le chemin du fichier de tokens."""
        from src.config.settings import BACKEND_DIR
        self._file_path = BACKEND_DIR / "data" / "saxo_tokens.json"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_from_file(self) -> None:
        """Charge les tokens depuis le fichier persistant."""
        import json
        try:
            if self._file_path.exists():
                with open(self._file_path, "r") as f:
                    data = json.load(f)
                for env, token_data in data.items():
                    expires_at = datetime.fromisoformat(token_data["expires_at"])
                    token = SaxoToken(
                        access_token=token_data["access_token"],
                        refresh_token=token_data["refresh_token"],
                        expires_at=expires_at,
                        environment=env
                    )
                    self._tokens[env] = token
                logger.info(f"Loaded {len(self._tokens)} tokens from file")
        except Exception as e:
            logger.warning(f"Could not load tokens from file: {e}")

    def _save_to_file(self) -> None:
        """Sauvegarde les tokens dans le fichier persistant."""
        import json
        try:
            data = {}
            for env, token in self._tokens.items():
                data[env] = {
                    "access_token": token.access_token,
                    "refresh_token": token.refresh_token,
                    "expires_at": token.expires_at.isoformat(),
                    "environment": env
                }
            with open(self._file_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} tokens to file")
        except Exception as e:
            logger.error(f"Could not save tokens to file: {e}")

    def save(self, token: SaxoToken) -> None:
        """Sauvegarde un token (memoire + fichier)."""
        with self._lock:
            self._tokens[token.environment] = token
            self._save_to_file()
            logger.info(f"Token saved for {token.environment}, expires in {token.expires_in_seconds}s")

    def get(self, environment: str) -> Optional[SaxoToken]:
        """Recupere un token par environnement."""
        with self._lock:
            # Recharger depuis le fichier si pas en memoire (nouveau processus)
            if environment not in self._tokens:
                self._load_from_file()
            return self._tokens.get(environment)

    def delete(self, environment: str) -> None:
        """Supprime un token (memoire + fichier)."""
        with self._lock:
            if environment in self._tokens:
                del self._tokens[environment]
                self._save_to_file()
                logger.info(f"Token deleted for {environment}")

    def clear(self) -> None:
        """Supprime tous les tokens (memoire + fichier)."""
        with self._lock:
            self._tokens.clear()
            self._save_to_file()
            logger.info("All tokens cleared")


class SaxoAuthService:
    """
    Service d'authentification OAuth2 pour Saxo Bank.

    Flow simple:
    1. get_auth_url() -> URL pour redirection utilisateur
    2. exchange_code(code) -> Echange code contre tokens
    3. refresh_token() -> Rafraichit un token expire
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.token_manager = SaxoTokenManager()

    @property
    def auth_url(self) -> str:
        """URL d'authentification Saxo."""
        return self.settings.saxo_auth_url

    @property
    def api_url(self) -> str:
        """URL de l'API Saxo."""
        return self.settings.saxo_api_url

    @property
    def environment(self) -> str:
        """Environnement actuel (SIM ou LIVE)."""
        return self.settings.SAXO_ENVIRONMENT

    @property
    def is_configured(self) -> bool:
        """Verifie si Saxo est configure."""
        return self.settings.is_saxo_configured

    def get_auth_url(self) -> str:
        """
        Genere l'URL d'autorisation OAuth2.

        Returns:
            URL complete pour rediriger l'utilisateur
        """
        if not self.is_configured:
            raise ValueError("Saxo non configure: SAXO_APP_KEY et SAXO_APP_SECRET requis")

        params = {
            "response_type": "code",
            "client_id": self.settings.SAXO_APP_KEY,
            "redirect_uri": self.settings.SAXO_REDIRECT_URI,
        }

        url = f"{self.auth_url}/authorize?{urlencode(params)}"
        logger.info(f"Generated auth URL for {self.environment}")
        return url

    def exchange_code(self, code: str) -> SaxoToken:
        """
        Echange le code d'autorisation contre des tokens.

        Args:
            code: Code recu du callback OAuth

        Returns:
            SaxoToken avec access_token et refresh_token

        Raises:
            Exception: Si l'echange echoue
        """
        if not self.is_configured:
            raise ValueError("Saxo non configure")

        token_url = f"{self.auth_url}/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.SAXO_REDIRECT_URI,
            "client_id": self.settings.SAXO_APP_KEY,
            "client_secret": self.settings.SAXO_APP_SECRET,
        }

        logger.info(f"Exchanging code for tokens ({self.environment})...")

        response = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )

        if response.status_code not in (200, 201):
            error = self._parse_error(response)
            logger.error(f"Token exchange failed: {error}")
            raise Exception(f"Echec authentification: {error}")

        tokens = response.json()

        if "access_token" not in tokens:
            raise Exception("Reponse invalide: access_token manquant")

        # Calculer expiration
        expires_in = tokens.get("expires_in", 1200)  # Default 20 min
        expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_EXPIRY_BUFFER)

        token = SaxoToken(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", ""),
            expires_at=expires_at,
            environment=self.environment
        )

        # Sauvegarder
        self.token_manager.save(token)

        logger.info(f"Token obtained successfully for {self.environment}")
        return token

    def refresh_token(self, refresh_token: str) -> SaxoToken:
        """
        Rafraichit un token expire.

        Args:
            refresh_token: Refresh token actuel

        Returns:
            Nouveau SaxoToken

        Raises:
            Exception: Si le refresh echoue
        """
        if not self.is_configured:
            raise ValueError("Saxo non configure")

        token_url = f"{self.auth_url}/token"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.SAXO_APP_KEY,
            "client_secret": self.settings.SAXO_APP_SECRET,
        }

        logger.info(f"Refreshing token for {self.environment}...")

        response = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )

        if response.status_code != 200:
            error = self._parse_error(response)
            logger.error(f"Token refresh failed: {error}")
            raise Exception(f"Echec refresh: {error}")

        tokens = response.json()

        expires_in = tokens.get("expires_in", 1200)
        expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_EXPIRY_BUFFER)

        token = SaxoToken(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", refresh_token),
            expires_at=expires_at,
            environment=self.environment
        )

        self.token_manager.save(token)

        logger.info(f"Token refreshed successfully for {self.environment}")
        return token

    def get_valid_token(self) -> Optional[SaxoToken]:
        """
        Recupere un token valide, en le rafraichissant si necessaire.

        Returns:
            SaxoToken valide ou None si aucun token disponible
        """
        token = self.token_manager.get(self.environment)

        if not token:
            return None

        if token.is_expired:
            if token.refresh_token:
                try:
                    return self.refresh_token(token.refresh_token)
                except Exception as e:
                    logger.warning(f"Refresh failed: {e}")
                    self.token_manager.delete(self.environment)
                    return None
            else:
                self.token_manager.delete(self.environment)
                return None

        return token

    def disconnect(self) -> None:
        """Deconnecte l'utilisateur (supprime le token)."""
        self.token_manager.delete(self.environment)

    def _parse_error(self, response: requests.Response) -> str:
        """Parse une erreur OAuth."""
        try:
            data = response.json()
            error = data.get("error", "unknown")
            desc = data.get("error_description", "")
            return f"{error}: {desc}" if desc else error
        except:
            return f"HTTP {response.status_code}: {response.text[:200]}"


# Singleton factory
_auth_service: Optional[SaxoAuthService] = None

def get_saxo_auth(settings: Settings = None) -> SaxoAuthService:
    """
    Factory pour obtenir le service d'authentification Saxo.

    Args:
        settings: Configuration (optionnel, utilise get_settings() par defaut)

    Returns:
        SaxoAuthService singleton
    """
    global _auth_service

    if _auth_service is None:
        if settings is None:
            from src.config.settings import get_settings
            settings = get_settings()
        _auth_service = SaxoAuthService(settings)

    return _auth_service
