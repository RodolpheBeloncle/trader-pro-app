"""
Moteur de Simulation Monte Carlo pour Analyse de Prix et Risque.

Ce module implemente:
- Simulation Geometric Brownian Motion (GBM) pour trajectoires de prix
- VaR (Value at Risk) - Quantile des pertes
- CVaR/ES (Expected Shortfall) - Moyenne des pertes extremes
- Intervalles de confiance pour projections de prix

FORMULE GBM:
dS = mu*S*dt + sigma*S*dW

Discretisee:
S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
ou Z ~ N(0,1)

REFERENCES:
- Hull - Options, Futures, and Other Derivatives
- Jorion - Value at Risk
- Glasserman - Monte Carlo Methods in Financial Engineering
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PriceSimulationResult:
    """
    Resultat d'une simulation Monte Carlo de prix.

    Contient les statistiques de la distribution des prix finaux
    et les intervalles de confiance.
    """
    ticker: str
    current_price: float
    time_horizon_days: int
    num_simulations: int

    # Parametres utilises
    annual_volatility: float
    annual_drift: float

    # Projections de prix
    mean_price: float
    median_price: float
    std_deviation: float

    # Intervalles de confiance (percentiles)
    percentile_5: float    # 5% pire cas
    percentile_25: float   # 25% pessimiste
    percentile_50: float   # 50% median
    percentile_75: float   # 75% optimiste
    percentile_95: float   # 95% meilleur cas

    # Metriques de risque
    probability_of_loss: float       # P(prix < prix_actuel)
    probability_of_gain_10pct: float # P(gain > 10%)
    probability_of_loss_10pct: float # P(perte > 10%)
    max_drawdown_expected: float

    # Donnees distribution pour visualisation
    price_distribution: List[float] = field(default_factory=list)
    sample_paths: List[List[float]] = field(default_factory=list)

    calculated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def expected_return_percent(self) -> float:
        """Rendement attendu en %."""
        if self.current_price == 0:
            return 0.0
        return ((self.mean_price - self.current_price) / self.current_price) * 100

    @property
    def confidence_range_50(self) -> Tuple[float, float]:
        """Intervalle de confiance 50% (25e-75e percentile)."""
        return (self.percentile_25, self.percentile_75)

    @property
    def confidence_range_90(self) -> Tuple[float, float]:
        """Intervalle de confiance 90% (5e-95e percentile)."""
        return (self.percentile_5, self.percentile_95)

    @property
    def risk_level(self) -> str:
        """Niveau de risque base sur la probabilite de perte."""
        if self.probability_of_loss > 0.5:
            return "ELEVE"
        elif self.probability_of_loss > 0.35:
            return "MODERE"
        else:
            return "FAIBLE"

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour JSON."""
        return {
            "ticker": self.ticker,
            "current_price": round(self.current_price, 2),
            "time_horizon_days": self.time_horizon_days,
            "num_simulations": self.num_simulations,
            "parameters": {
                "annual_volatility_pct": round(self.annual_volatility * 100, 2),
                "annual_drift_pct": round(self.annual_drift * 100, 2),
            },
            "projections": {
                "mean": round(self.mean_price, 2),
                "median": round(self.median_price, 2),
                "std_deviation": round(self.std_deviation, 2),
                "expected_return_pct": round(self.expected_return_percent, 2),
            },
            "confidence_intervals": {
                "5%": round(self.percentile_5, 2),
                "25%": round(self.percentile_25, 2),
                "50%": round(self.percentile_50, 2),
                "75%": round(self.percentile_75, 2),
                "95%": round(self.percentile_95, 2),
            },
            "risk_metrics": {
                "probability_of_loss_pct": round(self.probability_of_loss * 100, 2),
                "probability_of_gain_10pct": round(self.probability_of_gain_10pct * 100, 2),
                "probability_of_loss_10pct": round(self.probability_of_loss_10pct * 100, 2),
                "max_drawdown_expected_pct": round(self.max_drawdown_expected * 100, 2),
                "risk_level": self.risk_level,
            },
            "calculated_at": self.calculated_at,
        }


