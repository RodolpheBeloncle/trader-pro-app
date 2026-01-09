"""
Routes API pour le journal de trading.

Endpoints:
- POST /journal/trades           - Créer un trade
- GET /journal/trades            - Lister les trades
- GET /journal/trades/{id}       - Détails d'un trade
- PUT /journal/trades/{id}       - Modifier un trade
- POST /journal/trades/{id}/activate - Activer un trade planifié
- POST /journal/trades/{id}/close    - Clôturer un trade
- POST /journal/trades/{id}/cancel   - Annuler un trade
- POST /journal/entries          - Ajouter entrée de journal
- GET /journal/entries/{trade_id} - Entrée de journal d'un trade
- POST /journal/entries/{trade_id}/post-trade - Analyse post-trade
- GET /journal/stats             - Statistiques globales
- GET /journal/stats/monthly     - Stats mensuelles
- GET /journal/stats/by-setup    - Stats par setup
- GET /journal/dashboard         - Dashboard complet
"""

import logging
from typing import Optional, List
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.services.journal_service import JournalService
from src.infrastructure.database.repositories.trade_repository import Trade, TradeStatus
from src.infrastructure.database.repositories.journal_repository import JournalEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CreateTradeRequest(BaseModel):
    """Requête de création de trade."""
    ticker: str = Field(..., min_length=1, max_length=10)
    direction: str = Field(..., description="long ou short")
    entry_price: Optional[float] = Field(None, gt=0)
    stop_loss: Optional[float] = Field(None, gt=0)
    take_profit: Optional[float] = Field(None, gt=0)
    position_size: Optional[int] = Field(None, gt=0)
    status: str = Field("planned", description="planned ou active")

    # Journal entry optionnel
    setup_type: Optional[str] = None
    trade_thesis: Optional[str] = None
    market_regime: Optional[str] = None
    market_bias: Optional[str] = None
    timeframe: Optional[str] = None
    confluence_factors: Optional[List[str]] = None


class UpdateTradeRequest(BaseModel):
    """Requête de modification de trade."""
    stop_loss: Optional[float] = Field(None, gt=0)
    take_profit: Optional[float] = Field(None, gt=0)
    position_size: Optional[int] = Field(None, gt=0)


class ActivateTradeRequest(BaseModel):
    """Requête d'activation de trade."""
    entry_price: Optional[float] = Field(None, gt=0, description="Prix d'entrée réel")
    actual_entry_price: Optional[float] = Field(None, gt=0, description="Alias pour entry_price")


class CloseTradeRequest(BaseModel):
    """Requête de clôture de trade."""
    exit_price: float = Field(..., gt=0)
    fees: float = Field(0.0, ge=0)


class JournalEntryRequest(BaseModel):
    """Requête d'entrée de journal."""
    setup_type: Optional[str] = None
    trade_thesis: Optional[str] = None
    market_regime: Optional[str] = None
    market_bias: Optional[str] = None
    timeframe: Optional[str] = None
    confluence_factors: Optional[List[str]] = None


class PostTradeAnalysisRequest(BaseModel):
    """Requête d'analyse post-trade."""
    execution_quality: str = Field(..., description="excellent, good, average, poor")
    emotional_state: str = Field(..., description="calm, confident, anxious, fomo, revenge")
    process_compliance: str = Field(..., description="followed, deviated, ignored")
    trade_quality_score: int = Field(..., ge=1, le=10)
    mistakes: Optional[List[str]] = None
    what_went_well: Optional[List[str]] = None
    what_to_improve: Optional[List[str]] = None
    lessons_learned: Optional[str] = None


class TradeResponse(BaseModel):
    """Réponse avec un trade."""
    id: str
    ticker: str
    direction: str
    status: str
    entry_price: Optional[float]
    exit_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size: Optional[int]
    entry_time: Optional[str]
    exit_time: Optional[str]
    gross_pnl: Optional[float]
    net_pnl: Optional[float]
    fees: float
    r_multiple: Optional[float]
    created_at: str

    @classmethod
    def from_entity(cls, trade: Trade) -> "TradeResponse":
        return cls(
            id=trade.id,
            ticker=trade.ticker,
            direction=trade.direction.value,
            status=trade.status.value,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            position_size=trade.position_size,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            gross_pnl=trade.gross_pnl,
            net_pnl=trade.net_pnl,
            fees=trade.fees,
            r_multiple=trade.r_multiple,
            created_at=trade.created_at,
        )


