"""
Constantes globales de l'application Stock Analyzer.

Ce fichier centralise TOUTES les valeurs constantes pour éviter les "magic numbers".

RÈGLES:
1. Nommer les constantes en SCREAMING_SNAKE_CASE
2. Grouper par catégorie avec des commentaires
3. Documenter l'unité (jours, heures, %, etc.)
4. Ne JAMAIS utiliser de valeurs littérales dans le code, toujours importer depuis ici

UTILISATION:
    from src.config.constants import PERIOD_3_MONTHS_DAYS, HIGH_VOLATILITY_THRESHOLD

MODIFICATION:
    - Pour ajouter une constante : l'ajouter dans la catégorie appropriée
    - Pour modifier une valeur : changer ici, le changement se propage partout
"""

from enum import Enum, auto
from typing import Final

# =============================================================================
# PÉRIODES D'ANALYSE (en jours calendaires)
# =============================================================================

PERIOD_3_MONTHS_DAYS: Final[int] = 90
"""Période de 3 mois en jours."""

PERIOD_6_MONTHS_DAYS: Final[int] = 180
"""Période de 6 mois en jours."""

PERIOD_1_YEAR_DAYS: Final[int] = 365
"""Période d'1 an en jours."""

PERIOD_3_YEARS_DAYS: Final[int] = 1095
"""Période de 3 ans en jours (365 * 3)."""

PERIOD_5_YEARS_DAYS: Final[int] = 1825
"""Période de 5 ans en jours (365 * 5)."""

# Labels pour l'affichage
PERIOD_LABELS: Final[dict[int, str]] = {
    PERIOD_3_MONTHS_DAYS: "3M",
    PERIOD_6_MONTHS_DAYS: "6M",
    PERIOD_1_YEAR_DAYS: "1Y",
    PERIOD_3_YEARS_DAYS: "3Y",
    PERIOD_5_YEARS_DAYS: "5Y",
}

# Périodes par défaut pour l'analyse
DEFAULT_ANALYSIS_PERIODS: Final[list[int]] = [
    PERIOD_3_MONTHS_DAYS,
    PERIOD_6_MONTHS_DAYS,
    PERIOD_1_YEAR_DAYS,
    PERIOD_3_YEARS_DAYS,
    PERIOD_5_YEARS_DAYS,
]


# =============================================================================
# SÉCURITÉ & AUTHENTIFICATION
# =============================================================================

TOKEN_REFRESH_HOURS: Final[int] = 23
"""
Heures avant expiration pour rafraîchir le token.
Saxo expire les tokens après 24h, on rafraîchit à 23h pour marge de sécurité.
"""

OAUTH_STATE_TTL_SECONDS: Final[int] = 300
"""Durée de validité du state OAuth2 (5 minutes)."""

SESSION_TTL_SECONDS: Final[int] = 86400
"""Durée de validité de la session (24 heures)."""

PKCE_CODE_VERIFIER_LENGTH: Final[int] = 64
"""Longueur du code_verifier PKCE en caractères (doit être entre 43 et 128)."""


# =============================================================================
# PERFORMANCE & LIMITES
# =============================================================================

MAX_BATCH_SIZE: Final[int] = 50
"""Nombre maximum de tickers à analyser en une seule requête batch."""

MAX_CONCURRENT_REQUESTS: Final[int] = 5
"""Nombre maximum de requêtes parallèles vers les APIs externes."""

API_TIMEOUT_SECONDS: Final[int] = 30
"""Timeout par défaut pour les appels API externes."""

CACHE_TTL_SECONDS: Final[int] = 3600
"""Durée de vie du cache pour les analyses (1 heure)."""

CHART_RESAMPLE_INTERVAL: Final[str] = "W"
"""
Intervalle de rééchantillonnage pour les graphiques.
'W' = hebdomadaire, 'D' = journalier, 'M' = mensuel.
"""

CHART_MAX_POINTS: Final[int] = 260
"""Nombre maximum de points dans un graphique (environ 5 ans en données hebdomadaires)."""


# =============================================================================
# ANALYSE FINANCIÈRE
# =============================================================================

ANNUALIZATION_FACTOR: Final[int] = 252
"""
Nombre de jours de trading par an pour annualiser la volatilité.
Standard: 252 jours de marché ouvert par an.
"""

