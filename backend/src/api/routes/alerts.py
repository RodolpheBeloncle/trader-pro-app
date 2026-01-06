"""
Routes API pour la gestion des alertes de prix.

Endpoints:
- POST /alerts           - Créer une alerte
- GET /alerts            - Lister les alertes
- GET /alerts/{id}       - Détails d'une alerte
- PUT /alerts/{id}       - Modifier une alerte
- DELETE /alerts/{id}    - Supprimer une alerte
- POST /alerts/{id}/test - Tester la notification
- POST /alerts/check     - Vérifier toutes les alertes
- GET /alerts/stats      - Statistiques des alertes
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.services.alert_service import AlertService
from src.infrastructure.database.repositories.alert_repository import Alert, AlertType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CreateAlertRequest(BaseModel):
    """Requête de création d'alerte."""
    ticker: str = Field(..., description="Symbole du ticker", min_length=1, max_length=10)
    alert_type: str = Field(..., description="Type d'alerte: price_above, price_below, percent_change")
    target_value: float = Field(..., description="Valeur cible (prix ou pourcentage)")
    notes: Optional[str] = Field(None, description="Notes personnelles", max_length=500)


class UpdateAlertRequest(BaseModel):
    """Requête de modification d'alerte."""
    target_value: Optional[float] = Field(None, description="Nouvelle valeur cible")
    notes: Optional[str] = Field(None, description="Nouvelles notes")
    is_active: Optional[bool] = Field(None, description="Activer/désactiver")


class AlertResponse(BaseModel):
    """Réponse avec une alerte."""
    id: str
    ticker: str
    alert_type: str
    target_value: float
    current_value: Optional[float]
    is_active: bool
    is_triggered: bool
    triggered_at: Optional[str]
    notification_sent: bool
    notes: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, alert: Alert) -> "AlertResponse":
        alert_type_str = alert.alert_type.value if hasattr(alert.alert_type, 'value') else str(alert.alert_type)
        return cls(
            id=alert.id,
            ticker=alert.ticker,
            alert_type=alert_type_str,
            target_value=alert.target_value,
            current_value=alert.current_value,
            is_active=alert.is_active,
            is_triggered=alert.is_triggered,
            triggered_at=alert.triggered_at,
            notification_sent=alert.notification_sent,
            notes=alert.notes,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )


class AlertStatsResponse(BaseModel):
    """Statistiques des alertes."""
    total: int
    active: int
    triggered: int
    inactive: int


class CheckAlertsResponse(BaseModel):
    """Résultat de la vérification des alertes."""
    checked: int
    triggered: int
    errors: Optional[List[str]]


# =============================================================================
# SERVICE
# =============================================================================

def get_alert_service() -> AlertService:
    """Factory pour le service d'alertes."""
    return AlertService()


# =============================================================================
# ROUTES
# =============================================================================

@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(request: CreateAlertRequest):
    """
    Crée une nouvelle alerte de prix.

    L'alerte sera vérifiée périodiquement et une notification Telegram
    sera envoyée lorsque la condition sera remplie.

    Types d'alertes:
    - **price_above**: Se déclenche quand le prix dépasse la valeur cible
    - **price_below**: Se déclenche quand le prix descend sous la valeur cible
    - **percent_change**: Se déclenche lors d'une variation en % (+ ou -)
    """
    service = get_alert_service()

    try:
        alert = await service.create_alert(
            ticker=request.ticker.upper(),
            alert_type=request.alert_type,
            target_value=request.target_value,
            notes=request.notes,
        )
        return AlertResponse.from_entity(alert)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création de l'alerte")


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    active_only: bool = Query(False, description="Uniquement les alertes actives"),
    ticker: Optional[str] = Query(None, description="Filtrer par ticker"),
):
    """
    Liste les alertes.

    Paramètres optionnels:
    - **active_only**: Ne retourne que les alertes actives non déclenchées
    - **ticker**: Filtre par symbole de ticker
    """
    service = get_alert_service()
    alerts = await service.get_all_alerts(active_only=active_only, ticker=ticker)
    return [AlertResponse.from_entity(a) for a in alerts]


@router.get("/stats", response_model=AlertStatsResponse)
async def get_alert_stats():
    """
    Retourne les statistiques des alertes.

    Inclut le nombre total, actives, déclenchées et inactives.
    """
    service = get_alert_service()
    stats = await service.get_stats()
    return AlertStatsResponse(**stats)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str):
    """
    Récupère les détails d'une alerte.
    """
    service = get_alert_service()
    alert = await service.get_alert(alert_id)

    if alert is None:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")

    return AlertResponse.from_entity(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, request: UpdateAlertRequest):
    """
    Met à jour une alerte existante.

    Permet de modifier la valeur cible, les notes ou l'état actif.
    """
    service = get_alert_service()

    alert = await service.update_alert(
        alert_id=alert_id,
        target_value=request.target_value,
        notes=request.notes,
        is_active=request.is_active,
    )

    if alert is None:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")

    return AlertResponse.from_entity(alert)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: str):
    """
    Supprime une alerte.
    """
    service = get_alert_service()
    deleted = await service.delete_alert(alert_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")


@router.post("/{alert_id}/test")
async def test_alert_notification(alert_id: str):
    """
    Envoie une notification de test pour une alerte.

    Utile pour vérifier que Telegram est bien configuré.
    La notification indique clairement qu'il s'agit d'un test.
    """
    service = get_alert_service()

    alert = await service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")

    success = await service.test_notification(alert_id)

    if not success:
        raise HTTPException(
            status_code=503,
            detail="Échec de l'envoi. Vérifiez la configuration Telegram."
        )

    return {"message": "Notification de test envoyée avec succès"}


@router.post("/check", response_model=CheckAlertsResponse)
async def check_all_alerts():
    """
    Vérifie toutes les alertes actives contre les prix actuels.

    Cette route est appelée automatiquement par le job de fond,
    mais peut être déclenchée manuellement.

    Retourne le nombre d'alertes vérifiées et déclenchées.
    """
    service = get_alert_service()
    result = await service.check_all_alerts()
    return CheckAlertsResponse(**result)


@router.post("/retry-notifications")
async def retry_failed_notifications():
    """
    Réessaie d'envoyer les notifications échouées.

    Concerne les alertes déclenchées mais dont la notification
    n'a pas pu être envoyée.
    """
    service = get_alert_service()
    count = await service.retry_failed_notifications()

    return {"message": f"{count} notification(s) envoyée(s) avec succès"}
