"""
Implémentation du BrokerService pour Saxo Bank.

Service complet pour interagir avec l'API Saxo:
- Authentification OAuth2 avec PKCE
- Gestion du portefeuille
- Passage et gestion des ordres
- Recherche d'instruments

ARCHITECTURE:
- Implémente l'interface BrokerService
- Compose OAuth, ApiClient et TokenStore
- Gère le cycle de vie des tokens

DOCUMENTATION:
https://www.developer.saxo/openapi/learn
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.application.interfaces.broker_service import (
    BrokerService,
    BrokerCredentials,
    Portfolio,
    Position,
    Order,
    OrderRequest,
    OrderConfirmation,
    Instrument,
    Account,
)
from src.application.interfaces.token_repository import TokenRepository
from src.config.settings import Settings
from src.domain.exceptions import (
    BrokerError,
    BrokerAuthenticationError,
    TokenExpiredError,
)
from src.infrastructure.brokers.saxo.saxo_oauth import SaxoOAuthService
from src.infrastructure.brokers.saxo.saxo_api_client import SaxoApiClient
from src.infrastructure.brokers.saxo import saxo_mappers as mappers

logger = logging.getLogger(__name__)


class SaxoBroker(BrokerService):
    """
    Implémentation de BrokerService pour Saxo Bank.

    Fournit toutes les fonctionnalités de trading:
    - Authentification OAuth2 sécurisée
    - Consultation du portefeuille
    - Passage d'ordres
    - Recherche d'instruments

    Attributes:
        settings: Configuration de l'application
        oauth: Service OAuth pour l'authentification
        api_client: Client HTTP pour l'API Saxo
        token_store: Stockage sécurisé des tokens
    """

    BROKER_NAME = "saxo"

    def __init__(
        self,
        settings: Settings,
        token_store: Optional[TokenRepository] = None,
    ):
        """
        Initialise le broker Saxo.

        Args:
            settings: Configuration de l'application
            token_store: Repository pour le stockage des tokens
        """
        self.settings = settings
        self.oauth = SaxoOAuthService(settings)
        self.api_client = SaxoApiClient(settings)
        self.token_store = token_store

        self._client_key_cache: Dict[str, str] = {}

    # =========================================================================
    # BROKER PROPERTIES
    # =========================================================================

    @property
    def broker_name(self) -> str:
        """Retourne le nom du broker."""
        return self.BROKER_NAME

    @property
    def is_configured(self) -> bool:
        """Vérifie si le broker est configuré."""
        return self.settings.is_saxo_configured

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    async def get_authorization_url(
        self,
        user_id: str,
        state: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Génère l'URL d'autorisation OAuth2.

        Args:
            user_id: ID de l'utilisateur
            state: État personnalisé (optionnel)

        Returns:
            Dict avec auth_url et state
        """
        return self.oauth.get_authorization_url(user_id, state)

    async def handle_oauth_callback(
        self,
        user_id: str,
        authorization_code: str,
        state: str,
    ) -> BrokerCredentials:
        """
        Traite le callback OAuth et stocke les tokens.

        Args:
            user_id: ID de l'utilisateur
            authorization_code: Code d'autorisation
            state: État pour validation

        Returns:
            BrokerCredentials avec access_token

        Raises:
            BrokerAuthenticationError: Si l'authentification échoue
        """
        # Échanger le code contre des tokens
        token_response = self.oauth.exchange_code(authorization_code, state)

        # Stocker les tokens si un store est configuré
        if self.token_store:
            await self.token_store.save_token(
                user_id=user_id,
                broker=self.BROKER_NAME,
                token_data={
                    "access_token": token_response.access_token,
                    "refresh_token": token_response.refresh_token,
                    "expires_at": token_response.expires_at.isoformat(),
                }
            )

        logger.info(f"User {user_id} authenticated with Saxo")

        return BrokerCredentials(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            expires_at=token_response.expires_at,
            broker=self.BROKER_NAME,
        )

    async def refresh_credentials(
        self,
        credentials: BrokerCredentials,
    ) -> BrokerCredentials:
        """
        Rafraîchit les credentials expirés.

        Args:
            credentials: Credentials actuels

        Returns:
            Nouveaux credentials

        Raises:
            TokenExpiredError: Si le refresh échoue
        """
        if not credentials.refresh_token:
            raise TokenExpiredError(
                self.BROKER_NAME,
                "Pas de refresh token disponible"
            )

        token_response = self.oauth.refresh_tokens(credentials.refresh_token)

        return BrokerCredentials(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            expires_at=token_response.expires_at,
            broker=self.BROKER_NAME,
        )

    async def validate_credentials(
        self,
        credentials: BrokerCredentials,
    ) -> bool:
        """
        Valide que les credentials sont encore valides.

        Args:
            credentials: Credentials à valider

        Returns:
            True si les credentials sont valides
        """
        if credentials.is_expired:
            return False

        try:
            # Essayer un appel API simple
            self.api_client.get_client_info(credentials.access_token)
            return True
        except Exception:
            return False

    # =========================================================================
    # ACCOUNTS
    # =========================================================================

    async def get_accounts(
        self,
        credentials: BrokerCredentials,
    ) -> List[Account]:
        """
        Récupère la liste des comptes.

        Args:
            credentials: Credentials d'authentification

        Returns:
            Liste des comptes
        """
        self._check_credentials(credentials)

        client_key = await self._get_client_key(credentials)
        saxo_accounts = self.api_client.get_accounts(
            credentials.access_token,
            client_key,
        )

        return [
            Account(**mappers.map_account(acc))
            for acc in saxo_accounts
        ]

    # =========================================================================
    # PORTFOLIO
    # =========================================================================

    async def get_portfolio(
        self,
        credentials: BrokerCredentials,
    ) -> Portfolio:
        """
        Récupère le portefeuille complet.

        Args:
            credentials: Credentials d'authentification

        Returns:
            Portfolio avec positions et résumé
        """
        self._check_credentials(credentials)

        client_key = await self._get_client_key(credentials)

        # Récupérer positions et soldes
        saxo_positions = self.api_client.get_net_positions(
            credentials.access_token,
            client_key,
        )
        balances = self.api_client.get_balances(
            credentials.access_token,
            client_key,
        )

        # Mapper les positions
        positions_data = mappers.map_positions(saxo_positions)
        positions = [Position(**pos) for pos in positions_data]

        # Calculer le résumé
        summary = mappers.map_portfolio_summary(positions_data, balances)

        # Récupérer le premier compte
        accounts = self.api_client.get_accounts(
            credentials.access_token,
            client_key,
        )
        account_key = accounts[0].get("AccountKey") if accounts else None

        return Portfolio(
            positions=positions,
            account_key=account_key,
            summary=summary,
            updated_at=datetime.now().isoformat(),
        )

    async def get_positions(
        self,
        credentials: BrokerCredentials,
    ) -> List[Position]:
        """
        Récupère uniquement les positions.

        Args:
            credentials: Credentials d'authentification

        Returns:
            Liste des positions
        """
        portfolio = await self.get_portfolio(credentials)
        return portfolio.positions

    # =========================================================================
    # ORDERS
    # =========================================================================

    async def get_orders(
        self,
        credentials: BrokerCredentials,
        status: Optional[str] = "All",
    ) -> List[Order]:
        """
        Récupère les ordres.

        Args:
            credentials: Credentials d'authentification
            status: Filtre de statut

        Returns:
            Liste des ordres
        """
        self._check_credentials(credentials)

        client_key = await self._get_client_key(credentials)
        saxo_orders = self.api_client.get_orders(
            credentials.access_token,
            client_key,
            status=status or "All",
        )

        return [
            Order(**mappers.map_order(order))
            for order in saxo_orders
        ]

    async def place_order(
        self,
        credentials: BrokerCredentials,
        order: OrderRequest,
        account_id: str,
    ) -> OrderConfirmation:
        """
        Place un ordre.

        Args:
            credentials: Credentials d'authentification
            order: Requête d'ordre
            account_id: ID du compte (AccountKey)

        Returns:
            Confirmation de l'ordre
        """
        self._check_credentials(credentials)

        if not order.uic:
            raise BrokerError(
                self.BROKER_NAME,
                "UIC (Universal Instrument Code) requis pour placer un ordre Saxo"
            )

        # Construire la requête d'ordre
        order_data = mappers.build_order_request(
            account_key=account_id,
            uic=order.uic,
            asset_type=self._map_asset_type_to_saxo(order.asset_type),
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
        )

        # Placer l'ordre
        result = self.api_client.place_order(
            credentials.access_token,
            order_data,
        )

        logger.info(f"Order placed: {result.get('OrderId')}")

        return OrderConfirmation(
            order_id=str(result.get("OrderId", "")),
            status="pending",
            message=f"Ordre {order.side} {order.quantity} créé",
            details=result,
        )

    async def cancel_order(
        self,
        credentials: BrokerCredentials,
        order_id: str,
        account_id: str,
    ) -> bool:
        """
        Annule un ordre.

        Args:
            credentials: Credentials d'authentification
            order_id: ID de l'ordre
            account_id: ID du compte

        Returns:
            True si l'annulation a réussi
        """
        self._check_credentials(credentials)

        success = self.api_client.cancel_order(
            credentials.access_token,
            order_id,
            account_id,
        )

        if success:
            logger.info(f"Order {order_id} cancelled")
        else:
            logger.warning(f"Failed to cancel order {order_id}")

        return success

    # =========================================================================
    # INSTRUMENTS
    # =========================================================================

    async def search_instruments(
        self,
        credentials: BrokerCredentials,
        query: str,
        asset_types: Optional[List[str]] = None,
    ) -> List[Instrument]:
        """
        Recherche des instruments.

        Args:
            credentials: Credentials d'authentification
            query: Termes de recherche
            asset_types: Types d'actifs à chercher

        Returns:
            Liste des instruments correspondants
        """
        self._check_credentials(credentials)

        # Mapper les types d'actifs vers Saxo
        saxo_types = None
        if asset_types:
            saxo_types = [
                self._map_asset_type_to_saxo(at) for at in asset_types
            ]

        saxo_instruments = self.api_client.search_instruments(
            credentials.access_token,
            query,
            saxo_types,
        )

        return [
            Instrument(**mappers.map_instrument(inst))
            for inst in saxo_instruments
        ]

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _check_credentials(self, credentials: BrokerCredentials) -> None:
        """
        Vérifie que les credentials sont valides.

        Args:
            credentials: Credentials à vérifier

        Raises:
            TokenExpiredError: Si les credentials sont expirés
            BrokerAuthenticationError: Si pas de token
        """
        if not credentials.access_token:
            raise BrokerAuthenticationError(
                self.BROKER_NAME,
                "Authentification requise"
            )

        if credentials.is_expired:
            raise TokenExpiredError(
                self.BROKER_NAME,
                "Token expiré, rafraîchissement nécessaire"
            )

    async def _get_client_key(self, credentials: BrokerCredentials) -> str:
        """
        Récupère le ClientKey (avec cache).

        Args:
            credentials: Credentials d'authentification

        Returns:
            ClientKey Saxo
        """
        token_hash = hash(credentials.access_token)

        if token_hash in self._client_key_cache:
            return self._client_key_cache[token_hash]

        client_info = self.api_client.get_client_info(credentials.access_token)
        client_key = client_info.get("ClientKey", "")

        self._client_key_cache[token_hash] = client_key
        return client_key

    def _map_asset_type_to_saxo(self, asset_type: str) -> str:
        """
        Convertit un type d'actif vers le format Saxo.

        Args:
            asset_type: Type d'actif (stock, etf, etc.)

        Returns:
            Type Saxo correspondant
        """
        mapping = {
            "stock": "Stock",
            "etf": "Etf",
            "cfd": "CfdOnStock",
            "crypto": "FxSpot",
            "bond": "Bond",
        }
        return mapping.get(asset_type.lower(), "Stock")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_saxo_broker(
    settings: Settings,
    token_store: Optional[TokenRepository] = None,
) -> SaxoBroker:
    """
    Factory function pour créer un SaxoBroker.

    Args:
        settings: Configuration de l'application
        token_store: Repository pour les tokens

    Returns:
        Instance configurée de SaxoBroker
    """
    return SaxoBroker(settings, token_store)
