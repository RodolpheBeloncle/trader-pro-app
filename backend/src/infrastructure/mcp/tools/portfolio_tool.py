"""
Outil MCP pour le portefeuille Saxo.

Utilise l'API HTTP du backend Docker pour garantir que Claude Desktop
et l'interface web partagent les mêmes données et authentification.

ARCHITECTURE:
    Claude Desktop MCP → HTTP API → Docker Backend → Saxo API
    Web Frontend       → HTTP API → Docker Backend → Saxo API
"""

import json
import logging

import httpx

logger = logging.getLogger(__name__)

# URL de base de l'API (backend Docker)
API_BASE_URL = "http://localhost:8000/api"
HTTP_TIMEOUT = 30.0


async def get_portfolio_tool() -> str:
    """
    Recupere le portefeuille du compte Saxo connecte via l'API HTTP.

    Utilise le meme systeme d'authentification que l'API web.

    Returns:
        String JSON avec le portefeuille ou un message d'erreur
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # Appeler l'API portfolio
            response = await client.get(f"{API_BASE_URL}/saxo/portfolio")

            if response.status_code == 401:
                return json.dumps({
                    "error": "Non authentifie. Connectez-vous d'abord via l'interface web (http://localhost:5173).",
                    "authenticated": False,
                    "hint": "Allez sur l'interface web et cliquez sur 'Connexion Saxo'",
                }, ensure_ascii=False)

            response.raise_for_status()
            data = response.json()

            # Transformer la reponse pour le format MCP
            positions = data.get("positions", [])

            # Calculer les totaux
            total_value = sum(abs(p.get("market_value", 0) or 0) for p in positions)
            total_pnl = sum(p.get("pnl", 0) or 0 for p in positions)
            total_pnl_percent = (total_pnl / total_value * 100) if total_value > 0 else 0

            output = {
                "authenticated": True,
                "environment": data.get("environment", "LIVE"),
                "account_key": data.get("account_key"),
                "currency": data.get("currency", "EUR"),
                "summary": {
                    "total_positions": len(positions),
                    "total_value": round(total_value, 2),
                    "total_pnl": round(total_pnl, 2),
                    "total_pnl_percent": round(total_pnl_percent, 2),
                    "cash_available": round(data.get("cash_available", 0) or 0, 2),
                    "total_account_value": round(data.get("total_value", 0) or 0, 2),
                },
                "positions": [
                    {
                        "symbol": p.get("symbol", ""),
                        "description": p.get("description", ""),
                        "quantity": p.get("quantity", 0),
                        "current_price": round(p.get("current_price", 0) or 0, 2),
                        "average_price": round(p.get("average_price", 0) or 0, 2),
                        "market_value": round(p.get("market_value", 0) or 0, 2),
                        "pnl": round(p.get("pnl", 0) or 0, 2),
                        "pnl_percent": round(p.get("pnl_percent", 0) or 0, 2),
                        "currency": p.get("currency", "EUR"),
                        "asset_type": p.get("asset_type", "Stock"),
                    }
                    for p in positions
                ],
            }

            return json.dumps(output, ensure_ascii=False, indent=2)

    except httpx.ConnectError:
        return json.dumps({
            "error": "Impossible de se connecter au backend. Verifiez que Docker est lance.",
            "authenticated": False,
            "hint": "Lancez 'docker-compose up -d' dans le dossier stock-analyzer",
        }, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        error_detail = f"Erreur HTTP {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", error_detail)
        except Exception:
            pass
        return json.dumps({
            "error": error_detail,
            "authenticated": False,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error getting portfolio: {e}")
        return json.dumps({
            "error": f"Erreur lors de la recuperation du portefeuille: {str(e)}",
            "authenticated": False,
        }, ensure_ascii=False)
