"""
Entités pour les portefeuilles orientés revenus (Income Portfolio).

Contient les modèles de domaine pour:
- Analyse d'actifs à revenus (BDC, Covered Call, CEF, mREIT, Cash-like)
- Simulation de revenus passifs
- Configuration de backtest
- Résultats de backtest

ARCHITECTURE:
- Couche DOMAINE
- Indépendant de l'infrastructure
- Value Objects immuables
- Entités avec identité

UTILISATION:
    from src.domain.entities.income_portfolio import (
        IncomeAssetAnalysis,
        IncomeCategory,
        BacktestConfig,
        BacktestResult,
    )
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Literal, Optional
from enum import Enum
from decimal import Decimal


class IncomeCategory(str, Enum):
    """Catégories d'actifs à revenus."""
    BDC = "bdc"
    """Business Development Companies (ARCC, MAIN, HTGC...)"""

    COVERED_CALL = "covered_call"
    """ETFs Covered Call (JEPI, JEPQ, DIVO...)"""

    CEF = "cef"
    """Closed-End Funds (BST, UTF, PDI...)"""

    MREIT = "mreit"
    """Mortgage REITs (AGNC, NLY, STWD...)"""

    CASH_LIKE = "cash_like"
    """T-Bills et Money Market (SGOV, BIL, SHV...)"""

    DIVIDEND_GROWTH = "dividend_growth"
    """Actions à dividendes croissants (SCHD, VIG...)"""

    BONDS = "bonds"
    """Obligations (AGG, BND, TLT...)"""


class DistributionFrequency(str, Enum):
    """Fréquence de distribution des dividendes."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    VARIABLE = "variable"


@dataclass
class YieldMetrics:
    """
    Métriques de rendement pour un actif à revenus.
    """
    current_yield: float
    """Rendement actuel en %."""

    trailing_12m_yield: Optional[float] = None
    """Rendement sur 12 mois glissants."""

    sec_yield: Optional[float] = None
    """SEC 30-day yield (pour ETFs)."""

    distribution_rate: Optional[float] = None
    """Taux de distribution (peut différer du yield)."""

    yield_on_cost: Optional[float] = None
    """Rendement sur coût d'achat."""

    monthly_income_per_1000: Optional[float] = None
    """Revenu mensuel estimé pour 1000$ investis."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "current_yield": round(self.current_yield, 2),
            "trailing_12m_yield": round(self.trailing_12m_yield, 2) if self.trailing_12m_yield else None,
            "sec_yield": round(self.sec_yield, 2) if self.sec_yield else None,
            "distribution_rate": round(self.distribution_rate, 2) if self.distribution_rate else None,
            "yield_on_cost": round(self.yield_on_cost, 2) if self.yield_on_cost else None,
            "monthly_income_per_1000": round(self.monthly_income_per_1000, 2) if self.monthly_income_per_1000 else None,
        }


@dataclass
class DividendInfo:
    """
    Informations sur les dividendes d'un actif.
    """
    ex_dividend_date: Optional[date] = None
    """Prochaine date ex-dividende."""

    payment_date: Optional[date] = None
    """Prochaine date de paiement."""

    last_dividend_amount: Optional[float] = None
    """Montant du dernier dividende."""

    annual_dividend: Optional[float] = None
    """Dividende annuel total."""

    frequency: DistributionFrequency = DistributionFrequency.QUARTERLY
    """Fréquence de distribution."""

    payout_ratio: Optional[float] = None
    """Ratio de distribution (dividend / earnings)."""

    dividend_growth_5y: Optional[float] = None
    """Croissance des dividendes sur 5 ans (CAGR)."""

    consecutive_years: Optional[int] = None
    """Années consécutives de dividendes."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "ex_dividend_date": self.ex_dividend_date.isoformat() if self.ex_dividend_date else None,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "last_dividend_amount": round(self.last_dividend_amount, 4) if self.last_dividend_amount else None,
            "annual_dividend": round(self.annual_dividend, 4) if self.annual_dividend else None,
            "frequency": self.frequency.value,
            "payout_ratio": round(self.payout_ratio, 2) if self.payout_ratio else None,
            "dividend_growth_5y": round(self.dividend_growth_5y, 2) if self.dividend_growth_5y else None,
            "consecutive_years": self.consecutive_years,
        }


