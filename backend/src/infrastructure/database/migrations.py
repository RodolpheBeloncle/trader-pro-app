"""
Migrations de base de données SQLite.

Ce module gère la création et l'évolution du schéma de la base de données.
Les migrations sont exécutées automatiquement au démarrage.

SCHÉMA:
- alerts: Alertes de prix avec notification Telegram
- trades: Journal des trades avec P&L
- journal_entries: Analyses pré/post trade
- news_cache: Cache des actualités Finnhub
- backtest_results: Résultats des backtests

VERSIONING:
- Table _migrations stocke les migrations exécutées
- Chaque migration a un numéro unique et une description
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


# =============================================================================
# DÉFINITION DU SCHÉMA
# =============================================================================

SCHEMA_SQL = """
-- Table de suivi des migrations
CREATE TABLE IF NOT EXISTS _migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER UNIQUE NOT NULL,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================================
-- ALERTES DE PRIX
-- ==========================================================================
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('price_above', 'price_below', 'percent_change')),
    target_value REAL NOT NULL,
    current_value REAL,
    is_active BOOLEAN DEFAULT TRUE,
    is_triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(is_triggered);

-- ==========================================================================
-- JOURNAL DES TRADES
-- ==========================================================================
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'closed', 'cancelled')),

    -- Prix et sizing
    entry_price REAL,
    exit_price REAL,
    stop_loss REAL,
    take_profit REAL,
    position_size INTEGER,

    -- Temps
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,

    -- P&L
    gross_pnl REAL,
    net_pnl REAL,
    fees REAL DEFAULT 0,
    r_multiple REAL,

    -- Métadonnées
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);

-- ==========================================================================
-- ENTRÉES DE JOURNAL (analyse pré/post trade)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    trade_id TEXT REFERENCES trades(id) ON DELETE CASCADE,

    -- Analyse pré-trade
    market_regime TEXT,
    market_bias TEXT,
    setup_type TEXT,
    timeframe TEXT,
    trade_thesis TEXT,
    confluence_factors TEXT,  -- JSON array

    -- Exécution
    execution_quality TEXT CHECK (execution_quality IN ('excellent', 'good', 'average', 'poor')),
    emotional_state TEXT CHECK (emotional_state IN ('calm', 'confident', 'anxious', 'fomo', 'revenge')),

    -- Analyse post-trade
    process_compliance TEXT CHECK (process_compliance IN ('followed', 'deviated', 'ignored')),
    mistakes TEXT,           -- JSON array
    what_went_well TEXT,     -- JSON array
    what_to_improve TEXT,    -- JSON array
    lessons_learned TEXT,
    trade_quality_score INTEGER CHECK (trade_quality_score BETWEEN 1 AND 10),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_journal_trade ON journal_entries(trade_id);
CREATE INDEX IF NOT EXISTS idx_journal_setup ON journal_entries(setup_type);

-- ==========================================================================
-- CACHE DES ACTUALITÉS (Finnhub)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS news_cache (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    url TEXT,
    image_url TEXT,
    sentiment TEXT CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    sentiment_score REAL,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_cache(published_at);
CREATE INDEX IF NOT EXISTS idx_news_fetched ON news_cache(fetched_at);

-- ==========================================================================
-- RÉSULTATS DE BACKTESTS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS backtest_results (
    id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    ticker TEXT NOT NULL,

    -- Période
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Capital
    initial_capital REAL NOT NULL,
    final_capital REAL,

    -- Métriques de performance
    total_return REAL,
    annualized_return REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    max_drawdown REAL,
    max_drawdown_duration INTEGER,  -- en jours

    -- Statistiques de trades
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate REAL,
    avg_win REAL,
    avg_loss REAL,
    profit_factor REAL,
    expectancy REAL,

    -- Paramètres et données
    parameters TEXT,  -- JSON
    equity_curve TEXT,  -- JSON array
    trades_data TEXT,  -- JSON array

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON backtest_results(strategy_name);
CREATE INDEX IF NOT EXISTS idx_backtest_ticker ON backtest_results(ticker);
CREATE INDEX IF NOT EXISTS idx_backtest_created ON backtest_results(created_at);

-- ==========================================================================
-- TRIGGERS pour updated_at automatique
-- ==========================================================================
CREATE TRIGGER IF NOT EXISTS update_alerts_timestamp
    AFTER UPDATE ON alerts
    FOR EACH ROW
BEGIN
    UPDATE alerts SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_trades_timestamp
    AFTER UPDATE ON trades
    FOR EACH ROW
BEGIN
    UPDATE trades SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_journal_timestamp
    AFTER UPDATE ON journal_entries
    FOR EACH ROW
BEGIN
    UPDATE journal_entries SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""


async def run_migrations(db: "DatabaseConnection") -> None:
    """
    Exécute les migrations de base de données.

    Cette fonction:
    1. Vérifie si la migration a déjà été appliquée
    2. Crée le schéma si nécessaire
    3. Enregistre la migration dans _migrations

    Args:
        db: Instance DatabaseConnection
    """
    async with db.transaction() as conn:
        # Vérifier si les migrations ont déjà été exécutées
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
        )
        migrations_table_exists = await cursor.fetchone() is not None

        if migrations_table_exists:
            # Vérifier la dernière version
            cursor = await conn.execute(
                "SELECT MAX(version) as version FROM _migrations"
            )
            row = await cursor.fetchone()
            current_version = row["version"] if row and row["version"] else 0

            if current_version >= 1:
                logger.info(f"Base de données déjà à jour (version {current_version})")
                return

        # Exécuter le schéma
        logger.info("Création du schéma de base de données...")
        await conn.executescript(SCHEMA_SQL)

        # Enregistrer la migration
        await conn.execute(
            "INSERT OR IGNORE INTO _migrations (version, description) VALUES (?, ?)",
            (1, "Initial schema: alerts, trades, journal, news, backtest")
        )

        logger.info("Migration 1 appliquée: schéma initial créé")


async def reset_database(db: "DatabaseConnection") -> None:
    """
    Supprime et recrée toutes les tables.

    ATTENTION: Perte de données irréversible!
    À utiliser uniquement pour les tests.

    Args:
        db: Instance DatabaseConnection
    """
    async with db.transaction() as conn:
        # Supprimer les tables dans l'ordre (respect des FK)
        tables = [
            "journal_entries",
            "trades",
            "alerts",
            "news_cache",
            "backtest_results",
            "_migrations"
        ]

        for table in tables:
            await conn.execute(f"DROP TABLE IF EXISTS {table}")

        # Supprimer les triggers
        triggers = [
            "update_alerts_timestamp",
            "update_trades_timestamp",
            "update_journal_timestamp"
        ]

        for trigger in triggers:
            await conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")

        logger.warning("Base de données réinitialisée")

    # Recréer le schéma
    await run_migrations(db)
