"""
Service de gestion sécurisée de la configuration.

Gère les credentials (Saxo Bank, Telegram) de manière sécurisée:
- Stockage chiffré dans un fichier JSON
- Validation des credentials avant sauvegarde
- Notifications de confirmation via Telegram
- Masquage des valeurs sensibles à l'affichage

ARCHITECTURE:
- Les credentials sont chiffrés avec Fernet (AES-128)
- Le fichier est stocké dans data/config.encrypted.json
- Les valeurs ne sont jamais exposées en clair via l'API
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

import httpx

from src.infrastructure.persistence.encryption import get_encryption_service, EncryptionService
from src.config.settings import settings, BACKEND_DIR

logger = logging.getLogger(__name__)


class SaxoEnvironment(str, Enum):
    """Environnements Saxo Bank disponibles."""
    DEMO = "SIM"  # Simulation (sandbox)
    LIVE = "LIVE"  # Production


@dataclass
class SaxoConfig:
    """Configuration Saxo Bank."""
    app_key: str = ""
    app_secret: str = ""
    environment: str = "SIM"
    redirect_uri: str = "http://localhost:5173"
    configured: bool = False
    updated_at: Optional[str] = None


@dataclass
class TelegramConfig:
    """Configuration Telegram Bot."""
    bot_token: str = ""
    chat_id: str = ""
    configured: bool = False
    updated_at: Optional[str] = None


@dataclass
class FinnhubConfig:
    """Configuration Finnhub API."""
    api_key: str = ""
    configured: bool = False
    updated_at: Optional[str] = None


@dataclass
class AppConfig:
    """Configuration globale de l'application."""
    saxo: SaxoConfig
    telegram: TelegramConfig
    finnhub: FinnhubConfig = None
    version: str = "1.0"

    def __post_init__(self):
        if self.finnhub is None:
            self.finnhub = FinnhubConfig()


