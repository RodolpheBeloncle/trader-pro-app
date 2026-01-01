"""
Entités pour les recommandations d'investissement.

Ce module définit le système de scoring multi-facteurs et les recommandations
d'investissement générées par l'algorithme d'aide à la décision.

CRITÈRES D'ÉVALUATION:
1. Performance historique (résilience multi-période)
2. Analyse technique (signaux RSI, MACD, etc.)
3. Momentum et tendance
4. Volatilité et risque
5. Fondamentaux (dividendes, secteur)
6. Timing d'entrée

HORIZONS D'INVESTISSEMENT:
- Court terme: 1-6 mois (trading momentum)
- Moyen terme: 6 mois - 2 ans (swing trading)
- Long terme: 2-5+ ans (investissement value)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal

from src.domain.entities.technical_analysis import (
    Signal,
    Trend,
    TimeHorizon,
    TechnicalIndicators,
)


class RecommendationType(str, Enum):
    """Type de recommandation."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    ACCUMULATE = "accumulate"  # Acheter progressivement
    HOLD = "hold"
    REDUCE = "reduce"  # Réduire position
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    AVOID = "avoid"


class InvestmentCategory(str, Enum):
    """Catégorie d'investissement."""
    GROWTH = "growth"          # Croissance rapide
    VALUE = "value"            # Sous-évalué
    DIVIDEND = "dividend"      # Rendement dividende
    MOMENTUM = "momentum"      # Fort momentum
    DEFENSIVE = "defensive"    # Défensif, faible volatilité
    SPECULATIVE = "speculative"  # Spéculatif, haut risque


class RiskLevel(str, Enum):
    """Niveau de risque."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ScoreBreakdown:
    """
    Décomposition détaillée du score d'investissement.

    Chaque composante est notée sur 100 et pondérée.
    """

    # Scores individuels (0-100)
    performance_score: float
    """Score basé sur les performances historiques (résilience)."""

    technical_score: float
    """Score basé sur l'analyse technique (RSI, MACD, etc.)."""

    momentum_score: float
    """Score basé sur le momentum et la tendance."""

    volatility_score: float
    """Score basé sur la volatilité (inversé: faible vol = haut score)."""

    fundamental_score: float
    """Score basé sur les fondamentaux (dividende, secteur)."""

    timing_score: float
    """Score de timing d'entrée (Bollinger, supports/résistances)."""

    # Pondérations appliquées
    weights: Dict[str, float] = field(default_factory=lambda: {
        "performance": 0.25,
        "technical": 0.20,
        "momentum": 0.15,
        "volatility": 0.15,
        "fundamental": 0.15,
        "timing": 0.10,
    })

    @property
    def total_score(self) -> float:
        """Score global pondéré (0-100)."""
        return (
            self.performance_score * self.weights["performance"] +
            self.technical_score * self.weights["technical"] +
            self.momentum_score * self.weights["momentum"] +
            self.volatility_score * self.weights["volatility"] +
            self.fundamental_score * self.weights["fundamental"] +
            self.timing_score * self.weights["timing"]
        )

    @property
    def strengths(self) -> List[str]:
        """Points forts (scores > 70)."""
        strengths = []
        if self.performance_score > 70:
            strengths.append("Performance historique solide")
        if self.technical_score > 70:
            strengths.append("Signaux techniques favorables")
        if self.momentum_score > 70:
            strengths.append("Fort momentum positif")
        if self.volatility_score > 70:
            strengths.append("Volatilité maîtrisée")
        if self.fundamental_score > 70:
            strengths.append("Fondamentaux solides")
        if self.timing_score > 70:
            strengths.append("Bon timing d'entrée")
        return strengths

    @property
    def weaknesses(self) -> List[str]:
        """Points faibles (scores < 40)."""
        weaknesses = []
        if self.performance_score < 40:
            weaknesses.append("Performance historique faible")
        if self.technical_score < 40:
            weaknesses.append("Signaux techniques défavorables")
        if self.momentum_score < 40:
            weaknesses.append("Momentum négatif")
        if self.volatility_score < 40:
            weaknesses.append("Volatilité excessive")
        if self.fundamental_score < 40:
            weaknesses.append("Fondamentaux préoccupants")
        if self.timing_score < 40:
            weaknesses.append("Timing d'entrée défavorable")
        return weaknesses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "performance_score": round(self.performance_score, 1),
            "technical_score": round(self.technical_score, 1),
            "momentum_score": round(self.momentum_score, 1),
            "volatility_score": round(self.volatility_score, 1),
            "fundamental_score": round(self.fundamental_score, 1),
            "timing_score": round(self.timing_score, 1),
            "total_score": round(self.total_score, 1),
            "weights": self.weights,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }


@dataclass
class PriceTarget:
    """Objectif de prix."""
    target_price: float
    current_price: float
    potential_return: float  # En %
    stop_loss: float
    risk_reward_ratio: float
    horizon: TimeHorizon

    @property
    def upside_percent(self) -> float:
        """Potentiel de hausse en %."""
        return ((self.target_price - self.current_price) / self.current_price) * 100

    @property
    def downside_percent(self) -> float:
        """Risque de baisse jusqu'au stop loss en %."""
        return ((self.current_price - self.stop_loss) / self.current_price) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_price": round(self.target_price, 2),
            "current_price": round(self.current_price, 2),
            "potential_return": round(self.potential_return, 2),
            "stop_loss": round(self.stop_loss, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "horizon": self.horizon.value,
            "upside_percent": round(self.upside_percent, 2),
            "downside_percent": round(self.downside_percent, 2),
        }


