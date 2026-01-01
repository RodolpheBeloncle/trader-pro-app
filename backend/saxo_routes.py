"""
Saxo API Routes

Endpoints pour l'intégration Saxo Bank:
- /api/saxo/auth/url - Obtenir l'URL d'autorisation
- /api/saxo/auth/callback - Callback OAuth2
- /api/saxo/portfolio - Récupérer le portefeuille
- /api/saxo/orders - Gérer les ordres
- /api/saxo/history - Historique des transactions
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from saxo_service import saxo_service
from saxo_config import is_configured
from analyzer import analyze_stock

router = APIRouter(prefix="/api/saxo", tags=["Saxo"])

# =============================================================================
# MODELS
# =============================================================================

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str]
    expires_at: str


class OrderRequest(BaseModel):
    account_key: str
    symbol: str
    asset_type: str = "Stock"
    quantity: int
    order_type: str = "Market"
    buy_sell: str = "Buy"
    price: Optional[float] = None


class PortfolioPosition(BaseModel):
    symbol: str
    description: str
    quantity: float
    current_price: float
    average_price: float
    market_value: float
    pnl: float
    pnl_percent: float
    currency: str
    asset_type: str
    # Added by our analysis
    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_1y: Optional[float] = None
    is_resilient: Optional[bool] = None


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@router.get("/status")
async def get_saxo_status():
    """Vérifie si Saxo API est configurée."""
    return {
        "configured": is_configured(),
        "message": "Saxo API configurée" if is_configured() else "Configurez SAXO_APP_KEY et SAXO_APP_SECRET"
    }


@router.get("/auth/url")
async def get_auth_url(state: str = "default"):
    """
    Obtient l'URL d'autorisation Saxo.

    Redirigez l'utilisateur vers cette URL pour se connecter.
    """
    if not is_configured():
        raise HTTPException(
            status_code=400,
            detail="Saxo API non configurée. Définissez SAXO_APP_KEY et SAXO_APP_SECRET."
        )

    try:
        url = saxo_service.get_authorization_url(state)
        return {"auth_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def auth_callback(code: str, state: str = "default"):
    """
    Callback OAuth2 - échange le code contre des tokens.

    Ce endpoint est appelé par Saxo après la connexion.
    """
    try:
        tokens = saxo_service.exchange_code(code)
        return {
            "success": True,
            "access_token": tokens["access_token"],
            "expires_at": tokens["expires_at"].isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    """Rafraîchit le token d'accès."""
    try:
        tokens = saxo_service.refresh_token(refresh_token)
        return {
            "access_token": tokens["access_token"],
            "expires_at": tokens["expires_at"].isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# =============================================================================
# ACCOUNT ENDPOINTS
# =============================================================================

@router.get("/accounts")
async def get_accounts(access_token: str):
    """Récupère la liste des comptes Saxo."""
    try:
        accounts = saxo_service.get_accounts(access_token)
        return {"accounts": accounts}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client")
async def get_client_info(access_token: str):
    """Récupère les informations du client."""
    try:
        client = saxo_service.get_client_info(access_token)
        return client
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# PORTFOLIO ENDPOINTS
# =============================================================================

@router.get("/portfolio")
async def get_portfolio(access_token: str, analyze: bool = True):
    """
    Récupère le portefeuille Saxo avec analyse optionnelle.

    Args:
        access_token: Token d'accès Saxo
        analyze: Si True, analyse chaque position avec notre algorithme

    Returns:
        Portefeuille avec positions et analyses
    """
    try:
        positions = saxo_service.get_positions_with_details(access_token)

        # Get account key for trading
        accounts = saxo_service.get_accounts(access_token)
        account_key = accounts[0].get("AccountKey") if accounts else None

        # Enrichir avec notre analyse si demandé
        if analyze:
            for pos in positions:
                symbol = pos.get("symbol", "")
                if symbol:
                    try:
                        # Analyser avec notre algorithme
                        analysis = analyze_stock(symbol)
                        if "error" not in analysis:
                            pos["perf_3m"] = analysis.get("perf_3m")
                            pos["perf_6m"] = analysis.get("perf_6m")
                            pos["perf_1y"] = analysis.get("perf_1y")
                            pos["perf_3y"] = analysis.get("perf_3y")
                            pos["perf_5y"] = analysis.get("perf_5y")
                            pos["is_resilient"] = analysis.get("is_resilient")
                            pos["volatility"] = analysis.get("volatility")
                    except Exception as e:
                        pos["analysis_error"] = str(e)

        # Calculer les totaux
        total_value = sum(p.get("market_value", 0) for p in positions)
        total_pnl = sum(p.get("pnl", 0) for p in positions)
        resilient_count = sum(1 for p in positions if p.get("is_resilient", False))

        return {
            "positions": positions,
            "account_key": account_key,
            "summary": {
                "total_positions": len(positions),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round((total_pnl / total_value * 100) if total_value > 0 else 0, 2),
                "resilient_count": resilient_count,
                "resilient_percent": round((resilient_count / len(positions) * 100) if positions else 0, 1)
            },
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/portfolio/balance")
async def get_balance(access_token: str):
    """Récupère le solde du compte."""
    try:
        portfolio = saxo_service.get_portfolio(access_token)
        return {"balance": portfolio.get("balance", {})}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# ORDERS ENDPOINTS
# =============================================================================

@router.get("/orders")
async def get_orders(
    access_token: str,
    status: str = Query("All", enum=["All", "Working", "Filled", "Cancelled"])
):
    """Récupère la liste des ordres."""
    try:
        orders = saxo_service.get_orders(access_token, status)
        return {"orders": orders}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders")
async def place_order(access_token: str, order: OrderRequest):
    """
    Place un ordre d'achat ou de vente.

    ATTENTION: Cet endpoint passe de vrais ordres en mode LIVE !
    """
    try:
        result = saxo_service.place_order(
            access_token=access_token,
            account_key=order.account_key,
            symbol=order.symbol,
            asset_type=order.asset_type,
            quantity=order.quantity,
            order_type=order.order_type,
            buy_sell=order.buy_sell,
            price=order.price
        )
        return {"success": True, "order": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, access_token: str, account_key: str):
    """Annule un ordre en attente."""
    try:
        success = saxo_service.cancel_order(access_token, order_id, account_key)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# HISTORY ENDPOINTS
# =============================================================================

@router.get("/history")
async def get_history(
    access_token: str,
    days: int = Query(30, ge=1, le=365)
):
    """
    Récupère l'historique des transactions.

    Args:
        days: Nombre de jours d'historique (max 365)
    """
    try:
        from_date = datetime.now() - timedelta(days=days)
        transactions = saxo_service.get_transactions_history(
            access_token,
            from_date=from_date
        )
        return {"transactions": transactions, "days": days}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# INSTRUMENT SEARCH
# =============================================================================

@router.get("/search")
async def search_instrument(
    access_token: str,
    query: str = Query(..., min_length=1),
    asset_types: str = Query("Stock,Etf", description="Types séparés par virgule")
):
    """
    Recherche un instrument par nom ou symbole.

    Utile pour trouver l'UIC (Universal Instrument Code) pour passer des ordres.
    """
    try:
        types = asset_types.split(",")
        instruments = saxo_service.search_instrument(access_token, query, types)
        return {"results": instruments}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