HIGH_VOLATILITY_THRESHOLD: Final[float] = 0.30
"""Seuil de volatilité haute (30%). Au-delà, le stock est considéré risqué."""

MEDIUM_VOLATILITY_THRESHOLD: Final[float] = 0.20
"""Seuil de volatilité moyenne (20%). Entre stable et risqué."""

LOW_VOLATILITY_THRESHOLD: Final[float] = 0.15
"""Seuil de volatilité basse (15%). En-dessous, le stock est considéré stable."""

TOKEN_EXPIRY_BUFFER_SECONDS: Final[int] = 300
"""Marge de sécurité avant expiration du token (5 minutes)."""

MIN_DATA_POINTS_FOR_ANALYSIS: Final[int] = 20
"""Nombre minimum de points de données requis pour une analyse valide."""


# =============================================================================
# FORMATS & AFFICHAGE
# =============================================================================

PRICE_DECIMAL_PLACES: Final[int] = 2
"""Nombre de décimales pour les prix."""

PERCENTAGE_DECIMAL_PLACES: Final[int] = 2
"""Nombre de décimales pour les pourcentages."""

DATE_FORMAT_ISO: Final[str] = "%Y-%m-%d"
"""Format de date ISO standard."""

DATETIME_FORMAT_ISO: Final[str] = "%Y-%m-%dT%H:%M:%SZ"
"""Format datetime ISO avec timezone UTC."""


# =============================================================================
# TYPES D'ACTIFS (Énumération)
# =============================================================================

class AssetType(str, Enum):
    """
    Types d'actifs supportés.

    Hérite de str pour permettre la sérialisation JSON directe.
    """
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"
    CFD = "cfd"
    BOND = "bond"
    OPTION = "option"
    FUTURE = "future"


class OrderType(str, Enum):
    """Types d'ordres supportés."""
    MARKET = "Market"
    LIMIT = "Limit"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"


class OrderSide(str, Enum):
    """Direction de l'ordre."""
    BUY = "Buy"
    SELL = "Sell"


class OrderStatus(str, Enum):
    """Statuts possibles d'un ordre."""
    PENDING = "pending"
    WORKING = "working"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BrokerName(str, Enum):
    """Brokers supportés."""
    SAXO = "saxo"
    # Futures brokers (extensibilité)
    # INTERACTIVE_BROKERS = "ib"
    # ALPACA = "alpaca"
    # DEGIRO = "degiro"


class VolatilityLevel(str, Enum):
    """Niveaux de volatilité."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


# =============================================================================
# MESSAGES D'ERREUR STANDARDS
# =============================================================================

ERROR_MESSAGES: Final[dict[str, str]] = {
    "TICKER_INVALID": "Le ticker '{ticker}' n'est pas valide",
    "TICKER_NOT_FOUND": "Le ticker '{ticker}' n'a pas été trouvé",
    "INSUFFICIENT_DATA": "Données insuffisantes pour l'analyse de '{ticker}'",
    "API_ERROR": "Erreur lors de l'appel à l'API externe",
    "BROKER_NOT_CONFIGURED": "Le broker {broker} n'est pas configuré",
    "TOKEN_EXPIRED": "Le token d'accès a expiré",
    "TOKEN_INVALID": "Le token d'accès est invalide",
    "UNAUTHORIZED": "Authentification requise",
    "RATE_LIMITED": "Trop de requêtes, veuillez réessayer plus tard",
}


# =============================================================================
# ENDPOINTS SAXO (relatifs à l'URL de base)
# =============================================================================

SAXO_ENDPOINTS: Final[dict[str, str]] = {
    "authorize": "/authorize",
    "token": "/token",
    "client_info": "/port/v1/clients/me",
    "accounts": "/port/v1/accounts",
    "positions": "/port/v1/netpositions",
    "balance": "/port/v1/balances",
    "orders": "/port/v1/orders",
    "orders_place": "/trade/v2/orders",
    "history": "/cs/v1/reports/trades",
    "instruments": "/ref/v1/instruments",
}


# =============================================================================
# SCOPES OAUTH SAXO
# =============================================================================

SAXO_DEFAULT_SCOPES: Final[list[str]] = [
    "openid",
    "profile",
    "read",
    "write",
    "trade",
]
"""Scopes OAuth2 demandés par défaut pour Saxo."""
