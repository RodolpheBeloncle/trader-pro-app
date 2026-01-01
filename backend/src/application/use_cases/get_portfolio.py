"""
Use Case : Récupération du portefeuille broker.

Orchestre la récupération et l'enrichissement du portefeuille:
- Récupération des positions depuis le broker
- Enrichissement avec l'analyse de chaque position
- Calcul des métriques agrégées

ARCHITECTURE:
- Dépend du BrokerService et du StockDataProvider
- Enrichit les positions avec les données d'analyse
- Gère les erreurs d'enrichissement individuelles

UTILISATION:
    use_case = GetPortfolioUseCase(broker_service, yahoo_provider)
    portfolio = await use_case.execute(credentials)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from src.application.interfaces.broker_service import (
    BrokerService,
    BrokerCredentials,
    Portfolio,
    Position,
)
from src.application.interfaces.stock_data_provider import StockDataProvider
from src.application.use_cases.analyze_stock import AnalyzeStockUseCase
from src.config.constants import MAX_CONCURRENT_REQUESTS

logger = logging.getLogger(__name__)


@dataclass
class EnrichedPosition:
    """Position enrichie avec données d'analyse."""

    # Données de base du broker
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
    broker_id: Optional[str]
    uic: Optional[int]

    # Données d'analyse (enrichissement)
    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_1y: Optional[float] = None
    is_resilient: Optional[bool] = None
    volatility: Optional[float] = None
    analysis_error: Optional[str] = None


@dataclass
class EnrichedPortfolio:
    """Portefeuille enrichi avec données d'analyse."""

    positions: List[EnrichedPosition]
    account_key: Optional[str]
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    resilient_count: int
    resilient_percent: float
    updated_at: str


class GetPortfolioUseCase:
    """
    Use Case pour récupérer et enrichir le portefeuille.

    Récupère les positions du broker et les enrichit avec
    les données d'analyse de performance.

    Attributes:
        broker: Service broker pour récupérer les positions
        provider: Fournisseur de données pour l'enrichissement
    """

    def __init__(
        self,
        broker: BrokerService,
        provider: Optional[StockDataProvider] = None,
    ):
        """
        Initialise le use case.

        Args:
            broker: Service broker
            provider: Fournisseur de données (optionnel pour enrichissement)
        """
        self.broker = broker
        self.provider = provider
        if provider:
            self.analyze_use_case = AnalyzeStockUseCase(provider)
        else:
            self.analyze_use_case = None

    async def execute(
        self,
        credentials: BrokerCredentials,
        enrich: bool = True,
    ) -> EnrichedPortfolio:
        """
        Récupère et enrichit le portefeuille.

        Args:
            credentials: Credentials d'authentification broker
            enrich: Si True, enrichit avec les données d'analyse

        Returns:
            Portefeuille enrichi
        """
        logger.info(f"Fetching portfolio from {self.broker.broker_name}")

        # Récupérer le portefeuille du broker
        portfolio = await self.broker.get_portfolio(credentials)

        # Convertir les positions
        enriched_positions: List[EnrichedPosition] = []

        for pos in portfolio.positions:
            enriched_pos = EnrichedPosition(
                symbol=pos.symbol,
                description=pos.description or "",
                quantity=pos.quantity,
                current_price=pos.current_price,
                average_price=pos.average_price,
                market_value=pos.market_value,
                pnl=pos.pnl,
                pnl_percent=pos.pnl_percent,
                currency=pos.currency,
                asset_type=pos.asset_type,
                broker_id=pos.broker_id,
                uic=pos.uic,
            )
            enriched_positions.append(enriched_pos)

        # Enrichir avec les données d'analyse si demandé
        if enrich and self.analyze_use_case and enriched_positions:
            await self._enrich_positions(enriched_positions)

        # Calculer les métriques agrégées
        total_value = sum(p.market_value for p in enriched_positions)
        total_pnl = sum(p.pnl for p in enriched_positions)
        total_cost = sum(
            p.average_price * p.quantity for p in enriched_positions
        )
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        resilient_count = sum(
            1 for p in enriched_positions if p.is_resilient is True
        )
        resilient_percent = (
            resilient_count / len(enriched_positions) * 100
            if enriched_positions
            else 0
        )

        return EnrichedPortfolio(
            positions=enriched_positions,
            account_key=portfolio.account_key,
            total_value=round(total_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_percent=round(total_pnl_percent, 2),
            resilient_count=resilient_count,
            resilient_percent=round(resilient_percent, 2),
            updated_at=datetime.now().isoformat(),
        )

    async def _enrich_positions(
        self,
        positions: List[EnrichedPosition],
    ) -> None:
        """
        Enrichit les positions avec les données d'analyse.

        Modifie les positions en place.

        Args:
            positions: Liste des positions à enrichir
        """
        logger.info(f"Enriching {len(positions)} positions with analysis data")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def enrich_position(pos: EnrichedPosition) -> None:
            """Enrichit une position individuelle."""
            async with semaphore:
                try:
                    # Analyser le symbole
                    result = await self.analyze_use_case.execute(pos.symbol)

                    if result.is_success and result.analysis:
                        analysis = result.analysis
                        pos.perf_3m = analysis.performances.perf_3m
                        pos.perf_6m = analysis.performances.perf_6m
                        pos.perf_1y = analysis.performances.perf_1y
                        pos.is_resilient = analysis.is_resilient
                        pos.volatility = analysis.volatility
                    else:
                        pos.analysis_error = result.error

                except Exception as e:
                    logger.warning(f"Error enriching {pos.symbol}: {e}")
                    pos.analysis_error = str(e)

        # Enrichir toutes les positions en parallèle
        tasks = [enrich_position(pos) for pos in positions]
        await asyncio.gather(*tasks)

        enriched = sum(1 for p in positions if p.is_resilient is not None)
        logger.info(f"Successfully enriched {enriched}/{len(positions)} positions")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_get_portfolio_use_case(
    broker: BrokerService,
    provider: Optional[StockDataProvider] = None,
) -> GetPortfolioUseCase:
    """
    Factory function pour créer un GetPortfolioUseCase.

    Args:
        broker: Service broker
        provider: Fournisseur de données pour enrichissement

    Returns:
        Instance configurée du use case
    """
    return GetPortfolioUseCase(broker, provider)
