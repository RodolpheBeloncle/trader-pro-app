"""
Service de rafraichissement automatique des tokens Saxo.

Architecture Clean Code:
- Interface claire avec TokenRefreshService
- Retry avec backoff exponentiel
- Health monitoring et metriques
- Gestion intelligente des intervalles

SECURITE:
- Refresh proactif AVANT expiration
- Double tracking: access_token ET refresh_token
- Notifications en cas d'echec
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional, Protocol

logger = logging.getLogger(__name__)


class TokenStatus(Enum):
    """Statut du token."""
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    MISSING = "missing"
    REFRESH_FAILED = "refresh_failed"


@dataclass
class RefreshResult:
    """Resultat d'une tentative de refresh."""
    success: bool
    status: TokenStatus
    access_token_expires_in: int = 0
    refresh_token_expires_in: int = 0
    error: Optional[str] = None
    attempts: int = 1


@dataclass
class TokenHealth:
    """Etat de sante du systeme de tokens."""
    status: TokenStatus
    environment: str
    access_token_expires_in: int
    refresh_token_expires_in: int
    last_refresh: Optional[datetime]
    consecutive_failures: int
    next_refresh_in: int


class TokenRefreshStrategy(ABC):
    """Interface pour les strategies de refresh."""

    @abstractmethod
    def should_refresh(self, access_expires_in: int, refresh_expires_in: int) -> bool:
        """Determine si un refresh est necessaire."""
        pass

    @abstractmethod
    def get_refresh_interval(self, access_expires_in: int, refresh_expires_in: int) -> int:
        """Calcule l'intervalle optimal avant le prochain refresh."""
        pass


