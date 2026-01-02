"""
Module de jobs planifies pour Stock Analyzer.

Ce module contient les taches de fond:
- Alert Checker: Verification periodique des alertes

ARCHITECTURE:
- Utilise APScheduler pour la planification
- Les jobs sont demarre/arrete avec l'application FastAPI

UTILISATION:
    from src.jobs.scheduler import create_scheduler, start_scheduler, stop_scheduler

    scheduler = create_scheduler()
    start_scheduler(scheduler)
    # ...
    stop_scheduler(scheduler)
"""

from src.jobs.scheduler import create_scheduler, start_scheduler, stop_scheduler

__all__ = [
    "create_scheduler",
    "start_scheduler",
    "stop_scheduler",
]
