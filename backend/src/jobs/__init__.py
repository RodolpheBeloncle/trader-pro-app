"""
Module de jobs planifies pour Stock Analyzer.

Ce module contient les taches de fond:
- TokenRefreshJob: Rafraichissement automatique des tokens OAuth

ARCHITECTURE:
- Utilise APScheduler pour la planification
- Les jobs sont demarre/arrete avec l'application FastAPI
- Separe de la logique metier (utilise les services existants)

UTILISATION:
    from src.jobs.scheduler import create_scheduler, start_scheduler, stop_scheduler

    scheduler = create_scheduler()
    start_scheduler(scheduler)
    # ...
    stop_scheduler(scheduler)
"""

from src.jobs.token_refresh_job import TokenRefreshJob
from src.jobs.scheduler import create_scheduler, start_scheduler, stop_scheduler

__all__ = [
    "TokenRefreshJob",
    "create_scheduler",
    "start_scheduler",
    "stop_scheduler",
]
