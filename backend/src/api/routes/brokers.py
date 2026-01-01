"""
Routes API pour les brokers (Saxo, etc.).

Endpoints:
- GET /api/brokers/{broker}/status - Vérifie la configuration
- GET /api/brokers/{broker}/auth/url - URL d'autorisation OAuth
- GET /api/brokers/{broker}/callback - Callback OAuth
- GET /api/brokers/{broker}/portfolio - Portefeuille
- GET /api/brokers/{broker}/orders - Ordres
- POST /api/brokers/{broker}/orders - Place un ordre
- DELETE /api/brokers/{broker}/orders/{order_id} - Annule un ordre

ARCHITECTURE:
- Routes génériques avec {broker} pour supporter plusieurs brokers
- Validation des credentials via middleware ou session
- Injection des services broker
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.application.interfaces.broker_service import (
    BrokerCredentials,
    OrderRequest,
)
from src.application.use_cases import (
    GetPortfolioUseCase,
    PlaceOrderUseCase,
    CancelOrderUseCase,
    GetOrdersUseCase,
)
from src.config.constants import BrokerName
from src.domain.exceptions import (
    BrokerNotConfiguredError,
    BrokerAuthenticationError,
    TokenExpiredError,
    OrderValidationError,
)

router = APIRouter(prefix="/brokers", tags=["brokers"])


# =============================================================================
# SCHEMAS
# =============================================================================

class BrokerStatusResponse(BaseModel):
    """Statut de configuration d'un broker."""

    broker: str
    configured: bool
    message: str


class AuthUrlResponse(BaseModel):
    """URL d'autorisation OAuth."""

    auth_url: str
    state: str


class AuthCallbackResponse(BaseModel):
    """Réponse du callback OAuth."""

    success: bool
    message: str
    expires_at: Optional[str] = None


class PositionResponse(BaseModel):
    """Position dans le portefeuille."""

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
    uic: Optional[int] = None
    # Enrichissement optionnel
    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_1y: Optional[float] = None
    is_resilient: Optional[bool] = None
    volatility: Optional[float] = None


class PortfolioResponse(BaseModel):
    """Portefeuille complet."""

    positions: List[PositionResponse]
    account_key: Optional[str] = None
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    resilient_count: int
    resilient_percent: float
    updated_at: str


class OrderResponse(BaseModel):
    """Ordre."""

    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    filled_quantity: float
    price: Optional[float] = None
    status: str
    created_at: str


class PlaceOrderRequest(BaseModel):
    """Requête pour placer un ordre."""

    symbol: str = Field(..., description="Symbole de l'instrument")
    uic: int = Field(..., description="Universal Instrument Code (Saxo)")
    asset_type: str = Field(default="stock", description="Type d'actif")
    quantity: int = Field(..., gt=0, description="Quantité")
    side: str = Field(..., pattern="^(Buy|Sell)$", description="Direction")
    order_type: str = Field(default="Market", description="Type d'ordre")
    price: Optional[float] = Field(None, description="Prix (pour Limit)")


class PlaceOrderResponse(BaseModel):
    """Réponse de placement d'ordre."""

    order_id: str
    status: str
    message: str


class InstrumentResponse(BaseModel):
    """Instrument (résultat de recherche)."""

    symbol: str
    name: str
    asset_type: str
    exchange: Optional[str] = None
    currency: Optional[str] = None
    uic: Optional[int] = None


# =============================================================================
# HELPERS
# =============================================================================

def validate_broker_name(broker: str) -> str:
    """Valide et normalise le nom du broker."""
    broker_lower = broker.lower()
    try:
        BrokerName(broker_lower)
        return broker_lower
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Broker '{broker}' non supporté. Brokers disponibles: {[b.value for b in BrokerName]}",
        )


# =============================================================================
# PLACEHOLDER DEPENDENCIES
# =============================================================================

# Ces fonctions seront implémentées dans dependencies.py
async def get_broker_factory():
    """Placeholder pour l'injection."""
    from src.api.dependencies import get_broker_factory as factory
    return await factory()


async def get_credentials_from_session(request: Request, broker: str) -> Optional[BrokerCredentials]:
    """Récupère les credentials depuis la session."""
    # Placeholder - sera implémenté avec le middleware de session
    from src.api.dependencies import get_credentials
    return await get_credentials(request, broker)


# =============================================================================
# ROUTES - STATUS
# =============================================================================

