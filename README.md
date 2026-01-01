# Stock Analyzer

Application d'analyse multi-périodes pour identifier les **actions résilientes** avec des performances positives sur toutes les périodes (3M, 6M, 1Y, 3Y, 5Y) + intégration **Saxo Bank** pour le trading.

---

## Table des matières

- [Fonctionnalités](#fonctionnalités)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration Saxo Bank](#configuration-saxo-bank)
- [Utilisation](#utilisation)
- [API Reference](#api-reference)
- [Docker](#docker)
- [Structure du projet](#structure-du-projet)
- [Développement](#développement)
- [License](#license)

---

## Fonctionnalités

### Analyse de stocks
- **Analyse multi-périodes** : Performance sur 3M, 6M, 1Y, 3Y, 5Y
- **Détection de résilience** : Identifie les actions positives sur TOUTES les périodes
- **Presets de marchés** : Hong Kong, CAC 40, S&P 500, Tech, Dividendes
- **Graphiques interactifs** : Historique 5 ans avec Recharts
- **Volatilité** : Identification des actions à risque élevé
- **Export CSV** : Exportez vos analyses

### Intégration Saxo Bank
- **Authentification OAuth2** : Connexion sécurisée à votre compte Saxo
- **Portefeuille en temps réel** : Visualisez vos positions
- **Analyse enrichie** : Analyse de résilience sur vos positions
- **Trading** : Passez des ordres (Market/Limit)
- **Historique** : Consultez vos transactions

---

## Quick Start

### Option 1 : Script de lancement (Recommandé)

```bash
# Rendre le script exécutable
chmod +x run.sh

# Lancer l'application
./run.sh
```

Le script va :
1. Installer les dépendances Python
2. Installer les dépendances Node.js
3. Démarrer le backend sur le port 8000
4. Démarrer le frontend sur le port 5173
5. Ouvrir automatiquement le navigateur

### Option 2 : Docker Compose

```bash
# Copier la configuration d'environnement
cp backend/.env.example backend/.env
# Éditer backend/.env avec vos clés Saxo

# Lancer avec Docker
docker-compose up --build
```

### Option 3 : Installation manuelle

Voir [Installation](#installation) ci-dessous.

---

## Installation

### Prérequis

- **Python** 3.9+
- **Node.js** 18+
- **npm** ou **yarn**

### Backend

```bash
cd backend

# Créer l'environnement virtuel
python3 -m venv venv

# Activer l'environnement
source venv/bin/activate  # macOS/Linux
# ou
.\venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -r requirements.txt

# Copier et configurer l'environnement
cp .env.example .env
# Éditer .env avec vos clés Saxo (optionnel)

# Lancer le serveur
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Installer les dépendances
npm install

# Lancer le serveur de développement
npm run dev
```

### URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| OpenAPI Schema | http://localhost:8000/openapi.json |

---

## Configuration Saxo Bank

L'intégration Saxo Bank est **optionnelle**. L'application fonctionne sans pour l'analyse de stocks via Yahoo Finance.

### 1. Créer une application Saxo

1. Allez sur [Saxo Developer Portal](https://www.developer.saxo/openapi/appmanagement)
2. Créez une nouvelle application
3. Configurez le **Redirect URI** : `http://localhost:5173`
4. Notez votre **App Key** et **App Secret**

### 2. Configurer l'environnement

```bash
cd backend
cp .env.example .env
```

Éditez `backend/.env` :

```env
SAXO_APP_KEY=votre_app_key
SAXO_APP_SECRET=votre_app_secret
SAXO_ENVIRONMENT=SIM          # SIM pour simulation, LIVE pour production
SAXO_REDIRECT_URI=http://localhost:5173
```

### 3. Environnements Saxo

| Environnement | Description | URL Auth |
|---------------|-------------|----------|
| `SIM` | Sandbox avec données fictives | sim.logonvalidation.net |
| `LIVE` | Production avec argent réel | live.logonvalidation.net |

> **ATTENTION** : En mode `LIVE`, les ordres passés sont réels !

---

## Utilisation

### Analyse de stocks

1. **Ajouter manuellement** : Tapez un ticker (ex: `AAPL`, `MSFT`) et cliquez "Add"
2. **Charger un preset** : Cliquez sur Hong Kong, CAC 40, S&P 500, etc.
3. **Voir les détails** : Cliquez sur une ligne pour voir le graphique 5 ans
4. **Filtrer** :
   - Toggle "Resilient only" pour n'afficher que les actions positives sur toutes les périodes
   - Ajustez "Max volatility" pour filtrer par risque
5. **Exporter** : Cliquez "Export CSV" pour télécharger l'analyse

### Portefeuille Saxo

1. Cliquez sur "Connect Saxo" dans l'interface
2. Connectez-vous avec vos identifiants Saxo
3. Visualisez votre portefeuille avec analyse de résilience

---

## API Reference

### Endpoints d'analyse

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | GET | Health check |
| `POST /api/analyze` | POST | Analyse un ticker |
| `POST /api/analyze-batch` | POST | Analyse plusieurs tickers |
| `GET /api/markets` | GET | Liste des presets de marchés |
| `GET /api/markets/{id}` | GET | Tickers d'un marché |
| `POST /api/export/csv` | POST | Export CSV |

### Endpoints Saxo

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/saxo/status` | GET | Statut de configuration |
| `GET /api/saxo/auth/url` | GET | URL d'autorisation OAuth2 |
| `GET /api/saxo/auth/callback` | GET | Callback OAuth2 |
| `POST /api/saxo/auth/refresh` | POST | Rafraîchir le token |
| `GET /api/saxo/portfolio` | GET | Portefeuille avec positions |
| `GET /api/saxo/orders` | GET | Liste des ordres |
| `POST /api/saxo/orders` | POST | Passer un ordre |
| `DELETE /api/saxo/orders/{id}` | DELETE | Annuler un ordre |
| `GET /api/saxo/history` | GET | Historique des transactions |
| `GET /api/saxo/search` | GET | Rechercher un instrument |

### Exemple d'appel API

```bash
# Analyser une action
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'

# Analyser plusieurs actions
curl -X POST http://localhost:8000/api/analyze-batch \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT", "GOOGL"]}'
```

---

## Docker

### Commandes Docker

```bash
# Construire et lancer
docker-compose up --build

# Lancer en arrière-plan
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f backend
docker-compose logs -f frontend

# Arrêter
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v

# Reconstruire un service
docker-compose build backend
docker-compose build frontend
```

### Variables d'environnement Docker

Créez un fichier `.env` à la racine du projet :

```env
SAXO_APP_KEY=votre_app_key
SAXO_APP_SECRET=votre_app_secret
SAXO_ENVIRONMENT=SIM
SAXO_REDIRECT_URI=http://localhost:5173
```

Docker Compose lira automatiquement ce fichier.

### Ports exposés

| Service | Port Host | Port Container |
|---------|-----------|----------------|
| Backend | 8000 | 8000 |
| Frontend | 5173 | 5173 |

---

## Structure du projet

```
stock-analyzer/
├── backend/
│   ├── main.py              # FastAPI app & routes principales
│   ├── analyzer.py          # Logique d'analyse de stocks
│   ├── markets.py           # Presets de marchés
│   ├── saxo_config.py       # Configuration Saxo API
│   ├── saxo_service.py      # Service Saxo (auth, trading)
│   ├── saxo_routes.py       # Routes API Saxo
│   ├── requirements.txt     # Dépendances Python
│   ├── Dockerfile
│   ├── .env.example
│   └── .env                 # Configuration locale (non versionné)
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Composant principal
│   │   ├── api.js           # Client API
│   │   └── components/
│   │       ├── StockTable.jsx
│   │       ├── StockRow.jsx
│   │       ├── PerfBadge.jsx
│   │       ├── StockChart.jsx
│   │       └── Filters.jsx
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.yml
├── run.sh                   # Script de lancement
├── .gitignore
└── README.md
```

---

## Développement

### Stack technique

| Composant | Technologies |
|-----------|--------------|
| Backend | Python 3.11, FastAPI, yfinance, pandas, requests |
| Frontend | React 18, Vite, Tailwind CSS, Recharts, Lucide Icons |
| Data | Yahoo Finance API, Saxo OpenAPI |
| Container | Docker, Docker Compose |

### Qu'est-ce qu'une action "Résiliente" ?

Une action est considérée **résiliente** si elle a des rendements positifs sur **TOUTES** les cinq périodes :
- 3 mois
- 6 mois
- 1 an
- 3 ans
- 5 ans

Cela indique une croissance à long terme constante sans drawdowns majeurs.

### Tests

```bash
# Backend
cd backend
source venv/bin/activate
pytest

# Frontend
cd frontend
npm test
```

### Linting

```bash
# Python
cd backend
pip install flake8
flake8 .

# JavaScript
cd frontend
npm run lint
```

---

## Troubleshooting

### Le frontend ne démarre pas

```bash
# Vérifier que le port 5173 est libre
lsof -i :5173

# Tuer le processus si nécessaire
kill -9 <PID>
```

### Erreur CORS

Vérifiez que le backend est bien démarré sur le port 8000 et que le proxy Vite est configuré.

### Saxo OAuth échoue

1. Vérifiez que le `SAXO_REDIRECT_URI` correspond exactement à celui configuré dans votre app Saxo
2. Vérifiez que vous utilisez le bon environnement (`SIM` vs `LIVE`)
3. Consultez les logs backend : `docker-compose logs backend`

---

## License

MIT

---

## Contribution

Les contributions sont les bienvenues ! Ouvrez une issue ou une pull request.
