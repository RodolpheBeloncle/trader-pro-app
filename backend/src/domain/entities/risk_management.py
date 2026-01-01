"""
Entités pour la gestion du risque professionnelle.

Ce module implémente les concepts fondamentaux de risk management :
- Espérance mathématique (Edge)
- Position Sizing
- Kelly Criterion (adapté)
- Drawdown Management
- Risk/Reward Ratio

RÉFÉRENCES :
- Van K. Tharp - Trade Your Way to Financial Freedom
- Ralph Vince - Portfolio Management Formulas
- Nassim Taleb - Fooled by Randomness

PRINCIPE FONDAMENTAL :
> "Le risque prime TOUJOURS sur le rendement"
> "Ne jamais être éliminé du jeu"

FORMULE CLÉ - Espérance :
E = (Win% × Gain moyen) − (Loss% × Perte moyenne)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import math


class RiskProfile(str, Enum):
    """Profil de risque de l'investisseur."""
    CONSERVATIVE = "conservative"    # 0.5-1% par trade
    MODERATE = "moderate"            # 1-2% par trade
    AGGRESSIVE = "aggressive"        # 2-3% par trade
    VERY_AGGRESSIVE = "very_aggressive"  # 3-5% par trade (déconseillé)


class TradeOutcome(str, Enum):
    """Résultat d'un trade."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


@dataclass
class TradeStatistics:
    """
    Statistiques de trading pour calculer l'espérance.

    Ces stats doivent être mises à jour après chaque trade
    pour maintenir une vision précise de l'edge.
    """
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    total_profit: float = 0.0
    total_loss: float = 0.0  # Valeur absolue des pertes

    largest_win: float = 0.0
    largest_loss: float = 0.0

    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Pour tracking du drawdown
    peak_equity: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0

    @property
    def win_rate(self) -> float:
        """Taux de réussite (0-1)."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def loss_rate(self) -> float:
        """Taux de perte (0-1)."""
        if self.total_trades == 0:
            return 0.0
        return self.losing_trades / self.total_trades

    @property
    def average_win(self) -> float:
        """Gain moyen par trade gagnant."""
        if self.winning_trades == 0:
            return 0.0
        return self.total_profit / self.winning_trades

    @property
    def average_loss(self) -> float:
        """Perte moyenne par trade perdant (valeur absolue)."""
        if self.losing_trades == 0:
            return 0.0
        return self.total_loss / self.losing_trades

    @property
    def profit_factor(self) -> float:
        """
        Profit Factor = Total Profit / Total Loss

        > 1 = Profitable
        > 1.5 = Bon système
        > 2 = Excellent système
        """
        if self.total_loss == 0:
            return float('inf') if self.total_profit > 0 else 0
        return self.total_profit / self.total_loss

    @property
    def expectancy(self) -> float:
        """
        Espérance mathématique par trade.

        E = (Win% × Avg Win) - (Loss% × Avg Loss)

        > 0 = Edge positif
        """
        return (self.win_rate * self.average_win) - (self.loss_rate * self.average_loss)

    @property
    def expectancy_per_dollar_risked(self) -> float:
        """
        Espérance par dollar risqué (R-Multiple moyen).

        Plus utile que l'espérance brute car normalisé.
        """
        if self.average_loss == 0:
            return 0.0
        avg_win_r = self.average_win / self.average_loss
        return (self.win_rate * avg_win_r) - self.loss_rate

    @property
    def has_edge(self) -> bool:
        """Le système a-t-il un edge positif ?"""
        return self.expectancy > 0 and self.total_trades >= 30

    @property
    def risk_of_ruin(self) -> float:
        """
        Probabilité de ruine (simplifiée).

        Basé sur le win rate et le risk/reward.
        """
        if self.average_loss == 0 or self.win_rate == 0:
            return 1.0  # 100% de risque si pas de données

        # Formule simplifiée
        rr_ratio = self.average_win / self.average_loss if self.average_loss > 0 else 1
        if self.win_rate >= 1:
            return 0.0

        # Risk of Ruin = ((1 - edge) / (1 + edge))^units
        edge = self.expectancy_per_dollar_risked
        if edge <= 0:
            return 1.0

        return max(0, min(1, ((1 - edge) / (1 + edge)) ** 20))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "average_win": round(self.average_win, 2),
            "average_loss": round(self.average_loss, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 2),
            "expectancy_per_r": round(self.expectancy_per_dollar_risked, 2),
            "has_edge": self.has_edge,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_drawdown": round(self.max_drawdown * 100, 1),
            "risk_of_ruin": round(self.risk_of_ruin * 100, 1),
        }


