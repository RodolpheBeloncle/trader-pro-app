# Security Improvements TODO

## Status: Corrections effectuées le 2026-01-06

### FAIT
- [x] Nouvelle clé de chiffrement générée
- [x] Placeholders mis dans .env (secrets à régénérer manuellement)
- [x] Tokens Saxo maintenant chiffrés avec Fernet (AES-128)
- [x] Migration automatique des anciens tokens non chiffrés

---

## P1 - Priorité Haute (À faire rapidement)

### 1. Régénérer les secrets compromis
**Action manuelle requise !**

- [ ] **Saxo Bank**: Aller sur https://www.developer.saxo/openapi/appmanagement
  - Révoquer l'ancienne application
  - Créer une nouvelle application
  - Mettre à jour `SAXO_APP_KEY` et `SAXO_APP_SECRET` dans `.env`

- [ ] **Telegram**: Aller sur @BotFather
  - Envoyer `/revoke` pour révoquer l'ancien token
  - Envoyer `/token` pour obtenir un nouveau token
  - Mettre à jour `TELEGRAM_BOT_TOKEN` dans `.env`
  - Mettre à jour `TELEGRAM_CHAT_ID` avec votre ID

- [ ] **Finnhub**: Aller sur https://finnhub.io/dashboard
  - Régénérer une nouvelle clé API
  - Mettre à jour `FINNHUB_API_KEY` dans `.env`

### 2. Ajouter authentification sur l'API
**Fichiers concernés:** `backend/src/api/routes/*`

```python
# Exemple d'implémentation JWT
# backend/src/api/middleware/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 3. Sécuriser la configuration initiale
**Fichier:** `backend/src/api/routes/config.py:158-265`

Options:
- [ ] Ajouter une vérification par email
- [ ] Exiger une confirmation physique (bouton sur l'interface)
- [ ] Limiter à localhost uniquement pour la config initiale

### 4. Supprimer le token du callback OAuth
**Fichier:** `backend/src/api/routes/saxo.py:231`

```python
# AVANT (dangereux)
return AuthCallbackResponse(
    success=True,
    access_token=token.access_token,  # Exposé!
    ...
)

# APRÈS (sécurisé)
return AuthCallbackResponse(
    success=True,
    # access_token supprimé - stocké uniquement côté serveur
    environment=token.environment,
    expires_in=token.expires_in_seconds,
    message=f"Connecté à Saxo ({token.environment})"
)
```

---

## P2 - Priorité Moyenne

### 5. Restreindre CORS
**Fichier:** `backend/src/api/app.py:115-121`

```python
# AVANT
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APRÈS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    allow_credentials=True,
    max_age=86400,
)
```

### 6. Ajouter rate limiting
**Fichier:** Nouveau middleware à créer

```python
# backend/src/api/middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Dans les routes:
@router.get("/api/stocks/analyze")
@limiter.limit("30/minute")
async def analyze_stock(...):
```

### 7. Sécuriser les WebSockets
**Fichier:** `backend/src/api/routes/websocket.py`

- [ ] Ajouter authentification par token dans l'URL
- [ ] Limiter le nombre de connexions par IP
- [ ] Ajouter rate limiting sur les subscriptions

---

## P3 - Priorité Basse

### 8. Lockfile avec hashes
```bash
pip install pip-tools
pip-compile requirements.txt --generate-hashes -o requirements.lock
```

### 9. Audit des dépendances
```bash
pip install pip-audit
pip-audit -r requirements.txt
```

### 10. Headers de sécurité HTTP
```python
# backend/src/api/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

### 11. Logging sécurisé
- [ ] S'assurer qu'aucun secret n'est loggé
- [ ] Ajouter rotation des logs
- [ ] Masquer les données sensibles dans les erreurs

---

## Notes techniques

### Structure de chiffrement actuelle

Les tokens Saxo sont maintenant stockés dans ce format:
```json
{
  "encrypted": "gAAAAAB...(données Fernet)...",
  "updated_at": "2026-01-06T10:30:00"
}
```

Le contenu déchiffré a cette structure:
```json
{
  "SIM": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": "2026-01-06T11:30:00",
    "environment": "SIM"
  }
}
```

### Migration automatique

Le code `saxo_auth.py` détecte automatiquement les anciens fichiers non chiffrés et les migre vers le nouveau format chiffré au premier accès.