@dataclass
class IncomeAssetAnalysis:
    """
    Analyse complète d'un actif à revenus.
    """
    ticker: str
    """Symbole de l'actif."""

    name: str
    """Nom complet."""

    category: IncomeCategory
    """Catégorie d'actif income."""

    current_price: float
    """Prix actuel."""

    yield_metrics: YieldMetrics
    """Métriques de rendement."""

    dividend_info: DividendInfo
    """Informations sur les dividendes."""

    # Scores (0-100)
    yield_score: int = 0
    """Score basé sur le rendement."""

    stability_score: int = 0
    """Score de stabilité des distributions."""

    growth_score: int = 0
    """Score de croissance des dividendes."""

    risk_score: int = 0
    """Score de risque (100 = moins risqué)."""

    overall_income_score: int = 0
    """Score global orienté revenus."""

    # CEF spécifique
    nav: Optional[float] = None
    """Net Asset Value (pour CEF)."""

    nav_discount: Optional[float] = None
    """Discount/Premium par rapport à la NAV (en %)."""

    # Métriques additionnelles
    volatility: Optional[float] = None
    """Volatilité annualisée."""

    expense_ratio: Optional[float] = None
    """Ratio de frais (pour ETF/CEF)."""

    aum: Optional[float] = None
    """Actifs sous gestion."""

    recommendation: str = ""
    """Recommandation textuelle."""

    analyzed_at: datetime = field(default_factory=datetime.now)
    """Horodatage de l'analyse."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation JSON."""
        return {
            "ticker": self.ticker,
            "name": self.name,
            "category": self.category.value,
            "current_price": round(self.current_price, 2),
            "yield_metrics": self.yield_metrics.to_dict(),
            "dividend_info": self.dividend_info.to_dict(),
            "scores": {
                "yield_score": self.yield_score,
                "stability_score": self.stability_score,
                "growth_score": self.growth_score,
                "risk_score": self.risk_score,
                "overall_income_score": self.overall_income_score,
            },
            "nav": round(self.nav, 2) if self.nav else None,
            "nav_discount": round(self.nav_discount, 2) if self.nav_discount else None,
            "volatility": round(self.volatility, 2) if self.volatility else None,
            "expense_ratio": round(self.expense_ratio, 3) if self.expense_ratio else None,
            "aum": self.aum,
            "recommendation": self.recommendation,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class RebalanceOrder:
    """
    Un ordre de rebalancement.
    """
    ticker: str
    """Ticker de l'actif."""

    action: Literal["buy", "sell"]
    """Type d'action."""

    shares: float
    """Nombre d'actions."""

    amount: float
    """Montant en devise."""

    current_weight: float
    """Poids actuel dans le portefeuille (%)."""

    target_weight: float
    """Poids cible (%)."""

    drift: float
    """Écart par rapport à la cible (%)."""

    reason: str = ""
    """Raison de l'ordre."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "ticker": self.ticker,
            "action": self.action,
            "shares": round(self.shares, 4),
            "amount": round(self.amount, 2),
            "current_weight": round(self.current_weight, 2),
            "target_weight": round(self.target_weight, 2),
            "drift": round(self.drift, 2),
            "reason": self.reason,
        }


@dataclass
class RebalanceResult:
    """
    Résultat du calcul de rebalancement.
    """
    needs_rebalancing: bool
    """True si le portfolio a besoin de rebalancement."""

    total_value: float
    """Valeur totale du portfolio."""

    cash_available: float
    """Cash disponible."""

    drift_analysis: List[Dict]
    """Analyse du drift par position."""

    sell_orders: List[RebalanceOrder]
    """Ordres de vente."""

    buy_orders: List[RebalanceOrder]
    """Ordres d'achat."""

    estimated_fees: float
    """Frais estimés."""

    tax_loss_harvesting: List[Dict]
    """Opportunités de tax-loss harvesting."""

    summary: str = ""
    """Résumé textuel."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "needs_rebalancing": self.needs_rebalancing,
            "total_value": round(self.total_value, 2),
            "cash_available": round(self.cash_available, 2),
            "drift_analysis": self.drift_analysis,
            "sell_orders": [o.to_dict() for o in self.sell_orders],
            "buy_orders": [o.to_dict() for o in self.buy_orders],
            "estimated_fees": round(self.estimated_fees, 2),
            "tax_loss_harvesting": self.tax_loss_harvesting,
            "summary": self.summary,
        }


@dataclass
class IncomeSimulationResult:
    """
    Résultat d'une simulation de revenus passifs.
    """
    initial_value: float
    """Valeur initiale du portfolio."""

    current_annual_income: float
    """Revenu annuel actuel."""

    projected_value: float
    """Valeur projetée à la fin de la période."""

    projected_annual_income: float
    """Revenu annuel projeté."""

    projected_monthly_income: float
    """Revenu mensuel projeté."""

    yield_on_cost: float
    """Rendement sur coût à la fin."""

    total_contributions: float
    """Total des contributions."""

    total_dividends_received: float
    """Total des dividendes reçus."""

    drip_impact: float
    """Impact du DRIP (gain additionnel)."""

    sustainable_withdrawal: float
    """Retrait mensuel soutenable (règle 4%)."""

    yearly_projections: List[Dict]
    """Projections année par année."""

    assumptions: Dict
    """Hypothèses utilisées."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "initial_value": round(self.initial_value, 2),
            "current_annual_income": round(self.current_annual_income, 2),
            "projected_value": round(self.projected_value, 2),
            "projected_annual_income": round(self.projected_annual_income, 2),
            "projected_monthly_income": round(self.projected_monthly_income, 2),
            "yield_on_cost": round(self.yield_on_cost, 2),
            "total_contributions": round(self.total_contributions, 2),
            "total_dividends_received": round(self.total_dividends_received, 2),
            "drip_impact": round(self.drip_impact, 2),
            "sustainable_withdrawal": round(self.sustainable_withdrawal, 2),
            "yearly_projections": self.yearly_projections,
            "assumptions": self.assumptions,
        }


