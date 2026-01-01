"""
Factory pour la création de brokers.

Permet de créer des instances de brokers selon le type demandé.
Prépare l'architecture pour supporter plusieurs brokers.

ARCHITECTURE:
- Pattern Factory
- Extensible pour nouveaux brokers
- Injection de dépendances

UTILISATION:
    factory = BrokerFactory(settings, token_store)
    broker = factory.create("saxo")
"""

import logging
from typing import Dict, Optional, Type

from src.application.interfaces.broker_service import BrokerService
from src.application.interfaces.token_repository import TokenRepository
from src.config.settings import Settings
from src.domain.exceptions import BrokerNotConfiguredError
from src.infrastructure.brokers.saxo import SaxoBroker

logger = logging.getLogger(__name__)


# Registry des brokers supportés
BROKER_REGISTRY: Dict[str, Type[BrokerService]] = {
    "saxo": SaxoBroker,
    # Futurs brokers:
    # "interactive_brokers": InteractiveBrokersBroker,
    # "alpaca": AlpacaBroker,
}


class BrokerFactory:
    """
    Factory pour créer des instances de brokers.

    Gère:
    - Création d'instances selon le type
    - Injection des dépendances (settings, token_store)
    - Validation de la configuration

    Attributes:
        settings: Configuration de l'application
        token_store: Repository pour les tokens
    """

    def __init__(
        self,
        settings: Settings,
        token_store: Optional[TokenRepository] = None,
    ):
        """
        Initialise la factory.

        Args:
            settings: Configuration de l'application
            token_store: Repository pour les tokens
        """
        self.settings = settings
        self.token_store = token_store
        self._instances: Dict[str, BrokerService] = {}

    def create(self, broker_name: str) -> BrokerService:
        """
        Crée ou retourne une instance de broker.

        Utilise un cache pour réutiliser les instances.

        Args:
            broker_name: Nom du broker (saxo, etc.)

        Returns:
            Instance de BrokerService

        Raises:
            BrokerNotConfiguredError: Si le broker n'est pas supporté
        """
        broker_name = broker_name.lower()

        # Vérifier le cache
        if broker_name in self._instances:
            return self._instances[broker_name]

        # Vérifier que le broker est supporté
        if broker_name not in BROKER_REGISTRY:
            raise BrokerNotConfiguredError(
                broker_name,
                f"Broker '{broker_name}' non supporté. "
                f"Brokers disponibles: {', '.join(BROKER_REGISTRY.keys())}"
            )

        # Créer l'instance
        broker_class = BROKER_REGISTRY[broker_name]
        broker = broker_class(
            settings=self.settings,
            token_store=self.token_store,
        )

        # Vérifier la configuration
        if not broker.is_configured:
            logger.warning(f"Broker {broker_name} is not configured")

        # Mettre en cache
        self._instances[broker_name] = broker

        logger.info(f"Created broker instance: {broker_name}")
        return broker

    def get_available_brokers(self) -> Dict[str, bool]:
        """
        Retourne la liste des brokers avec leur état de configuration.

        Returns:
            Dict avec nom du broker et statut de configuration
        """
        result = {}
        for name in BROKER_REGISTRY:
            try:
                broker = self.create(name)
                result[name] = broker.is_configured
            except Exception:
                result[name] = False
        return result

    def is_broker_available(self, broker_name: str) -> bool:
        """
        Vérifie si un broker est disponible et configuré.

        Args:
            broker_name: Nom du broker

        Returns:
            True si le broker est disponible et configuré
        """
        try:
            broker = self.create(broker_name)
            return broker.is_configured
        except Exception:
            return False


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_broker_factory(
    settings: Settings,
    token_store: Optional[TokenRepository] = None,
) -> BrokerFactory:
    """
    Factory function pour créer un BrokerFactory.

    Args:
        settings: Configuration de l'application
        token_store: Repository pour les tokens

    Returns:
        Instance configurée de BrokerFactory
    """
    return BrokerFactory(settings, token_store)


def get_broker(
    broker_name: str,
    settings: Settings,
    token_store: Optional[TokenRepository] = None,
) -> BrokerService:
    """
    Fonction utilitaire pour obtenir rapidement un broker.

    Args:
        broker_name: Nom du broker
        settings: Configuration
        token_store: Repository pour les tokens

    Returns:
        Instance de BrokerService
    """
    factory = BrokerFactory(settings, token_store)
    return factory.create(broker_name)
