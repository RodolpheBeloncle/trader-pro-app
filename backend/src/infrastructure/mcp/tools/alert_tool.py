"""
Outils MCP pour la gestion des alertes de prix.

Utilise l'API HTTP du backend Docker pour garantir que Claude Desktop
et l'interface web partagent les mêmes données.

ARCHITECTURE:
    Claude Desktop MCP → HTTP API → Docker Backend → SQLite
    Web Frontend       → HTTP API → Docker Backend → SQLite
"""

import json
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

# URL de base de l'API (backend Docker)
API_BASE_URL = "http://localhost:8000/api"
HTTP_TIMEOUT = 30.0


async def _api_request(
    method: str,
    endpoint: str,
    data: Dict[str, Any] = None,
    params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Effectue une requête HTTP vers l'API backend.
    """
    url = f"{API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        if method.upper() == "GET":
            response = await client.get(url, params=params)
        elif method.upper() == "POST":
            response = await client.post(url, json=data)
        elif method.upper() == "DELETE":
            response = await client.delete(url)
        else:
            raise ValueError(f"Méthode HTTP non supportée: {method}")

        response.raise_for_status()

        # DELETE returns no content
        if response.status_code == 204:
            return {"success": True}

        return response.json()


async def create_alert_tool(
    ticker: str,
    alert_type: str,
    target_value: float,
    notes: str = ""
) -> str:
    """
    Crée une alerte de prix via l'API HTTP.

    Args:
        ticker: Symbole du ticker (ex: AAPL)
        alert_type: Type d'alerte (price_above, price_below, percent_change)
        target_value: Valeur cible (prix ou pourcentage)
        notes: Notes personnelles

    Returns:
        JSON avec l'alerte créée
    """
    try:
        payload = {
            "ticker": ticker.upper(),
            "alert_type": alert_type,
            "target_value": target_value,
        }
        if notes:
            payload["notes"] = notes

        alert = await _api_request("POST", "/alerts", data=payload)

        result = {
            "success": True,
            "alert": {
                "id": alert.get("id"),
                "ticker": alert.get("ticker"),
                "alert_type": alert.get("alert_type"),
                "target_value": alert.get("target_value"),
                "is_active": alert.get("is_active"),
                "created_at": alert.get("created_at"),
            },
            "message": f"Alerte créée pour {ticker}: {alert_type} à {target_value}"
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = "Erreur lors de la création de l'alerte"
        try:
            error_detail = e.response.json().get("detail", error_detail)
        except Exception:
            pass
        return json.dumps({
            "success": False,
            "error": error_detail
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
    Liste les alertes via l'API HTTP.

    Args:
        active_only: Uniquement les alertes actives
        ticker: Filtrer par ticker (optionnel)

    Returns:
        JSON avec la liste des alertes
    """
    try:
        params = {"active_only": active_only}
        if ticker:
            params["ticker"] = ticker

        alerts = await _api_request("GET", "/alerts", params=params)

        result = {
            "success": True,
            "count": len(alerts),
            "alerts": [
                {
                    "id": a.get("id"),
                    "ticker": a.get("ticker"),
                    "alert_type": a.get("alert_type"),
                    "target_value": a.get("target_value"),
                    "is_active": a.get("is_active"),
                    "is_triggered": a.get("is_triggered"),
                    "triggered_at": a.get("triggered_at"),
                    "notes": a.get("notes"),
                    "created_at": a.get("created_at"),
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
    Supprime une alerte via l'API HTTP.

    Args:
        alert_id: ID de l'alerte à supprimer

    Returns:
        JSON avec le résultat
    """
    try:
        await _api_request("DELETE", f"/alerts/{alert_id}")

        return json.dumps({
            "success": True,
            "message": f"Alerte {alert_id} supprimée"
        }, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return json.dumps({
                "success": False,
                "error": "Alerte non trouvée"
            }, ensure_ascii=False)
        return json.dumps({
            "success": False,
            "error": f"Erreur HTTP {e.response.status_code}"
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error deleting alert: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def check_alerts_tool() -> str:
    """
    Vérifie toutes les alertes actives contre les prix actuels via l'API HTTP.

    Returns:
        JSON avec le résultat de la vérification
    """
    try:
        result = await _api_request("POST", "/alerts/check")

        return json.dumps({
            "success": True,
            "checked": result.get("checked", 0),
            "triggered": result.get("triggered", 0),
            "message": f"{result.get('checked', 0)} alertes vérifiées, {result.get('triggered', 0)} déclenchées"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Error checking alerts: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


async def get_alerts_stats_tool() -> str:
    """
    Retourne les statistiques des alertes via l'API HTTP.

    Returns:
        JSON avec les statistiques
    """
    try:
        stats = await _api_request("GET", "/alerts/stats")

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
