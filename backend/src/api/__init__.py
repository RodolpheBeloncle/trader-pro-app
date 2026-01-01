"""
Couche API (Présentation).

Contient:
- Routes HTTP (FastAPI)
- Middlewares
- Schémas Pydantic
- Injection de dépendances
"""

from src.api.app import create_app, app

__all__ = ["create_app", "app"]
