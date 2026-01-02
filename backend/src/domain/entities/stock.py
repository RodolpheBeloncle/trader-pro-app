"""
Entité Stock - Représente une action avec ses données d'analyse.

Une Entité a une identité unique (ici le ticker) et un cycle de vie.
Contrairement aux Value Objects, deux Stocks avec les mêmes données
mais des tickers différents sont distincts.

ARCHITECTURE:
- Couche DOMAINE
- Contient les règles métier (calcul de résilience, etc.)
- Indépendant de l'infrastructure (pas d'import yfinance/API)

UTILISATION:
    from src.domain.entities.stock import Stock, StockAnalysis

    analysis = StockAnalysis(
        ticker=Ticker("AAPL"),
        performances={...},
        ...
    )
    stock = Stock(ticker=Ticker("AAPL"), analysis=analysis)
    print(stock.is_resilient)  # True si toutes les perfs sont positives
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from decimal import Decimal

from src.domain.value_objects.ticker import Ticker
from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage
from src.config.constants import (
    PERIOD_3_MONTHS_DAYS,
    PERIOD_6_MONTHS_DAYS,
    PERIOD_1_YEAR_DAYS,
    PERIOD_3_YEARS_DAYS,
    PERIOD_5_YEARS_DAYS,
    PERIOD_LABELS,
    HIGH_VOLATILITY_THRESHOLD,
    LOW_VOLATILITY_THRESHOLD,
    AssetType,
)


@dataclass
class PerformanceData:
    """
    Contient les performances d'un stock sur différentes périodes.

    Chaque attribut représente la performance (en %) sur la période correspondante.
    None signifie que les données ne sont pas disponibles pour cette période.
    """

    perf_3m: Optional[Percentage] = None
    """Performance sur 3 mois."""

    perf_6m: Optional[Percentage] = None
    """Performance sur 6 mois."""

    perf_1y: Optional[Percentage] = None
    """Performance sur 1 an."""

    perf_3y: Optional[Percentage] = None
    """Performance sur 3 ans."""

    perf_5y: Optional[Percentage] = None
    """Performance sur 5 ans."""

    @property
    def all_periods(self) -> Dict[int, Optional[Percentage]]:
        """Retourne toutes les performances indexées par période en jours."""
        return {
            PERIOD_3_MONTHS_DAYS: self.perf_3m,
            PERIOD_6_MONTHS_DAYS: self.perf_6m,
            PERIOD_1_YEAR_DAYS: self.perf_1y,
            PERIOD_3_YEARS_DAYS: self.perf_3y,
            PERIOD_5_YEARS_DAYS: self.perf_5y,
        }

    @property
    def available_periods(self) -> Dict[int, Percentage]:
        """Retourne uniquement les performances disponibles (non None)."""
        return {k: v for k, v in self.all_periods.items() if v is not None}

    @property
    def all_positive(self) -> bool:
        """
        Vérifie si toutes les performances disponibles sont positives.

        C'est le critère principal pour la "résilience" d'un stock.
        """
        available = self.available_periods
        if not available:
            return False
        return all(perf.is_positive for perf in available.values())

    @property
    def all_available(self) -> bool:
        """Vérifie si toutes les périodes ont des données."""
        return all(v is not None for v in self.all_periods.values())

    def get_by_label(self, label: str) -> Optional[Percentage]:
        """
        Récupère une performance par son label (3M, 6M, 1Y, 3Y, 5Y).

        Args:
            label: Label de la période

        Returns:
            Percentage ou None
        """
        label_to_attr = {
            "3M": self.perf_3m,
            "6M": self.perf_6m,
            "1Y": self.perf_1y,
            "3Y": self.perf_3y,
            "5Y": self.perf_5y,
        }
        return label_to_attr.get(label.upper())

    def to_dict(self) -> Dict[str, Optional[float]]:
        """Convertit en dictionnaire pour sérialisation."""
        return {
            "perf_3m": self.perf_3m.as_percent if self.perf_3m else None,
            "perf_6m": self.perf_6m.as_percent if self.perf_6m else None,
            "perf_1y": self.perf_1y.as_percent if self.perf_1y else None,
            "perf_3y": self.perf_3y.as_percent if self.perf_3y else None,
            "perf_5y": self.perf_5y.as_percent if self.perf_5y else None,
        }


@dataclass
class ChartDataPoint:
    """
    Un point de données pour le graphique de prix.

    Attributs:
        date: Date du point
        price: Prix de clôture
    """

    date: datetime
    price: float

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation JSON."""
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "price": round(self.price, 2),
        }


