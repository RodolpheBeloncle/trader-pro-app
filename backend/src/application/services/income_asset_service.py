"""
Service d'analyse des actifs à revenus (Income Assets).

Analyse les actifs orientés revenus:
- BDC (Business Development Companies)
- Covered Call ETFs
- CEF (Closed-End Funds)
- mREIT (Mortgage REITs)
- Cash-like (T-Bills, Money Market)
- Dividend Growth stocks

Fournit:
- Analyse de rendement
- Scoring orienté revenus
- Recommandations
- Simulation de revenus passifs
- Calcul de rebalancement

ARCHITECTURE:
- Service applicatif (couche Application)
- Utilise les providers pour les données
- Retourne les entités du domaine

UTILISATION:
    service = IncomeAssetService()
    analysis = await service.analyze_income_asset("JEPI")
    assets = await service.get_category_assets(IncomeCategory.COVERED_CALL)
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

import yfinance as yf

from src.domain.entities.income_portfolio import (
    IncomeAssetAnalysis,
    IncomeCategory,
    YieldMetrics,
    DividendInfo,
    DistributionFrequency,
    RebalanceOrder,
    RebalanceResult,
    IncomeSimulationResult,
    INCOME_ASSET_TICKERS,
    get_tickers_for_category,
)

logger = logging.getLogger(__name__)


class IncomeAssetService:
    """
    Service pour l'analyse des actifs à revenus.

    Analyse les rendements, la stabilité, et génère des recommandations
    pour les investisseurs orientés revenus passifs.
    """

    # Poids pour le scoring orienté revenus
    SCORING_WEIGHTS = {
        "yield": 0.25,           # Rendement actuel
        "dividend_growth": 0.20,  # Croissance des dividendes
        "payout_ratio": 0.15,    # Soutenabilité
        "nav_discount": 0.15,    # Discount NAV (CEF)
        "volatility": 0.15,      # Risque
        "stability": 0.10,       # Stabilité des distributions
    }

    # Seuils pour les scores
    YIELD_THRESHOLDS = {
        "excellent": 8.0,  # > 8% = score 100
        "good": 5.0,       # > 5% = score 75
        "average": 3.0,    # > 3% = score 50
        "low": 1.0,        # > 1% = score 25
    }

    def __init__(self):
        """Initialise le service."""
        self._cache = {}

    async def analyze_income_asset(self, ticker: str) -> Optional[IncomeAssetAnalysis]:
        """
        Analyse complète d'un actif à revenus.

        Args:
            ticker: Symbole de l'actif

        Returns:
            IncomeAssetAnalysis ou None si erreur
        """
        try:
            ticker = ticker.upper().strip()
            logger.info(f"Analyzing income asset: {ticker}")

            # Récupérer les données
            yf_ticker = yf.Ticker(ticker)
            info = self._get_ticker_info(yf_ticker)

            if not info:
                logger.warning(f"No info found for {ticker}")
                return None

            # Déterminer la catégorie
            category = self._determine_category(ticker)

            # Récupérer le prix actuel
            current_price = self._get_current_price(yf_ticker)
            if current_price is None:
                return None

            # Calculer les métriques de rendement
            yield_metrics = self._calculate_yield_metrics(info, current_price)

            # Récupérer les infos de dividendes
            dividend_info = self._extract_dividend_info(info, yf_ticker)

            # Calculer la volatilité
            volatility = await self._calculate_volatility(yf_ticker)

            # Pour les CEF, calculer le NAV discount
            nav, nav_discount = self._calculate_nav_discount(info, current_price)

            # Calculer les scores
            scores = self._calculate_scores(
                yield_metrics,
                dividend_info,
                volatility,
                nav_discount,
                category,
            )

            # Générer la recommandation
            recommendation = self._generate_recommendation(
                ticker, scores, yield_metrics, category
            )

            analysis = IncomeAssetAnalysis(
                ticker=ticker,
                name=info.get('shortName') or info.get('longName') or ticker,
                category=category,
                current_price=current_price,
                yield_metrics=yield_metrics,
                dividend_info=dividend_info,
                yield_score=scores["yield"],
                stability_score=scores["stability"],
                growth_score=scores["growth"],
                risk_score=scores["risk"],
                overall_income_score=scores["overall"],
                nav=nav,
                nav_discount=nav_discount,
                volatility=volatility,
                expense_ratio=info.get('netExpenseRatio') or info.get('expenseRatio'),
                aum=info.get('totalAssets'),
                recommendation=recommendation,
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return None

    async def get_category_assets(
        self,
        category: IncomeCategory,
        sort_by: str = "overall_income_score",
    ) -> List[IncomeAssetAnalysis]:
        """
        Récupère et analyse tous les actifs d'une catégorie.

        Args:
            category: Catégorie d'actifs
            sort_by: Champ de tri

        Returns:
            Liste d'analyses triées
        """
        tickers = get_tickers_for_category(category)
        analyses = []

        for ticker in tickers:
            analysis = await self.analyze_income_asset(ticker)
            if analysis:
                analyses.append(analysis)

        # Trier par score
        analyses.sort(
            key=lambda x: getattr(x, sort_by, 0),
            reverse=True,
        )

        return analyses

    async def get_all_income_assets(self) -> Dict[str, List[IncomeAssetAnalysis]]:
        """
        Récupère tous les actifs income par catégorie.

        Returns:
            Dict avec catégorie -> liste d'analyses
        """
        result = {}
        for category in IncomeCategory:
            analyses = await self.get_category_assets(category)
            if analyses:
                result[category.value] = analyses
        return result

    async def calculate_rebalancing(
        self,
        current_positions: List[Dict],
        target_allocation: Dict[str, float],
        cash_available: float = 0,
        threshold_percent: float = 5.0,
    ) -> RebalanceResult:
        """
        Calcule les ordres de rebalancement.

        Args:
            current_positions: [{ticker, shares, value, avg_cost}]
            target_allocation: {ticker: weight_percent}
            cash_available: Cash disponible
            threshold_percent: Seuil de drift pour déclencher le rebalancement

        Returns:
            RebalanceResult avec les ordres
        """
        try:
            # Calculer la valeur totale
            total_value = sum(p.get('value', 0) for p in current_positions) + cash_available

            if total_value == 0:
                return RebalanceResult(
                    needs_rebalancing=False,
                    total_value=0,
                    cash_available=cash_available,
                    drift_analysis=[],
                    sell_orders=[],
                    buy_orders=[],
                    estimated_fees=0,
                    tax_loss_harvesting=[],
                    summary="Portefeuille vide",
                )

            # Calculer les poids actuels
            current_weights = {}
            for pos in current_positions:
                ticker = pos.get('ticker', '')
                value = pos.get('value', 0)
                current_weights[ticker] = (value / total_value) * 100

            # Analyser le drift
            drift_analysis = []
            sell_orders = []
            buy_orders = []
            tax_loss_harvesting = []
            needs_rebalancing = False

            # Vérifier chaque position cible
            all_tickers = set(target_allocation.keys()) | set(current_weights.keys())

            for ticker in all_tickers:
                current_pct = current_weights.get(ticker, 0)
                target_pct = target_allocation.get(ticker, 0)
                drift = current_pct - target_pct

                drift_analysis.append({
                    "ticker": ticker,
                    "current_pct": round(current_pct, 2),
                    "target_pct": round(target_pct, 2),
                    "drift": round(drift, 2),
                })

                # Si le drift dépasse le seuil
                if abs(drift) > threshold_percent:
                    needs_rebalancing = True

                    # Récupérer le prix actuel
                    price = await self._get_price(ticker)
                    if not price:
                        continue

                    target_value = (target_pct / 100) * total_value
                    current_value = (current_pct / 100) * total_value
                    diff_value = target_value - current_value

                    if diff_value < 0:
                        # Vendre
                        shares_to_sell = abs(diff_value) / price
                        sell_orders.append(RebalanceOrder(
                            ticker=ticker,
                            action="sell",
                            shares=shares_to_sell,
                            amount=abs(diff_value),
                            current_weight=current_pct,
                            target_weight=target_pct,
                            drift=drift,
                            reason=f"Réduire de {abs(drift):.1f}% (surpondéré)",
                        ))

                        # Vérifier tax-loss harvesting
                        pos = next((p for p in current_positions if p.get('ticker') == ticker), None)
                        if pos:
                            avg_cost = pos.get('avg_cost', 0)
                            if avg_cost > 0 and price < avg_cost:
                                unrealized_loss = (avg_cost - price) * pos.get('shares', 0)
                                tax_loss_harvesting.append({
                                    "ticker": ticker,
                                    "unrealized_loss": round(unrealized_loss, 2),
                                    "loss_per_share": round(avg_cost - price, 2),
                                })

                    else:
                        # Acheter
                        shares_to_buy = diff_value / price
                        buy_orders.append(RebalanceOrder(
                            ticker=ticker,
                            action="buy",
                            shares=shares_to_buy,
                            amount=diff_value,
                            current_weight=current_pct,
                            target_weight=target_pct,
                            drift=drift,
                            reason=f"Augmenter de {abs(drift):.1f}% (sous-pondéré)",
                        ))

            # Estimer les frais
            total_trades = len(sell_orders) + len(buy_orders)
            estimated_fees = total_trades * 1.0 + (total_trades * 0.001 * total_value)  # 1$ + 0.1%

            # Générer le résumé
            if needs_rebalancing:
                summary = f"Rebalancement recommandé: {len(sell_orders)} ventes, {len(buy_orders)} achats"
            else:
                summary = f"Portefeuille équilibré (drift max: {max(abs(d['drift']) for d in drift_analysis):.1f}%)"

            return RebalanceResult(
                needs_rebalancing=needs_rebalancing,
                total_value=total_value,
                cash_available=cash_available,
                drift_analysis=drift_analysis,
                sell_orders=sell_orders,
                buy_orders=buy_orders,
                estimated_fees=estimated_fees,
                tax_loss_harvesting=tax_loss_harvesting,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Error calculating rebalancing: {e}")
            return RebalanceResult(
                needs_rebalancing=False,
                total_value=0,
                cash_available=cash_available,
                drift_analysis=[],
                sell_orders=[],
                buy_orders=[],
                estimated_fees=0,
                tax_loss_harvesting=[],
                summary=f"Erreur: {str(e)}",
            )

    async def simulate_income_portfolio(
        self,
        positions: List[Dict],
        monthly_contribution: float = 0,
        years: int = 10,
        reinvest_dividends: bool = True,
        dividend_growth_rate: float = 0.03,  # 3% par an
        price_appreciation: float = 0.05,     # 5% par an
    ) -> IncomeSimulationResult:
        """
        Simule l'évolution d'un portefeuille orienté revenus.

        Args:
            positions: [{ticker, shares, value}]
            monthly_contribution: Contribution mensuelle
            years: Nombre d'années à simuler
            reinvest_dividends: Réinvestir les dividendes (DRIP)
            dividend_growth_rate: Croissance annuelle des dividendes
            price_appreciation: Appréciation annuelle des prix

        Returns:
            IncomeSimulationResult
        """
        try:
            # Calculer la valeur initiale et le revenu actuel
            initial_value = sum(p.get('value', 0) for p in positions)
            current_annual_income = 0

            for pos in positions:
                ticker = pos.get('ticker', '')
                value = pos.get('value', 0)
                analysis = await self.analyze_income_asset(ticker)
                if analysis and analysis.yield_metrics.current_yield:
                    current_annual_income += value * (analysis.yield_metrics.current_yield / 100)

            # Simulation année par année
            yearly_projections = []
            portfolio_value = initial_value
            annual_income = current_annual_income
            total_contributions = 0
            total_dividends = 0

            for year in range(1, years + 1):
                # Contributions de l'année
                yearly_contribution = monthly_contribution * 12
                total_contributions += yearly_contribution

                # Dividendes de l'année
                yearly_dividends = annual_income

                if reinvest_dividends:
                    # DRIP: réinvestir les dividendes
                    portfolio_value += yearly_dividends
                    total_dividends += yearly_dividends
                else:
                    total_dividends += yearly_dividends

                # Contributions
                portfolio_value += yearly_contribution

                # Appréciation des prix
                portfolio_value *= (1 + price_appreciation)

                # Croissance des dividendes
                annual_income *= (1 + dividend_growth_rate)

                # Recalculer le revenu basé sur la nouvelle valeur
                avg_yield = (current_annual_income / initial_value) if initial_value > 0 else 0.05
                annual_income = portfolio_value * avg_yield * ((1 + dividend_growth_rate) ** year)

                yearly_projections.append({
                    "year": year,
                    "portfolio_value": round(portfolio_value, 2),
                    "annual_income": round(annual_income, 2),
                    "monthly_income": round(annual_income / 12, 2),
                    "yield_on_cost": round((annual_income / (initial_value + total_contributions)) * 100, 2) if (initial_value + total_contributions) > 0 else 0,
                })

            # Calculs finaux
            final_value = portfolio_value
            final_annual_income = annual_income
            yield_on_cost = (final_annual_income / (initial_value + total_contributions)) * 100 if (initial_value + total_contributions) > 0 else 0

            # Impact DRIP
            drip_impact = 0
            if reinvest_dividends:
                # Simuler sans DRIP pour comparer
                no_drip_value = initial_value + total_contributions
                no_drip_value *= ((1 + price_appreciation) ** years)
                drip_impact = final_value - no_drip_value

            # Retrait soutenable (règle des 4%)
            sustainable_withdrawal = final_value * 0.04 / 12

            return IncomeSimulationResult(
                initial_value=initial_value,
                current_annual_income=current_annual_income,
                projected_value=final_value,
                projected_annual_income=final_annual_income,
                projected_monthly_income=final_annual_income / 12,
                yield_on_cost=yield_on_cost,
                total_contributions=total_contributions,
                total_dividends_received=total_dividends,
                drip_impact=drip_impact,
                sustainable_withdrawal=sustainable_withdrawal,
                yearly_projections=yearly_projections,
                assumptions={
                    "dividend_growth_rate": dividend_growth_rate * 100,
                    "price_appreciation": price_appreciation * 100,
                    "reinvest_dividends": reinvest_dividends,
                    "years": years,
                },
            )

        except Exception as e:
            logger.error(f"Error simulating portfolio: {e}")
            return IncomeSimulationResult(
                initial_value=0,
                current_annual_income=0,
                projected_value=0,
                projected_annual_income=0,
                projected_monthly_income=0,
                yield_on_cost=0,
                total_contributions=0,
                total_dividends_received=0,
                drip_impact=0,
                sustainable_withdrawal=0,
                yearly_projections=[],
                assumptions={"error": str(e)},
            )

    async def get_dividend_calendar(
        self,
        tickers: List[str],
        days_ahead: int = 30,
    ) -> List[Dict]:
        """
        Récupère le calendrier des dividendes à venir.

        Args:
            tickers: Liste de tickers
            days_ahead: Nombre de jours à regarder

        Returns:
            Liste de dividendes à venir
        """
        upcoming = []
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        for ticker in tickers:
            try:
                analysis = await self.analyze_income_asset(ticker)
                if analysis and analysis.dividend_info.ex_dividend_date:
                    ex_date = analysis.dividend_info.ex_dividend_date
                    if today <= ex_date <= end_date:
                        upcoming.append({
                            "ticker": ticker,
                            "ex_date": ex_date.isoformat(),
                            "pay_date": analysis.dividend_info.payment_date.isoformat() if analysis.dividend_info.payment_date else None,
                            "amount": analysis.dividend_info.last_dividend_amount,
                            "yield": analysis.yield_metrics.current_yield,
                            "frequency": analysis.dividend_info.frequency.value,
                        })
            except Exception as e:
                logger.warning(f"Error getting dividend info for {ticker}: {e}")

        # Trier par date ex-div
        upcoming.sort(key=lambda x: x["ex_date"])
        return upcoming

    # =========================================================================
    # MÉTHODES PRIVÉES
    # =========================================================================

    def _get_ticker_info(self, yf_ticker: yf.Ticker) -> dict:
        """Récupère les informations d'un ticker."""
        try:
            return yf_ticker.info or {}
        except Exception as e:
            logger.warning(f"Could not fetch ticker info: {e}")
            return {}

    def _get_current_price(self, yf_ticker: yf.Ticker) -> Optional[float]:
        """Récupère le prix actuel."""
        try:
            hist = yf_ticker.history(period="5d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            return None
        except Exception as e:
            logger.warning(f"Could not get current price: {e}")
            return None

    async def _get_price(self, ticker: str) -> Optional[float]:
        """Récupère le prix d'un ticker."""
        try:
            yf_ticker = yf.Ticker(ticker)
            return self._get_current_price(yf_ticker)
        except Exception:
            return None

    def _determine_category(self, ticker: str) -> IncomeCategory:
        """Détermine la catégorie d'un ticker."""
        ticker = ticker.upper()
        for category, tickers in INCOME_ASSET_TICKERS.items():
            if ticker in tickers:
                return category
        # Catégorie par défaut
        return IncomeCategory.DIVIDEND_GROWTH

    def _calculate_yield_metrics(self, info: dict, current_price: float) -> YieldMetrics:
        """Calcule les métriques de rendement."""
        # Dividend yield
        div_yield = info.get('dividendYield') or info.get('yield')
        if div_yield:
            div_yield = float(div_yield) * 100  # Convertir en %
        else:
            # Calculer à partir du dividende annuel
            annual_div = info.get('dividendRate') or info.get('trailingAnnualDividendRate')
            if annual_div and current_price > 0:
                div_yield = (float(annual_div) / current_price) * 100
            else:
                div_yield = 0

        # Monthly income per $1000
        monthly_income = (div_yield / 100) * 1000 / 12 if div_yield else 0

        return YieldMetrics(
            current_yield=div_yield,
            trailing_12m_yield=info.get('trailingAnnualDividendYield', div_yield / 100) * 100 if div_yield else None,
            sec_yield=info.get('yield'),
            distribution_rate=div_yield,
            monthly_income_per_1000=monthly_income,
        )

    def _extract_dividend_info(self, info: dict, yf_ticker: yf.Ticker) -> DividendInfo:
        """Extrait les informations de dividende."""
        # Dates
        ex_date = None
        pay_date = None

        ex_dividend_date = info.get('exDividendDate')
        if ex_dividend_date:
            try:
                ex_date = datetime.fromtimestamp(ex_dividend_date).date()
            except Exception:
                pass

        # Fréquence
        frequency = DistributionFrequency.QUARTERLY
        dividend_freq = info.get('dividendFrequency')
        if dividend_freq:
            if dividend_freq >= 12:
                frequency = DistributionFrequency.MONTHLY
            elif dividend_freq >= 4:
                frequency = DistributionFrequency.QUARTERLY
            elif dividend_freq >= 2:
                frequency = DistributionFrequency.SEMI_ANNUAL
            else:
                frequency = DistributionFrequency.ANNUAL

        return DividendInfo(
            ex_dividend_date=ex_date,
            payment_date=pay_date,
            last_dividend_amount=info.get('lastDividendValue'),
            annual_dividend=info.get('dividendRate') or info.get('trailingAnnualDividendRate'),
            frequency=frequency,
            payout_ratio=info.get('payoutRatio'),
            dividend_growth_5y=info.get('fiveYearAvgDividendYield'),
        )

    async def _calculate_volatility(self, yf_ticker: yf.Ticker) -> Optional[float]:
        """Calcule la volatilité annualisée."""
        try:
            hist = yf_ticker.history(period="1y")
            if len(hist) < 20:
                return None

            returns = hist['Close'].pct_change().dropna()
            daily_vol = returns.std()
            annualized_vol = daily_vol * np.sqrt(252) * 100
            return round(annualized_vol, 2)
        except Exception:
            return None

    def _calculate_nav_discount(
        self,
        info: dict,
        current_price: float,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calcule le discount/premium par rapport à la NAV (pour CEF)."""
        nav = info.get('navPrice')
        if nav and current_price > 0:
            discount = ((current_price / float(nav)) - 1) * 100
            return float(nav), discount
        return None, None

    def _calculate_scores(
        self,
        yield_metrics: YieldMetrics,
        dividend_info: DividendInfo,
        volatility: Optional[float],
        nav_discount: Optional[float],
        category: IncomeCategory,
    ) -> Dict[str, int]:
        """Calcule les scores orientés revenus."""
        scores = {
            "yield": 0,
            "stability": 50,  # Par défaut
            "growth": 50,
            "risk": 50,
            "overall": 0,
        }

        # Score de rendement
        current_yield = yield_metrics.current_yield or 0
        if current_yield >= 8:
            scores["yield"] = 100
        elif current_yield >= 5:
            scores["yield"] = 75
        elif current_yield >= 3:
            scores["yield"] = 50
        elif current_yield >= 1:
            scores["yield"] = 25
        else:
            scores["yield"] = 0

        # Score de stabilité (basé sur la fréquence et le payout ratio)
        if dividend_info.frequency == DistributionFrequency.MONTHLY:
            scores["stability"] += 20
        elif dividend_info.frequency == DistributionFrequency.QUARTERLY:
            scores["stability"] += 10

        if dividend_info.payout_ratio:
            if 0.3 <= dividend_info.payout_ratio <= 0.7:
                scores["stability"] += 20
            elif dividend_info.payout_ratio > 0.9:
                scores["stability"] -= 20

        # Score de croissance
        if dividend_info.dividend_growth_5y:
            growth = dividend_info.dividend_growth_5y
            if growth >= 10:
                scores["growth"] = 100
            elif growth >= 5:
                scores["growth"] = 75
            elif growth >= 0:
                scores["growth"] = 50
            else:
                scores["growth"] = 25

        # Score de risque (inversé: 100 = moins risqué)
        if volatility:
            if volatility < 15:
                scores["risk"] = 100
            elif volatility < 25:
                scores["risk"] = 75
            elif volatility < 40:
                scores["risk"] = 50
            else:
                scores["risk"] = 25

        # Bonus/malus NAV discount (CEF)
        if nav_discount is not None and category == IncomeCategory.CEF:
            if nav_discount < -10:  # Discount > 10%
                scores["yield"] += 10
            elif nav_discount > 5:  # Premium > 5%
                scores["yield"] -= 10

        # Score global (moyenne pondérée)
        scores["overall"] = int(
            scores["yield"] * 0.35 +
            scores["stability"] * 0.25 +
            scores["growth"] * 0.20 +
            scores["risk"] * 0.20
        )

        # Limiter entre 0 et 100
        for key in scores:
            scores[key] = max(0, min(100, scores[key]))

        return scores

    def _generate_recommendation(
        self,
        ticker: str,
        scores: Dict[str, int],
        yield_metrics: YieldMetrics,
        category: IncomeCategory,
    ) -> str:
        """Génère une recommandation textuelle."""
        overall = scores["overall"]
        yield_score = scores["yield"]

        if overall >= 80:
            rec = "Strong Income Buy"
        elif overall >= 60:
            rec = "Income Buy"
        elif overall >= 40:
            rec = "Hold for Income"
        else:
            rec = "Review Position"

        details = []
        if yield_metrics.current_yield:
            details.append(f"Yield: {yield_metrics.current_yield:.1f}%")
        if yield_metrics.monthly_income_per_1000:
            details.append(f"${yield_metrics.monthly_income_per_1000:.2f}/mo per $1000")

        return f"{rec} - {', '.join(details)}"


# =============================================================================
# FACTORY / SINGLETON
# =============================================================================

_income_asset_service: Optional[IncomeAssetService] = None


def get_income_asset_service() -> IncomeAssetService:
    """Retourne une instance singleton du service."""
    global _income_asset_service
    if _income_asset_service is None:
        _income_asset_service = IncomeAssetService()
    return _income_asset_service