@router.get(
    "/{broker}/status",
    response_model=BrokerStatusResponse,
)
async def get_broker_status(
    broker: str,
    factory=Depends(get_broker_factory),
):
    """
    Vérifie le statut de configuration d'un broker.
    """
    broker_name = validate_broker_name(broker)

    try:
        broker_service = factory.create(broker_name)
        is_configured = broker_service.is_configured

        return BrokerStatusResponse(
            broker=broker_name,
            configured=is_configured,
            message="Broker configuré" if is_configured else "Broker non configuré",
        )
    except BrokerNotConfiguredError:
        return BrokerStatusResponse(
            broker=broker_name,
            configured=False,
            message="Broker non configuré",
        )


# =============================================================================
# ROUTES - AUTHENTICATION
# =============================================================================

@router.get(
    "/{broker}/auth/url",
    response_model=AuthUrlResponse,
)
async def get_auth_url(
    broker: str,
    factory=Depends(get_broker_factory),
):
    """
    Génère l'URL d'autorisation OAuth2.

    Redirigez l'utilisateur vers cette URL pour l'authentification.
    """
    broker_name = validate_broker_name(broker)

    try:
        broker_service = factory.create(broker_name)

        if not broker_service.is_configured:
            raise HTTPException(
                status_code=400,
                detail=f"Broker '{broker_name}' non configuré",
            )

        result = await broker_service.get_authorization_url(
            user_id="default",  # En mono-utilisateur
        )

        return AuthUrlResponse(
            auth_url=result["auth_url"],
            state=result["state"],
        )

    except BrokerNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{broker}/callback",
    response_model=AuthCallbackResponse,
)
async def oauth_callback(
    broker: str,
    code: str = Query(..., description="Code d'autorisation"),
    state: str = Query(..., description="État CSRF"),
    request: Request = None,
    factory=Depends(get_broker_factory),
):
    """
    Callback OAuth2.

    Ce endpoint est appelé par le broker après l'authentification.
    """
    broker_name = validate_broker_name(broker)

    try:
        broker_service = factory.create(broker_name)

        credentials = await broker_service.handle_oauth_callback(
            user_id="default",
            authorization_code=code,
            state=state,
        )

        # Stocker les credentials dans la session
        # (sera implémenté avec le middleware de session)
        if request and hasattr(request, "session"):
            request.session[f"{broker_name}_credentials"] = {
                "access_token": credentials.access_token,
                "refresh_token": credentials.refresh_token,
                "expires_at": credentials.expires_at.isoformat(),
            }

        return AuthCallbackResponse(
            success=True,
            message="Authentification réussie",
            expires_at=credentials.expires_at.isoformat(),
        )

    except BrokerAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{broker}/logout")
async def logout(
    broker: str,
    request: Request,
):
    """
    Déconnecte l'utilisateur du broker.
    """
    broker_name = validate_broker_name(broker)

    # Supprimer les credentials de la session
    if request and hasattr(request, "session"):
        request.session.pop(f"{broker_name}_credentials", None)

    return {"success": True, "message": "Déconnexion réussie"}


# =============================================================================
# ROUTES - PORTFOLIO
# =============================================================================

@router.get(
    "/{broker}/portfolio",
    response_model=PortfolioResponse,
)
async def get_portfolio(
    broker: str,
    enrich: bool = Query(True, description="Enrichir avec les données d'analyse"),
    request: Request = None,
    factory=Depends(get_broker_factory),
):
    """
    Récupère le portefeuille du broker.

    Optionnellement enrichi avec les métriques de performance.
    """
    broker_name = validate_broker_name(broker)

    credentials = await get_credentials_from_session(request, broker_name)
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Non authentifié. Veuillez vous connecter d'abord.",
        )

    try:
        broker_service = factory.create(broker_name)

        # Créer le use case avec ou sans provider selon enrich
        from src.api.dependencies import get_stock_provider
        provider = await get_stock_provider() if enrich else None

        use_case = GetPortfolioUseCase(broker_service, provider)
        portfolio = await use_case.execute(credentials, enrich=enrich)

        return PortfolioResponse(
            positions=[
                PositionResponse(
                    symbol=p.symbol,
                    description=p.description,
                    quantity=p.quantity,
                    current_price=p.current_price,
                    average_price=p.average_price,
                    market_value=p.market_value,
                    pnl=p.pnl,
                    pnl_percent=p.pnl_percent,
                    currency=p.currency,
                    asset_type=p.asset_type,
                    uic=p.uic,
                    perf_3m=p.perf_3m,
                    perf_6m=p.perf_6m,
                    perf_1y=p.perf_1y,
                    is_resilient=p.is_resilient,
                    volatility=p.volatility,
                )
                for p in portfolio.positions
            ],
            account_key=portfolio.account_key,
            total_value=portfolio.total_value,
            total_pnl=portfolio.total_pnl,
            total_pnl_percent=portfolio.total_pnl_percent,
            resilient_count=portfolio.resilient_count,
            resilient_percent=portfolio.resilient_percent,
            updated_at=portfolio.updated_at,
        )

    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Session expirée. Veuillez vous reconnecter.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROUTES - ORDERS
