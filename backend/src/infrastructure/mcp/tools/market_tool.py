"""
Outils MCP pour les marches.

Fonctions:
- list_markets_tool: Liste les presets de marches
- get_market_tickers_tool: Recupere les tickers d'un marche
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Chemin vers le fichier des marches
MARKETS_FILE = Path(__file__).parent.parent.parent.parent.parent / "data" / "markets.json"


def _load_markets() -> dict:
    """Charge les donnees des marches."""
    if not MARKETS_FILE.exists():
        logger.warning(f"Markets file not found: {MARKETS_FILE}")
        return {"markets": {}}

    try:
        with open(MARKETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading markets: {e}")
        return {"markets": {}}


async def list_markets_tool() -> str:
    """
    Liste tous les presets de marches disponibles.

    Returns:
        String JSON avec la liste des marches
    """
    try:
        data = _load_markets()
        markets_dict = data.get("markets", {})

        markets = []
        for market_id, market_data in markets_dict.items():
            markets.append({
                "id": market_id,
                "name": market_data.get("name", market_id),
                "type": market_data.get("type", "stocks"),
                "description": market_data.get("description", ""),
                "tickers_count": len(market_data.get("tickers", [])),
            })

        # Trier par type puis par nom
        markets.sort(key=lambda m: (m["type"], m["name"]))

        output = {
            "total": len(markets),
            "markets": markets,
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error listing markets: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def get_market_tickers_tool(market_id: str) -> str:
    """
    Recupere les tickers d'un preset de marche.

    Args:
        market_id: ID du marche (ex: sp500, cac40)

    Returns:
        String JSON avec les tickers
    """
    if not market_id or not market_id.strip():
        return json.dumps({"error": "market_id requis"}, ensure_ascii=False)

    market_id = market_id.strip().lower()

    try:
        data = _load_markets()
        markets_dict = data.get("markets", {})

        if market_id not in markets_dict:
            available = list(markets_dict.keys())
            return json.dumps({
                "error": f"Marche '{market_id}' non trouve",
                "available_markets": available,
            }, ensure_ascii=False)

        market = markets_dict[market_id]
        tickers = market.get("tickers", [])

        output = {
            "market_id": market_id,
            "name": market.get("name", market_id),
            "type": market.get("type", "stocks"),
            "description": market.get("description", ""),
            "tickers_count": len(tickers),
            "tickers": tickers,
        }

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting market tickers: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
