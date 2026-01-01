"""
Mappers pour convertir les réponses Saxo API vers le domaine.

Responsabilité unique: transformer les structures de données Saxo
vers nos entités et DTOs du domaine.

ARCHITECTURE:
- Fonctions pures sans effets de bord
- Gestion des champs manquants/null
- Mapping explicite des types Saxo vers nos types
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config.constants import AssetType, OrderType, OrderSide, OrderStatus


def map_saxo_asset_type(saxo_type: str) -> AssetType:
    """
    Convertit un type d'actif Saxo vers notre AssetType.

    Args:
        saxo_type: Type Saxo (Stock, CfdOnStock, Etf, etc.)

    Returns:
        AssetType correspondant
    """
    mapping = {
        "Stock": AssetType.STOCK,
        "CfdOnStock": AssetType.CFD,
        "Etf": AssetType.ETF,
        "CfdOnEtf": AssetType.CFD,
        "CfdOnIndex": AssetType.CFD,
        "FxSpot": AssetType.CRYPTO,  # Approximation
        "Bond": AssetType.BOND,
        "MutualFund": AssetType.ETF,
    }
    return mapping.get(saxo_type, AssetType.STOCK)


def map_saxo_order_type(saxo_type: str) -> OrderType:
    """
    Convertit un type d'ordre Saxo vers notre OrderType.

    Args:
        saxo_type: Type Saxo (Market, Limit, Stop, etc.)

    Returns:
        OrderType correspondant
    """
    mapping = {
        "Market": OrderType.MARKET,
        "Limit": OrderType.LIMIT,
        "Stop": OrderType.STOP,
        "StopLimit": OrderType.STOP_LIMIT,
        "TrailingStop": OrderType.STOP,
    }
    return mapping.get(saxo_type, OrderType.MARKET)


def map_saxo_order_side(saxo_side: str) -> OrderSide:
    """
    Convertit une direction d'ordre Saxo vers notre OrderSide.

    Args:
        saxo_side: Direction Saxo (Buy, Sell)

    Returns:
        OrderSide correspondant
    """
    return OrderSide.BUY if saxo_side == "Buy" else OrderSide.SELL


def map_saxo_order_status(saxo_status: str) -> OrderStatus:
    """
    Convertit un statut d'ordre Saxo vers notre OrderStatus.

    Args:
        saxo_status: Statut Saxo

    Returns:
        OrderStatus correspondant
    """
    mapping = {
        "Working": OrderStatus.WORKING,
        "Filled": OrderStatus.FILLED,
        "Cancelled": OrderStatus.CANCELLED,
        "Rejected": OrderStatus.REJECTED,
        "Expired": OrderStatus.EXPIRED,
        "PartiallyFilled": OrderStatus.PARTIALLY_FILLED,
        "Pending": OrderStatus.PENDING,
    }
    return mapping.get(saxo_status, OrderStatus.PENDING)


def map_position(saxo_position: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit une position Saxo vers notre format.

    Args:
        saxo_position: Position brute de l'API Saxo

    Returns:
        Dict au format attendu par le domaine
    """
    base = saxo_position.get("NetPositionBase", {})
    view = saxo_position.get("NetPositionView", {})
    display = saxo_position.get("DisplayAndFormat", {})

    # Extraire le ticker/symbol
    symbol = display.get("Symbol", "")
    if not symbol and base.get("Uic"):
        symbol = f"UIC:{base.get('Uic')}"

    # Calculer le PnL percent si non fourni
    pnl = view.get("ProfitLossOnTrade", 0)
    pnl_percent = view.get("ProfitLossOnTradeInPercentage", 0)
    avg_price = view.get("AverageOpenPrice", 0)
    quantity = view.get("PositionCount", 0)

    if not pnl_percent and avg_price and quantity:
        cost = avg_price * quantity
        if cost > 0:
            pnl_percent = (pnl / cost) * 100

    return {
        "symbol": symbol,
        "description": display.get("Description", ""),
        "quantity": quantity,
        "current_price": view.get("CurrentPrice", 0),
        "average_price": avg_price,
        "market_value": view.get("MarketValue", 0),
        "pnl": pnl,
        "pnl_percent": round(pnl_percent, 2),
        "currency": display.get("Currency", "USD"),
        "asset_type": map_saxo_asset_type(base.get("AssetType", "Stock")).value,
        "broker_id": str(base.get("NetPositionId", "")),
        "uic": base.get("Uic"),
    }