class ConfigService:
    """
    Service de gestion de la configuration.

    Gère le stockage sécurisé et la validation des credentials
    pour les différents services (Saxo Bank, Telegram).

    Attributs:
        _config_path: Chemin vers le fichier de configuration chiffré
        _encryption: Service de chiffrement
        _config: Configuration en mémoire
    """

    DEFAULT_CONFIG_PATH = BACKEND_DIR / "data" / "config.encrypted.json"

    def __init__(
        self,
        config_path: Optional[Path] = None,
        encryption_service: Optional[EncryptionService] = None
    ):
        """
        Initialise le service de configuration.

        Args:
            config_path: Chemin vers le fichier de config
            encryption_service: Service de chiffrement à utiliser
        """
        self._config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._encryption = encryption_service or get_encryption_service()
        self._config: Optional[AppConfig] = None

        # S'assurer que le dossier existe
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_from_env(self) -> AppConfig:
        """
        Charge la configuration initiale depuis les variables d'environnement.

        Returns:
            Configuration avec les valeurs de l'environnement
        """
        saxo_configured = bool(settings.SAXO_APP_KEY and settings.SAXO_APP_SECRET)
        telegram_configured = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
        finnhub_configured = bool(settings.FINNHUB_API_KEY)

        return AppConfig(
            saxo=SaxoConfig(
                app_key=settings.SAXO_APP_KEY or "",
                app_secret=settings.SAXO_APP_SECRET or "",
                environment=settings.SAXO_ENVIRONMENT,
                redirect_uri=settings.SAXO_REDIRECT_URI,
                configured=saxo_configured,
                updated_at=datetime.now().isoformat() if saxo_configured else None
            ),
            telegram=TelegramConfig(
                bot_token=settings.TELEGRAM_BOT_TOKEN or "",
                chat_id=settings.TELEGRAM_CHAT_ID or "",
                configured=telegram_configured,
                updated_at=datetime.now().isoformat() if telegram_configured else None
            ),
            finnhub=FinnhubConfig(
                api_key=settings.FINNHUB_API_KEY or "",
                configured=finnhub_configured,
                updated_at=datetime.now().isoformat() if finnhub_configured else None
            )
        )

    def load(self) -> AppConfig:
        """
        Charge la configuration (fichier ou environnement).

        Priorité (par défaut): Fichier chiffré > Variables d'environnement
        Si FORCE_ENV_CONFIG=true: Variables d'environnement uniquement

        Returns:
            Configuration chargée
        """
        if self._config is not None:
            return self._config

        # Si FORCE_ENV_CONFIG est activé, supprimer le fichier chiffré et utiliser .env
        if settings.FORCE_ENV_CONFIG:
            if self._config_path.exists():
                logger.info("FORCE_ENV_CONFIG=true: Suppression du fichier de config chiffré")
                self._config_path.unlink()
            self._config = self._load_from_env()
            logger.info("Configuration forcée depuis les variables d'environnement")
            return self._config

        # Essayer de charger depuis le fichier
        if self._config_path.exists():
            try:
                with open(self._config_path, "r") as f:
                    encrypted_data = f.read()

                data = self._encryption.decrypt_dict(encrypted_data)

                self._config = AppConfig(
                    saxo=SaxoConfig(**data.get("saxo", {})),
                    telegram=TelegramConfig(**data.get("telegram", {})),
                    finnhub=FinnhubConfig(**data.get("finnhub", {})),
                    version=data.get("version", "1.0")
                )
                logger.info("Configuration chargée depuis le fichier chiffré")
                return self._config

            except Exception as e:
                logger.warning(f"Erreur lors du chargement de la config: {e}")

        # Fallback sur les variables d'environnement
        self._config = self._load_from_env()
        logger.info("Configuration chargée depuis les variables d'environnement")
        return self._config

    def save(self) -> bool:
        """
        Sauvegarde la configuration dans le fichier chiffré.

        Returns:
            True si la sauvegarde a réussi
        """
        if self._config is None:
            return False

        try:
            data = {
                "saxo": asdict(self._config.saxo),
                "telegram": asdict(self._config.telegram),
                "finnhub": asdict(self._config.finnhub),
                "version": self._config.version
            }

            encrypted_data = self._encryption.encrypt_dict(data)

            with open(self._config_path, "w") as f:
                f.write(encrypted_data)

            logger.info("Configuration sauvegardée avec succès")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la config: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut de configuration (sans valeurs sensibles).

        Returns:
            Dictionnaire avec le statut des services
        """
        config = self.load()

        return {
            "saxo": {
                "configured": config.saxo.configured,
                "environment": config.saxo.environment,
                "app_key_preview": self._mask_value(config.saxo.app_key),
                "updated_at": config.saxo.updated_at
            },
            "telegram": {
                "configured": config.telegram.configured,
                "bot_token_preview": self._mask_value(config.telegram.bot_token),
                "chat_id_preview": self._mask_value(config.telegram.chat_id),
                "updated_at": config.telegram.updated_at
            },
            "finnhub": {
                "configured": config.finnhub.configured,
                "api_key_preview": self._mask_value(config.finnhub.api_key),
                "updated_at": config.finnhub.updated_at
            }
        }

    def _mask_value(self, value: str, visible_chars: int = 4) -> str:
        """
        Masque une valeur sensible pour l'affichage.

        Args:
            value: Valeur à masquer
            visible_chars: Nombre de caractères visibles à la fin

        Returns:
            Valeur masquée (ex: "****abc123")
        """
        if not value:
            return "(non configuré)"

        if len(value) <= visible_chars:
            return "****"

        return "****" + value[-visible_chars:]

    async def update_saxo(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        environment: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Met à jour la configuration Saxo Bank.

        Args:
            app_key: Clé d'application
            app_secret: Secret d'application
            environment: Environnement (SIM ou LIVE)
            redirect_uri: URI de redirection OAuth

        Returns:
            Résultat de la mise à jour
        """
        config = self.load()

        # Mise à jour partielle
        if app_key is not None:
            config.saxo.app_key = app_key
        if app_secret is not None:
            config.saxo.app_secret = app_secret
        if environment is not None:
            if environment not in [e.value for e in SaxoEnvironment]:
                return {"success": False, "error": f"Environnement invalide: {environment}"}
            config.saxo.environment = environment
        if redirect_uri is not None:
            config.saxo.redirect_uri = redirect_uri

        # Valider que la config est complète
        config.saxo.configured = bool(
            config.saxo.app_key and config.saxo.app_secret
        )
        config.saxo.updated_at = datetime.now().isoformat()

        # Sauvegarder
        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        # Mettre à jour les settings en mémoire pour usage immédiat
        self._apply_to_runtime_settings()

        return {
            "success": True,
            "message": "Configuration Saxo Bank mise à jour",
            "environment": config.saxo.environment,
            "configured": config.saxo.configured
        }

    async def update_telegram(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Met à jour la configuration Telegram.

        Args:
            bot_token: Token du bot
            chat_id: ID du chat

        Returns:
            Résultat de la mise à jour
        """
        config = self.load()

        # Validation préalable si les deux sont fournis
        new_token = bot_token if bot_token is not None else config.telegram.bot_token
        new_chat_id = chat_id if chat_id is not None else config.telegram.chat_id

        if new_token and new_chat_id:
            # Tester la connexion
            is_valid = await self._validate_telegram(new_token, new_chat_id)
            if not is_valid:
                return {
                    "success": False,
                    "error": "Impossible de valider les credentials Telegram. Vérifiez le token et le chat ID."
                }

        # Mise à jour
        if bot_token is not None:
            config.telegram.bot_token = bot_token
        if chat_id is not None:
            config.telegram.chat_id = chat_id

        config.telegram.configured = bool(
            config.telegram.bot_token and config.telegram.chat_id
        )
        config.telegram.updated_at = datetime.now().isoformat()

        # Sauvegarder
        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        # Mettre à jour les settings en mémoire
        self._apply_to_runtime_settings()

        return {
            "success": True,
            "message": "Configuration Telegram mise à jour",
            "configured": config.telegram.configured
        }

    async def delete_saxo(self) -> Dict[str, Any]:
        """
        Supprime les credentials Saxo Bank.

        Returns:
            Résultat de la suppression
        """
        config = self.load()

        config.saxo = SaxoConfig()
        config.saxo.updated_at = datetime.now().isoformat()

        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        self._apply_to_runtime_settings()

        return {
            "success": True,
            "message": "Credentials Saxo Bank supprimés"
        }

    async def delete_telegram(self) -> Dict[str, Any]:
        """
        Supprime la configuration Telegram.

        Returns:
            Résultat de la suppression
        """
        config = self.load()

        config.telegram = TelegramConfig()
        config.telegram.updated_at = datetime.now().isoformat()

        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        self._apply_to_runtime_settings()

        return {
            "success": True,
            "message": "Configuration Telegram supprimée"
        }

    async def update_finnhub(self, api_key: str) -> Dict[str, Any]:
        """
        Met à jour la configuration Finnhub.

        Args:
            api_key: Clé API Finnhub

        Returns:
            Résultat de la mise à jour
        """
        config = self.load()

        config.finnhub.api_key = api_key.strip() if api_key else ""
        config.finnhub.configured = bool(config.finnhub.api_key)
        config.finnhub.updated_at = datetime.now().isoformat()

        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        self._apply_to_runtime_settings()

        return {
            "success": True,
            "message": "Configuration Finnhub mise à jour",
            "configured": config.finnhub.configured
        }

    async def delete_finnhub(self) -> Dict[str, Any]:
        """
        Supprime la configuration Finnhub.

        Returns:
            Résultat de la suppression
        """
        config = self.load()

        config.finnhub = FinnhubConfig()
        config.finnhub.updated_at = datetime.now().isoformat()

        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        self._apply_to_runtime_settings()

        return {
            "success": True,
            "message": "Configuration Finnhub supprimée"
        }

    async def switch_saxo_environment(self, environment: str) -> Dict[str, Any]:
        """
        Bascule l'environnement Saxo (DEMO/LIVE).

        Args:
            environment: Nouvel environnement (SIM ou LIVE)

        Returns:
            Résultat du changement
        """
        if environment not in [e.value for e in SaxoEnvironment]:
            return {"success": False, "error": f"Environnement invalide: {environment}"}

        config = self.load()
        old_env = config.saxo.environment
        config.saxo.environment = environment
        config.saxo.updated_at = datetime.now().isoformat()

        if not self.save():
            return {"success": False, "error": "Erreur lors de la sauvegarde"}

        self._apply_to_runtime_settings()

        env_label = "DEMO (Simulation)" if environment == "SIM" else "PRODUCTION (LIVE)"

        return {
            "success": True,
            "message": f"Environnement changé de {old_env} vers {environment}",
            "environment": environment,
            "environment_label": env_label
        }

    async def _validate_telegram(self, token: str, chat_id: str) -> bool:
        """
        Valide les credentials Telegram en envoyant un test.

        Args:
            token: Bot token
            chat_id: Chat ID

        Returns:
            True si les credentials sont valides
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Vérifier le bot
                response = await client.get(
                    f"https://api.telegram.org/bot{token}/getMe"
                )
                if response.status_code != 200:
                    return False

                data = response.json()
                if not data.get("ok"):
                    return False

                # Vérifier qu'on peut envoyer au chat
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "✅ Configuration Telegram validée!",
                        "parse_mode": "HTML"
                    }
                )

                return response.status_code == 200 and response.json().get("ok", False)

        except Exception as e:
            logger.error(f"Erreur validation Telegram: {e}")
            return False

    def _apply_to_runtime_settings(self) -> None:
        """
        Applique la configuration aux settings en mémoire.

        Permet d'utiliser les nouveaux credentials sans redémarrer.
        """
        if self._config is None:
            return

        # Note: Ces attributs sont normalement immutables dans Pydantic Settings
        # On les modifie via object.__setattr__ pour le runtime
        if self._config.saxo.configured:
            object.__setattr__(settings, 'SAXO_APP_KEY', self._config.saxo.app_key)
            object.__setattr__(settings, 'SAXO_APP_SECRET', self._config.saxo.app_secret)
            object.__setattr__(settings, 'SAXO_ENVIRONMENT', self._config.saxo.environment)
            object.__setattr__(settings, 'SAXO_REDIRECT_URI', self._config.saxo.redirect_uri)

        if self._config.telegram.configured:
            object.__setattr__(settings, 'TELEGRAM_BOT_TOKEN', self._config.telegram.bot_token)
            object.__setattr__(settings, 'TELEGRAM_CHAT_ID', self._config.telegram.chat_id)

        if self._config.finnhub.configured:
            object.__setattr__(settings, 'FINNHUB_API_KEY', self._config.finnhub.api_key)

    def get_saxo_credentials(self) -> Optional[Dict[str, str]]:
        """
        Récupère les credentials Saxo Bank (pour usage interne).

        Returns:
            Dictionnaire avec les credentials ou None
        """
        config = self.load()
        if not config.saxo.configured:
            return None

        return {
            "app_key": config.saxo.app_key,
            "app_secret": config.saxo.app_secret,
            "environment": config.saxo.environment,
            "redirect_uri": config.saxo.redirect_uri
        }

    def get_telegram_credentials(self) -> Optional[Dict[str, str]]:
        """
        Récupère les credentials Telegram (pour usage interne).

        Returns:
            Dictionnaire avec les credentials ou None
        """
        config = self.load()
        if not config.telegram.configured:
            return None

        return {
            "bot_token": config.telegram.bot_token,
            "chat_id": config.telegram.chat_id
        }

    def get_finnhub_credentials(self) -> Optional[Dict[str, str]]:
        """
        Récupère les credentials Finnhub (pour usage interne).

        Returns:
            Dictionnaire avec l'API key ou None
        """
        config = self.load()
        if not config.finnhub.configured:
            return None

        return {
            "api_key": config.finnhub.api_key
        }


# Singleton
_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    """
    Retourne l'instance singleton du service de configuration.

    Charge la config et applique les credentials aux settings globaux
    pour que le reste de l'application puisse les utiliser.

    Returns:
        ConfigService initialisé
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
        # Charger la config et appliquer aux settings globaux
        _config_service.load()
        _config_service._apply_to_runtime_settings()
        logger.info("Configuration chargée et appliquée aux settings globaux")
    return _config_service
