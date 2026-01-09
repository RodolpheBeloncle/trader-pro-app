"""
Routes API Saxo Bank - Version simplifiee.

Architecture propre:
- OAuth simple sans PKCE
- Token en memoire (singleton)
- Auto-refresh transparent
"""

import logging
from typing import Optional, List

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.config.settings import get_settings
from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth, SaxoToken
from src.infrastructure.brokers.saxo.saxo_api_client import SaxoApiClient
from src.domain.exceptions import BrokerApiError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saxo", tags=["saxo"])


# =============================================================================
# SCHEMAS
# =============================================================================

class StatusResponse(BaseModel):
    """Statut de configuration Saxo."""
    configured: bool
    environment: str
    connected: bool
    expires_in: Optional[int] = None
    message: str


class AuthUrlResponse(BaseModel):
    """URL d'authentification."""
    auth_url: str


class AuthCallbackResponse(BaseModel):
    """Resultat du callback OAuth."""
    success: bool
    access_token: Optional[str] = None
    environment: str
    expires_in: Optional[int] = None
    message: str


class PositionItem(BaseModel):
    """Position du portefeuille."""
    symbol: str
    description: str
    quantity: float
    current_price: Optional[float] = None
    average_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    currency: str = "EUR"
    asset_type: str = "Stock"
    uic: Optional[int] = None


class PortfolioSummary(BaseModel):
    """Resume du portefeuille."""
    total_positions: int
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    cash_available: Optional[float] = None
    total_account_value: Optional[float] = None
    currency: str = "EUR"


class PortfolioResponse(BaseModel):
    """Reponse portefeuille complete."""
    positions: List[PositionItem]
    summary: PortfolioSummary
    account_key: Optional[str] = None


class OrderRequest(BaseModel):
    """Requete de placement d'ordre."""
    symbol: str = Field(..., description="UIC de l'instrument")
    asset_type: str = Field(default="Stock")
    buy_sell: str = Field(..., pattern="^(Buy|Sell)$")
    quantity: int = Field(..., gt=0)
    order_type: str = Field(default="Market")
    price: Optional[float] = None
    trailing_distance: Optional[float] = Field(default=None, description="Distance pour trailing stop (%)")
    account_key: str


class OrderResponse(BaseModel):
    """Reponse placement d'ordre."""
    order_id: str
    status: str
    message: str


class InstrumentResult(BaseModel):
    """Resultat recherche instrument."""
    uic: int
    symbol: str
    description: str
    asset_type: str
    exchange: Optional[str] = None


class SearchResponse(BaseModel):
    """Reponse recherche."""
    results: List[InstrumentResult]
    count: int


# =============================================================================
# HELPERS
# =============================================================================

def get_api_client() -> SaxoApiClient:
    """Cree un client API Saxo."""
    return SaxoApiClient(get_settings())


def require_token() -> SaxoToken:
    """
    Recupere un token valide ou leve une exception.

    Returns:
        SaxoToken valide

    Raises:
        HTTPException 401 si pas de token
    """
    auth = get_saxo_auth()
    token = auth.get_valid_token()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Non connecte a Saxo. Authentification requise."
        )

    return token


