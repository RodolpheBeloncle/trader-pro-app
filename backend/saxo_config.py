"""
Saxo OpenAPI Configuration

Pour obtenir vos credentials:
1. Créez un compte sur https://www.developer.saxo/
2. Créez une application: https://www.developer.saxo/openapi/appmanagement
3. Copiez App Key et App Secret dans le fichier .env

IMPORTANT: Ne jamais commiter le fichier .env avec de vraies credentials !
"""

import os
from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv()

# =============================================================================
# SAXO API CONFIGURATION
# =============================================================================

# Mode: "SIM" pour simulation, "LIVE" pour production
SAXO_ENV = os.getenv("SAXO_ENVIRONMENT", "SIM")

# URLs selon l'environnement
SAXO_URLS = {
    "SIM": {
        "auth": "https://sim.logonvalidation.net",
        "api": "https://gateway.saxobank.com/sim/openapi",
        "streaming": "wss://streaming.saxobank.com/sim/openapi"
    },
    "LIVE": {
        "auth": "https://live.logonvalidation.net",
        "api": "https://gateway.saxobank.com/openapi",
        "streaming": "wss://streaming.saxobank.com/openapi"
    }
}

# Credentials (à configurer via variables d'environnement)
SAXO_APP_KEY = os.getenv("SAXO_APP_KEY", "")
SAXO_APP_SECRET = os.getenv("SAXO_APP_SECRET", "")

# Redirect URI pour OAuth2
SAXO_REDIRECT_URI = os.getenv("SAXO_REDIRECT_URI", "http://localhost:5173")

# Scopes OAuth2 requis
SAXO_SCOPES = [
    "openid",
    "profile",
    "trade",          # Pour passer des ordres
    "portfolio",      # Pour voir le portefeuille
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_auth_url():
    """Get the OAuth2 authorization URL"""
    return SAXO_URLS[SAXO_ENV]["auth"]

def get_api_url():
    """Get the API base URL"""
    return SAXO_URLS[SAXO_ENV]["api"]

def get_streaming_url():
    """Get the streaming WebSocket URL"""
    return SAXO_URLS[SAXO_ENV]["streaming"]

def is_configured():
    """Check if Saxo API is configured"""
    return bool(SAXO_APP_KEY and SAXO_APP_SECRET)
