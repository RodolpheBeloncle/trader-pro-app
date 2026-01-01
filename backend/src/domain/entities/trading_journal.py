"""
Système de journal de trading professionnel.

Ce module implémente un journal structuré selon les meilleures pratiques :
- Journalisation orientée PROCESS, pas PnL
- Analyse post-trade focalisée sur le respect des règles
- Tracking des erreurs pour amélioration continue

RÉFÉRENCES :
- Brett Steenbarger - The Daily Trading Coach
- Mark Douglas - Trading in the Zone

PRINCIPE FONDAMENTAL :
> "Un bon journal ne trace pas seulement les résultats,
> il trace les DÉCISIONS et le PROCESSUS."

STRUCTURE DU JOURNAL :
1. Contexte pré-trade
2. Setup et rationale
3. Exécution
4. Gestion post-entrée
5. Résultat
6. Post-analyse (respect du process)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class TradeDirection(str, Enum):
    """Direction du trade."""
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    """Statut du trade."""
    PLANNED = "planned"      # En attente d'exécution
    ACTIVE = "active"        # Position ouverte
    CLOSED = "closed"        # Position fermée
    CANCELLED = "cancelled"  # Annulé avant exécution


class ExecutionQuality(str, Enum):
    """Qualité de l'exécution."""
    EXCELLENT = "excellent"  # Parfait timing
    GOOD = "good"            # Bon, léger slippage
    AVERAGE = "average"      # Acceptable
    POOR = "poor"            # Mauvais timing
    TERRIBLE = "terrible"    # FOMO ou panique


class ProcessCompliance(str, Enum):
    """Respect du processus de trading."""
    FULL = "full"            # 100% respecté
    PARTIAL = "partial"      # Partiellement respecté
    VIOLATED = "violated"    # Règles enfreintes


class EmotionalState(str, Enum):
    """État émotionnel pendant le trade."""
    CALM = "calm"            # Calme et objectif
    CONFIDENT = "confident"  # Confiant (attention à l'overconfidence)
    ANXIOUS = "anxious"      # Anxieux
    FOMO = "fomo"            # Fear of missing out
    REVENGE = "revenge"      # Revenge trading
    GREEDY = "greedy"        # Cupidité
    FEARFUL = "fearful"      # Peur


class MistakeType(str, Enum):
    """Types d'erreurs de trading."""
    NONE = "none"
    FOMO_ENTRY = "fomo_entry"
    CHASING = "chasing"
    EARLY_EXIT = "early_exit"
    LATE_EXIT = "late_exit"
    IGNORED_STOP = "ignored_stop"
    MOVED_STOP = "moved_stop"
    OVERSIZED = "oversized"
    WRONG_DIRECTION = "wrong_direction"
    NO_SETUP = "no_setup"
    REVENGE_TRADE = "revenge_trade"
    OVERTRADING = "overtrading"


@dataclass
class PreTradeAnalysis:
    """
    Analyse pré-trade : Contexte et rationale.

    OBLIGATOIRE avant chaque trade pour éviter les trades impulsifs.
    """
    # Contexte de marché
    market_regime: str  # trending_up, trending_down, ranging, etc.
    market_bias: str    # bullish, bearish, neutral
    session: str        # asian, london, new_york
    volatility_state: str  # low, normal, high

    # Setup
    setup_type: str     # Ex: "pullback_to_demand", "breakout", etc.
    timeframe: str      # Ex: "1H", "4H", "D"

    # Confluence (facteurs alignés)
    confluence_factors: List[str] = field(default_factory=list)

    # Invalidation
    invalidation_level: float = 0.0
    invalidation_reason: str = ""

    # Rationale (POURQUOI ce trade?)
    trade_thesis: str = ""
    expected_move: str = ""

    # Checklist pré-trade
    checklist_completed: bool = False
    checklist_items: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_regime": self.market_regime,
            "market_bias": self.market_bias,
            "session": self.session,
            "volatility_state": self.volatility_state,
            "setup_type": self.setup_type,
            "timeframe": self.timeframe,
            "confluence_factors": self.confluence_factors,
            "invalidation_level": self.invalidation_level,
            "invalidation_reason": self.invalidation_reason,
            "trade_thesis": self.trade_thesis,
            "expected_move": self.expected_move,
            "checklist_completed": self.checklist_completed,
        }


@dataclass
class TradeExecution:
    """Détails de l'exécution du trade."""
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None

    position_size: int = 0
    position_value: float = 0.0
    risk_amount: float = 0.0
    risk_percent: float = 0.0

    execution_quality: ExecutionQuality = ExecutionQuality.AVERAGE
    slippage: float = 0.0

    entry_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_time": self.entry_time.isoformat(),
            "entry_price": round(self.entry_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "take_profit_1": round(self.take_profit_1, 2),
            "take_profit_2": round(self.take_profit_2, 2) if self.take_profit_2 else None,
            "take_profit_3": round(self.take_profit_3, 2) if self.take_profit_3 else None,
            "position_size": self.position_size,
            "risk_amount": round(self.risk_amount, 2),
            "risk_percent": round(self.risk_percent, 2),
            "execution_quality": self.execution_quality.value,
            "slippage": round(self.slippage, 2),
        }


