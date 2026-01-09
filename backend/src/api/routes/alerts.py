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


@router.post("/test-scan")
async def test_technical_scan():
    """
    Execute un scan immediat des alertes techniques.

    Analyse toutes les positions du portefeuille pour detecter
    les signaux RSI, MACD et Bollinger Bands.

    Utile pour:
    - Tester que la configuration fonctionne
    - Voir les signaux actuels sans attendre le scan automatique
    - Verifier que Telegram recoit les notifications
    """
    from src.application.services.alert_config_service import get_alert_config_service
    from src.application.services.technical_alert_service import get_technical_alert_service

    config_service = get_alert_config_service()
    config = config_service.config
    technical_service = get_technical_alert_service()

    # Reset le cache pour forcer la detection des signaux
    technical_service.reset_signal_cache()

    # Scanner le portefeuille
    signals = await technical_service.check_portfolio_signals(
        rsi_enabled=config.rsi_enabled,
        rsi_overbought=config.rsi_overbought,
        rsi_oversold=config.rsi_oversold,
        macd_enabled=config.macd_enabled,
        bollinger_enabled=config.bollinger_enabled,
    )

    # Enregistrer les signaux dans l'historique
    for signal in signals:
        config_service.add_signal(
            ticker=signal.ticker,
            signal_type=signal.signal_type,
            indicator_value=signal.indicator_value,
            price=signal.current_price,
            severity=signal.severity,
        )

    # Envoyer les notifications si configurees
    notifications_sent = 0
    if signals and config.notify_telegram:
        notifications_sent = await technical_service.notify_signals(signals)

    return {
        "success": True,
        "signals_detected": len(signals),
        "notifications_sent": notifications_sent,
        "signals": [
            {
                "ticker": s.ticker,
                "signal_type": s.signal_type,
                "price": s.current_price,
                "indicator_value": round(s.indicator_value, 2),
                "message": s.message,
                "severity": s.severity,
            }
            for s in signals
        ],
        "config": {
            "rsi_enabled": config.rsi_enabled,
            "rsi_overbought": config.rsi_overbought,
            "rsi_oversold": config.rsi_oversold,
            "macd_enabled": config.macd_enabled,
            "bollinger_enabled": config.bollinger_enabled,
            "notify_telegram": config.notify_telegram,
        },
    }


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


# =============================================================================
# TECHNICAL ALERTS CONFIGURATION
# =============================================================================

class TechnicalConfigUpdate(BaseModel):
    """Requête de mise à jour de la configuration technique."""
    enabled: Optional[bool] = None
    scan_interval: Optional[int] = Field(None, ge=10, le=86400)
    rsi_enabled: Optional[bool] = None
    rsi_overbought: Optional[int] = Field(None, ge=50, le=95)
    rsi_oversold: Optional[int] = Field(None, ge=5, le=50)
    macd_enabled: Optional[bool] = None
    bollinger_enabled: Optional[bool] = None
    bollinger_std: Optional[float] = Field(None, ge=1.0, le=4.0)
    support_resistance_enabled: Optional[bool] = None
    notify_telegram: Optional[bool] = None
    notify_only_high_severity: Optional[bool] = None
    cooldown_minutes: Optional[int] = Field(None, ge=5, le=1440)
    trading_hours_only: Optional[bool] = None
    trading_start_hour: Optional[int] = Field(None, ge=0, le=23)
    trading_end_hour: Optional[int] = Field(None, ge=0, le=23)


@router.get("/technical/config")
async def get_technical_config():
    """
    Récupère la configuration des alertes techniques.

    Retourne tous les paramètres de scan automatique du portfolio.
    """
    from src.application.services.alert_config_service import get_alert_config_service

    config_service = get_alert_config_service()
    config = config_service.get_config()

    return {
        "config": config,
        "presets": config_service.get_presets(),
    }


@router.put("/technical/config")
async def update_technical_config(request: TechnicalConfigUpdate):
    """
    Met à jour la configuration des alertes techniques.

    Permet de modifier les seuils, fréquences et options.
    """
    from src.application.services.alert_config_service import get_alert_config_service

    config_service = get_alert_config_service()

    # Filtrer les valeurs None
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(status_code=400, detail="Aucune modification fournie")

    config = config_service.update_config(updates)

    # Mettre à jour le scheduler si l'intervalle a changé
    if "scan_interval" in updates:
        try:
            from src.jobs.scheduler import update_alert_checker_interval
            update_alert_checker_interval(updates["scan_interval"])
        except Exception as e:
            logger.warning(f"Could not update scheduler interval: {e}")

    return {
        "success": True,
        "message": "Configuration mise à jour",
        "config": config.to_dict(),
    }


@router.post("/technical/preset/{preset_name}")
async def apply_technical_preset(preset_name: str):
    """
    Applique un preset de configuration.

    Presets disponibles:
    - conservative: Alertes prudentes, scan 5min
    - moderate: Équilibré, scan 1min
    - aggressive: Alertes fréquentes, scan 30s
    - disabled: Alertes désactivées
    """
    from src.application.services.alert_config_service import get_alert_config_service

    config_service = get_alert_config_service()

    try:
        config = config_service.apply_preset(preset_name)

        # Mettre à jour le scheduler
        try:
            from src.jobs.scheduler import update_alert_checker_interval
            update_alert_checker_interval(config.scan_interval)
        except Exception as e:
            logger.warning(f"Could not update scheduler interval: {e}")

        return {
            "success": True,
            "message": f"Preset '{preset_name}' appliqué",
            "config": config.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/technical/toggle")
async def toggle_technical_alerts():
    """
    Active ou désactive les alertes techniques.

    Bascule l'état actuel.
    """
    from src.application.services.alert_config_service import get_alert_config_service

    config_service = get_alert_config_service()
    new_state = not config_service.is_enabled()
    config_service.set_enabled(new_state)

    return {
        "enabled": new_state,
        "message": f"Alertes techniques {'activées' if new_state else 'désactivées'}",
    }


@router.get("/technical/history")
async def get_technical_history(
    limit: int = Query(50, ge=1, le=500),
    ticker: Optional[str] = Query(None),
):
    """
    Récupère l'historique des signaux techniques détectés.

    Paramètres:
    - limit: Nombre max de signaux (défaut: 50)
    - ticker: Filtrer par ticker (optionnel)
    """
    from src.application.services.alert_config_service import get_alert_config_service

    config_service = get_alert_config_service()
    history = config_service.get_history(limit=limit, ticker=ticker)
    stats = config_service.get_stats()

    return {
        "history": history,
        "stats": stats,
    }


@router.delete("/technical/history")
async def clear_technical_history():
    """Efface l'historique des signaux techniques."""
    from src.application.services.alert_config_service import get_alert_config_service

    config_service = get_alert_config_service()
    config_service.clear_history()

    return {"success": True, "message": "Historique effacé"}
