"""
Exceptions métier du domaine Stock Analyzer.

Ce module définit les exceptions spécifiques au domaine métier.
Ces exceptions sont indépendantes de l'infrastructure (pas d'erreurs HTTP ici).

ARCHITECTURE:
- Les exceptions domaine sont lancées par les entités et services du domaine
- La couche API les capture et les traduit en réponses HTTP appropriées
- Chaque exception a un code unique pour le logging et le debugging

UTILISATION:
    from src.domain.exceptions import TickerNotFoundError, InsufficientDataError

    if not data:
        raise TickerNotFoundError(ticker="AAPL")

MODIFICATION:
    - Pour ajouter une exception : créer une classe héritant de DomainError
    - Pour ajouter des attributs : les définir dans __init__ et appeler super()
"""

from typing import Optional


class DomainError(Exception):
    """
    Exception de base pour toutes les erreurs du domaine.

    Attributs:
        message: Message d'erreur humainement lisible
        code: Code unique de l'erreur (pour logging/debugging)
        details: Détails supplémentaires optionnels

    Toutes les exceptions du domaine doivent hériter de cette classe.
    """

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convertit l'exception en dictionnaire pour la sérialisation."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# EXCEPTIONS TICKER / STOCK
# =============================================================================

class TickerError(DomainError):
    """Exception de base pour les erreurs liées aux tickers."""

    def __init__(
        self,
        ticker: str,
        message: str,
        code: str = "TICKER_ERROR"
    ):
        self.ticker = ticker
        super().__init__(
            message=message,
            code=code,
            details={"ticker": ticker}
        )


class TickerInvalidError(TickerError):
    """
    Le format du ticker est invalide.

    Lancée quand le ticker ne respecte pas les règles de validation
    (ex: caractères spéciaux non autorisés, longueur incorrecte).
    """

    def __init__(self, ticker: str, reason: str = "Format invalide"):
        super().__init__(
            ticker=ticker,
            message=f"Le ticker '{ticker}' n'est pas valide: {reason}",
            code="TICKER_INVALID"
        )
        self.reason = reason


class TickerNotFoundError(TickerError):
    """
    Le ticker n'existe pas ou n'a pas été trouvé.

    Lancée quand l'API de données (Yahoo Finance) ne trouve pas le ticker.
    """

    def __init__(self, ticker: str):
        super().__init__(
            ticker=ticker,
            message=f"Le ticker '{ticker}' n'a pas été trouvé",
            code="TICKER_NOT_FOUND"
        )


class InsufficientDataError(TickerError):
    """
    Données insuffisantes pour effectuer l'analyse.

    Lancée quand le ticker existe mais n'a pas assez de données historiques
    pour calculer les performances sur toutes les périodes demandées.
    """

    def __init__(self, ticker: str, required_days: int, available_days: int):
        super().__init__(
            ticker=ticker,
            message=(
                f"Données insuffisantes pour '{ticker}': "
                f"{available_days} jours disponibles, {required_days} requis"
            ),
            code="INSUFFICIENT_DATA"
        )
        self.required_days = required_days
        self.available_days = available_days
        self.details["required_days"] = required_days
        self.details["available_days"] = available_days


# =============================================================================
# EXCEPTIONS AUTHENTIFICATION / TOKEN
# =============================================================================

class AuthenticationError(DomainError):
    """Exception de base pour les erreurs d'authentification."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message=message, code=code)


class TokenExpiredError(AuthenticationError):
    """
    Le token d'accès a expiré.

    Lancée quand le token a dépassé sa date d'expiration.
    Le client doit rafraîchir le token ou se réauthentifier.
    """

    def __init__(self, broker: str = "unknown"):
        super().__init__(
            message=f"Le token d'accès pour '{broker}' a expiré",
            code="TOKEN_EXPIRED"
        )
        self.broker = broker
        self.details["broker"] = broker


class TokenInvalidError(AuthenticationError):
    """
    Le token est invalide (malformé, révoqué, etc.).

    Différent de TokenExpiredError : ici le token ne peut pas être rafraîchi.
    """

    def __init__(self, reason: str = "Token invalide"):
        super().__init__(
            message=f"Token invalide: {reason}",
            code="TOKEN_INVALID"
        )
        self.reason = reason


class TokenRefreshError(AuthenticationError):
    """
    Impossible de rafraîchir le token.

    Lancée quand le refresh_token est invalide ou que l'API refuse le refresh.
    """

    def __init__(self, broker: str, reason: str):
        super().__init__(
            message=f"Impossible de rafraîchir le token pour '{broker}': {reason}",
            code="TOKEN_REFRESH_FAILED"
        )
        self.broker = broker
        self.reason = reason
        self.details["broker"] = broker
        self.details["reason"] = reason


class OAuthError(AuthenticationError):
    """
    Erreur lors du flux OAuth2.

    Lancée pour les erreurs CSRF, state invalide, code expiré, etc.
    """

    def __init__(self, reason: str):
        super().__init__(
            message=f"Erreur OAuth: {reason}",
            code="OAUTH_ERROR"
        )
        self.reason = reason


# =============================================================================
# EXCEPTIONS BROKER / TRADING
# =============================================================================

class BrokerError(DomainError):
    """Exception de base pour les erreurs liées aux brokers."""

    def __init__(
        self,
        broker: str,
        message: str,
        code: str = "BROKER_ERROR"
    ):
        self.broker = broker
        super().__init__(
            message=message,
            code=code,
            details={"broker": broker}
        )


class BrokerNotConfiguredError(BrokerError):
    """
    Le broker n'est pas configuré.

    Lancée quand les credentials du broker manquent dans la configuration.
    """

    def __init__(self, broker: str):
        super().__init__(
            broker=broker,
            message=f"Le broker '{broker}' n'est pas configuré",
            code="BROKER_NOT_CONFIGURED"
        )


class BrokerConnectionError(BrokerError):
    """
    Impossible de se connecter au broker.

    Lancée pour les erreurs réseau ou les API inaccessibles.
    """

    def __init__(self, broker: str, reason: str):
        super().__init__(
            broker=broker,
            message=f"Impossible de se connecter à '{broker}': {reason}",
            code="BROKER_CONNECTION_ERROR"
        )
        self.reason = reason
        self.details["reason"] = reason


class OrderError(BrokerError):
    """Exception de base pour les erreurs d'ordres."""

    def __init__(
        self,
        broker: str,
        message: str,
        order_id: Optional[str] = None,
        code: str = "ORDER_ERROR"
    ):
        super().__init__(broker=broker, message=message, code=code)
        self.order_id = order_id
        if order_id:
            self.details["order_id"] = order_id


