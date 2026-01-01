"""
Outil MCP pour le portefeuille Saxo.

Fonctions:
- get_portfolio_tool: Recupere le portefeuille connecte
"""

import json
import logging

from src.config.settings import get_settings
from src.infrastructure.persistence.token_store import get_token_store
from src.infrastructure.brokers.saxo.saxo_broker import SaxoBroker

logger = logging.getLogger(__name__)


async def get_portfolio_tool() -> str:
    """
    Recupere le portefeuille du compte Saxo connecte.

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

    # Verifier l'authentification
    token_store = get_token_store()

    # Utiliser un user_id par defaut (session MCP)
    user_id = "mcp_session"
    token = await token_store.get_token(user_id, "saxo")

    if not token:
        return json.dumps({
            "error": "Non authentifie. Connectez-vous d'abord via l'interface web.",
            "authenticated": False,
        }, ensure_ascii=False)

    if token.is_expired:
        return json.dumps({
            "error": "Token expire. Reconnectez-vous via l'interface web.",
            "authenticated": False,
            "expired": True,
        }, ensure_ascii=False)

    try:
        # Creer le broker et recuperer le portfolio
        broker = SaxoBroker(settings)

        # Note: Ceci est une version simplifiee
        # En production, utilisez le use case GetPortfolioUseCase
        portfolio = await broker.get_portfolio(token.access_token)

        # Formater le resultat
        output = {
            "authenticated": True,
            "account_id": portfolio.account_id if hasattr(portfolio, 'account_id') else "N/A",
            "total_value": portfolio.total_value if hasattr(portfolio, 'total_value') else 0,
            "currency": portfolio.currency if hasattr(portfolio, 'currency') else "USD",
            "positions_count": len(portfolio.positions) if hasattr(portfolio, 'positions') else 0,
            "positions": [
                {
                    "symbol": pos.symbol if hasattr(pos, 'symbol') else "N/A",
                    "quantity": pos.quantity if hasattr(pos, 'quantity') else 0,
                    "current_price": pos.current_price if hasattr(pos, 'current_price') else 0,
                    "market_value": pos.market_value if hasattr(pos, 'market_value') else 0,
                    "unrealized_pnl": pos.unrealized_pnl if hasattr(pos, 'unrealized_pnl') else 0,
                    "unrealized_pnl_percent": pos.unrealized_pnl_percent if hasattr(pos, 'unrealized_pnl_percent') else 0,
                }
                for pos in (portfolio.positions if hasattr(portfolio, 'positions') else [])
            ],
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting portfolio: {e}")
        return json.dumps({
            "error": f"Erreur lors de la recuperation du portefeuille: {str(e)}",
            "authenticated": True,
        }, ensure_ascii=False)