# =============================================================================
# ROUTES - AUTHENTIFICATION
# =============================================================================

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Verifie le statut de connexion Saxo.

    Retourne si Saxo est configure et si un token valide existe.
    """
    settings = get_settings()
    auth = get_saxo_auth(settings)

    if not auth.is_configured:
        return StatusResponse(
            configured=False,
            environment=settings.SAXO_ENVIRONMENT,
            connected=False,
            message="Saxo non configure. Ajoutez SAXO_APP_KEY et SAXO_APP_SECRET."
        )

    token = auth.get_valid_token()

    if token:
        return StatusResponse(
            configured=True,
            environment=token.environment,
            connected=True,
            expires_in=token.expires_in_seconds,
            message=f"Connecte ({token.environment})"
        )

    return StatusResponse(
        configured=True,
        environment=settings.SAXO_ENVIRONMENT,
        connected=False,
        message="Authentification requise"
    )


@router.get("/auth/url", response_model=AuthUrlResponse)
async def get_auth_url():
    """
    Genere l'URL OAuth pour connecter Saxo.

    Redirige l'utilisateur vers cette URL pour autoriser l'application.
    """
    auth = get_saxo_auth()

    if not auth.is_configured:
        raise HTTPException(status_code=400, detail="Saxo non configure")

    try:
        url = auth.get_auth_url()
        return AuthUrlResponse(auth_url=url)
    except Exception as e:
        logger.exception("Error generating auth URL")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback", response_model=AuthCallbackResponse)
async def oauth_callback(code: str = Query(...)):
    """
    Callback OAuth - echange le code contre un token.

    Args:
        code: Code d'autorisation recu de Saxo
    """
    auth = get_saxo_auth()

    if not auth.is_configured:
        raise HTTPException(status_code=400, detail="Saxo non configure")

    try:
        token = auth.exchange_code(code)

        logger.info(f"OAuth callback successful: {token.environment}")

        return AuthCallbackResponse(
            success=True,
            access_token=token.access_token,
            environment=token.environment,
            expires_in=token.expires_in_seconds,
            message=f"Connecte a Saxo ({token.environment})"
        )

    except Exception as e:
        logger.exception("OAuth callback error")
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/disconnect")
async def disconnect():
    """Deconnecte l'utilisateur Saxo."""
    auth = get_saxo_auth()
    auth.disconnect()
    return {"success": True, "message": "Deconnecte"}


@router.post("/refresh-token")
async def force_refresh_token():
    """
    Force le rafraichissement du token Saxo.

    Utile quand le token est proche de l'expiration et que vous voulez
    le rafraichir manuellement sans attendre le job automatique.

    Returns:
        Statut du refresh avec le nouveau temps d'expiration
    """
    from src.jobs.token_refresh import force_refresh_token as do_refresh

    result = do_refresh()

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Refresh failed")
        )

    return {
        "success": True,
        "environment": result["environment"],
        "expires_in_seconds": result["expires_in_seconds"],
        "expires_in_minutes": result["expires_in_minutes"],
        "message": f"Token rafraichi avec succes, expire dans {result['expires_in_minutes']} minutes"
    }


@router.get("/token-info")
async def get_token_info():
    """
    Retourne les informations detaillees sur le token actuel.

    Utile pour le debugging et pour voir quand le token expire.
    """
    settings = get_settings()
    auth = get_saxo_auth(settings)

    if not auth.is_configured:
        return {
            "configured": False,
            "message": "Saxo non configure"
        }

    token = auth.token_manager.get(auth.environment)

    if not token:
        return {
            "configured": True,
            "connected": False,
            "message": "Aucun token trouve"
        }

    expires_in = token.expires_in_seconds
    expires_at = token.expires_at.isoformat() if token.expires_at else None

    return {
        "configured": True,
        "connected": True,
        "environment": token.environment,
        "expires_at": expires_at,
        "expires_in_seconds": expires_in,
        "expires_in_minutes": expires_in // 60,
        "has_refresh_token": bool(token.refresh_token),
        "is_expired": token.is_expired,
        "message": f"Token valide, expire dans {expires_in // 60} minutes"
    }


@router.get("/token-health")
async def get_token_health():
    """
    Retourne l'etat de sante complet du systeme de tokens.

    Inclut:
    - Statut du token (valid, expiring_soon, expired, missing)
    - Temps restant avant expiration (access ET refresh token)
    - Statistiques du service de refresh (tentatives, echecs, taux de succes)
    - Prochain refresh prevu

    Utile pour le monitoring et le debugging.
    """
    from src.jobs.token_refresh import get_token_health as do_get_health

    return do_get_health()


# =============================================================================
# ROUTES - PORTEFEUILLE
# =============================================================================