@dataclass
class PositionSizeCalculation:
    """
    Calcul de la taille de position selon plusieurs méthodes.

    RÈGLE D'OR : Ne jamais risquer plus de X% du capital par trade.
    """
    capital: float
    risk_per_trade_percent: float  # Ex: 0.01 = 1%
    entry_price: float
    stop_loss_price: float

    @property
    def risk_amount(self) -> float:
        """Montant à risquer en valeur absolue."""
        return self.capital * self.risk_per_trade_percent

    @property
    def risk_per_share(self) -> float:
        """Risque par action (distance au stop)."""
        return abs(self.entry_price - self.stop_loss_price)

    @property
    def position_size_shares(self) -> int:
        """Nombre d'actions à acheter."""
        if self.risk_per_share == 0:
            return 0
        shares = self.risk_amount / self.risk_per_share
        return int(shares)  # Arrondi inférieur pour sécurité

    @property
    def position_value(self) -> float:
        """Valeur totale de la position."""
        return self.position_size_shares * self.entry_price

    @property
    def position_percent_of_capital(self) -> float:
        """Pourcentage du capital investi."""
        if self.capital == 0:
            return 0
        return self.position_value / self.capital

    @property
    def actual_risk_percent(self) -> float:
        """Risque réel après arrondi."""
        actual_risk = self.position_size_shares * self.risk_per_share
        return actual_risk / self.capital if self.capital > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capital": round(self.capital, 2),
            "risk_per_trade_percent": round(self.risk_per_trade_percent * 100, 2),
            "risk_amount": round(self.risk_amount, 2),
            "entry_price": round(self.entry_price, 2),
            "stop_loss_price": round(self.stop_loss_price, 2),
            "risk_per_share": round(self.risk_per_share, 2),
            "position_size_shares": self.position_size_shares,
            "position_value": round(self.position_value, 2),
            "position_percent_of_capital": round(self.position_percent_of_capital * 100, 1),
            "actual_risk_percent": round(self.actual_risk_percent * 100, 2),
        }


@dataclass
class KellyCalculation:
    """
    Calcul du Kelly Criterion pour l'allocation optimale.

    Kelly% = W - [(1-W) / R]
    où W = Win Rate, R = Win/Loss Ratio

    ATTENTION : Kelly complet est trop agressif.
    Utiliser fraction (1/4 à 1/2) en pratique.

    RÉFÉRENCE : Ralph Vince - Portfolio Management Formulas
    """
    win_rate: float      # 0-1
    avg_win: float       # Gain moyen
    avg_loss: float      # Perte moyenne (absolue)

    @property
    def win_loss_ratio(self) -> float:
        """Ratio gain/perte moyen."""
        if self.avg_loss == 0:
            return float('inf')
        return self.avg_win / self.avg_loss

    @property
    def kelly_full(self) -> float:
        """Kelly complet (trop agressif en pratique)."""
        if self.avg_loss == 0:
            return 0
        r = self.win_loss_ratio
        kelly = self.win_rate - ((1 - self.win_rate) / r)
        return max(0, kelly)  # Jamais négatif

    @property
    def kelly_half(self) -> float:
        """Demi-Kelly (recommandé)."""
        return self.kelly_full / 2

    @property
    def kelly_quarter(self) -> float:
        """Quart-Kelly (conservateur)."""
        return self.kelly_full / 4

    @property
    def recommended_risk_percent(self) -> float:
        """
        Risque recommandé basé sur Kelly adapté.

        Plafonne à 5% max pour sécurité.
        """
        return min(0.05, self.kelly_half)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "win_rate": round(self.win_rate * 100, 1),
            "win_loss_ratio": round(self.win_loss_ratio, 2),
            "kelly_full": round(self.kelly_full * 100, 1),
            "kelly_half": round(self.kelly_half * 100, 2),
            "kelly_quarter": round(self.kelly_quarter * 100, 2),
            "recommended_risk_percent": round(self.recommended_risk_percent * 100, 2),
        }


