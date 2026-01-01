"""
Interface BrokerService - Abstraction pour les brokers de trading.

Cette interface définit le contrat que doit respecter tout broker
(Saxo, Interactive Brokers, Alpaca, Degiro, etc.).

ARCHITECTURE:
- Couche APPLICATION (port/interface)
- Implémentée par chaque broker dans infrastructure/brokers/
- Permet d'ajouter de nouveaux brokers sans modifier les use cases

PATTERN: Strategy + Repository

EXTENSIBILITÉ:
    Pour ajouter un nouveau broker:
    1. Créer infrastructure/brokers/nouveau/nouveau_broker.py
    2. Implémenter BrokerService
    3. L'enregistrer dans BrokerFactory
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from src.config.constants import OrderType, OrderSide, OrderStatus, AssetType


@dataclass
class BrokerCredentials:
    """
    Credentials pour un broker.

    Contient les tokens OAuth ou API keys selon le broker.
    """

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    api_key: Optional[str] = None  # Pour les brokers à API key
    api_secret: Optional[str] = None


@dataclass
class Position:
    """
    Une position dans le portefeuille.

    Représentation normalisée d'une position, indépendante du broker.
    """

    symbol: str
    """Symbole standardisé (ex: AAPL)."""

    quantity: float
    """Nombre d'unités détenues."""

    current_price: float
    """Prix actuel."""

    average_price: float
    """Prix d'achat moyen."""

    market_value: float
    """Valeur de marché totale."""

    pnl: float
    """Profit/perte en valeur absolue."""

    pnl_percent: float
    """Profit/perte en pourcentage."""

    currency: str
    """Devise de la position."""

    asset_type: AssetType
    """Type d'actif (stock, ETF, etc.)."""

    # Identifiants broker
    broker_id: Optional[str] = None
    """ID interne du broker pour cette position."""

    uic: Optional[int] = None
    """Universal Instrument Code (Saxo)."""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "current_price": self.current_price,
            "average_price": self.average_price,
            "market_value": self.market_value,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "currency": self.currency,
            "asset_type": self.asset_type.value,
            "broker_id": self.broker_id,
        }


@dataclass
class Portfolio:
    """
    Portefeuille complet d'un compte.
    """

    positions: List[Position]
    """Liste des positions."""

    total_value: float
    """Valeur totale du portefeuille."""

    cash_balance: float
    """Solde en cash."""

    buying_power: float
    """Pouvoir d'achat disponible."""

    currency: str
    """Devise principale."""

    account_id: str
    """ID du compte."""

    updated_at: datetime
    """Horodatage de la mise à jour."""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "positions": [p.to_dict() for p in self.positions],
            "total_value": self.total_value,
            "cash_balance": self.cash_balance,
            "buying_power": self.buying_power,
            "currency": self.currency,
            "account_id": self.account_id,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Order:
    """
    Un ordre de trading.
    """

    order_id: str
    """ID unique de l'ordre."""

    symbol: str
    """Symbole de l'instrument."""

    side: OrderSide
    """Direction (Buy/Sell)."""

    order_type: OrderType
    """Type d'ordre (Market/Limit/Stop)."""

    quantity: float
    """Quantité demandée."""

    filled_quantity: float
    """Quantité exécutée."""

    price: Optional[float]
    """Prix limite (si applicable)."""

    status: OrderStatus
    """Statut de l'ordre."""

    created_at: datetime
    """Date de création."""

    updated_at: Optional[datetime] = None
    """Date de dernière mise à jour."""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "price": self.price,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class OrderRequest:
    """
    Requête pour placer un ordre.
    """

    symbol: str
    """Symbole de l'instrument."""

    side: OrderSide
    """Direction (Buy/Sell)."""

    quantity: float
    """Quantité à acheter/vendre."""

    order_type: OrderType = OrderType.MARKET
    """Type d'ordre."""

    price: Optional[float] = None
    """Prix limite (requis pour Limit orders)."""

    asset_type: AssetType = AssetType.STOCK
    """Type d'actif."""

    uic: Optional[int] = None
    """Universal Instrument Code (Saxo)."""


@dataclass
class OrderConfirmation:
    """
    Confirmation après placement d'un ordre.
    """

    order_id: str
    """ID de l'ordre créé."""

    status: OrderStatus
    """Statut initial."""

    message: str
    """Message de confirmation."""


@dataclass
class Instrument:
    """
    Un instrument financier (résultat de recherche).
    """

    symbol: str
    """Symbole."""

    name: str
    """Nom complet."""

    asset_type: AssetType
    """Type d'actif."""

    exchange: Optional[str] = None
    """Bourse de cotation."""

    currency: Optional[str] = None
    """Devise."""

    uic: Optional[int] = None
    """Universal Instrument Code (Saxo)."""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_type": self.asset_type.value,
            "exchange": self.exchange,
            "currency": self.currency,
            "uic": self.uic,
        }


