"""
Service de configuration de l'application.

Permet de stocker et recuperer des configurations modifiables
par l'utilisateur via l'interface (cles API, preferences, etc.)

Les configurations sont stockees dans un fichier JSON
pour persister entre les redemarrages.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Configuration de l'application."""
    finnhub_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    default_trading_mode: str = "long_term"
    technical_alerts_enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    def to_safe_dict(self) -> dict:
        """Retourne la config avec les valeurs sensibles masquees."""
        data = self.to_dict()
        # Masquer les cles API (montrer seulement les derniers caracteres)
        if data.get("finnhub_api_key"):
            key = data["finnhub_api_key"]
            data["finnhub_api_key"] = f"***{key[-4:]}" if len(key) > 4 else "****"
        if data.get("telegram_bot_token"):
            token = data["telegram_bot_token"]
            data["telegram_bot_token"] = f"***{token[-4:]}" if len(token) > 4 else "****"
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Cree une config depuis un dict."""
        return cls(
            finnhub_api_key=data.get("finnhub_api_key"),
            telegram_bot_token=data.get("telegram_bot_token"),
            telegram_chat_id=data.get("telegram_chat_id"),
            default_trading_mode=data.get("default_trading_mode", "long_term"),
            technical_alerts_enabled=data.get("technical_alerts_enabled", True),
        )


class AppConfigService:
    """
    Service de gestion de la configuration.

    Stocke les configurations dans un fichier JSON.
    Permet de mettre a jour les valeurs sans redemarrer l'application.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: Chemin vers le fichier de config.
                        Par defaut: data/app_config.json
        """
        if config_path is None:
            from src.config.settings import settings
            config_path = f"{settings.DATA_DIR}/app_config.json"

        self._config_path = Path(config_path)
        self._config: AppConfig = self._load_config()
        self._env_loaded = False

    def _load_config(self) -> AppConfig:
        """Charge la configuration depuis le fichier."""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r") as f:
                    data = json.load(f)
                logger.info(f"Configuration loaded from {self._config_path}")
                return AppConfig.from_dict(data)
            except Exception as e:
                logger.warning(f"Error loading config: {e}")

        return AppConfig()

    def _save_config(self) -> None:
        """Sauvegarde la configuration dans le fichier."""
        try:
            # Creer le repertoire si necessaire
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self._config_path, "w") as f:
                json.dump(self._config.to_dict(), f, indent=2)
            logger.info(f"Configuration saved to {self._config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise

    def _load_from_env(self) -> None:
        """Charge les valeurs depuis l'environnement si pas deja definies."""
        if self._env_loaded:
            return

        from src.config.settings import settings

        # Charger depuis .env si pas defini dans le fichier config
        if not self._config.finnhub_api_key and settings.FINNHUB_API_KEY:
            self._config.finnhub_api_key = settings.FINNHUB_API_KEY

        if not self._config.telegram_bot_token and settings.TELEGRAM_BOT_TOKEN:
            self._config.telegram_bot_token = settings.TELEGRAM_BOT_TOKEN

        if not self._config.telegram_chat_id and settings.TELEGRAM_CHAT_ID:
            self._config.telegram_chat_id = settings.TELEGRAM_CHAT_ID

        self._env_loaded = True

    @property
    def config(self) -> AppConfig:
        """Retourne la configuration actuelle."""
        self._load_from_env()
        return self._config

    def get_config(self) -> dict:
        """Retourne la configuration (version safe pour l'API)."""
        self._load_from_env()
        return self._config.to_safe_dict()

    def get_finnhub_api_key(self) -> Optional[str]:
        """Retourne la cle API Finnhub."""
        self._load_from_env()
        return self._config.finnhub_api_key

    def set_finnhub_api_key(self, api_key: str) -> None:
        """
        Met a jour la cle API Finnhub.

        Args:
            api_key: Nouvelle cle API
        """
        self._config.finnhub_api_key = api_key.strip() if api_key else None
        self._save_config()
        logger.info("Finnhub API key updated")

        # Recharger la source Finnhub si possible
        self._reload_finnhub_source()

    def _reload_finnhub_source(self) -> None:
        """Recharge la source Finnhub avec la nouvelle cle."""
        try:
            from src.infrastructure.websocket.finnhub_source import _finnhub_source

            if _finnhub_source is not None:
                _finnhub_source._api_key = self._config.finnhub_api_key
                logger.info("Finnhub source reloaded with new API key")
        except Exception as e:
            logger.warning(f"Could not reload Finnhub source: {e}")

    def set_telegram_config(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> None:
        """Met a jour la configuration Telegram."""
        if bot_token is not None:
            self._config.telegram_bot_token = bot_token.strip() if bot_token else None
        if chat_id is not None:
            self._config.telegram_chat_id = chat_id.strip() if chat_id else None
        self._save_config()
        logger.info("Telegram config updated")

    def update_config(self, updates: Dict[str, Any]) -> AppConfig:
        """
        Met a jour plusieurs valeurs de configuration.

        Args:
            updates: Dict des valeurs a mettre a jour

        Returns:
            Configuration mise a jour
        """
        if "finnhub_api_key" in updates:
            self._config.finnhub_api_key = updates["finnhub_api_key"]
            self._reload_finnhub_source()

        if "telegram_bot_token" in updates:
            self._config.telegram_bot_token = updates["telegram_bot_token"]

        if "telegram_chat_id" in updates:
            self._config.telegram_chat_id = updates["telegram_chat_id"]

        if "default_trading_mode" in updates:
            self._config.default_trading_mode = updates["default_trading_mode"]

        if "technical_alerts_enabled" in updates:
            self._config.technical_alerts_enabled = updates["technical_alerts_enabled"]

        self._save_config()
        return self._config

    def is_finnhub_configured(self) -> bool:
        """Verifie si Finnhub est configure."""
        self._load_from_env()
        return bool(self._config.finnhub_api_key)

    def is_telegram_configured(self) -> bool:
        """Verifie si Telegram est configure."""
        self._load_from_env()
        return bool(self._config.telegram_bot_token and self._config.telegram_chat_id)


# Singleton
_app_config_service: Optional[AppConfigService] = None


def get_app_config_service() -> AppConfigService:
    """Retourne l'instance singleton du service de configuration."""
    global _app_config_service
    if _app_config_service is None:
        _app_config_service = AppConfigService()
    return _app_config_service