@dataclass
class RiskRewardAnalysis:
    """
    Analyse du Risk/Reward pour un trade potentiel.

    RÈGLE : Minimum 1:2 R/R pour compenser un win rate de 40%
    """
    entry_price: float
    stop_loss_price: float
    target_price: float

    @property
    def risk(self) -> float:
        """Risque (distance au stop)."""
        return abs(self.entry_price - self.stop_loss_price)

    @property
    def reward(self) -> float:
        """Reward (distance au target)."""
        return abs(self.target_price - self.entry_price)

    @property
    def risk_reward_ratio(self) -> float:
        """
        Ratio Risk/Reward.

        > 1:2 = Acceptable
        > 1:3 = Bon
        > 1:4+ = Excellent
        """
        if self.risk == 0:
            return float('inf')
        return self.reward / self.risk

    @property
    def required_win_rate(self) -> float:
        """
        Win rate minimum requis pour être profitable avec ce R/R.

        Formule : 1 / (1 + R/R)
        """
        rr = self.risk_reward_ratio
        if rr == 0:
            return 1.0
        return 1 / (1 + rr)

    @property
    def is_acceptable(self) -> bool:
        """Le trade a-t-il un R/R acceptable (>= 1:2) ?"""
        return self.risk_reward_ratio >= 2.0

    @property
    def quality(self) -> str:
        """Qualité du setup basée sur le R/R."""
        rr = self.risk_reward_ratio
        if rr >= 4:
            return "A+ (Excellent)"
        elif rr >= 3:
            return "A (Très bon)"
        elif rr >= 2:
            return "B (Acceptable)"
        elif rr >= 1.5:
            return "C (Médiocre)"
        return "D (À éviter)"

    @property
    def risk_percent(self) -> float:
        """Risque en % du prix d'entrée."""
        return (self.risk / self.entry_price) * 100 if self.entry_price > 0 else 0

    @property
    def reward_percent(self) -> float:
        """Reward en % du prix d'entrée."""
        return (self.reward / self.entry_price) * 100 if self.entry_price > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_price": round(self.entry_price, 2),
            "stop_loss_price": round(self.stop_loss_price, 2),
            "target_price": round(self.target_price, 2),
            "risk": round(self.risk, 2),
            "reward": round(self.reward, 2),
            "risk_percent": round(self.risk_percent, 2),
            "reward_percent": round(self.reward_percent, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "required_win_rate": round(self.required_win_rate * 100, 1),
            "is_acceptable": self.is_acceptable,
            "quality": self.quality,
        }