@dataclass
class PortfolioRiskResult:
    """
    Resultat de l'analyse de risque Monte Carlo pour un portefeuille.

    Inclut VaR, CVaR, et attribution de risque par position.
    """
    portfolio_value: float
    time_horizon_days: int
    num_simulations: int

    # VaR (Value at Risk) - Perte maximum avec X% de confiance
    var_99: float    # 1% pire cas
    var_95: float    # 5% pire cas
    var_90: float    # 10% pire cas

    # CVaR (Expected Shortfall) - Moyenne des pertes au-dela du VaR
    cvar_99: float   # Moyenne des pertes dans le pire 1%
    cvar_95: float   # Moyenne des pertes dans le pire 5%

    # Distribution des rendements
    expected_return: float
    return_std_deviation: float

    # Percentiles des rendements
    return_percentiles: Dict[str, float] = field(default_factory=dict)

    # Contribution au risque par position
    position_risk_contributions: Dict[str, float] = field(default_factory=dict)

    # Correlation moyenne du portefeuille
    average_correlation: float = 0.0
    diversification_ratio: float = 1.0

    calculated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def var_99_percent(self) -> float:
        """VaR 99% en pourcentage du portefeuille."""
        if self.portfolio_value == 0:
            return 0.0
        return (self.var_99 / self.portfolio_value) * 100

    @property
    def var_95_percent(self) -> float:
        """VaR 95% en pourcentage du portefeuille."""
        if self.portfolio_value == 0:
            return 0.0
        return (self.var_95 / self.portfolio_value) * 100

    @property
    def risk_level(self) -> str:
        """Niveau de risque global du portefeuille."""
        var_pct = self.var_99_percent
        if var_pct > 10:
            return "ELEVE"
        elif var_pct > 5:
            return "MODERE"
        else:
            return "FAIBLE"

    @property
    def is_well_diversified(self) -> bool:
        """Le portefeuille est-il bien diversifie ?"""
        return self.diversification_ratio > 1.2 and self.average_correlation < 0.6

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour JSON."""
        return {
            "portfolio_value": round(self.portfolio_value, 2),
            "time_horizon_days": self.time_horizon_days,
            "num_simulations": self.num_simulations,
            "var": {
                "99%": {
                    "amount": round(self.var_99, 2),
                    "percent": round(self.var_99_percent, 2),
                },
                "95%": {
                    "amount": round(self.var_95, 2),
                    "percent": round(self.var_95_percent, 2),
                },
                "90%": {
                    "amount": round(self.var_90, 2),
                    "percent": round((self.var_90 / self.portfolio_value * 100) if self.portfolio_value > 0 else 0, 2),
                },
            },
            "cvar": {
                "99%": round(self.cvar_99, 2),
                "95%": round(self.cvar_95, 2),
            },
            "distribution": {
                "expected_return_pct": round(self.expected_return * 100, 2),
                "std_deviation_pct": round(self.return_std_deviation * 100, 2),
            },
            "return_percentiles": {
                k: round(v * 100, 2) for k, v in self.return_percentiles.items()
            },
            "position_risk_contributions": {
                k: round(v * 100, 2) for k, v in self.position_risk_contributions.items()
            },
            "diversification": {
                "average_correlation": round(self.average_correlation, 3),
                "diversification_ratio": round(self.diversification_ratio, 2),
                "is_well_diversified": self.is_well_diversified,
            },
            "risk_level": self.risk_level,
            "calculated_at": self.calculated_at,
        }


class MonteCarloEngine:
    """
    Moteur de simulation Monte Carlo.

    Utilise le mouvement Brownien geometrique (GBM) pour simuler
    les trajectoires de prix et calculer les metriques de risque.

    GBM est le modele standard pour les actifs financiers car:
    - Les prix sont toujours positifs
    - Les rendements sont log-normaux
    - Modelise bien la volatilite historique

    LIMITATIONS:
    - Assume volatilite constante (pas de clusters)
    - Assume distribution normale des rendements (pas de fat tails)
    - Ne capture pas les evenements extremes (black swans)
    """

    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, random_seed: Optional[int] = None):
        """
        Initialise le moteur Monte Carlo.

        Args:
            random_seed: Graine pour reproductibilite (optionnel)
        """
        self._rng = np.random.default_rng(random_seed)

    def estimate_parameters(
        self,
        historical_returns: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Estime les parametres GBM a partir des rendements historiques.

        Args:
            historical_returns: Array des rendements journaliers

        Returns:
            Tuple (volatilite_annualisee, drift_annualise)
        """
        if len(historical_returns) < 20:
            raise ValueError("Minimum 20 points de donnees requis")

        # Volatilite annualisee (ecart-type * sqrt(252))
        daily_vol = np.std(historical_returns, ddof=1)
        annual_vol = daily_vol * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        # Drift annualise (moyenne * 252)
        daily_drift = np.mean(historical_returns)
        annual_drift = daily_drift * self.TRADING_DAYS_PER_YEAR

        return annual_vol, annual_drift

    def simulate_price_paths(
        self,
        current_price: float,
        annual_volatility: float,
        annual_drift: float,
        time_horizon_days: int,
        num_simulations: int = 10000,
    ) -> np.ndarray:
        """
        Simule des trajectoires de prix avec GBM.

        Args:
            current_price: Prix de depart
            annual_volatility: Volatilite annualisee (ex: 0.25 = 25%)
            annual_drift: Rendement annuel attendu (ex: 0.08 = 8%)
            time_horizon_days: Nombre de jours de trading
            num_simulations: Nombre de trajectoires

        Returns:
            Array de forme (num_simulations, time_horizon_days + 1)
        """
        dt = 1 / self.TRADING_DAYS_PER_YEAR

        # Termes GBM precalcules
        drift_term = (annual_drift - 0.5 * annual_volatility**2) * dt
        vol_term = annual_volatility * np.sqrt(dt)

        # Echantillons normaux
        Z = self._rng.standard_normal((num_simulations, time_horizon_days))

        # Rendements journaliers log-normaux
        daily_returns = np.exp(drift_term + vol_term * Z)

        # Construction des trajectoires
        price_paths = np.zeros((num_simulations, time_horizon_days + 1))
        price_paths[:, 0] = current_price

        # Produit cumulatif pour efficacite
        for t in range(1, time_horizon_days + 1):
            price_paths[:, t] = price_paths[:, t-1] * daily_returns[:, t-1]

        return price_paths

    def simulate_single_asset(
        self,
        ticker: str,
        current_price: float,
        historical_returns: np.ndarray,
        time_horizon_days: int = 30,
        num_simulations: int = 10000,
    ) -> PriceSimulationResult:
        """
        Execute une simulation Monte Carlo complete pour un actif.

        Args:
            ticker: Symbole de l'actif
            current_price: Prix actuel
            historical_returns: Rendements historiques journaliers
            time_horizon_days: Horizon de simulation
            num_simulations: Nombre de simulations

        Returns:
            PriceSimulationResult avec toutes les statistiques
        """
        # Estimation des parametres
        annual_vol, annual_drift = self.estimate_parameters(historical_returns)

        logger.info(
            f"Monte Carlo {ticker}: vol={annual_vol*100:.1f}%, "
            f"drift={annual_drift*100:.1f}%, horizon={time_horizon_days}j"
        )

        # Simulation
        price_paths = self.simulate_price_paths(
            current_price=current_price,
            annual_volatility=annual_vol,
            annual_drift=annual_drift,
            time_horizon_days=time_horizon_days,
            num_simulations=num_simulations,
        )

        # Prix finaux
        final_prices = price_paths[:, -1]

        # Statistiques de base
        mean_price = float(np.mean(final_prices))
        median_price = float(np.median(final_prices))
        std_dev = float(np.std(final_prices))

        # Percentiles
        percentiles = np.percentile(final_prices, [5, 25, 50, 75, 95])

        # Probabilites
        prob_loss = float(np.mean(final_prices < current_price))
        prob_gain_10 = float(np.mean(final_prices > current_price * 1.10))
        prob_loss_10 = float(np.mean(final_prices < current_price * 0.90))

        # Drawdown attendu (sur un echantillon pour performance)
        sample_size = min(500, num_simulations)
        max_drawdowns = []
        for i in range(sample_size):
            path = price_paths[i]
            peak = np.maximum.accumulate(path)
            drawdown = (path - peak) / peak
            max_drawdowns.append(np.min(drawdown))
        expected_max_dd = float(np.mean(max_drawdowns))

        # Trajectoires echantillon pour visualisation (5 trajectoires)
        sample_indices = self._rng.choice(num_simulations, size=5, replace=False)
        sample_paths = [price_paths[i].tolist() for i in sample_indices]

        # Distribution des prix finaux (limite pour JSON)
        price_distribution = final_prices[:1000].tolist()

        return PriceSimulationResult(
            ticker=ticker,
            current_price=current_price,
            time_horizon_days=time_horizon_days,
            num_simulations=num_simulations,
            annual_volatility=annual_vol,
            annual_drift=annual_drift,
            mean_price=mean_price,
            median_price=median_price,
            std_deviation=std_dev,
            percentile_5=float(percentiles[0]),
            percentile_25=float(percentiles[1]),
            percentile_50=float(percentiles[2]),
            percentile_75=float(percentiles[3]),
            percentile_95=float(percentiles[4]),
            probability_of_loss=prob_loss,
            probability_of_gain_10pct=prob_gain_10,
            probability_of_loss_10pct=prob_loss_10,
            max_drawdown_expected=abs(expected_max_dd),
            price_distribution=price_distribution,
            sample_paths=sample_paths,
        )

    def calculate_portfolio_var(
        self,
        positions: List[Dict],
        historical_returns: Dict[str, np.ndarray],
        time_horizon_days: int = 1,
        num_simulations: int = 10000,
    ) -> PortfolioRiskResult:
        """
        Calcule VaR et CVaR du portefeuille par Monte Carlo.

        Args:
            positions: Liste de dicts avec 'symbol' et 'market_value'
            historical_returns: Dict symbol -> rendements historiques
            time_horizon_days: Horizon du VaR (1 jour par defaut)
            num_simulations: Nombre de simulations

        Returns:
            PortfolioRiskResult avec VaR, CVaR, attribution risque
        """
        if not positions:
            raise ValueError("Aucune position fournie")

        # Extraction des donnees
        symbols = [p["symbol"] for p in positions]
        values = np.array([p["market_value"] for p in positions])
        total_value = float(np.sum(values))
        weights = values / total_value

        n_assets = len(symbols)

        # Construction de la matrice de rendements
        # Aligner les rendements sur la meme longueur
        min_len = min(
            len(historical_returns.get(s, np.zeros(100)))
            for s in symbols
        )
        min_len = max(min_len, 50)  # Minimum 50 points

        returns_matrix = np.column_stack([
            historical_returns.get(s, np.zeros(min_len))[-min_len:]
            for s in symbols
        ])

        # Matrice de covariance annualisee
        cov_matrix = np.cov(returns_matrix.T) * self.TRADING_DAYS_PER_YEAR

        # Correlation moyenne
        corr_matrix = np.corrcoef(returns_matrix.T)
        # Moyenne des correlations hors diagonale
        mask = ~np.eye(n_assets, dtype=bool)
        avg_corr = float(np.mean(corr_matrix[mask])) if n_assets > 1 else 0.0

        # Volatilite du portefeuille
        portfolio_var = weights.T @ cov_matrix @ weights
        portfolio_vol = np.sqrt(portfolio_var)

        # Volatilite individuelle ponderee (sans diversification)
        individual_vols = np.sqrt(np.diag(cov_matrix))
        weighted_vol = np.sum(weights * individual_vols)

        # Ratio de diversification
        div_ratio = weighted_vol / portfolio_vol if portfolio_vol > 0 else 1.0

        # Ajustement horizon temporel
        horizon_vol = portfolio_vol * np.sqrt(time_horizon_days / self.TRADING_DAYS_PER_YEAR)

        # Rendement attendu du portefeuille
        asset_returns = np.mean(returns_matrix, axis=0) * self.TRADING_DAYS_PER_YEAR
        portfolio_drift = float(np.sum(weights * asset_returns))
        horizon_drift = portfolio_drift * (time_horizon_days / self.TRADING_DAYS_PER_YEAR)

        # Simulation Monte Carlo des rendements du portefeuille
        simulated_returns = self._rng.normal(
            loc=horizon_drift,
            scale=horizon_vol,
            size=num_simulations
        )

        # Tri pour calcul VaR/CVaR
        sorted_returns = np.sort(simulated_returns)

        # Indices VaR
        idx_99 = int(0.01 * num_simulations)
        idx_95 = int(0.05 * num_simulations)
        idx_90 = int(0.10 * num_simulations)

        # VaR (perte maximale avec X% confiance)
        var_99 = float(-sorted_returns[idx_99] * total_value)
        var_95 = float(-sorted_returns[idx_95] * total_value)
        var_90 = float(-sorted_returns[idx_90] * total_value)

        # CVaR (moyenne des pertes au-dela du VaR)
        cvar_99 = float(-np.mean(sorted_returns[:idx_99]) * total_value)
        cvar_95 = float(-np.mean(sorted_returns[:idx_95]) * total_value)

        # Percentiles de rendement
        pcts = np.percentile(simulated_returns, [1, 5, 25, 50, 75, 95, 99])
        return_percentiles = {
            "1%": float(pcts[0]),
            "5%": float(pcts[1]),
            "25%": float(pcts[2]),
            "50%": float(pcts[3]),
            "75%": float(pcts[4]),
            "95%": float(pcts[5]),
            "99%": float(pcts[6]),
        }

        # Attribution du risque par position (VaR marginal)
        position_contributions = {}
        for i, symbol in enumerate(symbols):
            # Contribution marginale = weight * vol_i * correlation_with_portfolio
            asset_vol = np.sqrt(cov_matrix[i, i])
            # Correlation avec le portefeuille
            cov_with_portfolio = np.sum(weights * cov_matrix[i, :])
            corr_with_portfolio = cov_with_portfolio / (asset_vol * portfolio_vol) if (asset_vol * portfolio_vol) > 0 else 0

            marginal_contribution = weights[i] * asset_vol * corr_with_portfolio / portfolio_vol if portfolio_vol > 0 else 0
            position_contributions[symbol] = float(marginal_contribution)

        return PortfolioRiskResult(
            portfolio_value=total_value,
            time_horizon_days=time_horizon_days,
            num_simulations=num_simulations,
            var_99=var_99,
            var_95=var_95,
            var_90=var_90,
            cvar_99=cvar_99,
            cvar_95=cvar_95,
            expected_return=horizon_drift,
            return_std_deviation=horizon_vol,
            return_percentiles=return_percentiles,
            position_risk_contributions=position_contributions,
            average_correlation=avg_corr,
            diversification_ratio=float(div_ratio),
        )

    def scenario_analysis(
        self,
        ticker: str,
        current_price: float,
        historical_returns: np.ndarray,
        scenarios: Dict[str, Dict[str, float]],
        time_horizon_days: int = 30,
        num_simulations: int = 5000,
    ) -> Dict[str, PriceSimulationResult]:
        """
        Analyse de scenarios avec parametres modifies.

        Args:
            ticker: Symbole de l'actif
            current_price: Prix actuel
            historical_returns: Rendements historiques
            scenarios: Dict de scenarios avec vol/drift modifies
                Ex: {"bull": {"drift_mult": 1.5}, "crash": {"vol_mult": 2.0}}
            time_horizon_days: Horizon
            num_simulations: Simulations par scenario

        Returns:
            Dict de resultats par scenario
        """
        base_vol, base_drift = self.estimate_parameters(historical_returns)
        results = {}

        # Scenario de base
        results["base"] = self.simulate_single_asset(
            ticker=ticker,
            current_price=current_price,
            historical_returns=historical_returns,
            time_horizon_days=time_horizon_days,
            num_simulations=num_simulations,
        )

        # Scenarios personnalises
        for name, params in scenarios.items():
            vol_mult = params.get("vol_mult", 1.0)
            drift_mult = params.get("drift_mult", 1.0)
            drift_override = params.get("drift_override", None)

            adj_vol = base_vol * vol_mult
            adj_drift = drift_override if drift_override is not None else base_drift * drift_mult

            # Simulation avec parametres ajustes
            paths = self.simulate_price_paths(
                current_price=current_price,
                annual_volatility=adj_vol,
                annual_drift=adj_drift,
                time_horizon_days=time_horizon_days,
                num_simulations=num_simulations,
            )

            final_prices = paths[:, -1]
            percentiles = np.percentile(final_prices, [5, 25, 50, 75, 95])

            results[name] = PriceSimulationResult(
                ticker=ticker,
                current_price=current_price,
                time_horizon_days=time_horizon_days,
                num_simulations=num_simulations,
                annual_volatility=adj_vol,
                annual_drift=adj_drift,
                mean_price=float(np.mean(final_prices)),
                median_price=float(np.median(final_prices)),
                std_deviation=float(np.std(final_prices)),
                percentile_5=float(percentiles[0]),
                percentile_25=float(percentiles[1]),
                percentile_50=float(percentiles[2]),
                percentile_75=float(percentiles[3]),
                percentile_95=float(percentiles[4]),
                probability_of_loss=float(np.mean(final_prices < current_price)),
                probability_of_gain_10pct=float(np.mean(final_prices > current_price * 1.1)),
                probability_of_loss_10pct=float(np.mean(final_prices < current_price * 0.9)),
                max_drawdown_expected=0.0,  # Non calcule pour scenarios
                price_distribution=[],
                sample_paths=[],
            )

        return results


