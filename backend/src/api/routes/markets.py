"""
Routes API pour les presets de marchés.

Endpoints:
- GET /api/markets - Liste tous les marchés disponibles
- GET /api/markets/{market_id}/tickers - Tickers d'un marché

Les presets de marchés sont chargés depuis un fichier JSON.
"""

import json
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/markets", tags=["markets"])

logger = logging.getLogger(__name__)

# Chemin vers le fichier des marchés
MARKETS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "markets.json"


# =============================================================================
# SCHEMAS
# =============================================================================

class MarketPresetResponse(BaseModel):
    """Preset de marché."""

    id: str
    name: str
    count: int
    description: str = ""


class MarketsListResponse(BaseModel):
    """Liste des marchés."""

    markets: List[MarketPresetResponse]


class MarketTickersResponse(BaseModel):
    """Tickers d'un marché."""

    market: str
    tickers: List[str]
    total: int


# =============================================================================
# DATA LOADING
# =============================================================================

def load_markets_data() -> dict:
    """
    Charge les donnees des marches depuis le fichier JSON.

    Returns:
        Dictionnaire avec les donnees des marches
    """
    if not MARKETS_FILE.exists():
        logger.warning(f"Markets file not found: {MARKETS_FILE}")
        return {"markets": {}, "asset_types": {}}

    try:
        with open(MARKETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing markets file: {e}")
        return {"markets": {}, "asset_types": {}}


# =============================================================================
# ROUTES
# =============================================================================

@router.get(
    "",
    response_model=MarketsListResponse,
)
async def get_markets():
    """
    Liste tous les presets de marches disponibles.

    Les presets incluent des listes de tickers pre-definies
    comme S&P 500, CAC 40, Crypto Top 20, etc.
    """
    data = load_markets_data()
    markets_dict = data.get("markets", {})

    markets = [
        MarketPresetResponse(
            id=market_id,
            name=market_data.get("name", market_id),
            count=len(market_data.get("tickers", [])),
            description=market_data.get("description", ""),
        )
        for market_id, market_data in markets_dict.items()
    ]

    return MarketsListResponse(markets=markets)


@router.get(
    "/{market_id}/tickers",
    response_model=MarketTickersResponse,
)
async def get_market_tickers(market_id: str):
    """
    Recupere les tickers d'un preset de marche.
    """
    data = load_markets_data()
    markets_dict = data.get("markets", {})

    if market_id not in markets_dict:
        raise HTTPException(
            status_code=404,
            detail=f"Marche '{market_id}' non trouve",
        )

    market = markets_dict[market_id]
    tickers = market.get("tickers", [])

    return MarketTickersResponse(
        market=market_id,
        tickers=tickers,
        total=len(tickers),
    )


@router.get(
    "/{market_id}",
    response_model=MarketPresetResponse,
)
async def get_market_details(market_id: str):
    """
    Recupere les details d'un preset de marche.
    """
    data = load_markets_data()
    markets_dict = data.get("markets", {})

    if market_id not in markets_dict:
        raise HTTPException(
            status_code=404,
            detail=f"Marche '{market_id}' non trouve",
        )

    market = markets_dict[market_id]
    return MarketPresetResponse(
        id=market_id,
        name=market.get("name", market_id),
        count=len(market.get("tickers", [])),
        description=market.get("description", ""),
    )