@dataclass
class TradeManagement:
    """Gestion du trade en cours."""
    # Modifications du stop
    stop_moved: bool = False
    stop_move_reason: str = ""
    new_stop_levels: List[float] = field(default_factory=list)

    # Prises de profit partielles
    partial_closes: List[Dict[str, Any]] = field(default_factory=list)

    # Interventions
    intervention_count: int = 0
    intervention_reasons: List[str] = field(default_factory=list)

    # Émotions pendant le trade
    emotional_states: List[EmotionalState] = field(default_factory=list)
    emotional_notes: str = ""

    def add_partial_close(self, time: datetime, price: float, size: int, reason: str):
        """Ajoute une clôture partielle."""
        self.partial_closes.append({
            "time": time.isoformat(),
            "price": price,
            "size": size,
            "reason": reason,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stop_moved": self.stop_moved,
            "stop_move_reason": self.stop_move_reason,
            "partial_closes": self.partial_closes,
            "intervention_count": self.intervention_count,
            "emotional_states": [e.value for e in self.emotional_states],
            "emotional_notes": self.emotional_notes,
        }


@dataclass
class TradeResult:
    """Résultat du trade."""
    exit_time: datetime
    exit_price: float
    exit_reason: str  # "stop_loss", "take_profit", "manual", "trailing_stop"

    gross_pnl: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
    pnl_percent: float = 0.0
    r_multiple: float = 0.0  # Gain/Perte en multiples de R

    holding_time_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exit_time": self.exit_time.isoformat(),
            "exit_price": round(self.exit_price, 2),
            "exit_reason": self.exit_reason,
            "gross_pnl": round(self.gross_pnl, 2),
            "fees": round(self.fees, 2),
            "net_pnl": round(self.net_pnl, 2),
            "pnl_percent": round(self.pnl_percent, 2),
            "r_multiple": round(self.r_multiple, 2),
            "holding_time_hours": round(self.holding_time_hours, 1),
        }


@dataclass
class PostTradeAnalysis:
    """
    Analyse post-trade : Focus sur le PROCESS, pas le PnL.

    Questions clés :
    - Ai-je respecté mon process ?
    - Qu'ai-je bien fait ?
    - Qu'aurais-je pu améliorer ?
    - Cette erreur est-elle récurrente ?
    """
    # Respect du processus
    process_compliance: ProcessCompliance = ProcessCompliance.FULL
    rules_followed: List[str] = field(default_factory=list)
    rules_violated: List[str] = field(default_factory=list)

    # Erreurs
    mistakes: List[MistakeType] = field(default_factory=list)
    mistake_details: str = ""

    # Ce qui a bien fonctionné
    what_went_well: List[str] = field(default_factory=list)

    # Ce qui peut être amélioré
    what_to_improve: List[str] = field(default_factory=list)

    # Leçons apprises
    lessons_learned: str = ""

    # Score de qualité du trade (indépendant du PnL)
    trade_quality_score: int = 0  # 0-100

    # Aurait-on dû prendre ce trade ?
    should_have_traded: bool = True
    should_have_traded_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "process_compliance": self.process_compliance.value,
            "rules_followed": self.rules_followed,
            "rules_violated": self.rules_violated,
            "mistakes": [m.value for m in self.mistakes],
            "mistake_details": self.mistake_details,
            "what_went_well": self.what_went_well,
            "what_to_improve": self.what_to_improve,
            "lessons_learned": self.lessons_learned,
            "trade_quality_score": self.trade_quality_score,
            "should_have_traded": self.should_have_traded,
        }


