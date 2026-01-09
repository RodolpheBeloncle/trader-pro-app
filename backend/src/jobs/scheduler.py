"""
Scheduler pour les jobs de fond.

Utilise APScheduler pour planifier les taches periodiques.

ARCHITECTURE:
- Scheduler BackgroundScheduler (thread-based)
- Demarre au startup de l'application
- S'arrete proprement au shutdown

JOBS PLANIFIES:
- Alert Checker: toutes les 60s (verification alertes prix + techniques)
- Portfolio Monitor: toutes les 5min (detection nouvelles positions, auto-alertes SL/TP)
- Daily Summary: tous les jours a 18h (resume portefeuille via Telegram)
"""

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent

from src.jobs.alert_checker import register_alert_checker
from src.jobs.portfolio_monitor import register_portfolio_monitor
from src.jobs.daily_summary import register_daily_summary
from src.jobs.token_refresh import register_token_refresh_job
from src.jobs.cleanup_jobs import register_cleanup_jobs

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
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 60 * 5,
        }
    )

    # Listeners pour le logging
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    # Job de verification des alertes (toutes les 60s)
    register_alert_checker(scheduler)

    # Job de monitoring du portefeuille (toutes les 5min)
    register_portfolio_monitor(scheduler)

    # Job de resume journalier (tous les jours a 18h)
    register_daily_summary(scheduler)

    # Job de refresh proactif des tokens Saxo (toutes les 10min, run au demarrage)
    register_token_refresh_job(scheduler)

    # Jobs de nettoyage et maintenance (news cleanup, WAL checkpoint, memory cleanup)
    register_cleanup_jobs(scheduler)

    _scheduler = scheduler
    logger.info(
        "Scheduler created with jobs: "
        "alert_checker (60s), portfolio_monitor (5min), daily_summary (18h00), "
        "token_refresh (10min), cleanup_jobs (news 3am, WAL 6h, memory 4am)"
    )

    return scheduler


def start_scheduler(scheduler: Optional[BackgroundScheduler] = None) -> None:
    """Demarre le scheduler."""
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

    for job in sched.get_jobs():
        logger.info(f"  - {job.id}: {job.name} (next run: {job.next_run_time})")


def stop_scheduler(scheduler: Optional[BackgroundScheduler] = None) -> None:
    """Arrete le scheduler proprement."""
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
    """Retourne l'instance globale du scheduler."""
    return _scheduler


def update_alert_checker_interval(seconds: int) -> bool:
    """
    Met a jour l'intervalle du job de verification des alertes.

    Args:
        seconds: Nouvel intervalle en secondes

    Returns:
        True si mis a jour avec succes
    """
    global _scheduler

    if _scheduler is None:
        logger.warning("Cannot update interval: scheduler not initialized")
        return False

    try:
        # Reschedule le job avec le nouvel intervalle
        _scheduler.reschedule_job(
            "alert_checker",
            trigger="interval",
            seconds=seconds,
        )
        logger.info(f"Alert checker interval updated to {seconds}s")
        return True
    except Exception as e:
        logger.error(f"Failed to update alert checker interval: {e}")
        return False


def get_job_info(job_id: str) -> Optional[dict]:
    """
    Retourne les informations sur un job.

    Args:
        job_id: ID du job

    Returns:
        Dict avec les infos ou None
    """
    global _scheduler

    if _scheduler is None:
        return None

    job = _scheduler.get_job(job_id)
    if job is None:
        return None

    return {
        "id": job.id,
        "name": job.name,
        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        "trigger": str(job.trigger),
    }


def _on_job_executed(event: JobEvent) -> None:
    """Handler appele quand un job s'execute avec succes."""
    logger.debug(f"Job executed successfully: {event.job_id}")


def _on_job_error(event: JobEvent) -> None:
    """Handler appele quand un job echoue."""
    logger.error(f"Job failed: {event.job_id} - {event.exception}")