@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """
    Recupere le portefeuille Saxo.

    Necessite une connexion active.
    """
    token = require_token()
    client = get_api_client()

    try:
        # Info client
        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            raise HTTPException(status_code=404, detail="Client non trouve")

        # Comptes
        accounts = client.get_accounts(token.access_token, client_key)
        account_key = accounts[0].get("AccountKey") if accounts else None
        account_currency = accounts[0].get("Currency", "EUR") if accounts else "EUR"

        # Soldes du compte
        cash_available = None
        total_account_value = None
        try:
            balances = client.get_balances(token.access_token, client_key)
            cash_available = balances.get("CashAvailableForTrading", 0)
            total_account_value = balances.get("TotalValue", 0)
            logger.info(f"Balances: cash={cash_available}, total={total_account_value}")
        except Exception as e:
            logger.warning(f"Could not fetch balances: {e}")

        # Positions - utilise /positions/me avec PositionBase, PositionView, DisplayAndFormat
        positions_data = client.get_positions(token.access_token, client_key)

        positions = []
        total_value = 0
        total_pnl = 0

        for pos in positions_data:
            # Structure de /positions/me:
            # - PositionBase: Uic, Amount, AssetType, AccountId
            # - PositionView: CurrentPrice, Exposure, ProfitLossOnTrade, MarketValue
            # - DisplayAndFormat: Symbol, Description, Currency
            base = pos.get("PositionBase", {})
            view = pos.get("PositionView", {})
            display = pos.get("DisplayAndFormat", {})
            position_id = pos.get("PositionId", "")

            # Symbole depuis DisplayAndFormat
            symbol = display.get("Symbol", "")
            if not symbol:
                symbol = f"UIC:{base.get('Uic', 'N/A')}"

            # Prix et valeurs depuis PositionView
            quantity = base.get("Amount", 0) or 0
            current_price = view.get("CurrentPrice", 0) or 0
            avg_price = view.get("AverageOpenPrice", 0) or base.get("OpenPrice", 0) or 0

            # MarketValue peut etre dans Exposure ou calculé
            value = view.get("MarketValue", 0) or view.get("Exposure", 0) or 0
            if value == 0 and current_price > 0:
                value = current_price * abs(quantity)

            # P&L
            pnl = view.get("ProfitLossOnTrade", 0) or 0
            pnl_percent = view.get("ProfitLossOnTradeInPercentage", 0) or 0

            # Calculer P&L % si non fourni
            if pnl_percent == 0 and avg_price > 0 and current_price > 0:
                pnl_percent = ((current_price - avg_price) / avg_price) * 100

            # Log debug
            logger.info(f"Position {symbol}: qty={quantity}, price={current_price}, avg={avg_price}, value={value}, pnl={pnl}")

            positions.append(PositionItem(
                symbol=symbol,
                description=display.get("Description", ""),
                quantity=quantity,
                current_price=current_price,
                average_price=avg_price,
                market_value=value,
                pnl=pnl,
                pnl_percent=round(pnl_percent, 2),
                currency=display.get("Currency", "EUR"),
                asset_type=base.get("AssetType", "Stock"),
                uic=base.get("Uic")
            ))

            total_value += abs(value)
            total_pnl += pnl

        total_pnl_percent = (total_pnl / total_value * 100) if total_value > 0 else 0

        return PortfolioResponse(
            positions=positions,
            summary=PortfolioSummary(
                total_positions=len(positions),
                total_value=round(total_value, 2),
                total_pnl=round(total_pnl, 2),
                total_pnl_percent=round(total_pnl_percent, 2),
                cash_available=round(cash_available, 2) if cash_available else None,
                total_account_value=round(total_account_value, 2) if total_account_value else None,
                currency=account_currency
            ),
            account_key=account_key
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching portfolio")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/enhanced")
async def get_enhanced_portfolio():
    """
    Recupere le portefeuille avec analyse complete par position.

    Inclut pour chaque position:
    - Analyse technique (RSI, MACD, trend, support/resistance)
    - News et sentiment
    - Metriques de risque (poids, SL/TP suggeres)
    - Recommandation (BUY/SELL/HOLD)
    """
    from src.application.services.portfolio_analysis_service import (
        PortfolioAnalysisService,
    )

    token = require_token()
    client = get_api_client()

    try:
        # Recuperer le portfolio de base
        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            raise HTTPException(status_code=404, detail="Client non trouve")

        accounts = client.get_accounts(token.access_token, client_key)
        account_key = accounts[0].get("AccountKey") if accounts else None

        positions_data = client.get_positions(token.access_token, client_key)

        # Construire les positions de base
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
                "current_price": current_price,
                "average_price": avg_price,
                "market_value": value,
                "pnl": pnl,
                "pnl_percent": round(pnl_percent, 2),
                "currency": display.get("Currency", "EUR"),
                "asset_type": base.get("AssetType", "Stock"),
                "uic": base.get("Uic"),
            })

            total_value += abs(value)
            total_pnl += pnl

        # Analyser chaque position
        analysis_service = PortfolioAnalysisService()
        enhanced_positions = await analysis_service.analyze_portfolio(
            positions=positions,
            portfolio_total_value=total_value,
        )

        total_pnl_percent = (total_pnl / total_value * 100) if total_value > 0 else 0

        return {
            "positions": [p.to_dict() for p in enhanced_positions],
            "summary": {
                "total_positions": len(positions),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round(total_pnl_percent, 2),
            },
            "account_key": account_key,
            "analyzed_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching enhanced portfolio")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_orders(status: str = Query("All")):
    """Recupere les ordres."""
    token = require_token()
    client = get_api_client()

    try:
        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            return {"orders": []}

        orders = client.get_orders(token.access_token, client_key, status)
        return {"orders": orders}

    except Exception as e:
        logger.exception("Error fetching orders")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(days: int = Query(30)):
    """Recupere l'historique des transactions."""
    token = require_token()
    client = get_api_client()

    try:
        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            return {"transactions": []}

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        transactions = client.get_trade_history(
            token.access_token,
            client_key,
            start_date,
            end_date
        )

        return {"transactions": transactions}

    except Exception as e:
        logger.exception("Error fetching history")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROUTES - TRADING
