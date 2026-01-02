"""
Serveur MCP pour Stock Analyzer.

Expose les outils d'analyse de stocks a Claude Desktop.

UTILISATION:
    # Lancer le serveur MCP
    python -m src.infrastructure.mcp.mcp_server

    # Ou via le module
    from src.infrastructure.mcp.mcp_server import run_server
    run_server()

OUTILS DISPONIBLES:
    - analyze_stock: Analyse un ticker unique
    - analyze_batch: Analyse plusieurs tickers
    - get_portfolio: Recupere le portefeuille Saxo
    - list_markets: Liste les presets de marches
    - get_market_tickers: Recupere les tickers d'un marche
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ajouter le repertoire backend au path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logging.info(f"Loaded environment from {env_file}")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.infrastructure.mcp.tools.analyze_tool import (
    analyze_stock_tool,
    analyze_batch_tool,
)
from src.infrastructure.mcp.tools.portfolio_tool import get_portfolio_tool
from src.infrastructure.mcp.tools.market_tool import (
    list_markets_tool,
    get_market_tickers_tool,
)
from src.infrastructure.mcp.tools.decision_tool import (
    get_recommendation_tool,
    screen_opportunities_tool,
    get_technical_analysis_tool,
    get_portfolio_advice_tool,
    find_best_etfs_tool,
    compare_assets_tool,
)
from src.infrastructure.mcp.tools.pro_decision_tool import (
    pro_analyze_tool,
    get_market_structure_tool,
    calculate_position_size_tool,
    calculate_risk_reward_tool,
    calculate_kelly_tool,
)
from src.infrastructure.mcp.tools.alert_tool import (
    create_alert_tool,
    list_alerts_tool,
    delete_alert_tool,
    check_alerts_tool,
    get_alerts_stats_tool,
)
from src.infrastructure.mcp.tools.journal_tool import (
    log_trade_tool,
    close_trade_tool,
    get_journal_stats_tool,
    get_journal_dashboard_tool,
    list_trades_tool,
    add_post_trade_analysis_tool,
)
from src.infrastructure.mcp.tools.news_tool import (
    get_news_tool,
    get_sentiment_tool,
    get_market_news_tool,
    get_news_summary_tool,
)
from src.infrastructure.mcp.tools.backtest_tool import (
    run_backtest_tool,
    list_strategies_tool,
)
from src.infrastructure.mcp.tools.notification_tool import (
    test_notification,
    send_notification,
    send_market_alert,
    send_portfolio_update,
    get_notification_status,
)
from src.infrastructure.mcp.tools.monte_carlo_tool import (
    monte_carlo_price_simulation_tool,
    monte_carlo_portfolio_risk_tool,
    get_portfolio_analysis_tool,
    set_portfolio_alerts_tool,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mcp_server() -> Server:
    """
    Cree et configure le serveur MCP.

    Returns:
        Server MCP configure avec tous les outils
    """
    server = Server("stock-analyzer")

    # Enregistrer les outils
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Liste tous les outils disponibles."""
        return [
            # Analyse
            Tool(
                name="analyze_stock",
                description=(
                    "Analyse un ticker boursier en calculant les performances "
                    "sur 5 periodes (3m, 6m, 1y, 3y, 5y), la volatilite, "
                    "et determine si le stock est resilient (toutes perfs positives)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker (ex: AAPL, MSFT, BTC-USD)",
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="analyze_batch",
                description=(
                    "Analyse plusieurs tickers en batch. "
                    "Retourne les performances et la resilience de chaque stock."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des tickers a analyser",
                        }
                    },
                    "required": ["tickers"],
                },
            ),
            # Portfolio
            Tool(
                name="get_portfolio",
                description=(
                    "Recupere le portefeuille du compte Saxo Bank connecte. "
                    "Retourne les positions, les gains/pertes, et les metriques. "
                    "Necessite une authentification Saxo prealable."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            # Marches
            Tool(
                name="list_markets",
                description=(
                    "Liste tous les presets de marches disponibles. "
                    "Inclut: S&P 500, CAC 40, NASDAQ 100, Crypto, ETFs, etc."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_market_tickers",
                description=(
                    "Recupere les tickers d'un preset de marche specifique."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "market_id": {
                            "type": "string",
                            "description": "ID du marche (ex: sp500, cac40, crypto)",
                        }
                    },
                    "required": ["market_id"],
                },
            ),
            # Outils d'aide a la decision
            Tool(
                name="get_recommendation",
                description=(
                    "Genere une recommandation d'investissement complete pour un ticker. "
                    "Inclut: scoring multi-facteurs, analyse technique, objectifs de prix, "
                    "niveau de risque, et strategie d'entree. "
                    "Ideal pour decider d'acheter ou vendre un actif."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker (ex: AAPL, MSFT, VOO)",
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="screen_opportunities",
                description=(
                    "Screene une liste d'actifs pour trouver les meilleures opportunites. "
                    "Retourne les actifs classes par score avec recommandations. "
                    "Utile pour trouver les meilleurs investissements dans un marche."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des tickers a analyser",
                        },
                        "min_score": {
                            "type": "integer",
                            "description": "Score minimum pour inclusion (0-100, defaut: 50)",
                            "default": 50,
                        }
                    },
                    "required": ["tickers"],
                },
            ),
            Tool(
                name="get_technical_analysis",
                description=(
                    "Fournit une analyse technique detaillee avec tous les indicateurs: "
                    "RSI, MACD, Bollinger Bands, Moyennes Mobiles, Volume, ATR. "
                    "Inclut signaux, tendance, et interpretations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="get_portfolio_advice",
                description=(
                    "Genere des conseils pour construire un portefeuille optimal. "
                    "Categorise les actifs (croissance, valeur, dividende, momentum, defensif), "
                    "suggere une allocation, et identifie les opportunites emergentes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des actifs a considerer",
                        }
                    },
                    "required": ["tickers"],
                },
            ),
            Tool(
                name="find_best_etfs",
                description=(
                    "Trouve les meilleurs ETFs par categorie. "
                    "Categories: tech, world, dividend, emerging, bond, sp500, europe, crypto, gold, realestate, all. "
                    "Retourne les ETFs analyses et classes avec recommandations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Categorie d'ETF (tech, world, dividend, emerging, bond, sp500, europe, crypto, gold, realestate, all)",
                            "default": "all",
                        }
                    },
                },
            ),
            Tool(
                name="compare_assets",
                description=(
                    "Compare plusieurs actifs cote a cote avec scoring detaille. "
                    "Permet de choisir le meilleur investissement parmi plusieurs options."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des tickers a comparer (max 10)",
                            "maxItems": 10,
                        }
                    },
                    "required": ["tickers"],
                },
            ),
            # Outils professionnels (MCP Trader Pro)
            Tool(
                name="pro_analyze",
                description=(
                    "Analyse professionnelle complete avec processus MCP (Mental/Cognitive/Decision). "
                    "Inclut: structure de marche, zones de liquidite, Fair Value Gaps, Order Blocks, "
                    "decision de trading avec checklist, position sizing. "
                    "Utilise le processus decisonnel d'un trader institutionnel."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        },
                        "capital": {
                            "type": "number",
                            "description": "Capital disponible pour le trading (defaut: 10000)",
                            "default": 10000,
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="get_market_structure",
                description=(
                    "Analyse detaillee de la structure de marche professionnelle. "
                    "Retourne: regime (tendance/range), swing points (HH/HL/LH/LL), "
                    "zones de liquidite, Fair Value Gaps, Order Blocks. "
                    "Essentiel pour comprendre OU le marche va, pas seulement les indicateurs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="calculate_position_size",
                description=(
                    "Calcule la taille de position optimale selon la regle d'or du risk management. "
                    "Ne jamais risquer plus de X% du capital par trade. "
                    "Retourne: nombre d'actions, valeur de la position, risque reel."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "capital": {
                            "type": "number",
                            "description": "Capital total disponible",
                        },
                        "risk_percent": {
                            "type": "number",
                            "description": "Pourcentage de risque par trade (ex: 1.0 pour 1%)",
                        },
                        "entry_price": {
                            "type": "number",
                            "description": "Prix d'entree prevu",
                        },
                        "stop_loss_price": {
                            "type": "number",
                            "description": "Prix du stop loss",
                        }
                    },
                    "required": ["capital", "risk_percent", "entry_price", "stop_loss_price"],
                },
            ),
            Tool(
                name="calculate_risk_reward",
                description=(
                    "Calcule le ratio Risk/Reward d'un trade. "
                    "Regle: Minimum 1:2 R/R pour compenser un win rate de 40%. "
                    "Retourne: ratio R/R, qualite du setup, win rate minimum requis."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entry_price": {
                            "type": "number",
                            "description": "Prix d'entree",
                        },
                        "stop_loss_price": {
                            "type": "number",
                            "description": "Prix du stop loss",
                        },
                        "target_price": {
                            "type": "number",
                            "description": "Prix cible",
                        }
                    },
                    "required": ["entry_price", "stop_loss_price", "target_price"],
                },
            ),
            Tool(
                name="calculate_kelly",
                description=(
                    "Calcule le Kelly Criterion pour l'allocation optimale. "
                    "ATTENTION: Kelly complet est trop agressif. Utilisez 1/4 ou 1/2 Kelly. "
                    "Necessite vos statistiques de trading (win rate, gain/perte moyen)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "win_rate": {
                            "type": "number",
                            "description": "Taux de reussite en % (ex: 45 pour 45%)",
                        },
                        "avg_win": {
                            "type": "number",
                            "description": "Gain moyen par trade gagnant",
                        },
                        "avg_loss": {
                            "type": "number",
                            "description": "Perte moyenne par trade perdant (valeur positive)",
                        }
                    },
                    "required": ["win_rate", "avg_win", "avg_loss"],
                },
            ),
            # ========== OUTILS ALERTES ==========
            Tool(
                name="create_alert",
                description=(
                    "Cree une alerte de prix avec notification Telegram. "
                    "Types: price_above (prix depasse), price_below (prix descend), "
                    "percent_change (variation en %). "
                    "Quand l'alerte se declenche, vous recevez un message Telegram."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker (ex: AAPL, BTC-USD)",
                        },
                        "alert_type": {
                            "type": "string",
                            "enum": ["price_above", "price_below", "percent_change"],
                            "description": "Type d'alerte",
                        },
                        "target_value": {
                            "type": "number",
                            "description": "Valeur cible (prix ou pourcentage)",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Notes personnelles (optionnel)",
                        }
                    },
                    "required": ["ticker", "alert_type", "target_value"],
                },
            ),
            Tool(
                name="list_alerts",
                description=(
                    "Liste toutes les alertes de prix. "
                    "Peut filtrer par statut (actives uniquement) ou par ticker."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "active_only": {
                            "type": "boolean",
                            "description": "Uniquement les alertes actives (defaut: true)",
                            "default": True,
                        },
                        "ticker": {
                            "type": "string",
                            "description": "Filtrer par ticker (optionnel)",
                        }
                    },
                },
            ),
            Tool(
                name="delete_alert",
                description="Supprime une alerte de prix par son ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "alert_id": {
                            "type": "string",
                            "description": "ID de l'alerte a supprimer",
                        }
                    },
                    "required": ["alert_id"],
                },
            ),
            Tool(
                name="check_alerts",
                description=(
                    "Verifie manuellement toutes les alertes actives contre les prix actuels. "
                    "Declenche les notifications Telegram si les conditions sont remplies."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_alerts_stats",
                description="Retourne les statistiques des alertes (total, actives, declenchees).",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            # ========== OUTILS JOURNAL DE TRADING ==========
            Tool(
                name="log_trade",
                description=(
                    "Enregistre un nouveau trade dans le journal. "
                    "Peut etre en statut 'planned' (en attente) ou 'active' (execute). "
                    "Inclut la these de trade, le setup, les facteurs de confluence. "
                    "Notification Telegram a l'ouverture."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["long", "short"],
                            "description": "Direction du trade",
                        },
                        "entry_price": {
                            "type": "number",
                            "description": "Prix d'entree (0 si planned)",
                        },
                        "stop_loss": {
                            "type": "number",
                            "description": "Prix du stop loss",
                        },
                        "take_profit": {
                            "type": "number",
                            "description": "Prix du take profit",
                        },
                        "position_size": {
                            "type": "integer",
                            "description": "Nombre d'actions/unites",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["planned", "active"],
                            "description": "Statut du trade (defaut: planned)",
                            "default": "planned",
                        },
                        "setup_type": {
                            "type": "string",
                            "description": "Type de setup (breakout, pullback, reversal...)",
                        },
                        "trade_thesis": {
                            "type": "string",
                            "description": "Raison du trade, analyse",
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Timeframe (1m, 5m, 1h, 4h, D)",
                        },
                        "confluence_factors": {
                            "type": "string",
                            "description": "Facteurs de confluence separes par virgule",
                        }
                    },
                    "required": ["ticker", "direction"],
                },
            ),
            Tool(
                name="close_trade",
                description=(
                    "Cloture un trade actif avec calcul automatique du P&L. "
                    "Calcule: gross P&L, net P&L (apres frais), R-multiple. "
                    "Notification Telegram avec le resultat."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trade_id": {
                            "type": "string",
                            "description": "ID du trade a cloturer",
                        },
                        "exit_price": {
                            "type": "number",
                            "description": "Prix de sortie",
                        },
                        "fees": {
                            "type": "number",
                            "description": "Frais de transaction (defaut: 0)",
                            "default": 0,
                        }
                    },
                    "required": ["trade_id", "exit_price"],
                },
            ),
            Tool(
                name="get_journal_stats",
                description=(
                    "Retourne les statistiques globales du journal de trading. "
                    "Inclut: win rate, profit factor, R-multiple moyen, "
                    "meilleur/pire trade, serie de gains/pertes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_journal_dashboard",
                description=(
                    "Dashboard complet du journal de trading. "
                    "Inclut: stats, trades actifs, trades recents, "
                    "erreurs frequentes, lecons apprises."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_trades",
                description=(
                    "Liste les trades du journal avec filtres optionnels. "
                    "Peut filtrer par statut (planned, active, closed) ou ticker."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["planned", "active", "closed", "cancelled"],
                            "description": "Filtrer par statut",
                        },
                        "ticker": {
                            "type": "string",
                            "description": "Filtrer par ticker",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Nombre max de trades (defaut: 10)",
                            "default": 10,
                        }
                    },
                },
            ),
            Tool(
                name="add_post_trade_analysis",
                description=(
                    "Ajoute une analyse post-trade a un trade cloture. "
                    "Essentiel pour l'amelioration continue: qualite d'execution, "
                    "etat emotionnel, respect du processus, erreurs, lecons."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trade_id": {
                            "type": "string",
                            "description": "ID du trade",
                        },
                        "execution_quality": {
                            "type": "string",
                            "enum": ["excellent", "good", "average", "poor"],
                            "description": "Qualite d'execution",
                        },
                        "emotional_state": {
                            "type": "string",
                            "enum": ["calm", "confident", "anxious", "fomo", "revenge"],
                            "description": "Etat emotionnel pendant le trade",
                        },
                        "process_compliance": {
                            "type": "string",
                            "enum": ["followed", "deviated", "ignored"],
                            "description": "Respect du processus de trading",
                        },
                        "trade_quality_score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Score de qualite du trade (1-10)",
                        },
                        "mistakes": {
                            "type": "string",
                            "description": "Erreurs commises (separees par virgule)",
                        },
                        "what_went_well": {
                            "type": "string",
                            "description": "Ce qui a bien fonctionne (separe par virgule)",
                        },
                        "lessons_learned": {
                            "type": "string",
                            "description": "Lecon principale a retenir",
                        }
                    },
                    "required": ["trade_id", "execution_quality", "emotional_state", "process_compliance", "trade_quality_score"],
                },
            ),
            # ========== OUTILS NEWS ==========
            Tool(
                name="get_news",
                description=(
                    "Recupere les dernieres actualites Finnhub pour un ticker. "
                    "Inclut: titre, resume, source, sentiment, date."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Nombre max d'articles (defaut: 10)",
                            "default": 10,
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="get_sentiment",
                description=(
                    "Analyse le sentiment des actualites pour un ticker. "
                    "Retourne: score combine, repartition positif/negatif/neutre, "
                    "interpretation (haussier/baissier)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        }
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="get_market_news",
                description=(
                    "Recupere les actualites generales du marche. "
                    "Categories: general, forex, crypto, merger."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["general", "forex", "crypto", "merger"],
                            "description": "Categorie de news (defaut: general)",
                            "default": "general",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Nombre max d'articles (defaut: 15)",
                            "default": 15,
                        }
                    },
                },
            ),
            Tool(
                name="get_news_summary",
                description=(
                    "Resume des actualites pour plusieurs tickers. "
                    "Utile pour un scan rapide du sentiment de marche."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "string",
                            "description": "Tickers separes par virgule (ex: AAPL,MSFT,GOOGL)",
                        },
                        "limit_per_ticker": {
                            "type": "integer",
                            "description": "Articles par ticker (defaut: 3)",
                            "default": 3,
                        }
                    },
                    "required": ["tickers"],
                },
            ),
            # ========== OUTILS BACKTESTING ==========
            Tool(
                name="run_backtest",
                description=(
                    "Lance un backtest d'une strategie de trading sur donnees historiques. "
                    "Strategies disponibles: sma_crossover (croisement moyennes mobiles), "
                    "rsi (niveaux surachat/survente), momentum (force du mouvement). "
                    "Retourne: performance, Sharpe ratio, drawdown, win rate, etc."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker (ex: AAPL, MSFT)",
                        },
                        "strategy": {
                            "type": "string",
                            "enum": ["sma_crossover", "rsi", "momentum"],
                            "description": "Nom de la strategie",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Date de debut YYYY-MM-DD (defaut: 1 an)",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Date de fin YYYY-MM-DD (defaut: aujourd'hui)",
                        },
                        "initial_capital": {
                            "type": "number",
                            "description": "Capital initial (defaut: 10000)",
                            "default": 10000,
                        },
                        "parameters": {
                            "type": "string",
                            "description": "Parametres JSON (ex: {\"short_period\": 10, \"long_period\": 30})",
                        }
                    },
                    "required": ["ticker", "strategy"],
                },
            ),
            Tool(
                name="list_backtest_strategies",
                description=(
                    "Liste toutes les strategies de backtesting disponibles "
                    "avec leurs parametres par defaut."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            # Outils de notification
            Tool(
                name="test_notification",
                description=(
                    "Teste la connexion aux services de notification (Telegram). "
                    "Envoie un message de test si la connexion fonctionne."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="send_notification",
                description=(
                    "Envoie une notification personnalisee via Telegram. "
                    "Types: info, success, warning, error, trade, alert, analysis."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Le message a envoyer",
                        },
                        "title": {
                            "type": "string",
                            "description": "Titre optionnel du message",
                        },
                        "notification_type": {
                            "type": "string",
                            "enum": ["info", "success", "warning", "error", "trade", "alert", "analysis"],
                            "description": "Type de notification (defaut: info)",
                            "default": "info",
                        }
                    },
                    "required": ["message"],
                },
            ),
            Tool(
                name="send_market_alert",
                description=(
                    "Envoie une alerte de marche detaillee. "
                    "Inclut ticker, type d'alerte, prix actuel/cible, recommandation."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker",
                        },
                        "alert_type": {
                            "type": "string",
                            "enum": ["breakout", "reversal", "volume", "momentum", "support", "resistance", "opportunity", "warning"],
                            "description": "Type d'alerte",
                        },
                        "message": {
                            "type": "string",
                            "description": "Description de l'alerte",
                        },
                        "current_price": {
                            "type": "number",
                            "description": "Prix actuel",
                        },
                        "target_price": {
                            "type": "number",
                            "description": "Prix cible",
                        },
                        "recommendation": {
                            "type": "string",
                            "enum": ["buy", "sell", "hold", "watch"],
                            "description": "Recommandation",
                        }
                    },
                    "required": ["ticker", "alert_type", "message"],
                },
            ),
            Tool(
                name="send_portfolio_update",
                description=(
                    "Envoie un resume du portfolio avec P&L. "
                    "Inclut valeur totale, P&L du jour, top gagnants/perdants."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "total_value": {
                            "type": "number",
                            "description": "Valeur totale du portfolio",
                        },
                        "daily_pnl": {
                            "type": "number",
                            "description": "P&L du jour en valeur",
                        },
                        "daily_pnl_percent": {
                            "type": "number",
                            "description": "P&L du jour en pourcentage",
                        },
                        "positions_summary": {
                            "type": "string",
                            "description": "Resume des positions",
                        },
                        "top_gainers": {
                            "type": "string",
                            "description": "Top gagnants",
                        },
                        "top_losers": {
                            "type": "string",
                            "description": "Top perdants",
                        }
                    },
                    "required": ["total_value", "daily_pnl", "daily_pnl_percent"],
                },
            ),
            Tool(
                name="get_notification_status",
                description=(
                    "Retourne le statut des services de notification. "
                    "Indique si Telegram est configure et pret."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            # ========== Outils Monte Carlo & Portfolio ==========
            Tool(
                name="monte_carlo_price_simulation",
                description=(
                    "Simulation Monte Carlo des trajectoires de prix. "
                    "Utilise le mouvement Brownien geometrique (GBM) pour simuler "
                    "l'evolution future du prix et calculer les intervalles de confiance "
                    "(5%, 25%, 50%, 75%, 95%). Retourne aussi la probabilite de perte "
                    "et le drawdown attendu."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Symbole du ticker (ex: AAPL, MSFT)",
                        },
                        "time_horizon_days": {
                            "type": "integer",
                            "description": "Horizon de simulation en jours (defaut 30)",
                            "default": 30,
                        },
                        "num_simulations": {
                            "type": "integer",
                            "description": "Nombre de trajectoires simulees (defaut 10000)",
                            "default": 10000,
                        },
                    },
                    "required": ["ticker"],
                },
            ),
            Tool(
                name="monte_carlo_portfolio_risk",
                description=(
                    "Calcul du risque portefeuille par Monte Carlo. "
                    "Calcule VaR (Value at Risk) a 99%, 95%, 90%, CVaR/Expected Shortfall, "
                    "attribution du risque par position, et ratio de diversification."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "positions": {
                            "type": "string",
                            "description": 'JSON array des positions: [{"symbol": "AAPL", "market_value": 10000}, ...]',
                        },
                        "time_horizon_days": {
                            "type": "integer",
                            "description": "Horizon du VaR en jours (defaut 1)",
                            "default": 1,
                        },
                        "num_simulations": {
                            "type": "integer",
                            "description": "Nombre de simulations (defaut 10000)",
                            "default": 10000,
                        },
                    },
                    "required": ["positions"],
                },
            ),
            Tool(
                name="get_portfolio_analysis",
                description=(
                    "Analyse enrichie du portefeuille Saxo. "
                    "Pour chaque position: analyse technique (RSI, MACD, trend), "
                    "news et sentiment, metriques de risque (poids, SL/TP suggeres), "
                    "et recommandation (BUY/SELL/HOLD/ADD/REDUCE)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="set_portfolio_alerts",
                description=(
                    "Configure les alertes stop loss et take profit pour les positions Saxo. "
                    "Cree automatiquement des alertes basees sur le prix d'entree."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "string",
                            "description": "Liste de tickers separes par virgule (vide = toutes les positions)",
                        },
                        "stop_loss_percent": {
                            "type": "number",
                            "description": "Pourcentage de stop loss sous le prix d'entree (defaut 8)",
                            "default": 8,
                        },
                        "take_profit_percent": {
                            "type": "number",
                            "description": "Pourcentage de take profit au-dessus (defaut 24)",
                            "default": 24,
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Appelle un outil specifique."""
        logger.info(f"Calling tool: {name} with args: {arguments}")

        try:
            if name == "analyze_stock":
                result = await analyze_stock_tool(arguments.get("ticker", ""))
            elif name == "analyze_batch":
                result = await analyze_batch_tool(arguments.get("tickers", []))
            elif name == "get_portfolio":
                result = await get_portfolio_tool()
            elif name == "list_markets":
                result = await list_markets_tool()
            elif name == "get_market_tickers":
                result = await get_market_tickers_tool(arguments.get("market_id", ""))
            # Outils d'aide a la decision
            elif name == "get_recommendation":
                result = await get_recommendation_tool(arguments.get("ticker", ""))
            elif name == "screen_opportunities":
                result = await screen_opportunities_tool(
                    arguments.get("tickers", []),
                    arguments.get("min_score", 50),
                )
            elif name == "get_technical_analysis":
                result = await get_technical_analysis_tool(arguments.get("ticker", ""))
            elif name == "get_portfolio_advice":
                result = await get_portfolio_advice_tool(arguments.get("tickers", []))
            elif name == "find_best_etfs":
                result = await find_best_etfs_tool(arguments.get("category", "all"))
            elif name == "compare_assets":
                result = await compare_assets_tool(arguments.get("tickers", []))
            # Outils professionnels MCP Trader Pro
            elif name == "pro_analyze":
                result = await pro_analyze_tool(
                    arguments.get("ticker", ""),
                    arguments.get("capital", 10000),
                )
            elif name == "get_market_structure":
                result = await get_market_structure_tool(arguments.get("ticker", ""))
            elif name == "calculate_position_size":
                result = await calculate_position_size_tool(
                    arguments.get("capital", 0),
                    arguments.get("risk_percent", 1.0),
                    arguments.get("entry_price", 0),
                    arguments.get("stop_loss_price", 0),
                )
            elif name == "calculate_risk_reward":
                result = await calculate_risk_reward_tool(
                    arguments.get("entry_price", 0),
                    arguments.get("stop_loss_price", 0),
                    arguments.get("target_price", 0),
                )
            elif name == "calculate_kelly":
                result = await calculate_kelly_tool(
                    arguments.get("win_rate", 50),
                    arguments.get("avg_win", 100),
                    arguments.get("avg_loss", 100),
                )
            # ========== Outils Alertes ==========
            elif name == "create_alert":
                result = await create_alert_tool(
                    ticker=arguments.get("ticker", ""),
                    alert_type=arguments.get("alert_type", "price_above"),
                    target_value=arguments.get("target_value", 0),
                    notes=arguments.get("notes", ""),
                )
            elif name == "list_alerts":
                result = await list_alerts_tool(
                    active_only=arguments.get("active_only", True),
                    ticker=arguments.get("ticker", ""),
                )
            elif name == "delete_alert":
                result = await delete_alert_tool(arguments.get("alert_id", ""))
            elif name == "check_alerts":
                result = await check_alerts_tool()
            elif name == "get_alerts_stats":
                result = await get_alerts_stats_tool()
            # ========== Outils Journal de Trading ==========
            elif name == "log_trade":
                result = await log_trade_tool(
                    ticker=arguments.get("ticker", ""),
                    direction=arguments.get("direction", "long"),
                    entry_price=arguments.get("entry_price", 0),
                    stop_loss=arguments.get("stop_loss", 0),
                    take_profit=arguments.get("take_profit", 0),
                    position_size=arguments.get("position_size", 0),
                    status=arguments.get("status", "planned"),
                    setup_type=arguments.get("setup_type", ""),
                    trade_thesis=arguments.get("trade_thesis", ""),
                    timeframe=arguments.get("timeframe", ""),
                    confluence_factors=arguments.get("confluence_factors", ""),
                )
            elif name == "close_trade":
                result = await close_trade_tool(
                    trade_id=arguments.get("trade_id", ""),
                    exit_price=arguments.get("exit_price", 0),
                    fees=arguments.get("fees", 0),
                )
            elif name == "get_journal_stats":
                result = await get_journal_stats_tool()
            elif name == "get_journal_dashboard":
                result = await get_journal_dashboard_tool()
            elif name == "list_trades":
                result = await list_trades_tool(
                    status=arguments.get("status", ""),
                    ticker=arguments.get("ticker", ""),
                    limit=arguments.get("limit", 10),
                )
            elif name == "add_post_trade_analysis":
                result = await add_post_trade_analysis_tool(
                    trade_id=arguments.get("trade_id", ""),
                    execution_quality=arguments.get("execution_quality", "average"),
                    emotional_state=arguments.get("emotional_state", "calm"),
                    process_compliance=arguments.get("process_compliance", "followed"),
                    trade_quality_score=arguments.get("trade_quality_score", 5),
                    mistakes=arguments.get("mistakes", ""),
                    what_went_well=arguments.get("what_went_well", ""),
                    lessons_learned=arguments.get("lessons_learned", ""),
                )
            # ========== Outils News ==========
            elif name == "get_news":
                result = await get_news_tool(
                    ticker=arguments.get("ticker", ""),
                    limit=arguments.get("limit", 10),
                )
            elif name == "get_sentiment":
                result = await get_sentiment_tool(arguments.get("ticker", ""))
            elif name == "get_market_news":
                result = await get_market_news_tool(
                    category=arguments.get("category", "general"),
                    limit=arguments.get("limit", 15),
                )
            elif name == "get_news_summary":
                result = await get_news_summary_tool(
                    tickers=arguments.get("tickers", ""),
                    limit_per_ticker=arguments.get("limit_per_ticker", 3),
                )
            # ========== Outils Backtesting ==========
            elif name == "run_backtest":
                result = await run_backtest_tool(
                    ticker=arguments.get("ticker", ""),
                    strategy=arguments.get("strategy", "sma_crossover"),
                    start_date=arguments.get("start_date", ""),
                    end_date=arguments.get("end_date", ""),
                    initial_capital=arguments.get("initial_capital", 10000),
                    parameters=arguments.get("parameters", ""),
                )
            elif name == "list_backtest_strategies":
                result = await list_strategies_tool()
            # ========== Outils Notification ==========
            elif name == "test_notification":
                result = await test_notification()
            elif name == "send_notification":
                result = await send_notification(
                    message=arguments.get("message", ""),
                    title=arguments.get("title"),
                    notification_type=arguments.get("notification_type", "info"),
                )
            elif name == "send_market_alert":
                result = await send_market_alert(
                    ticker=arguments.get("ticker", ""),
                    alert_type=arguments.get("alert_type", ""),
                    message=arguments.get("message", ""),
                    current_price=arguments.get("current_price"),
                    target_price=arguments.get("target_price"),
                    recommendation=arguments.get("recommendation"),
                )
            elif name == "send_portfolio_update":
                result = await send_portfolio_update(
                    total_value=arguments.get("total_value", 0),
                    daily_pnl=arguments.get("daily_pnl", 0),
                    daily_pnl_percent=arguments.get("daily_pnl_percent", 0),
                    positions_summary=arguments.get("positions_summary"),
                    top_gainers=arguments.get("top_gainers"),
                    top_losers=arguments.get("top_losers"),
                )
            elif name == "get_notification_status":
                result = await get_notification_status()
            # ========== Outils Monte Carlo & Portfolio ==========
            elif name == "monte_carlo_price_simulation":
                result = await monte_carlo_price_simulation_tool(
                    ticker=arguments.get("ticker", ""),
                    time_horizon_days=arguments.get("time_horizon_days", 30),
                    num_simulations=arguments.get("num_simulations", 10000),
                )
            elif name == "monte_carlo_portfolio_risk":
                result = await monte_carlo_portfolio_risk_tool(
                    positions=arguments.get("positions", "[]"),
                    time_horizon_days=arguments.get("time_horizon_days", 1),
                    num_simulations=arguments.get("num_simulations", 10000),
                )
            elif name == "get_portfolio_analysis":
                result = await get_portfolio_analysis_tool()
            elif name == "set_portfolio_alerts":
                result = await set_portfolio_alerts_tool(
                    tickers=arguments.get("tickers"),
                    stop_loss_percent=arguments.get("stop_loss_percent", 8.0),
                    take_profit_percent=arguments.get("take_profit_percent", 24.0),
                )
            else:
                result = f"Outil inconnu: {name}"

            return [TextContent(type="text", text=result)]

        except Exception as e:
            logger.exception(f"Error in tool {name}: {e}")
            return [TextContent(type="text", text=f"Erreur: {str(e)}")]

    return server


async def run_server():
    """
    Lance le serveur MCP en mode stdio.
    """
    logger.info("Starting Stock Analyzer MCP Server...")

    # Initialiser la base de données avant de démarrer le serveur
    try:
        from src.infrastructure.database.connection import init_database
        await init_database()
        logger.info("Database initialized for MCP server")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    server = create_mcp_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Point d'entree principal."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