class JournalEntryResponse(BaseModel):
    """Réponse avec une entrée de journal."""
    id: str
    trade_id: str
    market_regime: Optional[str]
    market_bias: Optional[str]
    setup_type: Optional[str]
    timeframe: Optional[str]
    trade_thesis: Optional[str]
    confluence_factors: List[str]
    execution_quality: Optional[str]
    emotional_state: Optional[str]
    process_compliance: Optional[str]
    mistakes: List[str]
    what_went_well: List[str]
    what_to_improve: List[str]
    lessons_learned: Optional[str]
    trade_quality_score: Optional[int]
    created_at: str

    @classmethod
    def from_entity(cls, entry: JournalEntry) -> "JournalEntryResponse":
        return cls(
            id=entry.id,
            trade_id=entry.trade_id,
            market_regime=entry.market_regime,
            market_bias=entry.market_bias,
            setup_type=entry.setup_type,
            timeframe=entry.timeframe,
            trade_thesis=entry.trade_thesis,
            confluence_factors=entry.confluence_factors,
            execution_quality=entry.execution_quality.value if entry.execution_quality else None,
            emotional_state=entry.emotional_state.value if entry.emotional_state else None,
            process_compliance=entry.process_compliance.value if entry.process_compliance else None,
            mistakes=entry.mistakes,
            what_went_well=entry.what_went_well,
            what_to_improve=entry.what_to_improve,
            lessons_learned=entry.lessons_learned,
            trade_quality_score=entry.trade_quality_score,
            created_at=entry.created_at,
        )


# =============================================================================
# SERVICE
# =============================================================================

def get_journal_service() -> JournalService:
    """Factory pour le service de journal."""
    return JournalService()


# =============================================================================
# TRADES ROUTES
# =============================================================================

@router.post("/trades", response_model=TradeResponse, status_code=201)
async def create_trade(request: CreateTradeRequest):
    """
    Crée un nouveau trade.

    Le trade peut être créé avec le statut "planned" (en attente d'exécution)
    ou "active" (déjà en position).

    Optionnellement, les informations de journal peuvent être fournies
    pour l'analyse pré-trade.
    """
    service = get_journal_service()

    try:
        trade = await service.create_trade(
            ticker=request.ticker.upper(),
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            position_size=request.position_size,
            status=request.status,
            setup_type=request.setup_type,
            trade_thesis=request.trade_thesis,
            market_regime=request.market_regime,
            market_bias=request.market_bias,
            timeframe=request.timeframe,
            confluence_factors=request.confluence_factors,
        )
        return TradeResponse.from_entity(trade)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/trades", response_model=List[TradeResponse])
async def list_trades(
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    ticker: Optional[str] = Query(None, description="Filtrer par ticker"),
    limit: int = Query(50, ge=1, le=200),
):
    """Liste les trades avec filtres optionnels."""
    service = get_journal_service()
    trades = await service.get_trades(status=status, ticker=ticker, limit=limit)
    return [TradeResponse.from_entity(t) for t in trades]


