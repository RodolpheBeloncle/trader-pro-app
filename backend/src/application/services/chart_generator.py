"""
Générateur de graphiques professionnels avec Plotly.

Ce module crée des visualisations interactives de qualité institutionnelle
pour l'analyse technique et les recommandations d'investissement.

GRAPHIQUES DISPONIBLES:
1. Graphique de prix avec indicateurs (chandelier + Bollinger + MAs)
2. Tableau de bord RSI/MACD
3. Radar de scoring
4. Heatmap de corrélation
5. Comparatif de performances

UTILISATION:
    generator = ChartGenerator()
    fig = generator.create_technical_chart(ticker, data, indicators)
    html = fig.to_html()
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from src.application.interfaces.stock_data_provider import HistoricalDataPoint
from src.domain.entities.technical_analysis import TechnicalIndicators, Signal, Trend
from src.domain.entities.investment_recommendation import (
    InvestmentRecommendation,
    ScoreBreakdown,
    MarketScreenerResult,
)

logger = logging.getLogger(__name__)


# Palette de couleurs professionnelle
COLORS = {
    "primary": "#2962FF",      # Bleu principal
    "secondary": "#FF6D00",    # Orange
    "success": "#00C853",      # Vert
    "danger": "#FF1744",       # Rouge
    "warning": "#FFD600",      # Jaune
    "neutral": "#90A4AE",      # Gris
    "background": "#1E1E1E",   # Fond sombre
    "text": "#FFFFFF",         # Texte
    "grid": "#333333",         # Grille
    "bullish": "#26A69A",      # Vert chandelier
    "bearish": "#EF5350",      # Rouge chandelier
    "sma_20": "#FFEB3B",       # SMA 20
    "sma_50": "#FF9800",       # SMA 50
    "sma_200": "#E91E63",      # SMA 200
    "bollinger": "#7C4DFF",    # Bandes Bollinger
    "volume": "#42A5F5",       # Volume
}


class ChartGenerator:
    """
    Générateur de graphiques professionnels.

    Crée des visualisations interactives pour l'analyse technique
    et les recommandations d'investissement.
    """

    def __init__(self, theme: str = "dark"):
        """
        Initialise le générateur.

        Args:
            theme: "dark" ou "light"
        """
        self.theme = theme
        self._setup_template()

    def _setup_template(self):
        """Configure le template Plotly."""
        if self.theme == "dark":
            self.template = "plotly_dark"
            self.bg_color = COLORS["background"]
            self.text_color = COLORS["text"]
            self.grid_color = COLORS["grid"]
        else:
            self.template = "plotly_white"
            self.bg_color = "#FFFFFF"
            self.text_color = "#000000"
            self.grid_color = "#E0E0E0"

    def create_technical_chart(
        self,
        ticker: str,
        data: List[HistoricalDataPoint],
        indicators: TechnicalIndicators,
        show_bollinger: bool = True,
        show_mas: bool = True,
        show_volume: bool = True,
    ) -> go.Figure:
        """
        Crée un graphique technique complet avec chandeliers et indicateurs.

        Args:
            ticker: Symbole de l'actif
            data: Données historiques
            indicators: Indicateurs techniques calculés
            show_bollinger: Afficher les bandes de Bollinger
            show_mas: Afficher les moyennes mobiles
            show_volume: Afficher le volume

        Returns:
            Figure Plotly interactive
        """
        # Convertir en DataFrame
        df = pd.DataFrame([
            {
                'date': p.date,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume,
            }
            for p in data
        ])
        df.set_index('date', inplace=True)

        # Limiter aux 6 derniers mois pour la lisibilité
        df = df.tail(180)

        # Créer la figure avec sous-graphiques
        row_heights = [0.6, 0.2, 0.2] if show_volume else [0.7, 0.3]
        rows = 3 if show_volume else 2

        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=(f"{ticker} - Prix", "RSI", "Volume") if show_volume else (f"{ticker} - Prix", "RSI"),
        )

        # 1. Chandeliers japonais
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="Prix",
                increasing_line_color=COLORS["bullish"],
                decreasing_line_color=COLORS["bearish"],
            ),
            row=1, col=1
        )

        # 2. Bandes de Bollinger
        if show_bollinger:
            self._add_bollinger_bands(fig, df, indicators.bollinger.period, row=1, col=1)

        # 3. Moyennes mobiles
        if show_mas:
            self._add_moving_averages(fig, df, row=1, col=1)

        # 4. RSI
        self._add_rsi(fig, df, indicators.rsi.period, row=2, col=1)

        # 5. Volume
        if show_volume:
            self._add_volume(fig, df, row=3, col=1)

        # Layout
        fig.update_layout(
            template=self.template,
            title=dict(
                text=f"<b>{ticker}</b> - Analyse Technique | Signal: {indicators.overall_signal.value.upper()}",
                font=dict(size=20),
            ),
            xaxis_rangeslider_visible=False,
            height=800 if show_volume else 600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            hovermode="x unified",
        )

        # Ajouter des annotations pour les niveaux clés
        self._add_price_annotations(fig, df, indicators, row=1, col=1)

        return fig

    def _add_bollinger_bands(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
        period: int,
        row: int,
        col: int,
    ):
        """Ajoute les bandes de Bollinger."""
        middle = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = middle + (2 * std)
        lower = middle - (2 * std)

        # Zone remplie entre les bandes
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=upper,
                name="BB Upper",
                line=dict(color=COLORS["bollinger"], width=1, dash='dash'),
                showlegend=False,
            ),
            row=row, col=col
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=lower,
                name="BB Lower",
                fill='tonexty',
                fillcolor=f'rgba(124, 77, 255, 0.1)',
                line=dict(color=COLORS["bollinger"], width=1, dash='dash'),
                showlegend=False,
            ),
            row=row, col=col
        )

        # Bande centrale (SMA)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=middle,
                name="BB Middle",
                line=dict(color=COLORS["bollinger"], width=1),
            ),
            row=row, col=col
        )

    def _add_moving_averages(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
        row: int,
        col: int,
    ):
        """Ajoute les moyennes mobiles."""
        # SMA 20
        sma_20 = df['close'].rolling(window=20).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=sma_20,
                name="SMA 20",
                line=dict(color=COLORS["sma_20"], width=1),
            ),
            row=row, col=col
        )

        # SMA 50
        sma_50 = df['close'].rolling(window=50).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=sma_50,
                name="SMA 50",
                line=dict(color=COLORS["sma_50"], width=1.5),
            ),
            row=row, col=col
        )

        # SMA 200 (si assez de données)
        if len(df) >= 200:
            sma_200 = df['close'].rolling(window=200).mean()
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=sma_200,
                    name="SMA 200",
                    line=dict(color=COLORS["sma_200"], width=2),
                ),
                row=row, col=col
            )

    def _add_rsi(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
        period: int,
        row: int,
        col: int,
    ):
        """Ajoute l'indicateur RSI."""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # RSI line
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=rsi,
                name=f"RSI({period})",
                line=dict(color=COLORS["primary"], width=2),
            ),
            row=row, col=col
        )

        # Zones de surachat/survente
        fig.add_hline(y=70, line_dash="dash", line_color=COLORS["danger"], row=row, col=col)
        fig.add_hline(y=30, line_dash="dash", line_color=COLORS["success"], row=row, col=col)
        fig.add_hline(y=50, line_dash="dot", line_color=COLORS["neutral"], row=row, col=col)

        # Zone colorée
        fig.add_hrect(y0=70, y1=100, fillcolor=COLORS["danger"], opacity=0.1, row=row, col=col)
        fig.add_hrect(y0=0, y1=30, fillcolor=COLORS["success"], opacity=0.1, row=row, col=col)

        fig.update_yaxes(range=[0, 100], row=row, col=col)

    def _add_volume(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
        row: int,
        col: int,
    ):
        """Ajoute le graphique de volume."""
        colors = [
            COLORS["bullish"] if df['close'].iloc[i] >= df['open'].iloc[i] else COLORS["bearish"]
            for i in range(len(df))
        ]

        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                name="Volume",
                marker_color=colors,
                opacity=0.7,
            ),
            row=row, col=col
        )

        # Moyenne mobile du volume
        vol_sma = df['volume'].rolling(window=20).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=vol_sma,
                name="Vol SMA(20)",
                line=dict(color=COLORS["warning"], width=1),
            ),
            row=row, col=col
        )

    def _add_price_annotations(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
        indicators: TechnicalIndicators,
        row: int,
        col: int,
    ):
        """Ajoute des annotations pour les niveaux clés."""
        current_price = df['close'].iloc[-1]

        # Prix actuel
        fig.add_annotation(
            x=df.index[-1],
            y=current_price,
            text=f"Prix: {current_price:.2f}",
            showarrow=True,
            arrowhead=2,
            arrowcolor=COLORS["primary"],
            font=dict(color=COLORS["text"]),
            bgcolor=COLORS["primary"],
            row=row, col=col
        )

        # Supports
        for support in indicators.moving_averages.support_levels[:2]:
            fig.add_hline(
                y=support,
                line_dash="dot",
                line_color=COLORS["success"],
                annotation_text=f"Support: {support:.2f}",
                row=row, col=col
            )

        # Résistances
        for resistance in indicators.moving_averages.resistance_levels[:2]:
            fig.add_hline(
                y=resistance,
                line_dash="dot",
                line_color=COLORS["danger"],
                annotation_text=f"Résistance: {resistance:.2f}",
                row=row, col=col
            )

    def create_score_radar(
        self,
        recommendation: InvestmentRecommendation,
    ) -> go.Figure:
        """
        Crée un graphique radar du scoring multi-facteurs.

        Args:
            recommendation: Recommandation d'investissement

        Returns:
            Figure Plotly radar
        """
        breakdown = recommendation.score_breakdown

        categories = [
            'Performance',
            'Technique',
            'Momentum',
            'Volatilité',
            'Fondamentaux',
            'Timing',
        ]

        values = [
            breakdown.performance_score,
            breakdown.technical_score,
            breakdown.momentum_score,
            breakdown.volatility_score,
            breakdown.fundamental_score,
            breakdown.timing_score,
        ]

        # Fermer le polygone
        categories.append(categories[0])
        values.append(values[0])

        fig = go.Figure()

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                fillcolor=f'rgba(41, 98, 255, 0.3)',
                line=dict(color=COLORS["primary"], width=2),
                name=recommendation.ticker,
            )
        )

        # Zone de référence (50/100)
        fig.add_trace(
            go.Scatterpolar(
                r=[50] * 7,
                theta=categories,
                line=dict(color=COLORS["neutral"], width=1, dash='dash'),
                name="Référence (50)",
            )
        )

        fig.update_layout(
            template=self.template,
            title=dict(
                text=f"<b>{recommendation.ticker}</b> - Score Global: {recommendation.overall_score:.0f}/100",
                font=dict(size=18),
            ),
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                ),
            ),
            showlegend=True,
            height=500,
        )

        return fig

    def create_recommendation_dashboard(
        self,
        recommendation: InvestmentRecommendation,
        data: List[HistoricalDataPoint],
        indicators: TechnicalIndicators,
    ) -> go.Figure:
        """
        Crée un tableau de bord complet pour une recommandation.

        Args:
            recommendation: Recommandation
            data: Données historiques
            indicators: Indicateurs techniques

        Returns:
            Figure Plotly dashboard
        """
        fig = make_subplots(
            rows=2,
            cols=2,
            specs=[
                [{"type": "xy"}, {"type": "polar"}],
                [{"type": "indicator"}, {"type": "table"}],
            ],
            subplot_titles=(
                "Prix et Indicateurs",
                "Score Multi-Facteurs",
                "Recommandation",
                "Détails",
            ),
        )

        # 1. Mini graphique de prix (simplifié)
        df = pd.DataFrame([{'date': p.date, 'close': p.close} for p in data[-90:]])

        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['close'],
                name="Prix",
                line=dict(color=COLORS["primary"], width=2),
                fill='tozeroy',
                fillcolor='rgba(41, 98, 255, 0.1)',
            ),
            row=1, col=1
        )

        # 2. Radar scoring
        breakdown = recommendation.score_breakdown
        categories = ['Perf', 'Tech', 'Mom', 'Vol', 'Fund', 'Tim', 'Perf']
        values = [
            breakdown.performance_score,
            breakdown.technical_score,
            breakdown.momentum_score,
            breakdown.volatility_score,
            breakdown.fundamental_score,
            breakdown.timing_score,
            breakdown.performance_score,
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                fillcolor='rgba(41, 98, 255, 0.3)',
                line=dict(color=COLORS["primary"]),
            ),
            row=1, col=2
        )

        # 3. Indicateur de recommandation
        rec_colors = {
            "strong_buy": COLORS["success"],
            "buy": "#4CAF50",
            "accumulate": "#8BC34A",
            "hold": COLORS["warning"],
            "reduce": "#FF9800",
            "sell": "#FF5722",
            "strong_sell": COLORS["danger"],
            "avoid": "#B71C1C",
        }

        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=recommendation.overall_score,
                title={'text': recommendation.action_summary},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': rec_colors.get(recommendation.recommendation.value, COLORS["neutral"])},
                    'steps': [
                        {'range': [0, 30], 'color': "rgba(255, 23, 68, 0.3)"},
                        {'range': [30, 50], 'color': "rgba(255, 152, 0, 0.3)"},
                        {'range': [50, 70], 'color': "rgba(255, 235, 59, 0.3)"},
                        {'range': [70, 100], 'color': "rgba(0, 200, 83, 0.3)"},
                    ],
                },
            ),
            row=2, col=1
        )

        # 4. Tableau de détails
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Métrique", "Valeur"],
                    fill_color=COLORS["primary"],
                    font=dict(color="white"),
                    align="left",
                ),
                cells=dict(
                    values=[
                        ["Catégorie", "Risque", "Confiance", "Objectif CT", "Objectif LT"],
                        [
                            recommendation.category.value.title(),
                            recommendation.risk_level.value.title(),
                            f"{recommendation.confidence:.0f}%",
                            f"{recommendation.price_targets['short_term'].target_price:.2f}",
                            f"{recommendation.price_targets['long_term'].target_price:.2f}",
                        ],
                    ],
                    fill_color=self.bg_color,
                    align="left",
                ),
            ),
            row=2, col=2
        )

        fig.update_layout(
            template=self.template,
            title=dict(
                text=f"<b>{recommendation.ticker} - {recommendation.name}</b>",
                font=dict(size=20),
            ),
            height=700,
            showlegend=False,
        )

        return fig

    def create_market_heatmap(
        self,
        screener_results: MarketScreenerResult,
    ) -> go.Figure:
        """
        Crée une heatmap du marché basée sur les scores.

        Args:
            screener_results: Résultats du screening

        Returns:
            Figure Plotly heatmap
        """
        # Préparer les données
        tickers = []
        scores = []
        signals = []

        for rec in screener_results.best_overall[:30]:
            tickers.append(rec.ticker)
            scores.append(rec.overall_score)
            signals.append(rec.recommendation.value)

        # Créer une matrice pour le treemap
        df = pd.DataFrame({
            'ticker': tickers,
            'score': scores,
            'signal': signals,
        })

        # Treemap par score
        fig = px.treemap(
            df,
            path=['signal', 'ticker'],
            values='score',
            color='score',
            color_continuous_scale=['#FF1744', '#FFD600', '#00C853'],
            color_continuous_midpoint=50,
        )

        fig.update_layout(
            template=self.template,
            title=dict(
                text="<b>Market Overview</b> - Top 30 Actifs par Score",
                font=dict(size=20),
            ),
            height=600,
        )

        return fig

    def create_performance_comparison(
        self,
        recommendations: List[InvestmentRecommendation],
    ) -> go.Figure:
        """
        Crée un graphique comparatif des performances.

        Args:
            recommendations: Liste de recommandations à comparer

        Returns:
            Figure Plotly comparatif
        """
        if not recommendations:
            return go.Figure()

        tickers = [r.ticker for r in recommendations[:15]]
        overall_scores = [r.overall_score for r in recommendations[:15]]
        perf_scores = [r.score_breakdown.performance_score for r in recommendations[:15]]
        tech_scores = [r.score_breakdown.technical_score for r in recommendations[:15]]
        momentum_scores = [r.score_breakdown.momentum_score for r in recommendations[:15]]

        fig = go.Figure()

        # Score global
        fig.add_trace(
            go.Bar(
                name='Score Global',
                x=tickers,
                y=overall_scores,
                marker_color=COLORS["primary"],
            )
        )

        # Performance
        fig.add_trace(
            go.Bar(
                name='Performance',
                x=tickers,
                y=perf_scores,
                marker_color=COLORS["success"],
            )
        )

        # Technique
        fig.add_trace(
            go.Bar(
                name='Technique',
                x=tickers,
                y=tech_scores,
                marker_color=COLORS["secondary"],
            )
        )

        # Momentum
        fig.add_trace(
            go.Bar(
                name='Momentum',
                x=tickers,
                y=momentum_scores,
                marker_color=COLORS["warning"],
            )
        )

        fig.update_layout(
            template=self.template,
            title=dict(
                text="<b>Comparaison Multi-Facteurs</b>",
                font=dict(size=20),
            ),
            barmode='group',
            xaxis_tickangle=-45,
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
            ),
        )

        return fig

    def create_macd_chart(
        self,
        ticker: str,
        data: List[HistoricalDataPoint],
    ) -> go.Figure:
        """
        Crée un graphique MACD détaillé.

        Args:
            ticker: Symbole
            data: Données historiques

        Returns:
            Figure Plotly MACD
        """
        df = pd.DataFrame([
            {'date': p.date, 'close': p.close}
            for p in data[-180:]
        ])

        # Calculer MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.6, 0.4],
            subplot_titles=(f"{ticker} - Prix", "MACD"),
        )

        # Prix
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['close'],
                name="Prix",
                line=dict(color=COLORS["primary"]),
            ),
            row=1, col=1
        )

        # MACD Line
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=macd_line,
                name="MACD",
                line=dict(color=COLORS["primary"], width=2),
            ),
            row=2, col=1
        )

        # Signal Line
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=signal_line,
                name="Signal",
                line=dict(color=COLORS["secondary"], width=2),
            ),
            row=2, col=1
        )

        # Histogram
        colors = [COLORS["success"] if h >= 0 else COLORS["danger"] for h in histogram]
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=histogram,
                name="Histogram",
                marker_color=colors,
            ),
            row=2, col=1
        )

        fig.update_layout(
            template=self.template,
            title=f"<b>{ticker}</b> - Analyse MACD",
            height=600,
            showlegend=True,
            hovermode="x unified",
        )

        return fig

    def export_to_html(self, fig: go.Figure, filename: str) -> str:
        """
        Exporte un graphique en HTML.

        Args:
            fig: Figure Plotly
            filename: Nom du fichier

        Returns:
            Chemin du fichier créé
        """
        filepath = f"{filename}.html"
        fig.write_html(filepath, include_plotlyjs=True, full_html=True)
        return filepath

    def get_chart_json(self, fig: go.Figure) -> str:
        """
        Retourne le JSON d'un graphique pour intégration web.

        Args:
            fig: Figure Plotly

        Returns:
            JSON string
        """
        return fig.to_json()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_chart_generator(theme: str = "dark") -> ChartGenerator:
    """Factory function pour créer un générateur de graphiques."""
    return ChartGenerator(theme=theme)
