"""
Point d'entree principal du backend Stock Analyzer.

Ce fichier sert de point d'entree pour uvicorn et importe
l'application FastAPI depuis la nouvelle architecture Clean.

UTILISATION:
    # Developpement
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

    # Production
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

    # Avec python directement
    python main.py

ARCHITECTURE:
    - L'application est creee via le pattern Application Factory
    - La configuration est chargee depuis .env via pydantic-settings
    - Les routes sont organisees par domaine dans src/api/routes/
"""

import logging
import sys
from pathlib import Path

# Ajouter le repertoire backend au path pour les imports
# Cela permet d'importer depuis src.* meme quand on lance depuis ce fichier
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Importer l'application depuis la nouvelle architecture
from src.api.app import create_app
from src.config.settings import get_settings

# Configurer le logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Creer l'instance de l'application
# Cette instance est utilisee par uvicorn: uvicorn main:app
app = create_app()


def main():
    """
    Lance le serveur uvicorn en mode developpement.

    Cette fonction est appelee quand on execute directement ce fichier:
        python main.py

    En production, utilisez plutot:
        uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    """
    import uvicorn

    logger.info("=" * 60)
    logger.info("Stock Analyzer API - Starting server")
    logger.info("=" * 60)
    logger.info(f"Environment: {'DEBUG' if settings.DEBUG else 'PRODUCTION'}")
    logger.info(f"Saxo configured: {settings.is_saxo_configured}")
    logger.info(f"Server: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"API Docs: http://{settings.HOST}:{settings.PORT}/api/docs")
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