class ProactiveRefreshStrategy(TokenRefreshStrategy):
    """
    Strategie de refresh proactif.

    Refresh si:
    - Access token expire dans < access_threshold secondes
    - OU refresh token expire dans < refresh_threshold secondes (plus critique)
    """

    def __init__(
        self,
        access_threshold: int = 600,    # 10 minutes avant expiration access
        refresh_threshold: int = 1200,  # 20 minutes avant expiration refresh (critique!)
    ):
        self.access_threshold = access_threshold
        self.refresh_threshold = refresh_threshold

    def should_refresh(self, access_expires_in: int, refresh_expires_in: int) -> bool:
        """
        Determine si un refresh est necessaire.

        Le refresh_token est PLUS critique car s'il expire, on perd tout!
        """
        # Refresh si access_token expire bientot
        if access_expires_in < self.access_threshold:
            return True

        # Refresh si refresh_token expire bientot (PRIORITAIRE)
        if refresh_expires_in < self.refresh_threshold:
            return True

        return False

    def get_refresh_interval(self, access_expires_in: int, refresh_expires_in: int) -> int:
        """
        Calcule l'intervalle optimal.

        Retourne le temps avant le prochain refresh necessaire,
        avec une marge de securite.
        """
        # Prendre le minimum entre les deux expirations
        min_expiry = min(access_expires_in, refresh_expires_in)

        # Rafraichir a 50% de la duree restante (marge de securite)
        return max(60, min_expiry // 2)  # Minimum 1 minute


class RetryPolicy:
    """Politique de retry avec backoff exponentiel."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, attempt: int) -> float:
        """Calcule le delai avant la prochaine tentative."""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine si on doit reessayer."""
        if attempt >= self.max_attempts:
            return False

        # Ne pas retry sur certaines erreurs
        error_str = str(error).lower()
        non_retryable = ["invalid_grant", "unauthorized", "invalid_client"]
        if any(err in error_str for err in non_retryable):
            return False

        return True


class TokenRefreshService:
    """
    Service de rafraichissement automatique des tokens.

    Responsabilites:
    - Surveiller l'etat des tokens
    - Rafraichir proactivement avant expiration
    - Gerer les erreurs avec retry
    - Fournir des metriques de sante
    """

    # Durees par defaut Saxo (peuvent etre surchargees)
    DEFAULT_ACCESS_TOKEN_LIFETIME = 1200   # 20 minutes
    DEFAULT_REFRESH_TOKEN_LIFETIME = 2400  # 40 minutes

    def __init__(
        self,
        strategy: Optional[TokenRefreshStrategy] = None,
        retry_policy: Optional[RetryPolicy] = None,
        on_refresh_success: Optional[Callable[[RefreshResult], None]] = None,
        on_refresh_failure: Optional[Callable[[RefreshResult], None]] = None,
    ):
        self.strategy = strategy or ProactiveRefreshStrategy()
        self.retry_policy = retry_policy or RetryPolicy()
        self.on_refresh_success = on_refresh_success
        self.on_refresh_failure = on_refresh_failure

        # Metriques
        self._last_refresh: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._total_refreshes: int = 0
        self._total_failures: int = 0

    def check_and_refresh(self) -> RefreshResult:
        """
        Verifie l'etat du token et le rafraichit si necessaire.

        Returns:
            RefreshResult avec le resultat de l'operation
        """
        from src.config.settings import get_settings
        from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth

        settings = get_settings()

        if not settings.is_saxo_configured:
            return RefreshResult(
                success=True,
                status=TokenStatus.MISSING,
                error="Saxo not configured"
            )

        auth = get_saxo_auth(settings)
        token = auth.token_manager.get(auth.environment)

        if not token:
            return RefreshResult(
                success=True,
                status=TokenStatus.MISSING,
                error="No token found"
            )

        # Calculer les temps d'expiration
        access_expires_in = token.expires_in_seconds

        # Estimer expiration du refresh_token
        # Saxo ne donne pas cette info explicitement, on estime
        refresh_expires_in = self._estimate_refresh_token_expiry(token)

        logger.info(
            f"Token check: access expires in {access_expires_in}s, "
            f"refresh expires in ~{refresh_expires_in}s"
        )

        # Verifier si refresh necessaire
        if not self.strategy.should_refresh(access_expires_in, refresh_expires_in):
            return RefreshResult(
                success=True,
                status=TokenStatus.VALID,
                access_token_expires_in=access_expires_in,
                refresh_token_expires_in=refresh_expires_in,
            )

        # Effectuer le refresh avec retry
        return self._do_refresh_with_retry(auth, token.refresh_token)

    def _estimate_refresh_token_expiry(self, token) -> int:
        """
        Estime le temps restant avant expiration du refresh_token.

        Saxo refresh_token expire apres 40 min depuis l'emission.
        On estime en ajoutant 20 min (difference entre refresh et access lifetime)
        a l'expiration de l'access token.
        """
        access_expires_in = token.expires_in_seconds
        # refresh_token = access_token_expiry + 20 min (2400 - 1200 = 1200s = 20min)
        # Mais avec le buffer de 5 min applique, on ajuste
        return access_expires_in + 1200  # +20 minutes

    def _do_refresh_with_retry(self, auth, refresh_token: str) -> RefreshResult:
        """Execute le refresh avec politique de retry."""
        last_error = None
        attempts = 0

        while True:
            attempts += 1

            try:
                logger.info(f"Attempting token refresh (attempt {attempts})")
                new_token = auth.refresh_token(refresh_token)

                # Succes!
                self._last_refresh = datetime.now()
                self._consecutive_failures = 0
                self._total_refreshes += 1

                result = RefreshResult(
                    success=True,
                    status=TokenStatus.VALID,
                    access_token_expires_in=new_token.expires_in_seconds,
                    refresh_token_expires_in=self._estimate_refresh_token_expiry(new_token),
                    attempts=attempts,
                )

                logger.info(
                    f"Token refreshed successfully after {attempts} attempt(s). "
                    f"New expiration in {new_token.expires_in_seconds}s"
                )

                if self.on_refresh_success:
                    self.on_refresh_success(result)

                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Refresh attempt {attempts} failed: {e}")

                if not self.retry_policy.should_retry(attempts, e):
                    break

                delay = self.retry_policy.get_delay(attempts)
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)

        # Echec apres toutes les tentatives
        self._consecutive_failures += 1
        self._total_failures += 1

        result = RefreshResult(
            success=False,
            status=TokenStatus.REFRESH_FAILED,
            error=str(last_error),
            attempts=attempts,
        )

        logger.error(
            f"Token refresh failed after {attempts} attempts: {last_error}"
        )

        if self.on_refresh_failure:
            self.on_refresh_failure(result)

        return result

    def get_health(self) -> Optional[TokenHealth]:
        """
        Retourne l'etat de sante du systeme de tokens.

        Returns:
            TokenHealth ou None si pas de token
        """
        from src.config.settings import get_settings
        from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth

        settings = get_settings()

        if not settings.is_saxo_configured:
            return None

        auth = get_saxo_auth(settings)
        token = auth.token_manager.get(auth.environment)

        if not token:
            return TokenHealth(
                status=TokenStatus.MISSING,
                environment=auth.environment,
                access_token_expires_in=0,
                refresh_token_expires_in=0,
                last_refresh=self._last_refresh,
                consecutive_failures=self._consecutive_failures,
                next_refresh_in=0,
            )

        access_expires_in = token.expires_in_seconds
        refresh_expires_in = self._estimate_refresh_token_expiry(token)

        # Determiner le statut
        if access_expires_in <= 0:
            status = TokenStatus.EXPIRED
        elif self.strategy.should_refresh(access_expires_in, refresh_expires_in):
            status = TokenStatus.EXPIRING_SOON
        else:
            status = TokenStatus.VALID

        # Calculer prochain refresh
        next_refresh = self.strategy.get_refresh_interval(
            access_expires_in, refresh_expires_in
        )

        return TokenHealth(
            status=status,
            environment=auth.environment,
            access_token_expires_in=access_expires_in,
            refresh_token_expires_in=refresh_expires_in,
            last_refresh=self._last_refresh,
            consecutive_failures=self._consecutive_failures,
            next_refresh_in=next_refresh,
        )

    @property
    def stats(self) -> dict:
        """Retourne les statistiques du service."""
        return {
            "total_refreshes": self._total_refreshes,
            "total_failures": self._total_failures,
            "consecutive_failures": self._consecutive_failures,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "success_rate": (
                self._total_refreshes / (self._total_refreshes + self._total_failures)
                if (self._total_refreshes + self._total_failures) > 0
                else 1.0
            ),
        }


# Singleton
_service: Optional[TokenRefreshService] = None


def get_token_refresh_service() -> TokenRefreshService:
    """Factory pour obtenir le service de refresh."""
    global _service

    if _service is None:
        _service = TokenRefreshService(
            on_refresh_failure=_notify_refresh_failure,
        )

    return _service


def _notify_refresh_failure(result: RefreshResult) -> None:
    """Callback pour notifier un echec de refresh."""
    import asyncio

    async def send_notification():
        try:
            from src.infrastructure.notifications.telegram_service import get_telegram_service

            telegram = get_telegram_service()
            if not telegram.is_configured:
                return

            await telegram.send_message(
                f"<b>CONNEXION SAXO EXPIREE</b>\n\n"
                f"Erreur: {result.error}\n"
                f"Tentatives: {result.attempts}\n\n"
                f"<b>Action requise:</b> Reconnectez-vous via l'application."
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    try:
        asyncio.get_event_loop().run_until_complete(send_notification())
    except RuntimeError:
        asyncio.run(send_notification())
