"""
Use Cases (Cas d'utilisation) de l'application.

Orchestrent la logique métier en utilisant les interfaces.
"""

from src.application.use_cases.analyze_stock import (
    AnalyzeStockUseCase,
    AnalyzeStockResult,
    create_analyze_stock_use_case,
)
from src.application.use_cases.analyze_batch import (
    AnalyzeBatchUseCase,
    BatchResult,
    create_analyze_batch_use_case,
)
from src.application.use_cases.get_portfolio import (
    GetPortfolioUseCase,
    EnrichedPortfolio,
    EnrichedPosition,
    create_get_portfolio_use_case,
)
from src.application.use_cases.place_order import (
    PlaceOrderUseCase,
    CancelOrderUseCase,
    GetOrdersUseCase,
    create_place_order_use_case,
    create_cancel_order_use_case,
    create_get_orders_use_case,
)

__all__ = [
    # Analyze
    "AnalyzeStockUseCase",
    "AnalyzeStockResult",
    "create_analyze_stock_use_case",
    # Batch
    "AnalyzeBatchUseCase",
    "BatchResult",
    "create_analyze_batch_use_case",
    # Portfolio
    "GetPortfolioUseCase",
    "EnrichedPortfolio",
    "EnrichedPosition",
    "create_get_portfolio_use_case",
    # Orders
    "PlaceOrderUseCase",
    "CancelOrderUseCase",
    "GetOrdersUseCase",
    "create_place_order_use_case",
    "create_cancel_order_use_case",
    "create_get_orders_use_case",
]