@dataclass
class OHLCDataPoint:
    """
    Un point de données OHLC pour graphique candlestick.

    Attributs:
        time: Timestamp Unix (secondes)
        open: Prix d'ouverture
        high: Prix le plus haut
        low: Prix le plus bas
        close: Prix de cloture
        volume: Volume echange (optionnel)
    """

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convertit pour TradingView lightweight-charts."""
        result = {
            "time": self.time,
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
        }
        if self.volume is not None:
            result["value"] = self.volume
        return result


@dataclass
class StockInfo:
    """
    Informations de base sur un stock (métadonnées).

    Ces informations sont généralement stables et ne changent pas souvent.
    """

    name: str
    """Nom complet de l'entreprise."""

    currency: str = "USD"
    """Devise de cotation."""

    exchange: Optional[str] = None
    """Bourse de cotation (ex: NASDAQ, NYSE)."""

    sector: Optional[str] = None
    """Secteur d'activité."""

    industry: Optional[str] = None
    """Industrie spécifique."""

    asset_type: AssetType = AssetType.STOCK
    """Type d'actif (stock, ETF, crypto...)."""

    dividend_yield: Optional[Percentage] = None
    """Rendement du dividende."""

    def to_dict(self) -> Dict:
        """Convertit pour sérialisation."""
        return {
            "name": self.name,
            "currency": self.currency,
            "exchange": self.exchange,
            "sector": self.sector,
            "industry": self.industry,
            "asset_type": self.asset_type.value,
            "dividend_yield": (
                self.dividend_yield.as_percent if self.dividend_yield else None
            ),
        }


@dataclass
class StockAnalysis:
    """
    Résultat complet de l'analyse d'un stock.

    Contient toutes les métriques calculées et les données pour l'affichage.
    C'est l'objet principal retourné par le use case AnalyzeStock.
    """

    ticker: Ticker
    """Symbole boursier."""

    info: StockInfo
    """Informations de base."""

    performances: PerformanceData
    """Performances multi-périodes."""

    current_price: Optional[Money] = None
    """Prix actuel."""

    volatility: Optional[Percentage] = None
    """Volatilité annualisée."""

    chart_data: List[ChartDataPoint] = field(default_factory=list)
    """Données pour le graphique (derniers 5 ans)."""

    analyzed_at: datetime = field(default_factory=datetime.now)
    """Horodatage de l'analyse."""

    @property
    def is_resilient(self) -> bool:
        """
        Détermine si le stock est "résilient".

        Un stock est résilient s'il a des performances positives
        sur TOUTES les périodes analysées (3M, 6M, 1Y, 3Y, 5Y).

        Returns:
            True si toutes les performances sont positives
        """
        return self.performances.all_positive

    @property
    def volatility_level(self) -> str:
        """
        Catégorise le niveau de volatilité.

        Returns:
            "low", "medium", ou "high"
        """
        if self.volatility is None:
            return "unknown"

        vol_decimal = self.volatility.as_decimal
        if vol_decimal < LOW_VOLATILITY_THRESHOLD:
            return "low"
        elif vol_decimal > HIGH_VOLATILITY_THRESHOLD:
            return "high"
        return "medium"

    @property
    def is_high_volatility(self) -> bool:
        """Vérifie si la volatilité est élevée (> 30%)."""
        return self.volatility_level == "high"

    @property
    def score(self) -> int:
        """
        Calcule un score de qualité (0-100).

        Critères:
        - +20 points par période positive (max 100)
        - -10 points si haute volatilité

        Returns:
            Score entre 0 et 100
        """
        score = 0
        for perf in self.performances.available_periods.values():
            if perf.is_positive:
                score += 20

        if self.is_high_volatility:
            score = max(0, score - 10)

        return min(100, score)

    def to_dict(self) -> Dict:
        """
        Convertit l'analyse complète en dictionnaire.

        Utilisé pour la sérialisation JSON dans l'API.
        """
        return {
            "ticker": str(self.ticker),
            "info": self.info.to_dict(),
            "performances": self.performances.to_dict(),
            "current_price": (
                self.current_price.as_float() if self.current_price else None
            ),
            "currency": self.info.currency,
            "volatility": (
                self.volatility.as_percent if self.volatility else None
            ),
            "is_resilient": self.is_resilient,
            "volatility_level": self.volatility_level,
            "score": self.score,
            "chart_data": [point.to_dict() for point in self.chart_data],
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class Stock:
    """
    Entité principale représentant un stock.

    Agrège le ticker et son analyse. C'est l'entité racine pour
    les opérations liées aux stocks.
    """

    ticker: Ticker
    """Identifiant unique du stock."""

    analysis: Optional[StockAnalysis] = None
    """Analyse associée (peut être None si pas encore analysé)."""

    def __hash__(self) -> int:
        """Hash basé sur le ticker (identité)."""
        return hash(self.ticker)

    def __eq__(self, other: object) -> bool:
        """Égalité basée sur le ticker."""
        if isinstance(other, Stock):
            return self.ticker == other.ticker
        return False

    @property
    def is_analyzed(self) -> bool:
        """Vérifie si le stock a été analysé."""
        return self.analysis is not None

    @property
    def is_resilient(self) -> bool:
        """Raccourci vers analysis.is_resilient."""
        if self.analysis is None:
            return False
        return self.analysis.is_resilient

    def update_analysis(self, analysis: StockAnalysis) -> None:
        """
        Met à jour l'analyse du stock.

        Args:
            analysis: Nouvelle analyse

        Raises:
            ValueError: Si le ticker de l'analyse ne correspond pas
        """
        if analysis.ticker != self.ticker:
            raise ValueError(
                f"Le ticker de l'analyse ({analysis.ticker}) "
                f"ne correspond pas au stock ({self.ticker})"
            )
        self.analysis = analysis