@router.get("/trades/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str):
    """Récupère les détails d'un trade."""
    service = get_journal_service()
    trade = await service.get_trade(trade_id)

    if trade is None:
        raise HTTPException(status_code=404, detail="Trade non trouvé")

    return TradeResponse.from_entity(trade)


@router.put("/trades/{trade_id}", response_model=TradeResponse)
async def update_trade(trade_id: str, request: UpdateTradeRequest):
    """Met à jour un trade (stop loss, take profit, position size)."""
    service = get_journal_service()

    trade = await service.update_trade(
        trade_id=trade_id,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        position_size=request.position_size,
    )

    if trade is None:
        raise HTTPException(status_code=404, detail="Trade non trouvé")

    return TradeResponse.from_entity(trade)


@router.post("/trades/{trade_id}/activate", response_model=TradeResponse)
async def activate_trade(trade_id: str, request: ActivateTradeRequest):
    """
    Active un trade planifié.

    Passe le trade de "planned" à "active" avec le prix d'entrée réel.
    Si aucun prix n'est fourni, utilise le prix d'entrée planifié.
    """
    service = get_journal_service()

    # Utiliser entry_price ou actual_entry_price (alias du frontend)
    actual_price = request.entry_price or request.actual_entry_price

    trade = await service.activate_trade(trade_id, actual_price)

    if trade is None:
        raise HTTPException(
            status_code=400,
            detail="Trade non trouvé ou n'est pas en statut 'planned'"
        )

    return TradeResponse.from_entity(trade)


@router.post("/trades/{trade_id}/close", response_model=TradeResponse)
async def close_trade(trade_id: str, request: CloseTradeRequest):
    """
    Clôture un trade actif.

    Calcule automatiquement le P&L (gross et net) et le R-multiple.
    Envoie une notification Telegram avec le résultat.
    """
    service = get_journal_service()

    trade = await service.close_trade(
        trade_id=trade_id,
        exit_price=request.exit_price,
        fees=request.fees,
    )

    if trade is None:
        raise HTTPException(
            status_code=400,
            detail="Trade non trouvé ou n'est pas en statut 'active'"
        )

    return TradeResponse.from_entity(trade)


@router.post("/trades/{trade_id}/cancel", response_model=TradeResponse)
async def cancel_trade(trade_id: str):
    """Annule un trade (sans exécution)."""
    service = get_journal_service()

    trade = await service.cancel_trade(trade_id)

    if trade is None:
        raise HTTPException(status_code=404, detail="Trade non trouvé")

    return TradeResponse.from_entity(trade)


@router.delete("/trades/{trade_id}", status_code=204)
async def delete_trade(trade_id: str):
    """
    Supprime définitivement un trade et son entrée de journal associée.

    Cette action est irréversible.
    """
    service = get_journal_service()

    deleted = await service.delete_trade(trade_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Trade non trouvé")

    return None


# =============================================================================
# JOURNAL ENTRIES ROUTES
# =============================================================================

@router.post("/entries", response_model=JournalEntryResponse, status_code=201)
async def create_journal_entry(trade_id: str, request: JournalEntryRequest):
    """
    Crée une entrée de journal pour un trade.

    Utilisé pour l'analyse pré-trade: setup, thèse, confluence.
    """
    service = get_journal_service()

    # Vérifier que le trade existe
    trade = await service.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade non trouvé")

    entry = await service.add_journal_entry(
        trade_id=trade_id,
        setup_type=request.setup_type,
        trade_thesis=request.trade_thesis,
        market_regime=request.market_regime,
        market_bias=request.market_bias,
        timeframe=request.timeframe,
        confluence_factors=request.confluence_factors,
    )

    return JournalEntryResponse.from_entity(entry)


@router.get("/entries/{trade_id}", response_model=JournalEntryResponse)
async def get_journal_entry(trade_id: str):
    """Récupère l'entrée de journal pour un trade."""
    service = get_journal_service()

    entry = await service.get_journal_entry(trade_id)

    if entry is None:
        raise HTTPException(status_code=404, detail="Entrée de journal non trouvée")

    return JournalEntryResponse.from_entity(entry)


@router.post("/entries/{trade_id}/post-trade", response_model=JournalEntryResponse)
async def add_post_trade_analysis(trade_id: str, request: PostTradeAnalysisRequest):
    """
    Ajoute l'analyse post-trade à une entrée de journal.

    Utilisé après la clôture d'un trade pour:
    - Évaluer la qualité d'exécution
    - Analyser l'état émotionnel
    - Documenter les erreurs et leçons
    """
    service = get_journal_service()

    try:
        entry = await service.add_post_trade_analysis(
            trade_id=trade_id,
            execution_quality=request.execution_quality,
            emotional_state=request.emotional_state,
            process_compliance=request.process_compliance,
            trade_quality_score=request.trade_quality_score,
            mistakes=request.mistakes,
            what_went_well=request.what_went_well,
            what_to_improve=request.what_to_improve,
            lessons_learned=request.lessons_learned,
        )

        if entry is None:
            raise HTTPException(status_code=404, detail="Entrée de journal non trouvée")

        return JournalEntryResponse.from_entity(entry)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# STATISTICS ROUTES
# =============================================================================

@router.get("/stats")
async def get_stats():
    """
    Retourne les statistiques globales de trading.

    Inclut: nombre de trades, win rate, P&L total, profit factor, etc.
    """
    service = get_journal_service()
    return await service.get_stats()


@router.get("/stats/monthly")
async def get_monthly_stats(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    """Retourne les statistiques pour un mois donné."""
    service = get_journal_service()
    return await service.get_monthly_stats(year, month)


@router.get("/stats/by-setup")
async def get_stats_by_setup():
    """
    Retourne les statistiques par type de setup.

    Permet d'identifier les setups les plus rentables.
    """
    service = get_journal_service()
    return await service.get_stats_by_setup()


@router.get("/stats/emotional")
async def get_emotional_stats():
    """
    Retourne les statistiques par état émotionnel.

    Permet d'identifier l'impact des émotions sur les performances.
    """
    service = get_journal_service()
    return await service.get_emotional_stats()


@router.get("/stats/mistakes")
async def get_common_mistakes():
    """Retourne les erreurs les plus fréquentes."""
    service = get_journal_service()
    return await service.get_common_mistakes()


@router.get("/stats/lessons")
async def get_recent_lessons(limit: int = Query(10, ge=1, le=50)):
    """Retourne les dernières leçons apprises."""
    service = get_journal_service()
    return await service.get_recent_lessons(limit)


@router.get("/dashboard")
async def get_dashboard():
    """
    Retourne un dashboard complet du journal.

    Inclut les stats, trades actifs, récents, erreurs et leçons.
    """
    service = get_journal_service()
    return await service.get_dashboard()
