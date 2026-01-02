"""
Service de gestion des alertes de prix.

Ce service orchestre:
- La création et modification des alertes
- La vérification des prix contre les alertes actives
- L'envoi des notifications Telegram
- Le nettoyage des alertes déclenchées

UTILISATION:
    from src.application.services.alert_service import AlertService

    service = AlertService()
    await service.create_alert("AAPL", "price_above", 200.0)
    await service.check_all_alerts()
"""

import logging
from typing import Optional, List, Dict, Any

from src.infrastructure.database.repositories.alert_repository import (
    AlertRepository,
    Alert,
    AlertType,
)
from src.infrastructure.notifications.telegram_service import get_telegram_service
from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider

logger = logging.getLogger(__name__)


class AlertService:
    """
    Service métier pour les alertes de prix.

    Coordonne les repositories et les services d'infrastructure
    pour gérer le cycle de vie complet des alertes.
    """

    def __init__(
        self,
        alert_repo: Optional[AlertRepository] = None,
        price_provider: Optional[YahooFinanceProvider] = None,
    ):
        """
        Initialise le service.

        Args:
            alert_repo: Repository des alertes. Par défaut: nouvelle instance.
            price_provider: Provider de prix. Par défaut: Yahoo Finance.
        """
        self._alert_repo = alert_repo or AlertRepository()
        self._price_provider = price_provider or YahooFinanceProvider()
        self._telegram = get_telegram_service()

    async def create_alert(
        self,
        ticker: str,
        alert_type: str,
        target_value: float,
        notes: Optional[str] = None,
    ) -> Alert:
        """
        Crée une nouvelle alerte de prix.

        Args:
            ticker: Symbole du ticker (ex: AAPL)
            alert_type: Type d'alerte (price_above, price_below, percent_change)
            target_value: Valeur cible (prix ou pourcentage)
            notes: Notes personnelles

        Returns:
            Alert créée

        Raises:
            ValueError: Si le type d'alerte est invalide
        """
        # Valider le type
        try:
            alert_type_enum = AlertType(alert_type)
        except ValueError:
            raise ValueError(f"Type d'alerte invalide: {alert_type}")

        # Récupérer le prix actuel pour les alertes de variation
        current_value = None
        if alert_type_enum == AlertType.PERCENT_CHANGE:
            try:
                quote = await self._price_provider.get_current_quote(ticker)
                current_value = quote.price
            except Exception as e:
                logger.warning(f"Impossible de récupérer le prix pour {ticker}: {e}")

        # Créer l'alerte
        alert = await self._alert_repo.create(
            ticker=ticker,
            alert_type=alert_type_enum,
            target_value=target_value,
            current_value=current_value,
            notes=notes,
        )

        logger.info(f"Alerte créée: {ticker} {alert_type} {target_value}")
        return alert

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Récupère une alerte par son ID.

        Args:
            alert_id: Identifiant de l'alerte

        Returns:
            Alert ou None si non trouvée
        """
        return await self._alert_repo.get_by_id(alert_id)

    async def get_all_alerts(
        self,
        active_only: bool = False,
        ticker: Optional[str] = None,
    ) -> List[Alert]:
        """
        Récupère les alertes.

        Args:
            active_only: Uniquement les alertes actives non déclenchées
            ticker: Filtrer par ticker

        Returns:
            Liste des alertes
        """
        if ticker:
            alerts = await self._alert_repo.get_by_ticker(ticker)
            if active_only:
                alerts = [a for a in alerts if a.is_active and not a.is_triggered]
            return alerts

        if active_only:
            return await self._alert_repo.get_active()

        return await self._alert_repo.get_all()

    async def update_alert(
        self,
        alert_id: str,
        target_value: Optional[float] = None,
        notes: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Alert]:
        """
        Met à jour une alerte.

        Args:
            alert_id: ID de l'alerte
            target_value: Nouvelle valeur cible
            notes: Nouvelles notes
            is_active: Activer/désactiver

        Returns:
            Alert mise à jour ou None
        """
        alert = await self._alert_repo.get_by_id(alert_id)
        if alert is None:
            return None

        if target_value is not None:
            alert.target_value = target_value
        if notes is not None:
            alert.notes = notes
        if is_active is not None:
            alert.is_active = is_active

        return await self._alert_repo.update(alert)

    async def delete_alert(self, alert_id: str) -> bool:
        """
        Supprime une alerte.

        Args:
            alert_id: ID de l'alerte

        Returns:
            True si supprimée
        """
        return await self._alert_repo.delete(alert_id)

    async def deactivate_alert(self, alert_id: str) -> None:
        """
        Désactive une alerte sans la supprimer.

        Args:
            alert_id: ID de l'alerte
        """
        await self._alert_repo.deactivate(alert_id)

    async def check_alert(self, alert: Alert) -> bool:
        """
        Vérifie si une alerte doit être déclenchée.

        Args:
            alert: Alerte à vérifier

        Returns:
            True si l'alerte a été déclenchée
        """
        if not alert.is_active or alert.is_triggered:
            return False

        try:
            # Récupérer le prix actuel
            quote = await self._price_provider.get_current_quote(alert.ticker)
            current_price = quote.price

            # Vérifier si l'alerte doit se déclencher
            if alert.should_trigger(current_price):
                # Marquer comme déclenchée
                await self._alert_repo.mark_triggered(alert.id)

                # Envoyer la notification
                sent = await self._telegram.send_alert(
                    ticker=alert.ticker,
                    alert_type=alert.alert_type.value,
                    current_price=current_price,
                    target_value=alert.target_value,
                    notes=alert.notes,
                )

                if sent:
                    await self._alert_repo.mark_notification_sent(alert.id)
                    logger.info(f"Alerte déclenchée et notifiée: {alert.ticker}")
                else:
                    logger.warning(f"Alerte déclenchée mais notification échouée: {alert.ticker}")

                return True

        except Exception as e:
            logger.error(f"Erreur vérification alerte {alert.ticker}: {e}")

        return False

    async def check_all_alerts(self) -> Dict[str, Any]:
        """
        Vérifie toutes les alertes actives.

        Returns:
            Statistiques de vérification
        """
        active_alerts = await self._alert_repo.get_active()

        if not active_alerts:
            return {"checked": 0, "triggered": 0}

        triggered_count = 0
        errors = []

        for alert in active_alerts:
            try:
                if await self.check_alert(alert):
                    triggered_count += 1
            except Exception as e:
                errors.append(f"{alert.ticker}: {str(e)}")

        logger.info(f"Vérification alertes: {len(active_alerts)} vérifiées, {triggered_count} déclenchées")

        return {
            "checked": len(active_alerts),
            "triggered": triggered_count,
            "errors": errors if errors else None,
        }

    async def retry_failed_notifications(self) -> int:
        """
        Réessaie d'envoyer les notifications échouées.

        Returns:
            Nombre de notifications réussies
        """
        pending = await self._alert_repo.get_triggered_not_sent()
        success_count = 0

        for alert in pending:
            try:
                # Récupérer le prix actuel pour le message
                quote = await self._price_provider.get_current_quote(alert.ticker)

                sent = await self._telegram.send_alert(
                    ticker=alert.ticker,
                    alert_type=alert.alert_type.value,
                    current_price=quote.price,
                    target_value=alert.target_value,
                    notes=alert.notes,
                )

                if sent:
                    await self._alert_repo.mark_notification_sent(alert.id)
                    success_count += 1

            except Exception as e:
                logger.error(f"Échec notification retry {alert.ticker}: {e}")

        return success_count

    async def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques des alertes.

        Returns:
            Dictionnaire de statistiques
        """
        return await self._alert_repo.get_stats()

    async def test_notification(self, alert_id: str) -> bool:
        """
        Envoie une notification de test pour une alerte.

        Args:
            alert_id: ID de l'alerte

        Returns:
            True si la notification a été envoyée
        """
        alert = await self._alert_repo.get_by_id(alert_id)
        if alert is None:
            return False

        try:
            quote = await self._price_provider.get_current_quote(alert.ticker)
            current_price = quote.price
        except Exception:
            current_price = 0.0

        return await self._telegram.send_message(
            f"🧪 <b>TEST ALERTE</b>\n\n"
            f"Ticker: {alert.ticker}\n"
            f"Type: {alert.alert_type.value}\n"
            f"Cible: {alert.target_value}\n"
            f"Prix actuel: {current_price:.2f}\n\n"
            f"<i>Ceci est un test, l'alerte n'a pas été déclenchée.</i>"
        )
