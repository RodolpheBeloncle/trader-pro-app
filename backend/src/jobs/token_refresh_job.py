"""
Job de rafraichissement automatique des tokens OAuth.

Ce job s'execute periodiquement pour rafraichir les tokens
qui expirent bientot.

ARCHITECTURE:
- Utilise le TokenStore pour recuperer les tokens expirant
- Utilise SaxoOAuthService pour rafraichir les tokens
- Met a jour le store avec les nouveaux tokens

FREQUENCE:
- Execute toutes les heures
- Rafraichit les tokens qui expirent dans l'heure suivante

GESTION DES ERREURS:
- Log les erreurs mais continue avec les autres tokens
- Ne bloque pas l'application en cas d'echec
"""

import logging
from datetime import datetime
from typing import Optional

from src.config.settings import get_settings
from src.infrastructure.persistence.token_store import get_token_store, FileTokenStore
from src.infrastructure.brokers.saxo.saxo_oauth import SaxoOAuthService
from src.domain.exceptions import TokenRefreshError, BrokerNotConfiguredError

logger = logging.getLogger(__name__)


class TokenRefreshJob:
    """
    Job pour rafraichir automatiquement les tokens OAuth.

    Ce job:
    1. Recupere tous les tokens qui expirent bientot
    2. Appelle l'API pour rafraichir chaque token
    3. Sauvegarde les nouveaux tokens

    Attributes:
        token_store: Store de tokens (FileTokenStore)
        oauth_service: Service OAuth Saxo
        within_hours: Fenetre d'expiration pour selectionner les tokens
    """

    def __init__(
        self,
        token_store: Optional[FileTokenStore] = None,
        oauth_service: Optional[SaxoOAuthService] = None,
        within_hours: int = 1
    ):
        """
        Initialise le job.

        Args:
            token_store: Store de tokens (defaut: singleton global)
            oauth_service: Service OAuth (defaut: cree depuis settings)
            within_hours: Rafraichir les tokens expirant dans N heures
        """
        self.settings = get_settings()
        self.token_store = token_store or get_token_store()
        self.within_hours = within_hours

        # Creer le service OAuth si Saxo est configure
        if oauth_service:
            self.oauth_service = oauth_service
        elif self.settings.is_saxo_configured:
            self.oauth_service = SaxoOAuthService(self.settings)
        else:
            self.oauth_service = None
            logger.warning("Saxo not configured, token refresh job will be limited")

    async def run(self) -> dict:
        """
        Execute le job de rafraichissement.

        Returns:
            Dict avec statistiques d'execution:
            {
                "total_checked": int,
                "refreshed": int,
                "failed": int,
                "errors": list[str]
            }
        """
        logger.info("=" * 50)
        logger.info("Token Refresh Job - Starting")
        logger.info("=" * 50)

        stats = {
            "total_checked": 0,
            "refreshed": 0,
            "failed": 0,
            "errors": [],
            "started_at": datetime.now().isoformat(),
        }

        try:
            # Recuperer les tokens qui expirent bientot
            expiring_tokens = await self.token_store.get_expiring_tokens(
                within_hours=self.within_hours
            )

            stats["total_checked"] = len(expiring_tokens)
            logger.info(f"Found {len(expiring_tokens)} tokens expiring soon")

            if not expiring_tokens:
                logger.info("No tokens to refresh")
                return stats

            # Rafraichir chaque token
            for user_id, broker, token in expiring_tokens:
                try:
                    await self._refresh_token(user_id, broker, token)
                    stats["refreshed"] += 1
                    logger.info(f"Refreshed token for {user_id}/{broker}")

                except TokenRefreshError as e:
                    stats["failed"] += 1
                    error_msg = f"{user_id}/{broker}: {e.message}"
                    stats["errors"].append(error_msg)
                    logger.error(f"Failed to refresh token: {error_msg}")

                except Exception as e:
                    stats["failed"] += 1
                    error_msg = f"{user_id}/{broker}: {str(e)}"
                    stats["errors"].append(error_msg)
                    logger.exception(f"Unexpected error refreshing token: {error_msg}")

        except Exception as e:
            logger.exception(f"Token refresh job failed: {e}")
            stats["errors"].append(f"Job error: {str(e)}")

        stats["finished_at"] = datetime.now().isoformat()
        logger.info(f"Token Refresh Job - Complete: {stats['refreshed']}/{stats['total_checked']} refreshed")

        return stats

    async def _refresh_token(
        self,
        user_id: str,
        broker: str,
        token
    ) -> None:
        """
        Rafraichit un token specifique.

        Args:
            user_id: ID de l'utilisateur
            broker: Nom du broker
            token: Token a rafraichir

        Raises:
            TokenRefreshError: Si le rafraichissement echoue
            BrokerNotConfiguredError: Si le broker n'est pas supporte
        """
        # Verifier que le broker est supporte
        if broker != "saxo":
            logger.warning(f"Unsupported broker for refresh: {broker}")
            return

        # Verifier que le service OAuth est disponible
        if not self.oauth_service:
            raise BrokerNotConfiguredError(
                broker,
                "Service OAuth non disponible pour le refresh"
            )

        # Verifier qu'on a un refresh token
        if not token.refresh_token:
            raise TokenRefreshError(
                broker,
                "Pas de refresh token disponible"
            )

        # Appeler l'API pour rafraichir
        new_tokens = self.oauth_service.refresh_tokens(token.refresh_token)

        # Mettre a jour le store
        await self.token_store.update_access_token(
            user_id=user_id,
            broker=broker,
            new_access_token=new_tokens.access_token,
            new_expires_at=new_tokens.expires_at.isoformat(),
            new_refresh_token=new_tokens.refresh_token if new_tokens.refresh_token != token.refresh_token else None
        )


def create_token_refresh_job() -> TokenRefreshJob:
    """
    Factory function pour creer un TokenRefreshJob.

    Returns:
        Instance configuree de TokenRefreshJob
    """
    return TokenRefreshJob()