@dataclass
class JournalEntry:
    """
    Entrée complète du journal de trading.

    Combine toutes les phases : pré-trade, exécution, gestion, résultat, post-analyse.
    """
    id: str
    ticker: str
    direction: TradeDirection
    status: TradeStatus

    # Phases du trade
    pre_trade: PreTradeAnalysis
    execution: Optional[TradeExecution] = None
    management: Optional[TradeManagement] = None
    result: Optional[TradeResult] = None
    post_analysis: Optional[PostTradeAnalysis] = None

    # Métadonnées
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    screenshot_urls: List[str] = field(default_factory=list)

    @property
    def is_winner(self) -> bool:
        """Le trade est-il gagnant ?"""
        return self.result is not None and self.result.net_pnl > 0

    @property
    def was_good_trade(self) -> bool:
        """
        Le trade était-il de qualité (indépendamment du PnL) ?

        Un trade perdant peut être un bon trade si le process a été respecté.
        Un trade gagnant peut être un mauvais trade si c'était de la chance.
        """
        if self.post_analysis is None:
            return False
        return (
            self.post_analysis.process_compliance == ProcessCompliance.FULL and
            len(self.post_analysis.mistakes) == 0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "direction": self.direction.value,
            "status": self.status.value,
            "pre_trade": self.pre_trade.to_dict(),
            "execution": self.execution.to_dict() if self.execution else None,
            "management": self.management.to_dict() if self.management else None,
            "result": self.result.to_dict() if self.result else None,
            "post_analysis": self.post_analysis.to_dict() if self.post_analysis else None,
            "is_winner": self.is_winner if self.result else None,
            "was_good_trade": self.was_good_trade,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }

    def to_readable_summary(self) -> str:
        """
        Génère un résumé lisible pour un néophyte.

        Format éducatif expliquant chaque aspect du trade.
        """
        lines = [
            "=" * 60,
            f"JOURNAL DE TRADE - {self.ticker}",
            "=" * 60,
            "",
            "📊 CONTEXTE DU MARCHÉ",
            "-" * 30,
            f"Régime de marché : {self.pre_trade.market_regime}",
            f"   → Cela signifie que le marché était en mode '{self.pre_trade.market_regime}'",
            f"Biais directionnel : {self.pre_trade.market_bias}",
            f"Type de setup : {self.pre_trade.setup_type}",
            "",
            f"📝 POURQUOI CE TRADE ?",
            "-" * 30,
            f"{self.pre_trade.trade_thesis}",
            "",
            f"Facteurs de confluence (éléments alignés) :",
        ]

        for factor in self.pre_trade.confluence_factors:
            lines.append(f"   ✓ {factor}")

        if self.execution:
            lines.extend([
                "",
                "💰 EXÉCUTION",
                "-" * 30,
                f"Direction : {'ACHAT (Long)' if self.direction == TradeDirection.LONG else 'VENTE (Short)'}",
                f"Prix d'entrée : {self.execution.entry_price}",
                f"Stop Loss : {self.execution.stop_loss}",
                f"   → Perte maximale acceptée si le trade échoue",
                f"Objectif : {self.execution.take_profit_1}",
                f"Risque : {self.execution.risk_percent:.1f}% du capital",
                f"   → On ne risque jamais plus de 1-2% par trade",
            ])

        if self.result:
            emoji = "✅" if self.is_winner else "❌"
            lines.extend([
                "",
                f"{emoji} RÉSULTAT",
                "-" * 30,
                f"PnL : {self.result.net_pnl:+.2f}€ ({self.result.pnl_percent:+.1f}%)",
                f"R-Multiple : {self.result.r_multiple:.1f}R",
                f"   → Un R-Multiple de 2 signifie qu'on a gagné 2x le risque initial",
                f"Raison de sortie : {self.result.exit_reason}",
            ])

        if self.post_analysis:
            lines.extend([
                "",
                "📈 ANALYSE POST-TRADE",
                "-" * 30,
                f"Respect du processus : {self.post_analysis.process_compliance.value}",
                f"Score de qualité : {self.post_analysis.trade_quality_score}/100",
                "",
                "Ce qui a bien fonctionné :",
            ])
            for item in self.post_analysis.what_went_well:
                lines.append(f"   ✓ {item}")

            if self.post_analysis.what_to_improve:
                lines.append("\nCe qui peut être amélioré :")
                for item in self.post_analysis.what_to_improve:
                    lines.append(f"   → {item}")

            if self.post_analysis.lessons_learned:
                lines.extend([
                    "",
                    "💡 LEÇON APPRISE",
                    f"{self.post_analysis.lessons_learned}",
                ])

        lines.extend([
            "",
            "=" * 60,
            "RAPPEL IMPORTANT :",
            "Le profit est un sous-produit d'un bon processus.",
            "Un trade perdant peut être un BON trade si le process est respecté.",
            "Un trade gagnant peut être un MAUVAIS trade si c'était de la chance.",
            "=" * 60,
        ])

        return "\n".join(lines)


@dataclass
class TradingJournalStats:
    """
    Statistiques globales du journal de trading.

    Permet de mesurer la progression et identifier les patterns.
    """
    total_entries: int = 0
    total_winners: int = 0
    total_losers: int = 0
    total_breakeven: int = 0

    # PnL
    total_profit: float = 0.0
    total_loss: float = 0.0
    net_pnl: float = 0.0

    # Qualité
    good_trades_count: int = 0  # Trades avec process respecté
    bad_trades_count: int = 0   # Trades avec erreurs
    average_quality_score: float = 0.0

    # Erreurs les plus fréquentes
    mistake_frequency: Dict[str, int] = field(default_factory=dict)
    most_common_mistake: str = ""

    # Par setup type
    stats_by_setup: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Streak
    current_streak: int = 0
    max_win_streak: int = 0
    max_loss_streak: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "win_rate": round(self.total_winners / self.total_entries * 100, 1) if self.total_entries > 0 else 0,
            "total_winners": self.total_winners,
            "total_losers": self.total_losers,
            "net_pnl": round(self.net_pnl, 2),
            "profit_factor": round(self.total_profit / self.total_loss, 2) if self.total_loss > 0 else 0,
            "good_trades_percent": round(self.good_trades_count / self.total_entries * 100, 1) if self.total_entries > 0 else 0,
            "average_quality_score": round(self.average_quality_score, 1),
            "most_common_mistake": self.most_common_mistake,
            "mistake_frequency": self.mistake_frequency,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
        }