# =============================================================================

@router.get("/search", response_model=SearchResponse)
async def search_instruments(
    query: str = Query(..., min_length=1),
    asset_types: str = Query("Stock,Etf")
):
    """Recherche des instruments."""
    token = require_token()
    client = get_api_client()

    try:
        types_list = [t.strip() for t in asset_types.split(",")]
        results = client.search_instruments(token.access_token, query, types_list)

        formatted = [
            InstrumentResult(
                uic=r.get("Identifier", 0),
                symbol=r.get("Symbol", ""),
                description=r.get("Description", ""),
                asset_type=r.get("AssetType", "Stock"),
                exchange=r.get("ExchangeId")
            )
            for r in results
        ]

        return SearchResponse(results=formatted, count=len(formatted))

    except Exception as e:
        logger.exception("Error searching instruments")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROUTES - ANALYSE D'INSTRUMENT (PRE-ACHAT)
# =============================================================================

@router.get("/instruments/{symbol}/analyze")
async def analyze_instrument(symbol: str):
    """
    Analyse complete d'un instrument AVANT achat.

    Fournit toutes les informations necessaires pour prendre
    une decision d'achat eclairee:

    - **Info**: Nom, secteur, capitalisation
    - **Prix**: Cours actuel, variation, volume, plus haut/bas 52 semaines
    - **Technique**: RSI, MACD, Bollinger, tendance, supports/resistances
    - **Sentiment**: Score de sentiment, news recentes
    - **Niveaux de trading**: SL/TP suggeres, ratio risk/reward
    - **Recommandation**: BUY/WAIT/AVOID avec niveau de confiance

    Args:
        symbol: Symbole de l'instrument (ex: AAPL, MSFT, MC.PA)

    Returns:
        Analyse complete avec recommandation d'achat
    """
    from src.application.services.instrument_analysis_service import (
        get_instrument_analysis_service,
    )

    try:
        service = get_instrument_analysis_service()
        analysis = await service.analyze_instrument(symbol.upper())

        return analysis.to_dict()

    except ValueError as e:
        logger.warning(f"Analyse impossible pour {symbol}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Impossible d'analyser {symbol}: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Erreur analyse instrument {symbol}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse: {str(e)}"
        )