# =============================================================================
# BACKTEST ENTITIES
# =============================================================================

@dataclass
class BacktestConfig:
    """
    Configuration pour un backtest de portfolio.
    """
    allocation: Dict[str, float]
    """Allocation cible par ticker (en %)."""

    start_date: date
    """Date de début du backtest."""

    end_date: date = field(default_factory=date.today)
    """Date de fin du backtest."""

    initial_capital: float = 10000.0
    """Capital initial."""

    monthly_contribution: float = 0.0
    """Contribution mensuelle."""

    risk_off_enabled: bool = True
    """Activer le mode Risk-Off automatique."""

    risk_off_trigger: str = "combined"
    """Trigger pour Risk-Off: hyg_lqd_below_sma50, vix_above_25, combined."""

    risk_off_allocation: Optional[Dict[str, float]] = None
    """Allocation défensive en mode Risk-Off."""

    rebalance_frequency: str = "monthly"
    """Fréquence de rebalancement: monthly, quarterly, annual."""

    include_dividends: bool = True
    """Inclure les dividendes dans le calcul."""

    # Frais
    fx_fee: float = 0.002
    """Frais de change (0.2%)."""

    slippage: float = 0.001
    """Slippage (0.1%)."""

    commission_per_trade: float = 0.0
    """Commission par trade."""

    # Anti-Whipsaw
    risk_off_entry_days: int = 7
    """Jours de confirmation pour entrer en Risk-Off."""

    risk_off_exit_days: int = 14
    """Jours de confirmation pour sortir de Risk-Off."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "allocation": self.allocation,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "monthly_contribution": self.monthly_contribution,
            "risk_off_enabled": self.risk_off_enabled,
            "risk_off_trigger": self.risk_off_trigger,
            "risk_off_allocation": self.risk_off_allocation,
            "rebalance_frequency": self.rebalance_frequency,
            "include_dividends": self.include_dividends,
            "fx_fee": self.fx_fee,
            "slippage": self.slippage,
            "commission_per_trade": self.commission_per_trade,
            "risk_off_entry_days": self.risk_off_entry_days,
            "risk_off_exit_days": self.risk_off_exit_days,
        }


@dataclass
class RiskOffPeriod:
    """
    Une période où le portfolio était en mode Risk-Off.
    """
    start_date: date
    """Date d'entrée en Risk-Off."""

    end_date: Optional[date] = None
    """Date de sortie (None si toujours en Risk-Off)."""

    trigger: str = ""
    """Signal qui a déclenché le Risk-Off."""

    duration_days: int = 0
    """Durée en jours."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "trigger": self.trigger,
            "duration_days": self.duration_days,
        }


@dataclass
class EquityPoint:
    """
    Un point de la courbe d'équité.
    """
    date: date
    """Date du point."""

    portfolio_value: float
    """Valeur du portfolio."""

    drawdown: float = 0.0
    """Drawdown depuis le plus haut (en %)."""

    is_risk_off: bool = False
    """True si en mode Risk-Off à cette date."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "date": self.date.isoformat(),
            "value": round(self.portfolio_value, 2),
            "drawdown": round(self.drawdown * 100, 2),
            "risk_off": self.is_risk_off,
        }


