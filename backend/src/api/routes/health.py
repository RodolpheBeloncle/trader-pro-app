"""
Routes de santé et diagnostic.

Endpoints:
- GET /api/health - Statut de l'API
- GET /api/health/ready - Prêt à servir des requêtes
"""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Réponse de santé."""

    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


class ReadyResponse(BaseModel):
    """Réponse de disponibilité."""

    ready: bool
    message: str


# Version de l'application
APP_VERSION = "2.0.0"


@router.get(
    "",
    response_model=HealthResponse,
)
async def health_check():
    """
    Vérifie l'état de santé de l'API.

    Retourne toujours 200 si l'API fonctionne.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version=APP_VERSION,
        services={
            "api": "up",
            "database": "not_configured",  # Pas de DB pour l'instant
        },
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
)
async def readiness_check():
    """
    Vérifie si l'API est prête à recevoir des requêtes.

    Utilisé par Kubernetes/Docker pour les health probes.
    """
    # Vérifier que les dépendances critiques sont disponibles
    # Pour l'instant, on retourne toujours ready
    return ReadyResponse(
        ready=True,
        message="API ready to serve requests",
    )


@router.get("/live")
async def liveness_check():
    """
    Vérifie si l'API est vivante (probe liveness).

    Simple endpoint qui retourne 200 si le serveur répond.
    """
    return {"status": "alive"}
