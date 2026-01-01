"""
Module des brokers.

Fournit les implémentations des brokers et la factory.
"""

from src.infrastructure.brokers.broker_factory import (
    BrokerFactory,
    create_broker_factory,
    get_broker,
    BROKER_REGISTRY,
)
from src.infrastructure.brokers.saxo import (
    SaxoBroker,
    create_saxo_broker,
)

__all__ = [
    # Factory
    "BrokerFactory",
    "create_broker_factory",
    "get_broker",
    "BROKER_REGISTRY",
    # Saxo
    "SaxoBroker",
    "create_saxo_broker",
]
