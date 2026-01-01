"""
Scheduler pour les jobs de fond.

Utilise APScheduler pour planifier les taches periodiques.

ARCHITECTURE:
- Scheduler BackgroundScheduler (thread-based)
- Demarre au startup de l'application
- S'arrete proprement au shutdown

JOBS PLANIFIES:
- Token Refresh: toutes les heures

UTILISATION:
    from src.jobs.scheduler import create_scheduler, start_scheduler, stop_scheduler

    # Au startup
    scheduler = create_scheduler()
    start_scheduler(scheduler)

    # Au shutdown
    stop_scheduler(scheduler)
"""

import logging
import asyncio
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent

from src.jobs.token_refresh_job import create_token_refresh_job

logger = logging.getLogger(__name__)

# Instance globale du scheduler
_scheduler: Optional[BackgroundScheduler] = None


def create_scheduler() -> BackgroundScheduler:
    """
    Cree et configure le scheduler.

    Returns:
        BackgroundScheduler configure avec les jobs
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already exists, returning existing instance")
        return _scheduler

    logger.info("Creating scheduler...")

    scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,  # Fusionner les executions manquees
            "max_instances": 1,  # Une seule instance par job
            "misfire_grace_time": 60 * 5,  # 5 minutes de grace
        }
    )

    # Ajouter les listeners pour le logging
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    # Ajouter le job de refresh des tokens
    scheduler.add_job(
        _run_token_refresh_job,
        trigger=IntervalTrigger(hours=1),
        id="token_refresh",
        name="Token Refresh Job",
        replace_existing=True,
    )

    _scheduler = scheduler
    logger.info("Scheduler created with jobs: token_refresh (every 1h)")

    return scheduler


def start_scheduler(scheduler: Optional[BackgroundScheduler] = None) -> None:
    """
    Demarre le scheduler.

    Args:
        scheduler: Scheduler a demarrer (defaut: instance globale)
    """
    global _scheduler

    sched = scheduler or _scheduler
    if sched is None:
        logger.warning("No scheduler to start")
        return

    if sched.running:
        logger.warning("Scheduler already running")
        return

    sched.start()
    logger.info("Scheduler started")

    # Log les jobs planifies
    for job in sched.get_jobs():
        logger.info(f"  - {job.id}: {job.name} (next run: {job.next_run_time})")


def stop_scheduler(scheduler: Optional[BackgroundScheduler] = None) -> None:
    """
    Arrete le scheduler proprement.

    Args:
        scheduler: Scheduler a arreter (defaut: instance globale)
    """
    global _scheduler

    sched = scheduler or _scheduler
    if sched is None:
        logger.warning("No scheduler to stop")
        return

    if not sched.running:
        logger.warning("Scheduler not running")
        return

    sched.shutdown(wait=True)
    logger.info("Scheduler stopped")


def get_scheduler() -> Optional[BackgroundScheduler]:
    """
    Retourne l'instance globale du scheduler.

    Returns:
        BackgroundScheduler ou None si pas cree
    """
    return _scheduler


def run_job_now(job_id: str) -> bool:
    """
    Execute un job immediatement.

    Args:
        job_id: ID du job a executer

    Returns:
        True si le job a ete declenche, False sinon
    """
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        logger.warning("Scheduler not running, cannot trigger job")
        return False

    job = _scheduler.get_job(job_id)
    if job is None:
        logger.warning(f"Job not found: {job_id}")
        return False

    _scheduler.modify_job(job_id, next_run_time=None)  # Run immediately
    logger.info(f"Triggered job: {job_id}")
    return True


# =============================================================================
# PRIVATE FUNCTIONS
# =============================================================================

def _run_token_refresh_job() -> None:
    """
    Wrapper synchrone pour executer le job async.

    APScheduler ne supporte pas nativement les coroutines,
    donc on cree un event loop pour executer le job.
    """
    logger.debug("Running token refresh job...")

    job = create_token_refresh_job()

    # Creer ou recuperer un event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        stats = loop.run_until_complete(job.run())
        logger.info(f"Token refresh complete: {stats}")
    except Exception as e:
        logger.exception(f"Token refresh job failed: {e}")


def _on_job_executed(event: JobEvent) -> None:
    """Handler appele quand un job s'execute avec succes."""
    logger.debug(f"Job executed successfully: {event.job_id}")


def _on_job_error(event: JobEvent) -> None:
    """Handler appele quand un job echoue."""
    logger.error(
        f"Job failed: {event.job_id} - {event.exception}"
    )