@dataclass
class TradeSetup:
    """
    Setup de trade complet avec analyse de risque intégrée.

    C'est le format final avant exécution.
    """
    ticker: str
    direction: str  # "long" ou "short"

    # Prix
    entry_price: float
    stop_loss_price: float
    target_1: float  # Premier objectif
    target_2: Optional[float] = None  # Deuxième objectif
    target_3: Optional[float] = None  # Troisième objectif

    # Sizing
    position_size: int = 0
    position_value: float = 0.0
    risk_amount: float = 0.0

    # Analyse
    risk_reward: Optional[RiskRewardAnalysis] = None
    setup_quality: str = ""

    # Contexte
    setup_type: str = ""  # Ex: "pullback_to_demand", "breakout", etc.
    confluence_factors: List[str] = field(default_factory=list)
    invalidation_reason: str = ""

    # Journal
    rationale: str = ""  # Pourquoi ce trade ?
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def r_multiple_target_1(self) -> float:
        """R-Multiple du premier objectif."""
        risk = abs(self.entry_price - self.stop_loss_price)
        if risk == 0:
            return 0
        return abs(self.target_1 - self.entry_price) / risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": round(self.entry_price, 2),
            "stop_loss_price": round(self.stop_loss_price, 2),
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2) if self.target_2 else None,
            "target_3": round(self.target_3, 2) if self.target_3 else None,
            "position_size": self.position_size,
            "position_value": round(self.position_value, 2),
            "risk_amount": round(self.risk_amount, 2),
            "r_multiple_target_1": round(self.r_multiple_target_1, 1),
            "risk_reward": self.risk_reward.to_dict() if self.risk_reward else None,
            "setup_quality": self.setup_quality,
            "setup_type": self.setup_type,
            "confluence_factors": self.confluence_factors,
            "invalidation_reason": self.invalidation_reason,
            "rationale": self.rationale,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PortfolioRiskAnalysis:
    """
    Analyse du risque au niveau du portefeuille.

    RÈGLES FONDAMENTALES :
    - Drawdown max acceptable : 20-25%
    - Corrélation entre positions
    - Exposition sectorielle
    """
    total_capital: float
    positions_count: int
    total_exposure: float  # Valeur totale des positions
    total_risk: float      # Risque total si tous les stops sont touchés

    sector_exposure: Dict[str, float]  # % par secteur
    correlated_positions: List[Tuple[str, str, float]]  # (ticker1, ticker2, correlation)

    current_drawdown: float
    max_drawdown_limit: float

    @property
    def exposure_percent(self) -> float:
        """Exposition en % du capital."""
        return (self.total_exposure / self.total_capital * 100) if self.total_capital > 0 else 0

    @property
    def risk_percent(self) -> float:
        """Risque total en % du capital."""
        return (self.total_risk / self.total_capital * 100) if self.total_capital > 0 else 0

    @property
    def is_over_exposed(self) -> bool:
        """Le portefeuille est-il sur-exposé (>100%) ?"""
        return self.exposure_percent > 100

    @property
    def is_over_risked(self) -> bool:
        """Le risque total est-il excessif (>10%) ?"""
        return self.risk_percent > 10

    @property
    def drawdown_remaining(self) -> float:
        """Marge avant limite de drawdown."""
        return self.max_drawdown_limit - self.current_drawdown

    @property
    def can_add_risk(self) -> bool:
        """Peut-on ajouter une nouvelle position ?"""
        return (
            not self.is_over_risked and
            self.current_drawdown < self.max_drawdown_limit * 0.8
        )

    @property
    def risk_status(self) -> str:
        """Statut du risque du portefeuille."""
        if self.is_over_risked:
            return "DANGER - Réduire les positions"
        if self.risk_percent > 7:
            return "ATTENTION - Risque élevé"
        if self.risk_percent > 5:
            return "MODÉRÉ - Surveiller"
        return "OK - Dans les limites"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_capital": round(self.total_capital, 2),
            "positions_count": self.positions_count,
            "total_exposure": round(self.total_exposure, 2),
            "exposure_percent": round(self.exposure_percent, 1),
            "total_risk": round(self.total_risk, 2),
            "risk_percent": round(self.risk_percent, 2),
            "sector_exposure": {k: round(v, 1) for k, v in self.sector_exposure.items()},
            "current_drawdown": round(self.current_drawdown * 100, 1),
            "max_drawdown_limit": round(self.max_drawdown_limit * 100, 0),
            "drawdown_remaining": round(self.drawdown_remaining * 100, 1),
            "is_over_exposed": self.is_over_exposed,
            "is_over_risked": self.is_over_risked,
            "can_add_risk": self.can_add_risk,
            "risk_status": self.risk_status,
        }
