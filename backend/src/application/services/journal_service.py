"""
Service de gestion du journal de trading.

Ce service orchestre:
- La création et gestion des trades
- Les entrées de journal (analyse pré/post trade)
- Le calcul des statistiques P&L
- Les notifications Telegram pour les trades

UTILISATION:
    from src.application.services.journal_service import JournalService

    service = JournalService()
    trade = await service.create_trade("AAPL", "long", entry_price=150.0)
    await service.close_trade(trade.id, exit_price=160.0)
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from src.infrastructure.database.repositories.trade_repository import (
    TradeRepository,
    Trade,
    TradeDirection,
    TradeStatus,
)
from src.infrastructure.database.repositories.journal_repository import (
    JournalRepository,
    JournalEntry,
    ExecutionQuality,
    EmotionalState,
    ProcessCompliance,
)
from src.infrastructure.notifications.telegram_service import get_telegram_service

logger = logging.getLogger(__name__)


class JournalService:
    """
    Service métier pour le journal de trading.

    Coordonne les repositories et les services d'infrastructure
    pour gérer le cycle de vie complet des trades et du journal.
    """

    def __init__(
        self,
        trade_repo: Optional[TradeRepository] = None,
        journal_repo: Optional[JournalRepository] = None,
    ):
        """
        Initialise le service.

        Args:
            trade_repo: Repository des trades.
            journal_repo: Repository des entrées de journal.
        """
        self._trade_repo = trade_repo or TradeRepository()
        self._journal_repo = journal_repo or JournalRepository()
        self._telegram = get_telegram_service()

    # =========================================================================
    # TRADES
    # =========================================================================

    async def create_trade(
        self,
        ticker: str,
        direction: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[int] = None,
        status: str = "planned",
        # Journal entry
        setup_type: Optional[str] = None,
        trade_thesis: Optional[str] = None,
        market_regime: Optional[str] = None,
        market_bias: Optional[str] = None,
        timeframe: Optional[str] = None,
        confluence_factors: Optional[List[str]] = None,
        notify: bool = True,
    ) -> Trade:
        """
        Crée un nouveau trade avec entrée de journal optionnelle.

        Args:
            ticker: Symbole du ticker
            direction: Direction (long/short)
            entry_price: Prix d'entrée
            stop_loss: Stop loss
            take_profit: Take profit
            position_size: Taille de position
            status: Statut initial (planned/active)
            setup_type: Type de setup
            trade_thesis: Thèse du trade
            market_regime: Régime de marché
            market_bias: Biais de marché
            timeframe: Timeframe
            confluence_factors: Facteurs de confluence
            notify: Envoyer notification Telegram

        Returns:
            Trade créé
        """
        # Valider la direction
        try:
            direction_enum = TradeDirection(direction)
        except ValueError:
            raise ValueError(f"Direction invalide: {direction}")

        # Valider le statut
        try:
            status_enum = TradeStatus(status)
        except ValueError:
            raise ValueError(f"Statut invalide: {status}")

        # Créer le trade
        trade = await self._trade_repo.create(
            ticker=ticker,
            direction=direction_enum,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            status=status_enum,
        )

        # Créer l'entrée de journal si des infos sont fournies
        if setup_type or trade_thesis:
            await self._journal_repo.create(
                trade_id=trade.id,
                setup_type=setup_type,
                trade_thesis=trade_thesis,
                market_regime=market_regime,
                market_bias=market_bias,
                timeframe=timeframe,
                confluence_factors=confluence_factors,
            )

        # Notification si trade actif
        if notify and status_enum == TradeStatus.ACTIVE and entry_price:
            await self._telegram.send_trade_opened(
                ticker=ticker,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=position_size,
            )

        logger.info(f"Trade créé: {ticker} {direction} ({status})")
        return trade

    async def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Récupère un trade par son ID."""
        return await self._trade_repo.get_by_id(trade_id)

    async def get_trades(
        self,
        status: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[Trade]:
        """
        Récupère les trades avec filtres optionnels.

        Args:
            status: Filtrer par statut
            ticker: Filtrer par ticker
            limit: Nombre maximum de trades

        Returns:
            Liste des trades
        """
        if status:
            try:
                status_enum = TradeStatus(status)
                return await self._trade_repo.get_by_status(status_enum)
            except ValueError:
                return []

        if ticker:
            return await self._trade_repo.get_by_ticker(ticker)

        return await self._trade_repo.get_all(limit=limit)

    async def activate_trade(
        self,
        trade_id: str,
        entry_price: float,
        notify: bool = True,
    ) -> Optional[Trade]:
        """
        Active un trade planifié.

        Args:
            trade_id: ID du trade
            entry_price: Prix d'entrée réel
            notify: Envoyer notification Telegram

        Returns:
            Trade activé ou None
        """
        trade = await self._trade_repo.activate(trade_id, entry_price)

        if trade and notify:
            # Utiliser le prix du trade (qui a été mis à jour par activate)
            await self._telegram.send_trade_opened(
                ticker=trade.ticker,
                direction=trade.direction.value,
                entry_price=trade.entry_price,  # Utiliser le prix du trade, pas le paramètre
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
                position_size=trade.position_size,
            )

        return trade

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        fees: float = 0.0,
        notify: bool = True,
    ) -> Optional[Trade]:
        """
        Clôture un trade avec calcul du P&L.

        Args:
            trade_id: ID du trade
            exit_price: Prix de sortie
            fees: Frais de transaction
            notify: Envoyer notification Telegram

        Returns:
            Trade clôturé ou None
        """
        trade = await self._trade_repo.close(trade_id, exit_price, fees)

        if trade and notify:
            pnl_percent = 0
            if trade.entry_price and trade.entry_price > 0:
                pnl_percent = (trade.net_pnl / (trade.entry_price * (trade.position_size or 1))) * 100

            await self._telegram.send_trade_closed(
                ticker=trade.ticker,
                direction=trade.direction.value,
                entry_price=trade.entry_price or 0,
                exit_price=exit_price,
                pnl=trade.net_pnl or 0,
                pnl_percent=pnl_percent,
            )

        return trade

    async def cancel_trade(self, trade_id: str) -> Optional[Trade]:
        """Annule un trade."""
        return await self._trade_repo.cancel(trade_id)

    async def delete_trade(self, trade_id: str) -> bool:
        """
        Supprime un trade définitivement.

        Args:
            trade_id: ID du trade à supprimer

        Returns:
            True si supprimé, False sinon
        """
        # Supprimer aussi l'entrée de journal associée si elle existe
        await self._journal_repo.delete_by_trade_id(trade_id)
        return await self._trade_repo.delete(trade_id)

    async def update_trade(
        self,
        trade_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[int] = None,
    ) -> Optional[Trade]:
        """
        Met à jour un trade.

        Args:
            trade_id: ID du trade
            stop_loss: Nouveau stop loss
            take_profit: Nouveau take profit
            position_size: Nouvelle taille de position

        Returns:
            Trade mis à jour ou None
        """
        trade = await self._trade_repo.get_by_id(trade_id)
        if trade is None:
            return None

        if stop_loss is not None:
            trade.stop_loss = stop_loss
        if take_profit is not None:
            trade.take_profit = take_profit
        if position_size is not None:
            trade.position_size = position_size

        return await self._trade_repo.update(trade)

    # =========================================================================
    # JOURNAL ENTRIES
    # =========================================================================

    async def add_journal_entry(
        self,
        trade_id: str,
        setup_type: Optional[str] = None,
        trade_thesis: Optional[str] = None,
        market_regime: Optional[str] = None,
        market_bias: Optional[str] = None,
        timeframe: Optional[str] = None,
        confluence_factors: Optional[List[str]] = None,
    ) -> JournalEntry:
        """
        Ajoute une entrée de journal (analyse pré-trade).

        Args:
            trade_id: ID du trade associé
            setup_type: Type de setup
            trade_thesis: Thèse du trade
            market_regime: Régime de marché
            market_bias: Biais de marché
            timeframe: Timeframe
            confluence_factors: Facteurs de confluence

        Returns:
            Entrée de journal créée
        """
        return await self._journal_repo.create(
            trade_id=trade_id,
            setup_type=setup_type,
            trade_thesis=trade_thesis,
            market_regime=market_regime,
            market_bias=market_bias,
            timeframe=timeframe,
            confluence_factors=confluence_factors,
        )

    async def get_journal_entry(self, trade_id: str) -> Optional[JournalEntry]:
        """Récupère l'entrée de journal pour un trade."""
        return await self._journal_repo.get_by_trade_id(trade_id)

    async def add_post_trade_analysis(
        self,
        trade_id: str,
        execution_quality: str,
        emotional_state: str,
        process_compliance: str,
        trade_quality_score: int,
        mistakes: Optional[List[str]] = None,
        what_went_well: Optional[List[str]] = None,
        what_to_improve: Optional[List[str]] = None,
        lessons_learned: Optional[str] = None,
    ) -> Optional[JournalEntry]:
        """
        Ajoute l'analyse post-trade à une entrée de journal.

        Args:
            trade_id: ID du trade
            execution_quality: Qualité d'exécution
            emotional_state: État émotionnel
            process_compliance: Respect du processus
            trade_quality_score: Score de qualité (1-10)
            mistakes: Erreurs commises
            what_went_well: Ce qui a bien fonctionné
            what_to_improve: Points d'amélioration
            lessons_learned: Leçons apprises

        Returns:
            Entrée mise à jour ou None
        """
        try:
            exec_q = ExecutionQuality(execution_quality)
            emot_s = EmotionalState(emotional_state)
            proc_c = ProcessCompliance(process_compliance)
        except ValueError as e:
            raise ValueError(f"Valeur invalide: {e}")

        return await self._journal_repo.add_post_trade_analysis(
            trade_id=trade_id,
            execution_quality=exec_q,
            emotional_state=emot_s,
            process_compliance=proc_c,
            trade_quality_score=trade_quality_score,
            mistakes=mistakes,
            what_went_well=what_went_well,
            what_to_improve=what_to_improve,
            lessons_learned=lessons_learned,
        )

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques globales de trading."""
        return await self._trade_repo.get_stats()

    async def get_monthly_stats(self, year: int, month: int) -> Dict[str, Any]:
        """Retourne les statistiques pour un mois donné."""
        return await self._trade_repo.get_monthly_stats(year, month)

    async def get_stats_by_setup(self) -> List[Dict[str, Any]]:
        """Retourne les statistiques par type de setup."""
        return await self._journal_repo.get_stats_by_setup()

    async def get_emotional_stats(self) -> Dict[str, Dict[str, Any]]:
        """Retourne les statistiques par état émotionnel."""
        return await self._journal_repo.get_emotional_stats()

    async def get_common_mistakes(self) -> Dict[str, int]:
        """Retourne les erreurs les plus fréquentes."""
        return await self._journal_repo.get_common_mistakes()

    async def get_recent_lessons(self, limit: int = 10) -> List[str]:
        """Retourne les dernières leçons apprises."""
        return await self._journal_repo.get_lessons(limit)

    async def get_dashboard(self) -> Dict[str, Any]:
        """
        Retourne un dashboard complet du journal.

        Inclut:
        - Statistiques globales
        - Trades actifs
        - Derniers trades clôturés
        - Erreurs fréquentes
        - Leçons récentes
        """
        stats = await self.get_stats()
        active_trades = await self.get_trades(status="active")
        recent_closed = await self._trade_repo.get_by_status(TradeStatus.CLOSED)
        mistakes = await self.get_common_mistakes()
        lessons = await self.get_recent_lessons(5)

        return {
            "stats": stats,
            "active_trades": len(active_trades),
            "active_trades_list": [
                {
                    "id": t.id,
                    "ticker": t.ticker,
                    "direction": t.direction.value,
                    "entry_price": t.entry_price,
                }
                for t in active_trades[:5]
            ],
            "recent_closed": [
                {
                    "id": t.id,
                    "ticker": t.ticker,
                    "direction": t.direction.value,
                    "net_pnl": t.net_pnl,
                    "r_multiple": t.r_multiple,
                }
                for t in recent_closed[:5]
            ],
            "top_mistakes": dict(list(mistakes.items())[:5]),
            "recent_lessons": lessons,
        }
