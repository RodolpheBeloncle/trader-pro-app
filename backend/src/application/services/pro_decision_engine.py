"""
Moteur de décision professionnel (MCP - Mental/Cognitive/Decision Process).

Ce module implémente le processus décisionnel complet d'un trader professionnel :

1. CONTEXTE - Analyse du régime de marché
2. SETUP - Validation de la configuration
3. RISQUE - Calcul et validation
4. EXÉCUTION - Timing et entrée
5. GESTION - Règles de sortie
6. POST-ANALYSE - Journal et amélioration

RÉFÉRENCES :
- Van Tharp - Trade Your Way to Financial Freedom
- Mark Douglas - Trading in the Zone
- Brett Steenbarger - The Daily Trading Coach
- Adam Grimes - The Art and Science of Technical Analysis

PRINCIPE FONDAMENTAL :
> "Décision = Information × Contexte × Probabilité × Gestion du risque"
> "Le profit est un sous-produit du process, jamais l'objectif direct."
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import uuid

from src.application.interfaces.stock_data_provider import StockDataProvider, HistoricalDataPoint
from src.application.services.technical_calculator import TechnicalCalculator
from src.application.services.market_structure_analyzer import MarketStructureAnalyzer
from src.domain.entities.technical_analysis import TechnicalIndicators, Signal, Trend
from src.domain.entities.market_structure import (
    MarketRegime,
    StructureBias,
    MarketStructureAnalysis,
)
from src.domain.entities.risk_management import (
    RiskProfile,
    TradeStatistics,
    PositionSizeCalculation,
    KellyCalculation,
    RiskRewardAnalysis,
    TradeSetup,
    PortfolioRiskAnalysis,
)
from src.domain.entities.trading_journal import (
    JournalEntry,
    PreTradeAnalysis,
    TradeDirection,
    TradeStatus,
)
from src.domain.value_objects.ticker import Ticker
from src.config.constants import PERIOD_5_YEARS_DAYS

logger = logging.getLogger(__name__)


class DecisionType(str):
    """Type de décision du moteur."""
    TRADE = "trade"
    NO_TRADE = "no_trade"
    WAIT = "wait"


@dataclass
class TradeDecision:
    """
    Décision de trading complète générée par le moteur.

    Contient TOUS les éléments nécessaires pour prendre une décision éclairée.
    """
    # Décision
    decision_type: str  # "trade", "no_trade", "wait"
    ticker: str
    direction: Optional[str]  # "long", "short"
    confidence: float  # 0-100

    # Contexte
    market_structure: MarketStructureAnalysis
    technical_indicators: TechnicalIndicators

    # Setup (si décision = trade)
    trade_setup: Optional[TradeSetup] = None

    # Raisons
    decision_rationale: str = ""
    confluence_factors: List[str] = field(default_factory=list)
    warning_factors: List[str] = field(default_factory=list)
    invalidation_factors: List[str] = field(default_factory=list)

    # Checklist de validation
    checklist: Dict[str, bool] = field(default_factory=dict)
    checklist_passed: bool = False

    # Pour le journal
    pre_trade_analysis: Optional[PreTradeAnalysis] = None

    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def should_trade(self) -> bool:
        """Doit-on prendre ce trade ?"""
        return self.decision_type == "trade" and self.checklist_passed

    @property
    def summary(self) -> str:
        """Résumé de la décision."""
        if self.decision_type == "no_trade":
            return f"❌ NO TRADE - {self.decision_rationale}"
        elif self.decision_type == "wait":
            return f"⏳ WAIT - {self.decision_rationale}"
        else:
            direction = "LONG" if self.direction == "long" else "SHORT"
            return f"✅ {direction} - Confiance: {self.confidence:.0f}% - {self.decision_rationale}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "ticker": self.ticker,
            "direction": self.direction,
            "confidence": round(self.confidence, 1),
            "summary": self.summary,
            "should_trade": self.should_trade,
            "market_structure": self.market_structure.to_dict(),
            "technical_indicators": self.technical_indicators.to_dict(),
            "trade_setup": self.trade_setup.to_dict() if self.trade_setup else None,
            "decision_rationale": self.decision_rationale,
            "confluence_factors": self.confluence_factors,
            "warning_factors": self.warning_factors,
            "invalidation_factors": self.invalidation_factors,
            "checklist": self.checklist,
            "checklist_passed": self.checklist_passed,
            "generated_at": self.generated_at.isoformat(),
        }


class ProDecisionEngine:
    """
    Moteur de décision professionnel.

    Implémente le MCP (Mental/Cognitive/Decision Process) d'un trader institutionnel.
    Ne cherche pas à prédire, mais à exploiter des asymétries de probabilité.
    """

    # Règles strictes
    MIN_RISK_REWARD = 2.0      # Minimum 1:2 R/R
    MAX_RISK_PERCENT = 0.02    # Maximum 2% par trade
    MIN_CONFLUENCE = 3         # Minimum 3 facteurs de confluence

    def __init__(
        self,
        data_provider: StockDataProvider,
        technical_calculator: TechnicalCalculator,
        structure_analyzer: MarketStructureAnalyzer,
        capital: float = 10000.0,
        risk_profile: RiskProfile = RiskProfile.MODERATE,
    ):
        """
        Initialise le moteur de décision.

        Args:
            data_provider: Provider de données
            technical_calculator: Calculateur d'indicateurs techniques
            structure_analyzer: Analyseur de structure de marché
            capital: Capital disponible
            risk_profile: Profil de risque
        """
        self._provider = data_provider
        self._calculator = technical_calculator
        self._structure_analyzer = structure_analyzer
        self._capital = capital
        self._risk_profile = risk_profile

        # Statistiques de trading (pour calculer l'espérance)
        self._stats = TradeStatistics()

    async def analyze_and_decide(
        self,
        ticker: str,
    ) -> TradeDecision:
        """
        Analyse complète et décision de trading.

        Suit le processus MCP en 6 étapes :
        1. Contexte
        2. Setup
        3. Risque
        4. Exécution
        5. Gestion
        6. Validation

        Args:
            ticker: Symbole de l'actif

        Returns:
            Décision de trading complète
        """
        logger.info(f"Analyzing {ticker} with Pro Decision Engine")

        try:
            # 1. RÉCUPÉRATION DES DONNÉES
            ticker_obj = Ticker(ticker)
            historical_data = await self._provider.get_historical_data(
                ticker_obj, PERIOD_5_YEARS_DAYS
            )

            if len(historical_data) < 100:
                return self._create_no_trade_decision(
                    ticker,
                    "Données historiques insuffisantes",
                    None, None
                )

            # 2. ANALYSE DE STRUCTURE DE MARCHÉ
            structure = await self._structure_analyzer.analyze(ticker, historical_data)
            if not structure:
                return self._create_no_trade_decision(
                    ticker,
                    "Impossible d'analyser la structure de marché",
                    None, None
                )

            # 3. ANALYSE TECHNIQUE
            technical = await self._calculator.calculate_all(ticker, historical_data)
            if not technical:
                return self._create_no_trade_decision(
                    ticker,
                    "Impossible de calculer les indicateurs techniques",
                    structure, None
                )

            # 4. ÉTAPE 1 - ÉVALUATION DU CONTEXTE
            context_ok, context_issues = self._evaluate_context(structure)
            if not context_ok:
                return self._create_wait_decision(
                    ticker,
                    f"Contexte défavorable: {', '.join(context_issues)}",
                    structure, technical
                )

            # 5. ÉTAPE 2 - IDENTIFICATION DU SETUP
            setup_found, direction, confluence = self._identify_setup(
                structure, technical, historical_data[-1].close
            )

            if not setup_found:
                return self._create_no_trade_decision(
                    ticker,
                    "Pas de setup valide identifié",
                    structure, technical
                )

            if len(confluence) < self.MIN_CONFLUENCE:
                return self._create_wait_decision(
                    ticker,
                    f"Confluence insuffisante ({len(confluence)}/{self.MIN_CONFLUENCE})",
                    structure, technical
                )

            # 6. ÉTAPE 3 - CALCUL DU RISQUE
            current_price = historical_data[-1].close
            stop_loss = self._calculate_stop_loss(
                direction, current_price, structure, technical
            )
            target = self._calculate_target(
                direction, current_price, structure, technical
            )

            rr_analysis = RiskRewardAnalysis(
                entry_price=current_price,
                stop_loss_price=stop_loss,
                target_price=target,
            )

            if not rr_analysis.is_acceptable:
                return self._create_no_trade_decision(
                    ticker,
                    f"R/R insuffisant ({rr_analysis.risk_reward_ratio:.1f} < {self.MIN_RISK_REWARD})",
                    structure, technical
                )

            # 7. CALCUL DE LA POSITION
            risk_percent = self._get_risk_percent()
            position_calc = PositionSizeCalculation(
                capital=self._capital,
                risk_per_trade_percent=risk_percent,
                entry_price=current_price,
                stop_loss_price=stop_loss,
            )

            # 8. CRÉATION DU SETUP DE TRADE
            trade_setup = TradeSetup(
                ticker=ticker,
                direction=direction,
                entry_price=current_price,
                stop_loss_price=stop_loss,
                target_1=target,
                target_2=self._calculate_target_2(direction, current_price, structure),
                position_size=position_calc.position_size_shares,
                position_value=position_calc.position_value,
                risk_amount=position_calc.risk_amount,
                risk_reward=rr_analysis,
                setup_quality=rr_analysis.quality,
                setup_type=self._get_setup_type(structure, technical),
                confluence_factors=confluence,
                rationale=self._generate_rationale(direction, structure, technical, confluence),
            )

            # 9. VALIDATION CHECKLIST
            checklist = self._validate_checklist(
                structure, technical, rr_analysis, confluence
            )
            checklist_passed = all(checklist.values())

            # 10. CALCUL DE LA CONFIANCE
            confidence = self._calculate_confidence(
                structure, technical, rr_analysis, len(confluence), checklist_passed
            )

            # 11. WARNINGS ET INVALIDATIONS
            warnings = self._identify_warnings(structure, technical)
            invalidations = self._identify_invalidations(structure, technical, direction)

            # 12. PRÉ-TRADE ANALYSIS POUR LE JOURNAL
            pre_trade = PreTradeAnalysis(
                market_regime=structure.regime.value,
                market_bias=structure.structure_bias.value,
                session=self._get_current_session(),
                volatility_state=self._get_volatility_state(technical.atr_percent),
                setup_type=trade_setup.setup_type,
                timeframe="D",
                confluence_factors=confluence,
                invalidation_level=stop_loss,
                invalidation_reason="Break of structure",
                trade_thesis=trade_setup.rationale,
                expected_move=f"Target {target:.2f} ({rr_analysis.reward_percent:.1f}%)",
                checklist_completed=checklist_passed,
                checklist_items=checklist,
            )

            # 13. DÉCISION FINALE
            decision_type = "trade" if checklist_passed and confidence >= 60 else "wait"

            return TradeDecision(
                decision_type=decision_type,
                ticker=ticker,
                direction=direction,
                confidence=confidence,
                market_structure=structure,
                technical_indicators=technical,
                trade_setup=trade_setup,
                decision_rationale=trade_setup.rationale if checklist_passed else "Checklist non validée",
                confluence_factors=confluence,
                warning_factors=warnings,
                invalidation_factors=invalidations,
                checklist=checklist,
                checklist_passed=checklist_passed,
                pre_trade_analysis=pre_trade,
            )

        except Exception as e:
            logger.exception(f"Error in Pro Decision Engine for {ticker}: {e}")
            return self._create_no_trade_decision(
                ticker,
                f"Erreur d'analyse: {str(e)}",
                None, None
            )

    def _evaluate_context(
        self,
        structure: MarketStructureAnalysis
    ) -> Tuple[bool, List[str]]:
        """
        Évalue si le contexte de marché est favorable au trading.

        Règles :
        - Pas de trading en régime transitionnel
        - Pas de trading en volatilité extrême (sauf stratégies spécifiques)
        - Pas de trading sans biais clair
        """
        issues = []

        if structure.regime == MarketRegime.TRANSITIONAL:
            issues.append("Marché en transition")

        if structure.regime == MarketRegime.HIGH_VOLATILITY:
            issues.append("Volatilité excessive")

        if structure.structure_bias == StructureBias.NEUTRAL:
            issues.append("Pas de biais directionnel clair")

        if structure.choch_detected:
            issues.append("CHoCH détecté - potentiel retournement")

        return len(issues) == 0, issues

    def _identify_setup(
        self,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators,
        current_price: float
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Identifie si un setup valide existe.

        Retourne (setup_found, direction, confluence_factors)
        """
        confluence = []
        direction = None

        # 1. BIAIS DE STRUCTURE
        if structure.structure_bias == StructureBias.BULLISH:
            direction = "long"
            confluence.append("Structure haussière (HH/HL)")
        elif structure.structure_bias == StructureBias.BEARISH:
            direction = "short"
            confluence.append("Structure baissière (LH/LL)")
        else:
            return False, None, []

        # 2. RÉGIME DE MARCHÉ
        if structure.regime == MarketRegime.TRENDING_UP and direction == "long":
            confluence.append("Régime tendanciel haussier")
        elif structure.regime == MarketRegime.TRENDING_DOWN and direction == "short":
            confluence.append("Régime tendanciel baissier")

        # 3. INDICATEURS TECHNIQUES
        if direction == "long":
            if technical.rsi.value < 40:
                confluence.append("RSI survendu (rebond potentiel)")
            if technical.macd.histogram > 0:
                confluence.append("MACD positif")
            if technical.moving_averages.trend in [Trend.UPTREND, Trend.STRONG_UPTREND]:
                confluence.append("Moyennes mobiles alignées haussier")
            if technical.bollinger.percent_b < 0.3:
                confluence.append("Prix proche du support Bollinger")
        else:
            if technical.rsi.value > 60:
                confluence.append("RSI suracheté (correction potentielle)")
            if technical.macd.histogram < 0:
                confluence.append("MACD négatif")
            if technical.moving_averages.trend in [Trend.DOWNTREND, Trend.STRONG_DOWNTREND]:
                confluence.append("Moyennes mobiles alignées baissier")
            if technical.bollinger.percent_b > 0.7:
                confluence.append("Prix proche de la résistance Bollinger")

        # 4. FAIR VALUE GAPS
        unfilled_fvgs = [fvg for fvg in structure.fair_value_gaps if not fvg.filled]
        if direction == "long":
            bullish_fvgs = [fvg for fvg in unfilled_fvgs if fvg.is_bullish and current_price > fvg.top]
            if bullish_fvgs:
                confluence.append("FVG haussier comme support potentiel")
        else:
            bearish_fvgs = [fvg for fvg in unfilled_fvgs if not fvg.is_bullish and current_price < fvg.bottom]
            if bearish_fvgs:
                confluence.append("FVG baissier comme résistance potentielle")

        # 5. ORDER BLOCKS
        if direction == "long" and structure.nearest_bullish_ob:
            if current_price <= structure.nearest_bullish_ob.high * 1.02:
                confluence.append("Proche d'un Order Block haussier")
        elif direction == "short" and structure.nearest_bearish_ob:
            if current_price >= structure.nearest_bearish_ob.low * 0.98:
                confluence.append("Proche d'un Order Block baissier")

        # 6. VOLUME
        if technical.volume.volume_confirmation:
            confluence.append("Volume confirme le mouvement")

        return len(confluence) >= 2, direction, confluence

    def _calculate_stop_loss(
        self,
        direction: str,
        current_price: float,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators
    ) -> float:
        """
        Calcule le stop loss logique (structurel).

        Le stop doit être placé là où le setup est INVALIDÉ, pas arbitrairement.
        """
        atr = structure.atr

        if direction == "long":
            # Stop sous le dernier swing low ou support
            if structure.last_swing_low:
                structural_stop = structure.last_swing_low.price - (atr * 0.5)
            else:
                structural_stop = current_price * 0.95  # -5% par défaut

            # Ne pas dépasser 3 ATR
            max_stop = current_price - (atr * 3)
            return max(structural_stop, max_stop)

        else:  # short
            # Stop au-dessus du dernier swing high ou résistance
            if structure.last_swing_high:
                structural_stop = structure.last_swing_high.price + (atr * 0.5)
            else:
                structural_stop = current_price * 1.05  # +5% par défaut

            # Ne pas dépasser 3 ATR
            max_stop = current_price + (atr * 3)
            return min(structural_stop, max_stop)

    def _calculate_target(
        self,
        direction: str,
        current_price: float,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators
    ) -> float:
        """
        Calcule l'objectif de prix (target 1).

        Basé sur :
        - Zones de liquidité
        - Fair Value Gaps à combler
        - Extension de Fibonacci
        """
        if direction == "long":
            # Cible = prochaine zone de liquidité ou swing high
            if structure.nearest_buy_side_liquidity:
                return structure.nearest_buy_side_liquidity
            elif structure.last_swing_high:
                return structure.last_swing_high.price
            else:
                return current_price * 1.05  # +5%
        else:
            # Cible = prochaine zone de liquidité ou swing low
            if structure.nearest_sell_side_liquidity:
                return structure.nearest_sell_side_liquidity
            elif structure.last_swing_low:
                return structure.last_swing_low.price
            else:
                return current_price * 0.95  # -5%

    def _calculate_target_2(
        self,
        direction: str,
        current_price: float,
        structure: MarketStructureAnalysis
    ) -> Optional[float]:
        """Calcule le target 2 (extension)."""
        if direction == "long":
            return current_price * 1.10  # +10%
        else:
            return current_price * 0.90  # -10%

    def _get_risk_percent(self) -> float:
        """Retourne le % de risque selon le profil."""
        risk_map = {
            RiskProfile.CONSERVATIVE: 0.005,    # 0.5%
            RiskProfile.MODERATE: 0.01,         # 1%
            RiskProfile.AGGRESSIVE: 0.02,       # 2%
            RiskProfile.VERY_AGGRESSIVE: 0.03,  # 3%
        }
        return risk_map.get(self._risk_profile, 0.01)

    def _get_setup_type(
        self,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators
    ) -> str:
        """Identifie le type de setup."""
        if structure.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            if technical.rsi.value < 40 or technical.rsi.value > 60:
                return "pullback_in_trend"
            return "trend_continuation"

        if structure.regime == MarketRegime.RANGING:
            if technical.bollinger.percent_b < 0.2:
                return "range_support_bounce"
            elif technical.bollinger.percent_b > 0.8:
                return "range_resistance_fade"
            return "range_breakout_watch"

        return "undefined"

    def _generate_rationale(
        self,
        direction: str,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators,
        confluence: List[str]
    ) -> str:
        """Génère la justification du trade."""
        dir_text = "achat" if direction == "long" else "vente"
        return (
            f"Setup de {dir_text} basé sur {len(confluence)} facteurs de confluence. "
            f"Structure {structure.structure_bias.value}, "
            f"régime {structure.regime.value}, "
            f"confiance technique {technical.confidence_level}. "
            f"Le risque est défini par la structure, pas par un niveau arbitraire."
        )

    def _validate_checklist(
        self,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators,
        rr_analysis: RiskRewardAnalysis,
        confluence: List[str]
    ) -> Dict[str, bool]:
        """
        Valide la checklist pré-trade.

        Toutes les cases doivent être cochées pour trader.
        """
        return {
            "context_clear": structure.regime != MarketRegime.TRANSITIONAL,
            "structure_defined": structure.structure_bias != StructureBias.NEUTRAL,
            "no_choch": not structure.choch_detected,
            "risk_reward_ok": rr_analysis.is_acceptable,
            "confluence_sufficient": len(confluence) >= self.MIN_CONFLUENCE,
            "not_overbought_oversold_extreme": 20 < technical.rsi.value < 80,
            "volume_confirms": technical.volume.volume_confirmation,
        }

    def _calculate_confidence(
        self,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators,
        rr_analysis: RiskRewardAnalysis,
        confluence_count: int,
        checklist_passed: bool
    ) -> float:
        """Calcule le niveau de confiance dans la décision."""
        confidence = 50.0

        # Structure
        if structure.structure_bias in [StructureBias.BULLISH, StructureBias.BEARISH]:
            confidence += 10

        # Régime confiance
        confidence += structure.regime_confidence * 0.2

        # R/R
        if rr_analysis.risk_reward_ratio >= 3:
            confidence += 15
        elif rr_analysis.risk_reward_ratio >= 2:
            confidence += 10

        # Confluence
        confidence += min(20, confluence_count * 4)

        # Checklist
        if checklist_passed:
            confidence += 10

        # Technique
        if technical.confidence_level == "Haute":
            confidence += 10

        return min(95, confidence)

    def _identify_warnings(
        self,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators
    ) -> List[str]:
        """Identifie les signaux d'alerte."""
        warnings = []

        if technical.rsi.value > 70:
            warnings.append("RSI en zone de surachat")
        elif technical.rsi.value < 30:
            warnings.append("RSI en zone de survente")

        if structure.structure_bias in [StructureBias.BULLISH_WEAKENING, StructureBias.BEARISH_WEAKENING]:
            warnings.append("Structure qui s'affaiblit")

        if not technical.volume.volume_confirmation:
            warnings.append("Volume ne confirme pas")

        if technical.atr_percent > 5:
            warnings.append("Volatilité élevée (ATR > 5%)")

        return warnings

    def _identify_invalidations(
        self,
        structure: MarketStructureAnalysis,
        technical: TechnicalIndicators,
        direction: Optional[str]
    ) -> List[str]:
        """Identifie les conditions d'invalidation du setup."""
        invalidations = []

        if direction == "long":
            if structure.last_swing_low:
                invalidations.append(f"Cassure sous {structure.last_swing_low.price:.2f}")
            invalidations.append("CHoCH baissier")
        elif direction == "short":
            if structure.last_swing_high:
                invalidations.append(f"Cassure au-dessus de {structure.last_swing_high.price:.2f}")
            invalidations.append("CHoCH haussier")

        return invalidations

    def _get_current_session(self) -> str:
        """Retourne la session de trading actuelle."""
        hour = datetime.now().hour
        if 0 <= hour < 8:
            return "asian"
        elif 8 <= hour < 14:
            return "london"
        else:
            return "new_york"

    def _get_volatility_state(self, atr_percent: float) -> str:
        """Retourne l'état de volatilité."""
        if atr_percent > 4:
            return "high"
        elif atr_percent < 1.5:
            return "low"
        return "normal"

    def _create_no_trade_decision(
        self,
        ticker: str,
        reason: str,
        structure: Optional[MarketStructureAnalysis],
        technical: Optional[TechnicalIndicators]
    ) -> TradeDecision:
        """Crée une décision NO TRADE."""
        return TradeDecision(
            decision_type="no_trade",
            ticker=ticker,
            direction=None,
            confidence=0,
            market_structure=structure,
            technical_indicators=technical,
            decision_rationale=reason,
            invalidation_factors=[reason],
            checklist={},
            checklist_passed=False,
        )

    def _create_wait_decision(
        self,
        ticker: str,
        reason: str,
        structure: Optional[MarketStructureAnalysis],
        technical: Optional[TechnicalIndicators]
    ) -> TradeDecision:
        """Crée une décision WAIT."""
        return TradeDecision(
            decision_type="wait",
            ticker=ticker,
            direction=None,
            confidence=30,
            market_structure=structure,
            technical_indicators=technical,
            decision_rationale=reason,
            warning_factors=[reason],
            checklist={},
            checklist_passed=False,
        )

    def create_journal_entry(self, decision: TradeDecision) -> JournalEntry:
        """
        Crée une entrée de journal à partir d'une décision.

        Permet de tracker le trade avant, pendant et après.
        """
        direction = TradeDirection.LONG if decision.direction == "long" else TradeDirection.SHORT

        return JournalEntry(
            id=str(uuid.uuid4()),
            ticker=decision.ticker,
            direction=direction,
            status=TradeStatus.PLANNED if decision.should_trade else TradeStatus.CANCELLED,
            pre_trade=decision.pre_trade_analysis or PreTradeAnalysis(
                market_regime=decision.market_structure.regime.value if decision.market_structure else "unknown",
                market_bias=decision.market_structure.structure_bias.value if decision.market_structure else "unknown",
                session=self._get_current_session(),
                volatility_state="unknown",
                setup_type="unknown",
                timeframe="D",
            ),
        )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_pro_decision_engine(
    data_provider: StockDataProvider,
    technical_calculator: TechnicalCalculator,
    structure_analyzer: MarketStructureAnalyzer,
    capital: float = 10000.0,
    risk_profile: RiskProfile = RiskProfile.MODERATE,
) -> ProDecisionEngine:
    """Factory function pour créer le moteur de décision pro."""
    return ProDecisionEngine(
        data_provider=data_provider,
        technical_calculator=technical_calculator,
        structure_analyzer=structure_analyzer,
        capital=capital,
        risk_profile=risk_profile,
    )