class OrderRejectedError(OrderError):
    """
    L'ordre a été rejeté par le broker.

    Peut être dû à : fonds insuffisants, marché fermé, ticker invalide, etc.
    """

    def __init__(self, broker: str, reason: str, order_id: Optional[str] = None):
        super().__init__(
            broker=broker,
            message=f"Ordre rejeté: {reason}",
            order_id=order_id,
            code="ORDER_REJECTED"
        )
        self.reason = reason
        self.details["reason"] = reason


class InsufficientFundsError(OrderError):
    """Fonds insuffisants pour passer l'ordre."""

    def __init__(self, broker: str, required: float, available: float):
        super().__init__(
            broker=broker,
            message=(
                f"Fonds insuffisants: {available:.2f} disponibles, "
                f"{required:.2f} requis"
            ),
            code="INSUFFICIENT_FUNDS"
        )
        self.required = required
        self.available = available
        self.details["required"] = required
        self.details["available"] = available


class OrderValidationError(DomainError):
    """
    Erreur de validation d'un ordre.

    Lancée quand les paramètres de l'ordre sont invalides.
    """

    def __init__(self, message: str):
        super().__init__(
            message=f"Validation de l'ordre échouée: {message}",
            code="ORDER_VALIDATION_ERROR"
        )


class BrokerAuthenticationError(BrokerError):
    """
    Erreur d'authentification avec le broker.

    Lancée quand l'authentification OAuth échoue.
    """

    def __init__(self, broker: str, reason: str):
        super().__init__(
            broker=broker,
            message=f"Authentification échouée pour '{broker}': {reason}",
            code="BROKER_AUTH_ERROR"
        )
        self.reason = reason
        self.details["reason"] = reason


class BrokerApiError(BrokerError):
    """
    Erreur lors d'un appel API au broker.

    Lancée pour les erreurs HTTP non spécifiques.
    """

    def __init__(self, broker: str, message: str):
        super().__init__(
            broker=broker,
            message=message,
            code="BROKER_API_ERROR"
        )


class BrokerRateLimitError(BrokerError):
    """
    Rate limit atteint pour le broker.
    """

    def __init__(self, broker: str, message: str):
        super().__init__(
            broker=broker,
            message=message,
            code="BROKER_RATE_LIMIT"
        )


# =============================================================================
# EXCEPTIONS DATA
# =============================================================================

class DataFetchError(DomainError):
    """
    Erreur lors de la récupération de données externes.

    Lancée quand un appel à une API de données échoue.
    """

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="DATA_FETCH_ERROR"
        )


class AnalysisError(TickerError):
    """
    Erreur lors de l'analyse d'un stock.

    Lancée quand l'analyse ne peut pas être complétée.
    """

    def __init__(self, ticker: str, reason: str):
        super().__init__(
            ticker=ticker,
            message=f"Erreur d'analyse pour '{ticker}': {reason}",
            code="ANALYSIS_ERROR"
        )
        self.reason = reason
        self.details["reason"] = reason


# =============================================================================
# EXCEPTIONS VALIDATION
# =============================================================================

class ValidationError(DomainError):
    """
    Erreur de validation des données d'entrée.

    Utilisée pour les value objects et entités quand les données
    ne respectent pas les règles métier.
    """

    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation échouée pour '{field}': {message}",
            code="VALIDATION_ERROR",
            details={"field": field}
        )
        self.field = field


# =============================================================================
# EXCEPTIONS RATE LIMITING
# =============================================================================

class RateLimitError(DomainError):
    """
    Limite de taux d'appels atteinte.

    Lancée quand l'API externe refuse les requêtes pour cause de rate limiting.
    """

    def __init__(self, service: str, retry_after: Optional[int] = None):
        message = f"Limite de requêtes atteinte pour '{service}'"
        if retry_after:
            message += f", réessayer dans {retry_after} secondes"

        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details={
                "service": service,
                "retry_after": retry_after
            }
        )
        self.service = service
        self.retry_after = retry_after