def interpret_simulation(result: PriceSimulationResult) -> str:
    """
    Genere une interpretation humaine des resultats.

    Args:
        result: Resultat de simulation

    Returns:
        Texte d'interpretation
    """
    change_pct = result.expected_return_percent
    prob_loss = result.probability_of_loss * 100

    # Direction attendue
    if change_pct > 10:
        direction = f"hausse significative de {change_pct:.1f}%"
    elif change_pct > 3:
        direction = f"hausse moderee de {change_pct:.1f}%"
    elif change_pct > -3:
        direction = f"stabilite ({change_pct:+.1f}%)"
    elif change_pct > -10:
        direction = f"baisse moderee de {abs(change_pct):.1f}%"
    else:
        direction = f"baisse significative de {abs(change_pct):.1f}%"

    # Risque
    if prob_loss > 55:
        risk = "Le risque de perte est eleve"
    elif prob_loss > 45:
        risk = "Le risque est equilibre"
    else:
        risk = "Le risque de perte est modere"

    return (
        f"Sur {result.time_horizon_days} jours, le modele anticipe une {direction}. "
        f"{risk} ({prob_loss:.0f}% de probabilite de baisse). "
        f"Intervalle 90%: {result.percentile_5:.2f} - {result.percentile_95:.2f}."
    )


def interpret_portfolio_risk(result: PortfolioRiskResult) -> str:
    """
    Genere une interpretation du risque portefeuille.

    Args:
        result: Resultat VaR/CVaR

    Returns:
        Texte d'interpretation
    """
    var_pct = result.var_99_percent

    if var_pct > 10:
        level = "ELEVE - Le portefeuille est tres expose"
    elif var_pct > 5:
        level = "MODERE - Risque acceptable pour un investisseur standard"
    else:
        level = "FAIBLE - Portefeuille bien diversifie"

    div_comment = ""
    if result.is_well_diversified:
        div_comment = " La diversification est bonne."
    elif result.diversification_ratio < 1.1:
        div_comment = " Attention: positions trop correlees."

    return (
        f"VaR 99% sur {result.time_horizon_days} jour(s): {result.var_99:.2f} ({var_pct:.1f}% du portefeuille). "
        f"Niveau de risque: {level}.{div_comment}"
    )