def map_positions(saxo_positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convertit une liste de positions Saxo.

    Args:
        saxo_positions: Liste de positions brutes

    Returns:
        Liste de positions au format domaine
    """
    return [map_position(pos) for pos in saxo_positions]


def map_account(saxo_account: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit un compte Saxo vers notre format.

    Args:
        saxo_account: Compte brut de l'API Saxo

    Returns:
        Dict au format attendu
    """
    return {
        "account_key": saxo_account.get("AccountKey", ""),
        "account_id": saxo_account.get("AccountId", ""),
        "name": saxo_account.get("DisplayName", saxo_account.get("AccountId", "")),
        "currency": saxo_account.get("Currency", "EUR"),
        "balance": saxo_account.get("Balance"),
    }


def map_accounts(saxo_accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convertit une liste de comptes Saxo.

    Args:
        saxo_accounts: Liste de comptes bruts

    Returns:
        Liste de comptes au format domaine
    """
    return [map_account(acc) for acc in saxo_accounts]


def map_order(saxo_order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit un ordre Saxo vers notre format.

    Args:
        saxo_order: Ordre brut de l'API Saxo

    Returns:
        Dict au format attendu
    """
    return {
        "order_id": saxo_order.get("OrderId", ""),
        "symbol": saxo_order.get("DisplayAndFormat", {}).get("Symbol", ""),
        "side": map_saxo_order_side(saxo_order.get("BuySell", "Buy")).value,
        "order_type": map_saxo_order_type(saxo_order.get("OrderType", "Market")).value,
        "quantity": saxo_order.get("Amount", 0),
        "filled_quantity": saxo_order.get("FilledAmount", 0),
        "price": saxo_order.get("Price"),
        "status": map_saxo_order_status(saxo_order.get("Status", "Pending")).value,
        "created_at": saxo_order.get("ActivationTime", datetime.now().isoformat()),
        "updated_at": saxo_order.get("LastUpdatedTime"),
    }


def map_orders(saxo_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convertit une liste d'ordres Saxo.

    Args:
        saxo_orders: Liste d'ordres bruts

    Returns:
        Liste d'ordres au format domaine
    """
    return [map_order(order) for order in saxo_orders]


def map_instrument(saxo_instrument: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit un instrument Saxo vers notre format.

    Args:
        saxo_instrument: Instrument brut de l'API Saxo

    Returns:
        Dict au format attendu
    """
    return {
        "symbol": saxo_instrument.get("Symbol", ""),
        "name": saxo_instrument.get("Description", ""),
        "asset_type": map_saxo_asset_type(saxo_instrument.get("AssetType", "Stock")).value,
        "exchange": saxo_instrument.get("ExchangeId", ""),
        "currency": saxo_instrument.get("CurrencyCode", ""),
        "uic": saxo_instrument.get("Uic"),
    }


def map_instruments(saxo_instruments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convertit une liste d'instruments Saxo.

    Args:
        saxo_instruments: Liste d'instruments bruts

    Returns:
        Liste d'instruments au format domaine
    """
    return [map_instrument(inst) for inst in saxo_instruments]


def map_portfolio_summary(
    positions: List[Dict[str, Any]],
    balances: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcule le résumé du portefeuille.

    Args:
        positions: Liste des positions mappées
        balances: Soldes du compte

    Returns:
        Résumé du portefeuille
    """
    total_value = sum(pos.get("market_value", 0) for pos in positions)
    total_pnl = sum(pos.get("pnl", 0) for pos in positions)
    total_cost = sum(
        pos.get("average_price", 0) * pos.get("quantity", 0)
        for pos in positions
    )

    total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    resilient_count = sum(
        1 for pos in positions
        if pos.get("is_resilient", False)
    )

    return {
        "total_positions": len(positions),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_percent": round(total_pnl_percent, 2),
        "resilient_count": resilient_count,
        "resilient_percent": round(
            resilient_count / len(positions) * 100 if positions else 0,
            2
        ),
    }


def build_order_request(
    account_key: str,
    uic: int,
    asset_type: str,
    side: str,
    quantity: int,
    order_type: str = "Market",
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Construit une requête d'ordre pour l'API Saxo.

    Args:
        account_key: Clé du compte
        uic: Universal Instrument Code
        asset_type: Type d'actif Saxo (Stock, CfdOnStock, etc.)
        side: Direction (Buy, Sell)
        quantity: Quantité
        order_type: Type d'ordre (Market, Limit, etc.)
        price: Prix limite (optionnel)

    Returns:
        Dict prêt pour l'API Saxo
    """
    order = {
        "AccountKey": account_key,
        "Uic": uic,
        "AssetType": asset_type,
        "BuySell": side,
        "Amount": quantity,
        "OrderType": order_type,
        "OrderDuration": {"DurationType": "DayOrder"},
        "ManualOrder": True,  # Requis par Saxo
    }

    if order_type == "Limit" and price is not None:
        order["OrderPrice"] = price
    elif order_type in ("Stop", "StopLimit") and price is not None:
        order["StopLimitPrice"] = price

    return order
