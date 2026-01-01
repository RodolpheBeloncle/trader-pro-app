"""
Use Case : Placement d'un ordre.

Orchestre le placement d'un ordre via le broker:
- Validation de l'ordre
- Vérification des contraintes
- Placement effectif
- Retour de confirmation

ARCHITECTURE:
- Dépend uniquement du BrokerService
- Applique les règles métier de validation
- Gère les erreurs de placement

UTILISATION:
    use_case = PlaceOrderUseCase(broker_service)
    confirmation = await use_case.execute(credentials, order_request, account_id)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.application.interfaces.broker_service import (
    BrokerService,
    BrokerCredentials,
    OrderRequest,
    OrderConfirmation,
)
from src.config.constants import OrderType, OrderSide
from src.domain.exceptions import (
    OrderValidationError,
    InsufficientFundsError,
    BrokerError,
)

logger = logging.getLogger(__name__)


@dataclass
class OrderValidationResult:
    """Résultat de la validation d'un ordre."""

    is_valid: bool
    errors: list[str]

    @classmethod
    def valid(cls) -> "OrderValidationResult":
        """Crée un résultat valide."""
        return cls(is_valid=True, errors=[])

    @classmethod
    def invalid(cls, errors: list[str]) -> "OrderValidationResult":
        """Crée un résultat invalide."""
        return cls(is_valid=False, errors=errors)


class PlaceOrderUseCase:
    """
    Use Case pour placer un ordre.

    Valide l'ordre selon les règles métier puis le soumet au broker.

    Attributes:
        broker: Service broker pour exécuter l'ordre
    """

    # Quantités min/max par type d'actif
    MIN_QUANTITIES = {
        "stock": 1,
        "etf": 1,
        "cfd": 0.01,
        "crypto": 0.0001,
    }

    MAX_QUANTITIES = {
        "stock": 100000,
        "etf": 100000,
        "cfd": 10000,
        "crypto": 1000000,
    }

    def __init__(self, broker: BrokerService):
        """
        Initialise le use case.

        Args:
            broker: Service broker
        """
        self.broker = broker

    async def execute(
        self,
        credentials: BrokerCredentials,
        order: OrderRequest,
        account_id: str,
    ) -> OrderConfirmation:
        """
        Place un ordre après validation.

        Args:
            credentials: Credentials d'authentification
            order: Requête d'ordre
            account_id: ID du compte cible

        Returns:
            Confirmation de l'ordre

        Raises:
            OrderValidationError: Si l'ordre est invalide
            BrokerError: Si le placement échoue
        """
        logger.info(
            f"Placing {order.side} order for {order.quantity} "
            f"{order.asset_type} (UIC: {order.uic})"
        )

        # Valider l'ordre
        validation = self._validate_order(order)
        if not validation.is_valid:
            error_msg = "; ".join(validation.errors)
            logger.warning(f"Order validation failed: {error_msg}")
            raise OrderValidationError(error_msg)

        # Placer l'ordre via le broker
        try:
            confirmation = await self.broker.place_order(
                credentials,
                order,
                account_id,
            )

            logger.info(
                f"Order placed successfully: {confirmation.order_id} "
                f"(status: {confirmation.status})"
            )

            return confirmation

        except BrokerError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error placing order: {e}")
            raise BrokerError(self.broker.broker_name, str(e))

    def _validate_order(self, order: OrderRequest) -> OrderValidationResult:
        """
        Valide un ordre selon les règles métier.

        Args:
            order: Ordre à valider

        Returns:
            Résultat de la validation
        """
        errors: list[str] = []

        # Valider la quantité
        min_qty = self.MIN_QUANTITIES.get(order.asset_type, 1)
        max_qty = self.MAX_QUANTITIES.get(order.asset_type, 100000)

        if order.quantity <= 0:
            errors.append("La quantité doit être positive")
        elif order.quantity < min_qty:
            errors.append(f"Quantité minimum: {min_qty}")
        elif order.quantity > max_qty:
            errors.append(f"Quantité maximum: {max_qty}")

        # Valider le type d'ordre
        if order.order_type not in [ot.value for ot in OrderType]:
            errors.append(f"Type d'ordre invalide: {order.order_type}")

        # Valider la direction
        if order.side not in [os.value for os in OrderSide]:
            errors.append(f"Direction invalide: {order.side}")

        # Valider le prix pour les ordres Limit
        if order.order_type in (OrderType.LIMIT.value, "Limit"):
            if order.price is None or order.price <= 0:
                errors.append("Prix requis pour un ordre Limit")

        # Valider l'UIC
        if order.uic is None:
            errors.append("UIC (Universal Instrument Code) requis")

        if errors:
            return OrderValidationResult.invalid(errors)

        return OrderValidationResult.valid()


class CancelOrderUseCase:
    """
    Use Case pour annuler un ordre.

    Attributes:
        broker: Service broker
    """

    def __init__(self, broker: BrokerService):
        """
        Initialise le use case.

        Args:
            broker: Service broker
        """
        self.broker = broker

    async def execute(
        self,
        credentials: BrokerCredentials,
        order_id: str,
        account_id: str,
    ) -> bool:
        """
        Annule un ordre existant.

        Args:
            credentials: Credentials d'authentification
            order_id: ID de l'ordre à annuler
            account_id: ID du compte

        Returns:
            True si l'annulation a réussi
        """
        logger.info(f"Cancelling order {order_id}")

        success = await self.broker.cancel_order(
            credentials,
            order_id,
            account_id,
        )

        if success:
            logger.info(f"Order {order_id} cancelled successfully")
        else:
            logger.warning(f"Failed to cancel order {order_id}")

        return success


class GetOrdersUseCase:
    """
    Use Case pour récupérer les ordres.

    Attributes:
        broker: Service broker
    """

    def __init__(self, broker: BrokerService):
        """
        Initialise le use case.

        Args:
            broker: Service broker
        """
        self.broker = broker

    async def execute(
        self,
        credentials: BrokerCredentials,
        status: Optional[str] = None,
    ) -> list:
        """
        Récupère les ordres.

        Args:
            credentials: Credentials d'authentification
            status: Filtre de statut (optionnel)

        Returns:
            Liste des ordres
        """
        logger.info(f"Fetching orders (status: {status or 'All'})")

        orders = await self.broker.get_orders(credentials, status)

        logger.info(f"Retrieved {len(orders)} orders")
        return orders


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_place_order_use_case(broker: BrokerService) -> PlaceOrderUseCase:
    """Factory pour PlaceOrderUseCase."""
    return PlaceOrderUseCase(broker)


def create_cancel_order_use_case(broker: BrokerService) -> CancelOrderUseCase:
    """Factory pour CancelOrderUseCase."""
    return CancelOrderUseCase(broker)


def create_get_orders_use_case(broker: BrokerService) -> GetOrdersUseCase:
    """Factory pour GetOrdersUseCase."""
    return GetOrdersUseCase(broker)
