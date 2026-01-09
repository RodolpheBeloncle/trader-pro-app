"""
Jobs de maintenance et nettoyage automatique.

Ce module contient les jobs pour:
- Nettoyer le cache des news anciennes (>72h)
- Optimiser la base de donnees SQLite (checkpoint WAL)
- Nettoyer les caches en memoire

PLANIFICATION:
- News cleanup: tous les jours a 3h du matin
- WAL checkpoint: toutes les 6 heures
"""

import logging
import asyncio
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# Configuration
NEWS_MAX_AGE_HOURS = 72  # Supprimer les news de plus de 72h
WAL_CHECKPOINT_INTERVAL_HOURS = 6


async def cleanup_news_cache_async() -> dict:
    """
    Nettoie les anciennes entrees du cache de news.

    Supprime toutes les news de plus de NEWS_MAX_AGE_HOURS heures
    pour eviter que la base de donnees ne grossisse indefiniment.

    Returns:
        Dict avec le nombre d'entrees supprimees
    """
    try:
        from src.infrastructure.database.repositories.news_repository import NewsRepository

        repo = NewsRepository()
        deleted_count = await repo.cleanup_old(max_age_hours=NEWS_MAX_AGE_HOURS)

        logger.info(f"News cache cleanup: {deleted_count} old entries deleted (>{NEWS_MAX_AGE_HOURS}h)")

        return {
            "success": True,
            "deleted_count": deleted_count,
            "max_age_hours": NEWS_MAX_AGE_HOURS,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error during news cache cleanup: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def wal_checkpoint_async() -> dict:
    """
    Execute un checkpoint WAL sur la base SQLite.

    Le mode WAL (Write-Ahead Logging) peut accumuler des donnees
    dans le fichier .wal. Ce checkpoint force SQLite a ecrire
    les donnees dans le fichier principal et libere l'espace.

    Returns:
        Dict avec les informations du checkpoint
    """
    try:
        from src.infrastructure.database.connection import get_database

        db = get_database()
        async with db.connection() as conn:
            # PRAGMA wal_checkpoint(TRUNCATE) force un checkpoint complet
            # et tronque le fichier WAL pour recuperer l'espace disque
            cursor = await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = await cursor.fetchone()

            # Resultat: (busy, log, checkpointed)
            # busy: 0 si succes, 1 si une autre connexion bloquait
            # log: nombre de frames dans le WAL avant checkpoint
            # checkpointed: nombre de frames ecrites dans la DB

            busy = result[0] if result else -1
            log_frames = result[1] if result else 0
            checkpointed = result[2] if result else 0

            if busy == 0:
                logger.info(
                    f"WAL checkpoint completed: {checkpointed}/{log_frames} frames written"
                )
            else:
                logger.warning(
                    f"WAL checkpoint partial (busy): {checkpointed}/{log_frames} frames"
                )

            return {
                "success": busy == 0,
                "busy": busy,
                "log_frames": log_frames,
                "checkpointed_frames": checkpointed,
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"Error during WAL checkpoint: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def cleanup_memory_caches_async() -> dict:
    """
    Nettoie les caches en memoire qui pourraient grossir.

    Cible:
    - Cache des client keys Saxo
    - Cache du backtest data loader

    Returns:
        Dict avec les caches nettoyes
    """
    cleaned = []

    try:
        # Nettoyer le cache du backtest data loader si disponible
        try:
            from src.backtesting.data_loader import BacktestDataLoader
            loader = BacktestDataLoader()
            loader.clear_cache()
            cleaned.append("backtest_data_loader")
            logger.debug("Backtest data loader cache cleared")
        except Exception as e:
            logger.debug(f"Could not clear backtest cache: {e}")

        # Les caches LRU dans dependencies.py ont deja clear_caches()
        # mais on ne veut pas les nettoyer car ce sont des singletons

        logger.info(f"Memory caches cleaned: {cleaned}")

        return {
            "success": True,
            "cleaned_caches": cleaned,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error during memory cache cleanup: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def cleanup_news_cache_job() -> None:
    """Point d'entree sync pour APScheduler - nettoyage news."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(cleanup_news_cache_async())
        finally:
            loop.close()
    except Exception as e:
        logger.exception(f"Error in news cleanup job: {e}")


def wal_checkpoint_job() -> None:
    """Point d'entree sync pour APScheduler - checkpoint WAL."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(wal_checkpoint_async())
        finally:
            loop.close()
    except Exception as e:
        logger.exception(f"Error in WAL checkpoint job: {e}")


def cleanup_memory_job() -> None:
    """Point d'entree sync pour APScheduler - nettoyage memoire."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(cleanup_memory_caches_async())
        finally:
            loop.close()
    except Exception as e:
        logger.exception(f"Error in memory cleanup job: {e}")


async def run_startup_cleanup_async() -> None:
    """
    Execute le nettoyage au demarrage de l'application (version async).

    Important pour les environnements ou l'app est souvent redemarree
    (PC personnel, Docker local) et ou les jobs cron nocturnes
    ne s'executent jamais.
    """
    print("[CLEANUP] Running startup cleanup tasks...", flush=True)
    logger.info("Running startup cleanup tasks...")

    # Nettoyage news
    result_news = await cleanup_news_cache_async()
    print(f"[CLEANUP] News: {result_news.get('deleted_count', 0)} old entries deleted", flush=True)

    # Checkpoint WAL
    result_wal = await wal_checkpoint_async()
    print(f"[CLEANUP] WAL checkpoint: {result_wal.get('checkpointed_frames', 0)} frames", flush=True)

    print("[CLEANUP] Startup cleanup completed", flush=True)
    logger.info("Startup cleanup completed")


def register_cleanup_jobs(scheduler: "BackgroundScheduler") -> None:
    """
    Enregistre tous les jobs de nettoyage.

    Args:
        scheduler: Instance APScheduler
    """
    # NOTE: Le cleanup au demarrage est fait dans app.py via run_startup_cleanup_async()
    # car ici on est dans un contexte sync et FastAPI a deja une boucle async

    # ==========================================================================
    # JOBS PLANIFIES
    # ==========================================================================

    # Nettoyage des news - tous les jours a 3h du matin OU toutes les 24h
    scheduler.add_job(
        cleanup_news_cache_job,
        "interval",
        hours=24,
        id="news_cache_cleanup",
        name="News Cache Cleanup (every 24h)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Checkpoint WAL - toutes les 6 heures
    scheduler.add_job(
        wal_checkpoint_job,
        "interval",
        hours=WAL_CHECKPOINT_INTERVAL_HOURS,
        id="wal_checkpoint",
        name=f"WAL Checkpoint (every {WAL_CHECKPOINT_INTERVAL_HOURS}h)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Nettoyage memoire - toutes les 24h
    scheduler.add_job(
        cleanup_memory_job,
        "interval",
        hours=24,
        id="memory_cleanup",
        name="Memory Cache Cleanup (every 24h)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "Cleanup jobs registered: "
        "news_cache_cleanup (startup + every 24h), "
        f"wal_checkpoint (startup + every {WAL_CHECKPOINT_INTERVAL_HOURS}h), "
        "memory_cleanup (every 24h)"
    )
