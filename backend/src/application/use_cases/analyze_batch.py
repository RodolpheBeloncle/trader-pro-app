"""
Use Case : Analyse batch de plusieurs stocks.

Orchestre l'analyse de plusieurs tickers en parallèle
avec gestion de la concurrence et des erreurs individuelles.

ARCHITECTURE:
- Utilise AnalyzeStockUseCase pour chaque ticker
- Limite la concurrence pour éviter de surcharger les APIs
- Retourne les succès ET les erreurs

UTILISATION:
    use_case = AnalyzeBatchUseCase(yahoo_provider)
    results = await use_case.execute(["AAPL", "MSFT", "GOOGL"])
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List

from src.application.interfaces.stock_data_provider import StockDataProvider
from src.application.use_cases.analyze_stock import (
    AnalyzeStockUseCase,
    AnalyzeStockResult,
)
from src.config.constants import MAX_BATCH_SIZE, MAX_CONCURRENT_REQUESTS
from src.domain.entities.stock import StockAnalysis

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Résultat d'une analyse batch."""

    results: List[AnalyzeStockResult]
    """Tous les résultats (succès et erreurs)."""

    @property
    def successful(self) -> List[StockAnalysis]:
        """Retourne uniquement les analyses réussies."""
        return [r.analysis for r in self.results if r.is_success and r.analysis]

    @property
    def failed(self) -> List[dict]:
        """Retourne les erreurs avec leurs tickers."""
        return [
            {"ticker": r.ticker, "error": r.error}
            for r in self.results
            if not r.is_success
        ]

    @property
    def success_count(self) -> int:
        """Nombre d'analyses réussies."""
        return len(self.successful)

    @property
    def error_count(self) -> int:
        """Nombre d'erreurs."""
        return len(self.failed)

    @property
    def total_count(self) -> int:
        """Nombre total de tickers traités."""
        return len(self.results)


class AnalyzeBatchUseCase:
    """
    Use Case pour analyser plusieurs stocks en batch.

    Gère:
    - Limitation de la taille du batch
    - Concurrence contrôlée
    - Agrégation des résultats

    Attributes:
        provider: Fournisseur de données de marché
        analyze_use_case: Use case pour l'analyse individuelle
        max_concurrent: Nombre max de requêtes parallèles
    """

    def __init__(
        self,
        provider: StockDataProvider,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
    ):
        """
        Initialise le use case.

        Args:
            provider: Fournisseur de données (Yahoo, etc.)
            max_concurrent: Nombre max de requêtes parallèles
        """
        self.provider = provider
        self.analyze_use_case = AnalyzeStockUseCase(provider)
        self.max_concurrent = max_concurrent

    async def execute(self, tickers: List[str]) -> BatchResult:
        """
        Analyse plusieurs stocks en parallèle.

        Args:
            tickers: Liste des symboles à analyser

        Returns:
            BatchResult avec tous les résultats
        """
        if not tickers:
            return BatchResult(results=[])

        # Limiter la taille du batch
        if len(tickers) > MAX_BATCH_SIZE:
            logger.warning(
                f"Batch size {len(tickers)} exceeds max {MAX_BATCH_SIZE}, truncating"
            )
            tickers = tickers[:MAX_BATCH_SIZE]

        # Dédupliquer les tickers
        unique_tickers = list(dict.fromkeys(tickers))

        logger.info(f"Starting batch analysis of {len(unique_tickers)} tickers")

        # Créer un semaphore pour limiter la concurrence
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def analyze_with_semaphore(ticker: str) -> AnalyzeStockResult:
            """Analyse un ticker avec limite de concurrence."""
            async with semaphore:
                return await self.analyze_use_case.execute(ticker)

        # Lancer toutes les analyses en parallèle
        tasks = [analyze_with_semaphore(ticker) for ticker in unique_tickers]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Convertir les exceptions en AnalyzeStockResult
        processed_results: List[AnalyzeStockResult] = []
        for ticker, result in zip(unique_tickers, results):
            if isinstance(result, AnalyzeStockResult):
                processed_results.append(result)
            else:
                # Exception inattendue
                processed_results.append(
                    AnalyzeStockResult(
                        analysis=None,
                        error=str(result),
                        ticker=ticker,
                    )
                )

        batch_result = BatchResult(results=processed_results)

        logger.info(
            f"Batch analysis complete: {batch_result.success_count} success, "
            f"{batch_result.error_count} errors"
        )

        return batch_result


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_analyze_batch_use_case(
    provider: StockDataProvider,
    max_concurrent: int = MAX_CONCURRENT_REQUESTS,
) -> AnalyzeBatchUseCase:
    """
    Factory function pour créer un AnalyzeBatchUseCase.

    Args:
        provider: Fournisseur de données de marché
        max_concurrent: Nombre max de requêtes parallèles

    Returns:
        Instance configurée du use case
    """
    return AnalyzeBatchUseCase(provider, max_concurrent)