@dataclass
class TradeRecord:
    """
    Enregistrement d'un trade dans le backtest.
    """
    date: date
    """Date du trade."""

    ticker: str
    """Ticker."""

    action: Literal["buy", "sell", "rebalance"]
    """Type d'action."""

    shares: float
    """Nombre d'actions."""

    price: float
    """Prix d'exécution."""

    amount: float
    """Montant total."""

    fees: float = 0.0
    """Frais."""

    reason: str = ""
    """Raison du trade."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "date": self.date.isoformat(),
            "ticker": self.ticker,
            "action": self.action,
            "shares": round(self.shares, 4),
            "price": round(self.price, 2),
            "amount": round(self.amount, 2),
            "fees": round(self.fees, 2),
            "reason": self.reason,
        }


@dataclass
class BacktestResult:
    """
    Résultat complet d'un backtest.
    """
    # Métriques de performance
    final_value: float
    """Valeur finale du portfolio."""

    cagr: float
    """Compound Annual Growth Rate (%)."""

    total_return: float
    """Rendement total (%)."""

    sharpe_ratio: float
    """Sharpe Ratio (risk-free rate = 0)."""

    sortino_ratio: float
    """Sortino Ratio."""

    max_drawdown: float
    """Drawdown maximum (%)."""

    max_drawdown_duration: int
    """Durée du plus long drawdown (jours)."""

    volatility: float
    """Volatilité annualisée (%)."""

    # Dividendes
    total_dividends: float
    """Total des dividendes reçus."""

    dividend_yield_avg: float
    """Rendement moyen des dividendes."""

    # Risk-Off
    time_in_risk_off: float
    """Temps passé en Risk-Off (%)."""

    risk_off_periods: List[RiskOffPeriod]
    """Liste des périodes Risk-Off."""

    # Frais
    total_fees: float
    """Total des frais."""

    # Données détaillées
    trades: List[TradeRecord]
    """Liste des trades."""

    equity_curve: List[EquityPoint]
    """Courbe d'équité (échantillonnée)."""

    monthly_returns: List[float]
    """Rendements mensuels."""

    # Comparaison benchmark
    benchmark_cagr: Optional[float] = None
    """CAGR du benchmark (SPY)."""

    alpha: Optional[float] = None
    """Alpha vs benchmark."""

    beta: Optional[float] = None
    """Beta vs benchmark."""

    # Méta
    config: Optional[BacktestConfig] = None
    """Configuration utilisée."""

    warnings: List[str] = field(default_factory=list)
    """Avertissements (ex: données manquantes)."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation JSON."""
        return {
            "performance": {
                "final_value": round(self.final_value, 2),
                "cagr": round(self.cagr, 2),
                "total_return": round(self.total_return, 2),
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "max_drawdown": round(self.max_drawdown, 2),
                "max_drawdown_duration_days": self.max_drawdown_duration,
                "volatility": round(self.volatility, 2),
            },
            "dividends": {
                "total_received": round(self.total_dividends, 2),
                "average_yield": round(self.dividend_yield_avg, 2),
            },
            "risk_off": {
                "time_in_risk_off_pct": round(self.time_in_risk_off, 2),
                "periods": [p.to_dict() for p in self.risk_off_periods],
            },
            "fees": {
                "total": round(self.total_fees, 2),
            },
            "benchmark": {
                "cagr": round(self.benchmark_cagr, 2) if self.benchmark_cagr else None,
                "alpha": round(self.alpha, 2) if self.alpha else None,
                "beta": round(self.beta, 2) if self.beta else None,
            },
            "trades_count": len(self.trades),
            "equity_curve": [p.to_dict() for p in self.equity_curve[::5]],  # Échantillonner
            "monthly_returns": [round(r, 2) for r in self.monthly_returns[-12:]],  # 12 derniers mois
            "warnings": self.warnings,
        }


# =============================================================================
# INCOME PRESETS
# =============================================================================

INCOME_ASSET_TICKERS = {
    IncomeCategory.BDC: ["ARCC", "MAIN", "HTGC", "OBDC", "CSWC", "TCPC"],
    IncomeCategory.COVERED_CALL: ["JEPI", "JEPQ", "DIVO", "XYLD", "QYLD"],
    IncomeCategory.CEF: ["BST", "UTF", "PDI", "GOF", "PTY"],
    IncomeCategory.MREIT: ["AGNC", "NLY", "STWD", "BXMT"],
    IncomeCategory.CASH_LIKE: ["SGOV", "BIL", "SHV", "USFR"],
    IncomeCategory.DIVIDEND_GROWTH: ["SCHD", "VIG", "DGRO", "NOBL"],
    IncomeCategory.BONDS: ["AGG", "BND", "TLT", "VCIT"],
}


def get_tickers_for_category(category: IncomeCategory) -> List[str]:
    """Retourne les tickers pour une catégorie donnée."""
    return INCOME_ASSET_TICKERS.get(category, [])


def get_all_income_tickers() -> List[str]:
    """Retourne tous les tickers income."""
    all_tickers = []
    for tickers in INCOME_ASSET_TICKERS.values():
        all_tickers.extend(tickers)
    return list(set(all_tickers))


def get_category_for_ticker(ticker: str) -> Optional[IncomeCategory]:
    """Retourne la categorie d'un ticker, ou None si non trouve."""
    ticker = ticker.upper()
    for category, tickers in INCOME_ASSET_TICKERS.items():
        if ticker in tickers:
            return category
    return None