# =============================================================================

@router.get(
    "/{broker}/orders",
    response_model=List[OrderResponse],
)
async def get_orders(
    broker: str,
    status: Optional[str] = Query(None, description="Filtre de statut"),
    request: Request = None,
    factory=Depends(get_broker_factory),
):
    """
    Récupère les ordres du broker.
    """
    broker_name = validate_broker_name(broker)

    credentials = await get_credentials_from_session(request, broker_name)
    if not credentials:
        raise HTTPException(status_code=401, detail="Non authentifié")

    try:
        broker_service = factory.create(broker_name)
        use_case = GetOrdersUseCase(broker_service)
        orders = await use_case.execute(credentials, status)

        return [
            OrderResponse(
                order_id=o.order_id,
                symbol=o.symbol,
                side=o.side,
                order_type=o.order_type,
                quantity=o.quantity,
                filled_quantity=o.filled_quantity,
                price=o.price,
                status=o.status,
                created_at=o.created_at,
            )
            for o in orders
        ]

    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Session expirée")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{broker}/orders",
    response_model=PlaceOrderResponse,
)
async def place_order(
    broker: str,
    order_request: PlaceOrderRequest,
    account_key: str = Query(..., description="Clé du compte"),
    request: Request = None,
    factory=Depends(get_broker_factory),
):
    """
    Place un ordre.
    """
    broker_name = validate_broker_name(broker)

    credentials = await get_credentials_from_session(request, broker_name)
    if not credentials:
        raise HTTPException(status_code=401, detail="Non authentifié")

    try:
        broker_service = factory.create(broker_name)
        use_case = PlaceOrderUseCase(broker_service)

        order = OrderRequest(
            symbol=order_request.symbol,
            uic=order_request.uic,
            asset_type=order_request.asset_type,
            quantity=order_request.quantity,
            side=order_request.side,
            order_type=order_request.order_type,
            price=order_request.price,
        )

        confirmation = await use_case.execute(credentials, order, account_key)

        return PlaceOrderResponse(
            order_id=confirmation.order_id,
            status=confirmation.status,
            message=confirmation.message,
        )

    except OrderValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Session expirée")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{broker}/orders/{order_id}",
)
async def cancel_order(
    broker: str,
    order_id: str,
    account_key: str = Query(..., description="Clé du compte"),
    request: Request = None,
    factory=Depends(get_broker_factory),
):
    """
    Annule un ordre.
    """
    broker_name = validate_broker_name(broker)

    credentials = await get_credentials_from_session(request, broker_name)
    if not credentials:
        raise HTTPException(status_code=401, detail="Non authentifié")

    try:
        broker_service = factory.create(broker_name)
        use_case = CancelOrderUseCase(broker_service)

        success = await use_case.execute(credentials, order_id, account_key)

        if success:
            return {"success": True, "message": "Ordre annulé"}
        else:
            raise HTTPException(status_code=400, detail="Impossible d'annuler l'ordre")

    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Session expirée")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROUTES - INSTRUMENTS
# =============================================================================

@router.get(
    "/{broker}/instruments/search",
    response_model=List[InstrumentResponse],
)
async def search_instruments(
    broker: str,
    query: str = Query(..., min_length=2, description="Terme de recherche"),
    asset_types: Optional[str] = Query(
        None,
        description="Types d'actifs (séparés par virgules)",
    ),
    request: Request = None,
    factory=Depends(get_broker_factory),
):
    """
    Recherche des instruments.
    """
    broker_name = validate_broker_name(broker)

    credentials = await get_credentials_from_session(request, broker_name)
    if not credentials:
        raise HTTPException(status_code=401, detail="Non authentifié")

    try:
        broker_service = factory.create(broker_name)

        # Parser les types d'actifs
        types_list = None
        if asset_types:
            types_list = [t.strip() for t in asset_types.split(",")]

        instruments = await broker_service.search_instruments(
            credentials,
            query,
            types_list,
        )

        return [
            InstrumentResponse(
                symbol=i.symbol,
                name=i.name,
                asset_type=i.asset_type,
                exchange=i.exchange,
                currency=i.currency,
                uic=i.uic,
            )
            for i in instruments
        ]

    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Session expirée")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
