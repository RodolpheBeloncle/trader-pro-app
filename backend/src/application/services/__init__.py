"""
Services d'application pour le Stock Analyzer.

Ce package contient les services métier:
- TechnicalCalculator: Calcul des indicateurs techniques
- RecommendationEngine: Moteur de recommandation d'investissement
- ChartGenerator: Génération de graphiques avec Plotly
"""

from src.application.services.technical_calculator import (
    TechnicalCalculator,
    create_technical_calculator,
)
from src.application.services.recommendation_engine import (
    RecommendationEngine,
    create_recommendation_engine,
)
from src.application.services.chart_generator import (
    ChartGenerator,
    create_chart_generator,
)

__all__ = [
    "TechnicalCalculator",
    "create_technical_calculator",
    "RecommendationEngine",
    "create_recommendation_engine",
    "ChartGenerator",
    "create_chart_generator",
]
