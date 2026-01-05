"""
Outil MCP pour le portefeuille Saxo.

Fonctions:
- get_portfolio_tool: Recupere le portefeuille connecte
"""

import json
import logging

from src.config.settings import get_settings
from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth
from src.infrastructure.brokers.saxo.saxo_api_client import SaxoApiClient

logger = logging.getLogger(__name__)


async def get_portfolio_tool() -> str:
    """
    Recupere le portefeuille du compte Saxo connecte.

    Utilise le meme systeme d'authentification que l'API web (SaxoAuth).

    Returns:
        String JSON avec le portefeuille ou un message d'erreur
    """
    settings = get_settings()

    # Verifier la configuration Saxo
    if not settings.is_saxo_configured:
        return json.dumps({
            "error": "Saxo Bank n'est pas configure. Definissez SAXO_APP_KEY et SAXO_APP_SECRET.",
            "configured": False,
        }, ensure_ascii=False)

    # Verifier l'authentification via SaxoAuth (meme systeme que l'API web)
    auth = get_saxo_auth(settings)
    token = auth.get_valid_token()

    if not token:
        return json.dumps({
            "error": "Non authentifie. Connectez-vous d'abord via l'interface web (http://localhost:5173).",
            "authenticated": False,
            "hint": "Allez sur l'interface web et cliquez sur 'Connexion Saxo'",
        }, ensure_ascii=False)

    try:
        # Creer le client API et recuperer le portfolio
        client = SaxoApiClient(settings)

        # Recuperer info client
        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            return json.dumps({
                "error": "Client Saxo non trouve",
                "authenticated": True,
            }, ensure_ascii=False)

        # Recuperer comptes et balances
        accounts = client.get_accounts(token.access_token, client_key)
        account_key = accounts[0].get("AccountKey") if accounts else None
        account_currency = accounts[0].get("Currency", "EUR") if accounts else "EUR"

        # Balances
        total_account_value = 0
        cash_available = 0
        try:
            balances = client.get_balances(token.access_token, client_key)
            cash_available = balances.get("CashAvailableForTrading", 0)
            total_account_value = balances.get("TotalValue", 0)
        except Exception as e:
            logger.warning(f"Could not fetch balances: {e}")

        # Positions
        positions_data = client.get_positions(token.access_token, client_key)

        positions = []
        total_value = 0
        total_pnl = 0

        for pos in positions_data:
            base = pos.get("PositionBase", {})
            view = pos.get("PositionView", {})
            display = pos.get("DisplayAndFormat", {})

            symbol = display.get("Symbol", "")
            if not symbol:
                symbol = f"UIC:{base.get('Uic', 'N/A')}"

            quantity = base.get("Amount", 0) or 0
            current_price = view.get("CurrentPrice", 0) or 0
            avg_price = view.get("AverageOpenPrice", 0) or base.get("OpenPrice", 0) or 0

            value = view.get("MarketValue", 0) or view.get("Exposure", 0) or 0
            if value == 0 and current_price > 0:
                value = current_price * abs(quantity)

            pnl = view.get("ProfitLossOnTrade", 0) or 0
            pnl_percent = view.get("ProfitLossOnTradeInPercentage", 0) or 0

            if pnl_percent == 0 and avg_price > 0 and current_price > 0:
                pnl_percent = ((current_price - avg_price) / avg_price) * 100

            positions.append({
                "symbol": symbol,
                "description": display.get("Description", ""),
                "quantity": quantity,
                "current_price": round(current_price, 2),
                "average_price": round(avg_price, 2),
                "market_value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "currency": display.get("Currency", "EUR"),
                "asset_type": base.get("AssetType", "Stock"),
            })

            total_value += abs(value)
            total_pnl += pnl

        total_pnl_percent = (total_pnl / total_value * 100) if total_value > 0 else 0

        # Formater le resultat
        output = {
            "authenticated": True,
            "environment": token.environment,
            "account_key": account_key,
            "currency": account_currency,
            "summary": {
                "total_positions": len(positions),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round(total_pnl_percent, 2),
                "cash_available": round(cash_available, 2),
                "total_account_value": round(total_account_value, 2),
            },
            "positions": positions,
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting portfolio: {e}")
        return json.dumps({
            "error": f"Erreur lors de la recuperation du portefeuille: {str(e)}",
            "authenticated": True,
        }, ensure_ascii=False)
