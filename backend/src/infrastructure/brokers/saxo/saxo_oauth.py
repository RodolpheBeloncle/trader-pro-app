"""
Service OAuth2 pour Saxo Bank.

Gère le flux d'authentification OAuth2 avec PKCE:
- Génération des URLs d'autorisation
- Échange de code contre tokens
- Rafraîchissement des tokens

ARCHITECTURE:
- Responsabilité unique : authentification OAuth2
- PKCE pour la sécurité
- Intégration avec le token store chiffré

DOCUMENTATION SAXO:
https://www.developer.saxo/openapi/learn/oauth-authorization-code-grant
"""

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode

import requests

from src.config.settings import Settings
from src.config.constants import (
    OAUTH_STATE_TTL_SECONDS,
    TOKEN_EXPIRY_BUFFER_SECONDS,
)
from src.domain.exceptions import (
    BrokerAuthenticationError,
    TokenRefreshError,
    BrokerNotConfiguredError,
)

logger = logging.getLogger(__name__)


@dataclass
class PKCEData:
    """Données PKCE pour la sécurité OAuth2."""

    code_verifier: str
    code_challenge: str
    state: str
    created_at: datetime

    def is_expired(self) -> bool:
        """Vérifie si les données PKCE ont expiré."""
        return datetime.now() > self.created_at + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)


