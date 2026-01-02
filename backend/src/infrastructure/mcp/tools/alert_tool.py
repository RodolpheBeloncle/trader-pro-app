"""
Outils MCP pour la gestion des alertes de prix.

Ces outils permettent à Claude Desktop de:
- Créer des alertes de prix
- Lister les alertes actives
- Supprimer des alertes
- Vérifier manuellement les alertes
"""

import json
import logging
import asyncio
from typing import Any, Dict

from src.application.services.alert_service import AlertService

logger = logging.getLogger(__name__)


async def create_alert_tool(
    ticker: str,
    alert_type: str,
    target_value: float,
    notes: str = ""
) -> str:
    """
    Crée une alerte de prix.

    Args:
        ticker: Symbole du ticker (ex: AAPL)
        alert_type: Type d'alerte (price_above, price_below, percent_change)
        target_value: Valeur cible (prix ou pourcentage)
        notes: Notes personnelles

    Returns:
        JSON avec l'alerte créée
    """
    try:
        service = AlertService()
        alert = await service.create_alert(
            ticker=ticker.upper(),
            alert_type=alert_type,
            target_value=target_value,
            notes=notes if notes else None,
        )

        result = {
            "success": True,
            "alert": {
                "id": alert.id,
                "ticker": alert.ticker,
                "alert_type": alert.alert_type.value,
                "target_value": alert.target_value,
                "is_active": alert.is_active,
                "created_at": alert.created_at,
            },
            "message": f"Alerte créée pour {ticker}: {alert_type} à {target_value}"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error creating alert: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erreur lors de la création de l'alerte: {str(e)}"
        }, ensure_ascii=False)


async def list_alerts_tool(
    active_only: bool = True,
    ticker: str = ""
) -> str:
    """
    Liste les alertes.

    Args:
        active_only: Uniquement les alertes actives
        ticker: Filtrer par ticker (optionnel)

    Returns:
        JSON avec la liste des alertes
    """
    try:
        service = AlertService()
        alerts = await service.get_all_alerts(
            active_only=active_only,
            ticker=ticker if ticker else None,
        )

        result = {
            "success": True,
            "count": len(alerts),
            "alerts": [
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "alert_type": a.alert_type.value,
                    "target_value": a.target_value,
                    "is_active": a.is_active,
                    "is_triggered": a.is_triggered,
                    "triggered_at": a.triggered_at,
                    "notes": a.notes,
                    "created_at": a.created_at,
                }
                for a in alerts
            ]
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error listing alerts: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def delete_alert_tool(alert_id: str) -> str:
    """
    Supprime une alerte.

    Args:
        alert_id: ID de l'alerte à supprimer

    Returns:
        JSON avec le résultat
    """
    try:
        service = AlertService()
        deleted = await service.delete_alert(alert_id)

        if deleted:
            return json.dumps({
                "success": True,
                "message": f"Alerte {alert_id} supprimée"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": "Alerte non trouvée"
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error deleting alert: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def check_alerts_tool() -> str:
    """
    Vérifie toutes les alertes actives contre les prix actuels.

    Returns:
        JSON avec le résultat de la vérification
    """
    try:
        service = AlertService()
        result = await service.check_all_alerts()

        return json.dumps({
            "success": True,
            "checked": result["checked"],
            "triggered": result["triggered"],
            "message": f"{result['checked']} alertes vérifiées, {result['triggered']} déclenchées"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error checking alerts: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_alerts_stats_tool() -> str:
    """
    Retourne les statistiques des alertes.

    Returns:
        JSON avec les statistiques
    """
    try:
        service = AlertService()
        stats = await service.get_stats()

        return json.dumps({
            "success": True,
            "stats": stats
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error getting alert stats: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)
