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