@router.get("/instruments/compare")
async def compare_instruments(symbols: str = Query(..., description="Symboles separes par des virgules")):
    """
    Compare plusieurs instruments pour aider au choix.

    Args:
        symbols: Liste de symboles separes par des virgules (ex: "AAPL,MSFT,GOOGL")

    Returns:
        Comparaison des instruments avec scores et rankings
    """
    import asyncio
    from src.application.services.instrument_analysis_service import (
        get_instrument_analysis_service,
    )

    symbol_list = [s.strip().upper() for s in symbols.split(",")]

    if len(symbol_list) < 2:
        raise HTTPException(
            status_code=400,
            detail="Au moins 2 symboles requis pour la comparaison"
        )

    if len(symbol_list) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 symboles pour la comparaison"
        )

    try:
        service = get_instrument_analysis_service()

        # Analyser tous les instruments en parallele
        tasks = [service.analyze_instrument(symbol) for symbol in symbol_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        comparisons = []
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({"symbol": symbol_list[i], "error": str(result)})
            else:
                comparisons.append({
                    "symbol": result.info.symbol,
                    "name": result.info.name,
                    "price": result.price.current_price,
                    "change_percent": result.price.change_percent,
                    "rsi": result.technical.rsi,
                    "trend": result.technical.trend,
                    "sentiment": result.sentiment.sentiment_label,
                    "recommendation": result.recommendation.action,
                    "confidence": result.recommendation.confidence,
                    "rating": result.recommendation.rating,
                    "pros_count": len(result.recommendation.pros),
                    "cons_count": len(result.recommendation.cons),
                })

        # Trier par rating puis confidence
        comparisons.sort(key=lambda x: (x["rating"], x["confidence"]), reverse=True)

        # Ajouter le ranking
        for i, comp in enumerate(comparisons):
            comp["rank"] = i + 1

        return {
            "comparisons": comparisons,
            "best_pick": comparisons[0]["symbol"] if comparisons else None,
            "errors": errors if errors else None,
            "analyzed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.exception("Erreur comparaison instruments")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders", response_model=OrderResponse)
async def place_order(order: OrderRequest):
    """Place un ordre."""
    token = require_token()
    client = get_api_client()

    try:
        # Déterminer la durée selon le type d'ordre
        # Market orders: DayOrder (GTC not allowed)
        # Limit orders: GoodTillCancel
        # Stop orders: DayOrder (default selon Saxo docs)
        if order.order_type == "Market":
            duration_type = "DayOrder"
        elif order.order_type in ("Stop", "StopIfTraded", "StopLimit", "TrailingStop", "TrailingStopIfTraded"):
            duration_type = "DayOrder"  # Stop orders use DayOrder by default
        else:
            duration_type = "GoodTillCancel"  # Limit orders can use GTC

        order_data = {
            "AccountKey": order.account_key,
            "Uic": int(order.symbol),
            "AssetType": order.asset_type,
            "Amount": float(order.quantity),  # Saxo attend un float
            "BuySell": order.buy_sell,
            "OrderType": order.order_type,
            "OrderDuration": {"DurationType": duration_type},
            "ManualOrder": True
        }

        # Gestion du prix selon le type d'ordre
        if order.order_type == "Limit" and order.price:
            order_data["OrderPrice"] = float(order.price)

        elif order.order_type in ("StopIfTraded", "Stop", "StopLimit") and order.price:
            # Pour les ordres Stop, OrderPrice est le prix de déclenchement
            order_data["OrderPrice"] = float(order.price)

        elif order.order_type in ("TrailingStop", "TrailingStopIfTraded") and order.price:
            # Trailing stop nécessite OrderPrice ET une distance
            order_data["OrderPrice"] = float(order.price)
            if order.trailing_distance:
                order_data["TrailingStopDistanceToMarket"] = float(order.trailing_distance)
                order_data["TrailingStopStep"] = 0.01

        logger.info(f"Placing order: {order_data}")
        result = client.place_order(token.access_token, order_data)

        return OrderResponse(
            order_id=str(result.get("OrderId", "unknown")),
            status="Placed",
            message="Ordre place avec succes"
        )

    except BrokerApiError as e:
        logger.error(f"Broker error placing order: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error placing order")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, account_key: str = Query(...)):
    """Annule un ordre."""
    token = require_token()
    client = get_api_client()

    try:
        success = client.cancel_order(token.access_token, order_id, account_key)

        if success:
            return {"success": True, "message": "Ordre annule"}
        else:
            raise HTTPException(status_code=400, detail="Impossible d'annuler l'ordre")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error canceling order")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROUTES - ALERTES POSITIONS
