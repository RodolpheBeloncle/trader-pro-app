"""
Outil MCP pour le moteur de décision professionnel.

Fournit un accès au système de décision MCP complet :
- Analyse de structure de marché
- Gestion du risque professionnelle
- Journal de trading structuré

OUTILS:
    - pro_analyze: Analyse professionnelle complète (structure + technique + décision)
    - get_trade_setup: Génère un setup de trade avec sizing
    - calculate_position_size: Calcule la taille de position
    - get_market_structure: Analyse de structure détaillée
    - create_journal_entry: Crée une entrée de journal
"""

import json
import logging
from typing import List

from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
from src.application.services.technical_calculator import TechnicalCalculator
from src.application.services.market_structure_analyzer import MarketStructureAnalyzer
from src.application.services.pro_decision_engine import ProDecisionEngine
from src.domain.entities.risk_management import (
    RiskProfile,
    PositionSizeCalculation,
    RiskRewardAnalysis,
    KellyCalculation,
)
from src.domain.value_objects.ticker import Ticker
from src.config.constants import PERIOD_5_YEARS_DAYS

logger = logging.getLogger(__name__)


async def pro_analyze_tool(ticker: str, capital: float = 10000.0) -> str:
    """
    Analyse professionnelle complete avec decision de trading.

    Utilise le MCP (Mental/Cognitive/Decision Process) d'un trader pro.

    Args:
        ticker: Symbole boursier
        capital: Capital disponible pour le trading

    Returns:
        JSON avec l'analyse complete et la decision
    """
    try:
        provider = YahooFinanceProvider()
        calculator = TechnicalCalculator()
        structure_analyzer = MarketStructureAnalyzer()
        engine = ProDecisionEngine(
            provider, calculator, structure_analyzer,
            capital=capital,
            risk_profile=RiskProfile.MODERATE,
        )

        decision = await engine.analyze_and_decide(ticker)

        if not decision:
            return json.dumps({
                "error": f"Impossible d'analyser {ticker}",
            }, indent=2, ensure_ascii=False)

        result = decision.to_dict()

        # Ajouter un resume executif pour un neophyte
        result["executive_summary"] = _generate_executive_summary(decision)

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error in pro_analyze for {ticker}: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def get_market_structure_tool(ticker: str) -> str:
    """
    Analyse detaillee de la structure de marche.

    Retourne :
    - Regime de marche (tendance/range)
    - Swing points (HH/HL/LH/LL)
    - Zones de liquidite
    - Fair Value Gaps
    - Order Blocks

    Args:
        ticker: Symbole boursier

    Returns:
        JSON avec l'analyse de structure
    """
    try:
        provider = YahooFinanceProvider()
        structure_analyzer = MarketStructureAnalyzer()

        ticker_obj = Ticker(ticker)
        historical_data = await provider.get_historical_data(ticker_obj, PERIOD_5_YEARS_DAYS)

        if len(historical_data) < 100:
            return json.dumps({
                "error": f"Donnees insuffisantes pour {ticker}",
                "data_points": len(historical_data),
                "minimum_required": 100,
            }, indent=2)

        structure = await structure_analyzer.analyze(ticker, historical_data)

        if not structure:
            return json.dumps({
                "error": f"Impossible d'analyser la structure pour {ticker}"
            }, indent=2)

        result = structure.to_dict()

        # Ajouter des explications pour neophytes
        result["explanations"] = {
            "regime": _explain_regime(structure.regime.value),
            "structure_bias": _explain_bias(structure.structure_bias.value),
            "trading_bias": structure.trading_bias,
            "what_to_do": _generate_action_advice(structure),
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error getting market structure for {ticker}: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def calculate_position_size_tool(
    capital: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float,
) -> str:
    """
    Calcule la taille de position optimale.

    Applique la regle d'or : Ne jamais risquer plus de X% par trade.

    Args:
        capital: Capital total disponible
        risk_percent: Pourcentage de risque par trade (ex: 1.0 pour 1%)
        entry_price: Prix d'entree prevu
        stop_loss_price: Prix du stop loss

    Returns:
        JSON avec le calcul de position
    """
    try:
        calculation = PositionSizeCalculation(
            capital=capital,
            risk_per_trade_percent=risk_percent / 100,  # Convertir en decimal
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
        )

        result = calculation.to_dict()

        # Ajouter des explications
        result["explanations"] = {
            "rule": f"Avec {risk_percent}% de risque sur {capital}€, vous risquez {calculation.risk_amount:.2f}€",
            "distance_to_stop": f"Distance au stop: {calculation.risk_per_share:.2f}€ par action",
            "shares": f"Vous pouvez acheter {calculation.position_size_shares} actions",
            "total_investment": f"Investissement total: {calculation.position_value:.2f}€",
            "warning": "Ne jamais risquer plus de 2% par trade. Preferez 1% pour les debutants.",
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error calculating position size: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def calculate_risk_reward_tool(
    entry_price: float,
    stop_loss_price: float,
    target_price: float,
) -> str:
    """
    Calcule le ratio Risk/Reward d'un trade.

    Regle : Minimum 1:2 R/R pour compenser un win rate de 40%.

    Args:
        entry_price: Prix d'entree
        stop_loss_price: Prix du stop loss
        target_price: Prix cible

    Returns:
        JSON avec l'analyse R/R
    """
    try:
        analysis = RiskRewardAnalysis(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
        )

        result = analysis.to_dict()

        # Ajouter des explications
        result["explanations"] = {
            "interpretation": f"Pour 1€ risque, vous pouvez gagner {analysis.risk_reward_ratio:.1f}€",
            "quality": analysis.quality,
            "recommendation": "ACCEPTABLE" if analysis.is_acceptable else "A EVITER - R/R trop faible",
            "min_winrate_needed": f"Avec ce R/R, vous devez gagner {analysis.required_win_rate*100:.0f}% des trades pour etre rentable",
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error calculating R/R: {e}")
        return json.dumps({"error": str(e)}, indent=2)


async def calculate_kelly_tool(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> str:
    """
    Calcule le Kelly Criterion pour l'allocation optimale.

    ATTENTION : Kelly complet est trop agressif. Utilisez 1/4 ou 1/2 Kelly.

    Args:
        win_rate: Taux de reussite en pourcentage (ex: 45 pour 45%)
        avg_win: Gain moyen par trade gagnant
        avg_loss: Perte moyenne par trade perdant (valeur positive)

    Returns:
        JSON avec le calcul Kelly
    """
    try:
        kelly = KellyCalculation(
            win_rate=win_rate / 100,  # Convertir en decimal
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

        result = kelly.to_dict()

        # Ajouter des explications
        result["explanations"] = {
            "full_kelly": f"Kelly complet: {kelly.kelly_full*100:.1f}% - TROP AGRESSIF, ne pas utiliser",
            "half_kelly": f"Demi-Kelly: {kelly.kelly_half*100:.1f}% - Recommande pour traders experimentes",
            "quarter_kelly": f"Quart-Kelly: {kelly.kelly_quarter*100:.1f}% - Recommande pour debutants",
            "practical_advice": f"Risquez maximum {kelly.recommended_risk_percent*100:.1f}% par trade",
            "warning": "Kelly suppose que vos stats sont fiables (minimum 30+ trades)",
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Error calculating Kelly: {e}")
        return json.dumps({"error": str(e)}, indent=2)


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def _generate_executive_summary(decision) -> str:
    """Genere un resume executif de la decision."""
    lines = [
        "=" * 50,
        "RÉSUMÉ EXÉCUTIF",
        "=" * 50,
        "",
        f"Ticker: {decision.ticker}",
        f"Décision: {decision.summary}",
        "",
    ]

    if decision.should_trade and decision.trade_setup:
        setup = decision.trade_setup
        lines.extend([
            "SETUP DE TRADE:",
            f"  Direction: {setup.direction.upper()}",
            f"  Entrée: {setup.entry_price:.2f}",
            f"  Stop Loss: {setup.stop_loss_price:.2f}",
            f"  Target 1: {setup.target_1:.2f}",
            f"  Position: {setup.position_size} actions",
            f"  Risque: {setup.risk_amount:.2f}€",
            f"  Qualité: {setup.setup_quality}",
            "",
        ])

    lines.extend([
        "FACTEURS DE CONFLUENCE:",
    ])
    for factor in decision.confluence_factors:
        lines.append(f"  ✓ {factor}")

    if decision.warning_factors:
        lines.extend(["", "POINTS D'ATTENTION:"])
        for warning in decision.warning_factors:
            lines.append(f"  ⚠ {warning}")

    if decision.invalidation_factors:
        lines.extend(["", "CONDITIONS D'INVALIDATION:"])
        for inv in decision.invalidation_factors:
            lines.append(f"  ✗ {inv}")

    lines.extend([
        "",
        "=" * 50,
        "RAPPEL: Le profit est un sous-produit du process.",
        "Respectez TOUJOURS votre stop loss.",
        "=" * 50,
    ])

    return "\n".join(lines)


def _explain_regime(regime: str) -> str:
    """Explique le regime de marche pour un neophyte."""
    explanations = {
        "trending_up": "Le marché est en TENDANCE HAUSSIÈRE. Les prix font des hauts et des bas de plus en plus hauts. Favorisez les achats.",
        "trending_down": "Le marché est en TENDANCE BAISSIÈRE. Les prix font des hauts et des bas de plus en plus bas. Favorisez les ventes ou restez à l'écart.",
        "ranging": "Le marché est en RANGE (consolidation). Les prix oscillent entre un support et une résistance. Achetez le bas, vendez le haut.",
        "high_volatility": "VOLATILITÉ ÉLEVÉE. Le marché bouge beaucoup. Réduisez la taille de vos positions ou restez à l'écart.",
        "low_volatility": "VOLATILITÉ FAIBLE. Le marché est calme. Attention aux breakouts potentiels (explosions de volatilité).",
        "transitional": "MARCHÉ EN TRANSITION. La direction n'est pas claire. Attendez un signal plus net avant de trader.",
    }
    return explanations.get(regime, "Régime de marché non identifié.")


def _explain_bias(bias: str) -> str:
    """Explique le biais de structure pour un neophyte."""
    explanations = {
        "bullish": "Structure HAUSSIÈRE. Les acheteurs dominent. Cherchez des opportunités d'achat.",
        "bearish": "Structure BAISSIÈRE. Les vendeurs dominent. Cherchez des opportunités de vente ou évitez les achats.",
        "neutral": "Structure NEUTRE. Pas de direction claire. Attendez une cassure de structure.",
        "bullish_weakening": "Structure haussière qui S'AFFAIBLIT. Les acheteurs perdent du terrain. Prudence sur les achats.",
        "bearish_weakening": "Structure baissière qui S'AFFAIBLIT. Les vendeurs perdent du terrain. Prudence sur les ventes.",
    }
    return explanations.get(bias, "Biais non identifié.")


def _generate_action_advice(structure) -> str:
    """Genere un conseil d'action basé sur la structure."""
    if structure.choch_detected:
        return "⚠️ ATTENTION: Un changement de caractère (CHoCH) a été détecté. Le marché pourrait se retourner. Soyez prudent."

    if structure.regime.value == "trending_up" and structure.structure_bias.value == "bullish":
        return "✅ CONDITIONS FAVORABLES: Cherchez des pullbacks (replis) vers les zones de demande pour acheter."

    if structure.regime.value == "trending_down" and structure.structure_bias.value == "bearish":
        return "✅ CONDITIONS FAVORABLES (pour vente): Cherchez des rallyes vers les zones d'offre pour vendre."

    if structure.regime.value == "ranging":
        return "📊 RANGE: Achetez proche du support (bas du range), vendez proche de la résistance (haut du range)."

    if structure.regime.value == "transitional":
        return "⏳ ATTENDEZ: Le marché est en transition. Pas de trading recommandé pour l'instant."

    return "Analysez les facteurs de confluence avant de prendre une décision."