@dataclass
class InvestmentRecommendation:
    """
    Recommandation d'investissement complète pour un actif.

    Contient le scoring, la recommandation, les objectifs et l'analyse.
    """

    ticker: str
    name: str
    asset_type: str
    sector: Optional[str]

    # Scoring
    score_breakdown: ScoreBreakdown

    # Recommandation
    recommendation: RecommendationType
    category: InvestmentCategory
    risk_level: RiskLevel
    confidence: float  # 0-100%

    # Horizons
    short_term_outlook: str
    medium_term_outlook: str
    long_term_outlook: str

    # Objectifs de prix
    price_targets: Dict[str, PriceTarget]  # Par horizon

    # Analyse
    key_insights: List[str]
    risks: List[str]
    catalysts: List[str]

    # Technique
    technical_summary: str
    entry_strategy: str

    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def overall_score(self) -> float:
        """Score global."""
        return self.score_breakdown.total_score

    @property
    def action_summary(self) -> str:
        """Résumé de l'action recommandée."""
        actions = {
            RecommendationType.STRONG_BUY: "ACHAT FORT - Position importante recommandée",
            RecommendationType.BUY: "ACHAT - Bon point d'entrée",
            RecommendationType.ACCUMULATE: "ACCUMULATION - Construire position progressivement",
            RecommendationType.HOLD: "CONSERVER - Maintenir positions existantes",
            RecommendationType.REDUCE: "RÉDUIRE - Alléger la position",
            RecommendationType.SELL: "VENDRE - Prendre les profits",
            RecommendationType.STRONG_SELL: "VENTE URGENTE - Sortir rapidement",
            RecommendationType.AVOID: "ÉVITER - Ne pas entrer en position",
        }
        return actions.get(self.recommendation, "Analyse en cours")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "asset_type": self.asset_type,
            "sector": self.sector,
            "score_breakdown": self.score_breakdown.to_dict(),
            "overall_score": round(self.overall_score, 1),
            "recommendation": self.recommendation.value,
            "action_summary": self.action_summary,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "confidence": round(self.confidence, 1),
            "short_term_outlook": self.short_term_outlook,
            "medium_term_outlook": self.medium_term_outlook,
            "long_term_outlook": self.long_term_outlook,
            "price_targets": {k: v.to_dict() for k, v in self.price_targets.items()},
            "key_insights": self.key_insights,
            "risks": self.risks,
            "catalysts": self.catalysts,
            "technical_summary": self.technical_summary,
            "entry_strategy": self.entry_strategy,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class PortfolioRecommendation:
    """
    Recommandations pour la construction/gestion d'un portefeuille.
    """

    # Top picks par catégorie
    top_growth: List[InvestmentRecommendation]
    top_value: List[InvestmentRecommendation]
    top_dividend: List[InvestmentRecommendation]
    top_momentum: List[InvestmentRecommendation]
    top_defensive: List[InvestmentRecommendation]

    # ETFs recommandés par secteur
    recommended_etfs: Dict[str, List[InvestmentRecommendation]]

    # Allocation suggérée
    suggested_allocation: Dict[str, float]

    # Actifs à éviter
    avoid_list: List[str]

    # Opportunités détectées
    emerging_opportunities: List[Dict[str, Any]]

    # Résumé marché
    market_sentiment: str
    market_trend: Trend

    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "top_growth": [r.to_dict() for r in self.top_growth[:5]],
            "top_value": [r.to_dict() for r in self.top_value[:5]],
            "top_dividend": [r.to_dict() for r in self.top_dividend[:5]],
            "top_momentum": [r.to_dict() for r in self.top_momentum[:5]],
            "top_defensive": [r.to_dict() for r in self.top_defensive[:5]],
            "recommended_etfs": {
                k: [r.to_dict() for r in v[:3]]
                for k, v in self.recommended_etfs.items()
            },
            "suggested_allocation": self.suggested_allocation,
            "avoid_list": self.avoid_list,
            "emerging_opportunities": self.emerging_opportunities,
            "market_sentiment": self.market_sentiment,
            "market_trend": self.market_trend.value,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class MarketScreenerResult:
    """
    Résultat du screener de marché.

    Identifie les meilleures opportunités selon différents critères.
    """

    # Actions les mieux notées
    best_overall: List[InvestmentRecommendation]

    # Par critère
    best_momentum: List[InvestmentRecommendation]
    best_value: List[InvestmentRecommendation]
    oversold_bounces: List[InvestmentRecommendation]  # Potentiels rebonds
    breakout_candidates: List[InvestmentRecommendation]  # Ruptures potentielles

    # Signaux forts
    strong_buy_signals: List[InvestmentRecommendation]
    strong_sell_signals: List[InvestmentRecommendation]

    # Statistiques
    total_analyzed: int
    buy_count: int
    sell_count: int
    neutral_count: int

    screened_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_overall": [r.to_dict() for r in self.best_overall[:10]],
            "best_momentum": [r.to_dict() for r in self.best_momentum[:10]],
            "best_value": [r.to_dict() for r in self.best_value[:10]],
            "oversold_bounces": [r.to_dict() for r in self.oversold_bounces[:10]],
            "breakout_candidates": [r.to_dict() for r in self.breakout_candidates[:10]],
            "strong_buy_signals": [r.to_dict() for r in self.strong_buy_signals[:10]],
            "strong_sell_signals": [r.to_dict() for r in self.strong_sell_signals[:10]],
            "statistics": {
                "total_analyzed": self.total_analyzed,
                "buy_count": self.buy_count,
                "sell_count": self.sell_count,
                "neutral_count": self.neutral_count,
                "buy_percent": round(self.buy_count / self.total_analyzed * 100, 1) if self.total_analyzed > 0 else 0,
            },
            "screened_at": self.screened_at.isoformat(),
        }