# =============================================================================

class PositionAlertRequest(BaseModel):
    """Requete creation alerte position."""
    symbol: str
    current_price: float
    stop_loss_percent: float = Field(default=8.0, description="% sous prix actuel")
    take_profit_percent: float = Field(default=24.0, description="% au-dessus prix actuel")


class PositionAlertResponse(BaseModel):
    """Reponse creation alerte."""
    success: bool
    stop_loss_alert_id: Optional[str] = None
    take_profit_alert_id: Optional[str] = None
    stop_loss_price: float
    take_profit_price: float
    message: str


@router.post("/positions/alerts", response_model=PositionAlertResponse)
async def create_position_alerts(request: PositionAlertRequest):
    """
    Cree des alertes Stop Loss et Take Profit pour une position.

    Args:
        request: Parametres de l'alerte (symbol, prix, % SL/TP)

    Returns:
        IDs des alertes creees et prix calcules
    """
    from src.application.services.alert_service import AlertService
    from src.infrastructure.notifications.telegram_service import get_telegram_service

    try:
        service = AlertService()
        telegram = get_telegram_service()

        # Calculer les prix SL/TP
        sl_price = request.current_price * (1 - request.stop_loss_percent / 100)
        tp_price = request.current_price * (1 + request.take_profit_percent / 100)

        # Creer alerte Stop Loss
        sl_alert = await service.create_alert(
            ticker=request.symbol,
            alert_type="price_below",
            target_value=sl_price,
            notes=f"Stop Loss {request.stop_loss_percent}% - Prix entree: {request.current_price:.2f}"
        )

        # Creer alerte Take Profit
        tp_alert = await service.create_alert(
            ticker=request.symbol,
            alert_type="price_above",
            target_value=tp_price,
            notes=f"Take Profit {request.take_profit_percent}% - Prix entree: {request.current_price:.2f}"
        )

        logger.info(f"Created SL/TP alerts for {request.symbol}: SL={sl_price:.2f}, TP={tp_price:.2f}")

        # Envoyer confirmation Telegram
        if telegram.is_configured:
            await telegram.send_message(
                f"🔔 <b>ALERTES CONFIGUREES</b>\n\n"
                f"📊 <b>{request.symbol}</b>\n"
                f"💰 Prix actuel: {request.current_price:.2f}€\n\n"
                f"🔴 <b>Stop Loss:</b> {sl_price:.2f}€ (-{request.stop_loss_percent}%)\n"
                f"🟢 <b>Take Profit:</b> {tp_price:.2f}€ (+{request.take_profit_percent}%)\n\n"
                f"<i>Vous serez notifie quand ces niveaux seront atteints.</i>"
            )

        return PositionAlertResponse(
            success=True,
            stop_loss_alert_id=str(sl_alert.id) if hasattr(sl_alert, 'id') else "created",
            take_profit_alert_id=str(tp_alert.id) if hasattr(tp_alert, 'id') else "created",
            stop_loss_price=round(sl_price, 2),
            take_profit_price=round(tp_price, 2),
            message=f"Alertes creees: SL a {sl_price:.2f}, TP a {tp_price:.2f}"
        )

    except Exception as e:
        logger.exception("Error creating position alerts")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{symbol}/alerts")