@dataclass
class Account:
    """
    Un compte de trading.
    """

    account_id: str
    """ID unique du compte."""

    account_key: str
    """Clé du compte (Saxo)."""

    name: str
    """Nom du compte."""

    currency: str
    """Devise du compte."""

    account_type: str
    """Type de compte (margin, cash, etc.)."""

    is_default: bool = False
    """Compte par défaut."""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "account_id": self.account_id,
            "account_key": self.account_key,
            "name": self.name,
            "currency": self.currency,
            "account_type": self.account_type,
            "is_default": self.is_default,
        }


class BrokerService(ABC):
    """
    Interface abstraite pour les services de broker.

    Chaque broker (Saxo, IB, Alpaca...) doit implémenter cette interface.
    Cela permet au code métier de fonctionner avec n'importe quel broker.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Retourne le nom du broker (ex: 'saxo', 'ib')."""
        pass

    # =========================================================================
    # AUTHENTIFICATION
    # =========================================================================

    @abstractmethod
    async def get_authorization_url(
        self,
        user_id: str,
        state: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Génère l'URL d'autorisation OAuth2.

        Args:
            user_id: ID de l'utilisateur
            state: État CSRF (généré si non fourni)

        Returns:
            Dict avec:
                - auth_url: URL vers laquelle rediriger
                - state: État à valider lors du callback
        """
        pass

    @abstractmethod
    async def handle_auth_callback(
        self,
        code: str,
        state: str
    ) -> BrokerCredentials:
        """
        Gère le callback OAuth2 et échange le code contre des tokens.

        Args:
            code: Code d'autorisation reçu
            state: État à valider

        Returns:
            BrokerCredentials avec les tokens

        Raises:
            OAuthError: Si le state est invalide ou l'échange échoue
        """
        pass

    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str
    ) -> BrokerCredentials:
        """
        Rafraîchit l'access token.

        Args:
            refresh_token: Token de rafraîchissement

        Returns:
            Nouveaux credentials

        Raises:
            TokenRefreshError: Si le refresh échoue
        """
        pass

    # =========================================================================
    # PORTEFEUILLE
    # =========================================================================

    @abstractmethod
    async def get_portfolio(
        self,
        credentials: BrokerCredentials,
        account_id: Optional[str] = None
    ) -> Portfolio:
        """
        Récupère le portefeuille.

        Args:
            credentials: Tokens d'authentification
            account_id: ID du compte (si multiple comptes)

        Returns:
            Portfolio avec toutes les positions

        Raises:
            TokenExpiredError: Si le token a expiré
            BrokerConnectionError: Si erreur de connexion
        """
        pass

    @abstractmethod
    async def get_accounts(
        self,
        credentials: BrokerCredentials
    ) -> List[Dict[str, Any]]:
        """
        Liste les comptes disponibles.

        Args:
            credentials: Tokens d'authentification

        Returns:
            Liste des comptes avec leurs détails
        """
        pass

    # =========================================================================
    # ORDRES
    # =========================================================================

    @abstractmethod
    async def place_order(
        self,
        credentials: BrokerCredentials,
        order: OrderRequest,
        account_id: str
    ) -> OrderConfirmation:
        """
        Place un ordre.

        Args:
            credentials: Tokens d'authentification
            order: Détails de l'ordre
            account_id: ID du compte

        Returns:
            Confirmation de l'ordre

        Raises:
            OrderRejectedError: Si l'ordre est rejeté
            InsufficientFundsError: Si fonds insuffisants
        """
        pass

    @abstractmethod
    async def cancel_order(
        self,
        credentials: BrokerCredentials,
        order_id: str,
        account_id: str
    ) -> bool:
        """
        Annule un ordre en attente.

        Args:
            credentials: Tokens d'authentification
            order_id: ID de l'ordre
            account_id: ID du compte

        Returns:
            True si annulé avec succès
        """
        pass

    @abstractmethod
    async def get_orders(
        self,
        credentials: BrokerCredentials,
        account_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Order]:
        """
        Récupère la liste des ordres.

        Args:
            credentials: Tokens d'authentification
            account_id: ID du compte (optionnel)
            status: Filtrer par statut ("working", "filled", etc.)

        Returns:
            Liste des ordres
        """
        pass

    # =========================================================================
    # RECHERCHE
    # =========================================================================

    @abstractmethod
    async def search_instrument(
        self,
        credentials: BrokerCredentials,
        query: str,
        asset_types: Optional[List[AssetType]] = None
    ) -> List[Instrument]:
        """
        Recherche un instrument par nom ou symbole.

        Args:
            credentials: Tokens d'authentification
            query: Terme de recherche
            asset_types: Types d'actifs à chercher

        Returns:
            Liste d'instruments correspondants
        """
        pass