@dataclass
class TokenResponse:
    """Réponse de l'échange de tokens."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    token_type: str = "Bearer"


class SaxoOAuthService:
    """
    Service OAuth2 pour Saxo Bank avec support PKCE.

    Gère le flux complet d'authentification:
    1. Génération URL d'autorisation avec PKCE
    2. Échange code → tokens
    3. Rafraîchissement des tokens

    Attributes:
        settings: Configuration de l'application
        _pkce_store: Stockage temporaire des données PKCE (en mémoire)
    """

    def __init__(self, settings: Settings):
        """
        Initialise le service OAuth.

        Args:
            settings: Configuration de l'application

        Raises:
            BrokerNotConfiguredError: Si Saxo n'est pas configuré
        """
        self.settings = settings
        self._pkce_store: Dict[str, PKCEData] = {}  # state → PKCEData

        if not settings.is_saxo_configured:
            logger.warning("Saxo API credentials not configured")

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def get_authorization_url(self, user_id: str, custom_state: Optional[str] = None) -> Dict[str, str]:
        """
        Génère l'URL d'autorisation OAuth2 avec PKCE.

        Args:
            user_id: ID de l'utilisateur (pour tracer le flow)
            custom_state: État personnalisé (optionnel)

        Returns:
            Dict avec auth_url et state

        Raises:
            BrokerNotConfiguredError: Si Saxo n'est pas configuré
        """
        self._check_configured()

        # Générer les données PKCE
        pkce = self._generate_pkce(custom_state)

        # Stocker pour la validation callback
        self._pkce_store[pkce.state] = pkce

        # Nettoyer les données PKCE expirées
        self._cleanup_expired_pkce()

        # Construire l'URL
        params = {
            "response_type": "code",
            "client_id": self.settings.SAXO_APP_KEY,
            "redirect_uri": self.settings.SAXO_REDIRECT_URI,
            "state": pkce.state,
            "code_challenge": pkce.code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{self.settings.saxo_auth_url}/authorize?{urlencode(params)}"

        logger.info(f"Generated auth URL for user {user_id} with state {pkce.state[:8]}...")
        return {
            "auth_url": auth_url,
            "state": pkce.state,
        }

    def exchange_code(self, authorization_code: str, state: str) -> TokenResponse:
        """
        Échange le code d'autorisation contre des tokens.

        Args:
            authorization_code: Code reçu du callback OAuth
            state: État pour validation CSRF/PKCE

        Returns:
            TokenResponse avec access_token, refresh_token, expires_at

        Raises:
            BrokerAuthenticationError: Si l'échange échoue
        """
        self._check_configured()

        # Récupérer et valider les données PKCE
        pkce = self._pkce_store.get(state)
        if not pkce:
            raise BrokerAuthenticationError(
                "saxo",
                "État OAuth invalide ou expiré. Veuillez réessayer l'authentification."
            )

        if pkce.is_expired():
            del self._pkce_store[state]
            raise BrokerAuthenticationError(
                "saxo",
                "Session d'authentification expirée. Veuillez réessayer."
            )

        token_url = f"{self.settings.saxo_auth_url}/token"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.settings.SAXO_REDIRECT_URI,
            "client_id": self.settings.SAXO_APP_KEY,
            "client_secret": self.settings.SAXO_APP_SECRET,
            "code_verifier": pkce.code_verifier,
        }

        logger.info(f"Exchanging authorization code for tokens...")

        try:
            response = requests.post(token_url, headers=headers, data=data, timeout=30)

            if response.status_code != 200:
                error_msg = self._parse_error_response(response)
                logger.error(f"Token exchange failed: {error_msg}")
                raise BrokerAuthenticationError("saxo", error_msg)

            tokens = response.json()

            # Nettoyer les données PKCE utilisées
            del self._pkce_store[state]

            # Calculer la date d'expiration
            expires_in = tokens.get("expires_in", 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_EXPIRY_BUFFER_SECONDS)

            token_response = TokenResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token", ""),
                expires_at=expires_at,
                token_type=tokens.get("token_type", "Bearer"),
            )

            logger.info("Token exchange successful")
            return token_response

        except requests.RequestException as e:
            logger.error(f"Network error during token exchange: {e}")
            raise BrokerAuthenticationError(
                "saxo",
                f"Erreur réseau lors de l'authentification: {str(e)}"
            )

    def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Rafraîchit les tokens d'accès.

        Args:
            refresh_token: Refresh token actuel

        Returns:
            TokenResponse avec nouveaux tokens

        Raises:
            TokenRefreshError: Si le rafraîchissement échoue
        """
        self._check_configured()

        token_url = f"{self.settings.saxo_auth_url}/token"

        # Utiliser Basic Auth pour le refresh
        credentials = base64.b64encode(
            f"{self.settings.SAXO_APP_KEY}:{self.settings.SAXO_APP_SECRET}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        logger.info("Refreshing Saxo tokens...")

        try:
            response = requests.post(token_url, headers=headers, data=data, timeout=30)

            if response.status_code != 200:
                error_msg = self._parse_error_response(response)
                logger.error(f"Token refresh failed: {error_msg}")
                raise TokenRefreshError("saxo", error_msg)

            tokens = response.json()

            expires_in = tokens.get("expires_in", 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_EXPIRY_BUFFER_SECONDS)

            token_response = TokenResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token", refresh_token),
                expires_at=expires_at,
                token_type=tokens.get("token_type", "Bearer"),
            )

            logger.info("Token refresh successful")
            return token_response

        except requests.RequestException as e:
            logger.error(f"Network error during token refresh: {e}")
            raise TokenRefreshError(
                "saxo",
                f"Erreur réseau lors du rafraîchissement: {str(e)}"
            )

    def validate_state(self, state: str) -> bool:
        """
        Valide un état OAuth.

        Args:
            state: État à valider

        Returns:
            True si l'état est valide et non expiré
        """
        pkce = self._pkce_store.get(state)
        if not pkce:
            return False
        return not pkce.is_expired()

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _check_configured(self) -> None:
        """Vérifie que Saxo est configuré."""
        if not self.settings.is_saxo_configured:
            raise BrokerNotConfiguredError(
                "saxo",
                "Saxo API n'est pas configuré. Définissez SAXO_APP_KEY et SAXO_APP_SECRET."
            )

    def _generate_pkce(self, custom_state: Optional[str] = None) -> PKCEData:
        """
        Génère les données PKCE (code_verifier, code_challenge, state).

        Args:
            custom_state: État personnalisé (sinon généré)

        Returns:
            PKCEData avec toutes les valeurs nécessaires
        """
        # Générer un code_verifier aléatoire (43-128 caractères, base64url)
        code_verifier = secrets.token_urlsafe(32)

        # Créer le code_challenge (SHA256 hash, base64url encoded sans padding)
        code_challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).rstrip(b'=').decode()

        # Générer ou utiliser l'état
        state = custom_state or secrets.token_urlsafe(16)

        return PKCEData(
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            state=state,
            created_at=datetime.now(),
        )

    def _cleanup_expired_pkce(self) -> None:
        """Nettoie les données PKCE expirées."""
        expired_states = [
            state for state, pkce in self._pkce_store.items()
            if pkce.is_expired()
        ]
        for state in expired_states:
            del self._pkce_store[state]

        if expired_states:
            logger.debug(f"Cleaned up {len(expired_states)} expired PKCE entries")

    def _parse_error_response(self, response: requests.Response) -> str:
        """
        Parse une réponse d'erreur OAuth.

        Args:
            response: Réponse HTTP avec erreur

        Returns:
            Message d'erreur lisible
        """
        try:
            error_data = response.json()
            error = error_data.get("error", "unknown_error")
            description = error_data.get("error_description", "Erreur inconnue")
            return f"{error}: {description}"
        except Exception:
            return f"HTTP {response.status_code}: {response.text[:200]}"


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_saxo_oauth_service(settings: Settings) -> SaxoOAuthService:
    """
    Factory function pour créer un SaxoOAuthService.

    Args:
        settings: Configuration de l'application

    Returns:
        Instance configurée de SaxoOAuthService
    """
    return SaxoOAuthService(settings)