async def get_position_alerts(symbol: str):
    """
    Recupere les alertes actives pour une position.

    Args:
        symbol: Symbole de la position

    Returns:
        Liste des alertes actives
    """
    from src.application.services.alert_service import AlertService

    try:
        service = AlertService()
        alerts = await service.get_all_alerts(active_only=True, ticker=symbol.upper())

        return {
            "symbol": symbol.upper(),
            "alerts": [
                {
                    "id": a.id,
                    "type": a.alert_type.value if hasattr(a.alert_type, 'value') else str(a.alert_type),
                    "target_price": a.target_value,
                    "notes": a.notes,
                    "created_at": a.created_at,
                }
                for a in alerts
            ],
            "count": len(alerts)
        }

    except Exception as e:
        logger.exception(f"Error fetching alerts for {symbol}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROUTES - DEBUG & TEST
# =============================================================================

@router.get("/debug/portfolio-raw")
async def get_portfolio_raw():
    """
    DEBUG: Retourne les donnees brutes de l'API Saxo pour diagnostic.

    Utile pour voir la structure exacte des donnees retournees.
    Utilise /port/v1/positions/me avec FieldGroups complets.
    """
    token = require_token()
    client = get_api_client()

    try:
        client_info = client.get_client_info(token.access_token)
        client_key = client_info.get("ClientKey")

        if not client_key:
            return {"error": "No client key found", "client_info": client_info}

        # Recuperer les positions brutes (utilise /positions/me)
        positions_data = client.get_positions(token.access_token, client_key)

        # Extraire un exemple de structure
        sample_position = None
        if positions_data:
            sample_position = {
                "raw": positions_data[0],
                "keys": list(positions_data[0].keys()),
                "PositionBase_keys": list(positions_data[0].get("PositionBase", {}).keys()),
                "PositionView_keys": list(positions_data[0].get("PositionView", {}).keys()),
                "DisplayAndFormat_keys": list(positions_data[0].get("DisplayAndFormat", {}).keys()),
            }

        return {
            "positions_count": len(positions_data),
            "sample_position": sample_position,
            "all_positions": positions_data,
        }

    except Exception as e:
        logger.exception("Debug portfolio error")
        return {"error": str(e)}


@router.post("/test/telegram")
async def test_telegram_notification(
    message: str = Query(default="Test notification from Stock Analyzer")
):
    """
    TEST: Envoie une notification Telegram de test.

    Args:
        message: Message a envoyer

    Returns:
        Resultat de l'envoi
    """
    from src.infrastructure.notifications.telegram_service import get_telegram_service

    try:
        telegram = get_telegram_service()

        if not telegram.is_configured:
            return {
                "success": False,
                "error": "Telegram non configure. Ajoutez TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID."
            }

        # Envoyer message de test
        result = await telegram.send_message(
            f"🧪 <b>TEST NOTIFICATION</b>\n\n{message}\n\n"
            f"<i>Envoye depuis Stock Analyzer</i>"
        )

        return {
            "success": result,
            "message": "Notification envoyee!" if result else "Echec envoi"
        }

    except Exception as e:
        logger.exception("Telegram test error")
        return {"success": False, "error": str(e)}


@router.post("/test/alert-notification")
async def test_alert_notification(
    symbol: str = Query(...),
    price: float = Query(...),
    alert_type: str = Query(default="stop_loss")
):
    """
    TEST: Simule une notification d'alerte SL/TP.

    Args:
        symbol: Symbole de l'action
        price: Prix actuel
        alert_type: Type d'alerte (stop_loss ou take_profit)

    Returns:
        Resultat de l'envoi
    """
    from src.infrastructure.notifications.telegram_service import get_telegram_service

    try:
        telegram = get_telegram_service()

        if not telegram.is_configured:
            return {"success": False, "error": "Telegram non configure"}

        if alert_type == "stop_loss":
            result = await telegram.send_stop_loss_alert(
                ticker=symbol,
                current_price=price,
                stop_loss_price=price * 0.92,
                entry_price=price * 1.05,
                pnl_percent=-8.0
            )
        else:
            result = await telegram.send_take_profit_alert(
                ticker=symbol,
                current_price=price,
                take_profit_price=price * 0.95,
                entry_price=price * 0.80,
                pnl_percent=25.0
            )

        return {
            "success": result,
            "alert_type": alert_type,
            "message": f"Alerte {alert_type} envoyee pour {symbol}!"
        }

    except Exception as e:
        logger.exception("Alert notification test error")
        return {"success": False, "error": str(e)}
