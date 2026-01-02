"""
Configuration centralisée de l'application Stock Analyzer.

Ce module utilise Pydantic Settings pour :
- Charger les variables d'environnement depuis .env
- Valider les types et formats
- Fournir des valeurs par défaut sécurisées

ARCHITECTURE: Ce fichier fait partie de la couche CONFIG, accessible par toutes les couches.

UTILISATION:
    from src.config.settings import settings
    print(settings.SAXO_APP_KEY)

MODIFICATION:
    - Pour ajouter une nouvelle variable : ajouter un attribut à la classe Settings
    - Pour changer une valeur par défaut : modifier la valeur dans la classe
    - Pour rendre une variable obligatoire : ne pas fournir de valeur par défaut
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    """
    Configuration de l'application chargée depuis les variables d'environnement.

    Les variables sont automatiquement chargées depuis :
    1. Variables d'environnement système
    2. Fichier .env (si présent)

    Attributs:
        APP_NAME: Nom de l'application
        DEBUG: Mode debug (True pour développement)

        # Saxo Bank API
        SAXO_APP_KEY: Clé d'application Saxo
        SAXO_APP_SECRET: Secret d'application Saxo
        SAXO_ENVIRONMENT: Environnement ('SIM' ou 'LIVE')
        SAXO_REDIRECT_URI: URI de redirection OAuth2

        # Sécurité
        ENCRYPTION_KEY: Clé Fernet pour chiffrer les tokens
        SESSION_SECRET: Secret pour les cookies de session

        # Serveur
        HOST: Adresse d'écoute du serveur
        PORT: Port d'écoute du serveur
        CORS_ORIGINS: Origines autorisées pour CORS
    """

    # ==========================================================================
    # APPLICATION
    # ==========================================================================
    APP_NAME: str = "Stock Analyzer"
    DEBUG: bool = Field(default=False, description="Active le mode debug")
    LOG_LEVEL: str = Field(default="INFO", description="Niveau de log")

    # ==========================================================================
    # SAXO BANK API
    # ==========================================================================
    SAXO_APP_KEY: Optional[str] = Field(
        default=None,
        description="Clé d'application Saxo (obtenue sur developer.saxo)"
    )
    SAXO_APP_SECRET: Optional[str] = Field(
        default=None,
        description="Secret d'application Saxo"
    )
    SAXO_ENVIRONMENT: str = Field(
        default="SIM",
        description="Environnement Saxo: 'SIM' (simulation) ou 'LIVE' (production)"
    )
    SAXO_REDIRECT_URI: str = Field(
        default="http://localhost:5173",
        description="URI de redirection OAuth2 (doit correspondre à l'app Saxo)"
    )

    # ==========================================================================
    # SÉCURITÉ
    # ==========================================================================
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Clé Fernet 32 bytes base64 pour chiffrer les tokens"
    )
    SESSION_SECRET: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret pour signer les cookies de session"
    )

    # ==========================================================================
    # SERVEUR
    # ==========================================================================
    HOST: str = Field(default="0.0.0.0", description="Adresse d'écoute")
    PORT: int = Field(default=8000, description="Port d'écoute")
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Origines CORS autorisées (séparées par des virgules)"
    )

    # ==========================================================================
    # CONFIGURATION CACHE
    # ==========================================================================
    FORCE_ENV_CONFIG: bool = Field(
        default=False,
        description="Force l'utilisation des variables .env au lieu du fichier chiffré"
    )

    # ==========================================================================
    # CHEMINS
    # ==========================================================================
    DATA_DIR: str = Field(
        default="data",
        description="Répertoire pour les données (tokens, cache)"
    )
    TOKENS_FILE: str = Field(
        default="tokens.json",
        description="Nom du fichier de stockage des tokens"
    )
    MARKETS_FILE: str = Field(
        default="markets.json",
        description="Nom du fichier des presets de marchés"
    )
    DATABASE_PATH: str = Field(
        default="data/stock_analyzer.db",
        description="Chemin de la base de données SQLite"
    )

    # ==========================================================================
    # TELEGRAM (pour les alertes)
    # ==========================================================================
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Token du bot Telegram (obtenu via @BotFather)"
    )
    TELEGRAM_CHAT_ID: Optional[str] = Field(
        default=None,
        description="ID du chat Telegram pour recevoir les alertes"
    )

    # ==========================================================================
    # FINNHUB (pour les actualités)
    # ==========================================================================
    FINNHUB_API_KEY: Optional[str] = Field(
        default=None,
        description="Clé API Finnhub (gratuit: 60 req/min)"
    )

    # ==========================================================================
    # VALIDATION
    # ==========================================================================

    @field_validator("SAXO_ENVIRONMENT")
    @classmethod
    def validate_saxo_environment(cls, v: str) -> str:
        """Valide que l'environnement Saxo est SIM ou LIVE."""
        allowed = ("SIM", "LIVE")
        if v.upper() not in allowed:
            raise ValueError(f"SAXO_ENVIRONMENT doit être parmi {allowed}")
        return v.upper()

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Valide le niveau de log."""
        allowed = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL doit être parmi {allowed}")
        return v.upper()

    # ==========================================================================
    # PROPRIÉTÉS CALCULÉES
    # ==========================================================================

    @property
    def cors_origins_list(self) -> list[str]:
        """Retourne la liste des origines CORS autorisées."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def saxo_auth_url(self) -> str:
        """Retourne l'URL d'authentification Saxo selon l'environnement."""
        if self.SAXO_ENVIRONMENT == "LIVE":
            return "https://live.logonvalidation.net"
        return "https://sim.logonvalidation.net"

    @property
    def saxo_api_url(self) -> str:
        """Retourne l'URL de l'API Saxo selon l'environnement."""
        if self.SAXO_ENVIRONMENT == "LIVE":
            return "https://gateway.saxobank.com/openapi"
        return "https://gateway.saxobank.com/sim/openapi"

    @property
    def is_saxo_configured(self) -> bool:
        """Vérifie si Saxo Bank est configuré."""
        return bool(self.SAXO_APP_KEY and self.SAXO_APP_SECRET)

    @property
    def is_telegram_configured(self) -> bool:
        """Vérifie si Telegram est configuré."""
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)

    @property
    def is_finnhub_configured(self) -> bool:
        """Vérifie si Finnhub est configuré."""
        return bool(self.FINNHUB_API_KEY)

    @property
    def tokens_path(self) -> str:
        """Retourne le chemin complet du fichier de tokens."""
        return f"{self.DATA_DIR}/{self.TOKENS_FILE}"

    # ==========================================================================
    # CONFIGURATION PYDANTIC
    # ==========================================================================

    class Config:
        """Configuration Pydantic Settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore les variables d'environnement inconnues


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne l'instance unique des settings (singleton avec cache).

    Utilise lru_cache pour éviter de relire le fichier .env à chaque appel.

    Returns:
        Settings: Instance des paramètres de l'application
    """
    return Settings()


# Instance globale pour import facile
settings = get_settings()
