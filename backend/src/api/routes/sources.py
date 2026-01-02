"""
Routes API pour la gestion des sources de données.

Endpoints:
- GET /api/sources - Liste les sources disponibles
- GET /api/sources/status - Statut de santé des sources
- POST /api/sources/switch - Changer la source par défaut
- GET /api/sources/stats - Statistiques du streamer
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


# =============================================================================
# SCHEMAS
# =============================================================================

class SourceInfo(BaseModel):
    """Information sur une source de données."""
    name: str
    is_realtime: bool
    is_available: bool
    is_default: bool
    description: str


class SourcesListResponse(BaseModel):
    """Liste des sources disponibles."""
    sources: List[SourceInfo]
    default_source: str
    active_tickers: int


class SourceHealthResponse(BaseModel):
    """Statut de santé d'une source."""
    name: str
    status: str  # "healthy", "degraded", "unavailable"
    last_check: Optional[str]
    error_count: int
    success_rate: float


class SourcesHealthResponse(BaseModel):
    """Santé de toutes les sources."""
    sources: List[SourceHealthResponse]
    overall_status: str


class SwitchSourceRequest(BaseModel):
    """Requête pour changer de source."""
    source: str


class SwitchSourceResponse(BaseModel):
    """Réponse au changement de source."""
    success: bool
    previous_source: str
    new_source: str
    message: str


class StreamerStatsResponse(BaseModel):
    """Statistiques du streamer de prix."""
    running: bool
    sources: List[str]
    default_source: Optional[str]
    subscribed_count: int
    priority_tickers: List[str]
    poll_interval: float
    priority_interval: float


# =============================================================================
# STATE - Compteurs d'erreurs pour le health check
# =============================================================================

_source_errors: dict = {}
_source_successes: dict = {}
_last_health_check: dict = {}


def record_source_success(source_name: str) -> None:
    """Enregistre un succès pour une source."""
    if source_name not in _source_successes:
        _source_successes[source_name] = 0
    _source_successes[source_name] += 1
    _last_health_check[source_name] = datetime.now().isoformat()


def record_source_error(source_name: str) -> None:
    """Enregistre une erreur pour une source."""
    if source_name not in _source_errors:
        _source_errors[source_name] = 0
    _source_errors[source_name] += 1
    _last_health_check[source_name] = datetime.now().isoformat()


def get_source_health(source_name: str) -> SourceHealthResponse:
    """Calcule la santé d'une source."""
    errors = _source_errors.get(source_name, 0)
    successes = _source_successes.get(source_name, 0)
    total = errors + successes

    if total == 0:
        success_rate = 1.0
        status = "healthy"
    else:
        success_rate = successes / total
        if success_rate >= 0.95:
            status = "healthy"
        elif success_rate >= 0.7:
            status = "degraded"
        else:
            status = "unavailable"

    return SourceHealthResponse(
        name=source_name,
        status=status,
        last_check=_last_health_check.get(source_name),
        error_count=errors,
        success_rate=round(success_rate * 100, 1)
    )


# =============================================================================
# ROUTES
# =============================================================================

@router.get("", response_model=SourcesListResponse)
async def list_sources():
    """
    Liste toutes les sources de données disponibles.
    """
    from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer

    try:
        streamer = get_hybrid_streamer()
        sources_list = []

        # Source descriptions
        descriptions = {
            "yahoo": "Yahoo Finance (polling toutes les 10s, données différées)",
            "saxo": "Saxo Bank WebSocket (temps réel, nécessite authentification)",
        }

        for source_name, source in streamer._sources.items():
            is_available = await source.is_available()
            is_default = streamer._default_source and streamer._default_source.source_name == source_name

            sources_list.append(SourceInfo(
                name=source_name,
                is_realtime=source.is_realtime,
                is_available=is_available,
                is_default=is_default,
                description=descriptions.get(source_name, f"Source de prix {source_name}")
            ))

        return SourcesListResponse(
            sources=sources_list,
            default_source=streamer._default_source.source_name if streamer._default_source else "none",
            active_tickers=len(streamer.manager.active_tickers)
        )

    except Exception as e:
        logger.exception(f"Error listing sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SourcesHealthResponse)
async def get_sources_health():
    """
    Retourne le statut de santé de toutes les sources.
    """
    from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer

    try:
        streamer = get_hybrid_streamer()
        health_list = []

        for source_name in streamer._sources.keys():
            health = get_source_health(source_name)
            health_list.append(health)

        # Calculer le statut global
        statuses = [h.status for h in health_list]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "unavailable" for s in statuses):
            overall = "degraded"
        else:
            overall = "degraded" if any(s == "degraded" for s in statuses) else "healthy"

        return SourcesHealthResponse(
            sources=health_list,
            overall_status=overall
        )

    except Exception as e:
        logger.exception(f"Error getting sources health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch", response_model=SwitchSourceResponse)
async def switch_source(request: SwitchSourceRequest):
    """
    Change la source de données par défaut.
    """
    from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer

    try:
        streamer = get_hybrid_streamer()

        # Vérifier que la source existe
        if request.source not in streamer._sources:
            available = list(streamer._sources.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Source '{request.source}' non disponible. Sources disponibles: {available}"
            )

        # Récupérer l'ancienne source
        previous = streamer._default_source.source_name if streamer._default_source else "none"

        # Vérifier que la nouvelle source est disponible
        new_source = streamer._sources[request.source]
        if not await new_source.is_available():
            raise HTTPException(
                status_code=400,
                detail=f"Source '{request.source}' n'est pas disponible actuellement"
            )

        # Changer la source par défaut
        streamer._default_source = new_source

        logger.info(f"Switched default source from {previous} to {request.source}")

        return SwitchSourceResponse(
            success=True,
            previous_source=previous,
            new_source=request.source,
            message=f"Source changée de {previous} à {request.source}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error switching source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StreamerStatsResponse)
async def get_streamer_stats():
    """
    Retourne les statistiques du streamer de prix.
    """
    from src.infrastructure.websocket.hybrid_streamer import get_hybrid_streamer

    try:
        streamer = get_hybrid_streamer()
        stats = streamer.get_stats()

        return StreamerStatsResponse(**stats)

    except Exception as e:
        logger.exception(f"Error getting streamer stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-health")
async def reset_health_counters():
    """
    Réinitialise les compteurs de santé des sources.
    """
    global _source_errors, _source_successes, _last_health_check

    _source_errors = {}
    _source_successes = {}
    _last_health_check = {}

    return {"success": True, "message": "Compteurs de santé réinitialisés"}
