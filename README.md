# Stock Analyzer

Application d'analyse multi-periodes pour identifier les **actions resilientes** avec des performances positives sur toutes les periodes (3M, 6M, 1Y, 3Y, 5Y) + integration **Saxo Bank** pour le trading + **Serveur MCP** pour l'IA.

---

## Table des matieres

- [Fonctionnalites](#fonctionnalités)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Serveur MCP (Claude)](#serveur-mcp-claude)
- [Income Shield](#income-shield)
- [Tests](#tests)
- [API Reference](#api-reference)
- [Docker](#docker)
- [Structure du projet](#structure-du-projet)
- [Developpement](#développement)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Fonctionnalites

### Analyse de stocks
- **Analyse multi-periodes** : Performance sur 3M, 6M, 1Y, 3Y, 5Y
- **Detection de resilience** : Identifie les actions positives sur TOUTES les periodes
- **Presets de marches** : Hong Kong, CAC 40, S&P 500, Tech, Dividendes, **Income Shield**
- **Graphiques interactifs** : Historique 5 ans avec Recharts
- **Volatilite** : Identification des actions a risque eleve
- **Export CSV** : Exportez vos analyses

### Integration Saxo Bank
- **Authentification OAuth2** : Connexion securisee a votre compte Saxo
- **Portefeuille en temps reel** : Visualisez vos positions avec analyse
- **Stop-Loss/Take-Profit** : Configuration par position (alertes Telegram + ordres Saxo)
- **Aide a la decision** : Panel de decision par position avec signaux techniques
- **Analyse au clic** : Modal d'analyse complete sur chaque ticker
- **Trading** : Passez des ordres (Market/Limit/Stop)
- **Historique** : Consultez vos transactions

### Serveur MCP (Model Context Protocol)
- **24 outils MCP** pour Claude et autres LLMs
- Analyse technique (RSI, MACD, Bollinger)
- Analyse fondamentale et sentiment
- Trading automatise via Saxo Bank
- Alertes Telegram configurables
- **Income Shield** : Signaux macro et regime de marche

### Income Shield Portfolio
- **Detection de regime** : Risk-On, Risk-Off, Neutral, High Uncertainty
- **Signaux macro** : HYG/LQD ratio, VIX, SPY trend, Yield Curve
- **Anti-Whipsaw** : Filtres temporels (7j entree, 14j sortie)
- **Actifs revenus** : BDC, Covered Call ETFs, CEF, mREIT, Cash-like
- **Backtest 10 ans** : Simulation multi-assets avec mode Risk-Off

### Alertes & Notifications
- **Alertes de prix** : Prix au-dessus/en-dessous, variation %
- **Alertes macro** : VIX spike, credit stress, correction, recession
- **Notifications Telegram** : Alertes en temps reel sur mobile

---

## Quick Start

### Option 1 : Script de lancement (Recommande)

```bash
# Rendre le script executable
chmod +x run.sh

# Lancer l'application
./run.sh
```

Le script va :
1. Installer les dependances Python
2. Installer les dependances Node.js
3. Demarrer le backend sur le port 8000
4. Demarrer le frontend sur le port 5173
5. Ouvrir automatiquement le navigateur

### Option 2 : Docker Compose

```bash
# Copier la configuration d'environnement
cp backend/.env.example backend/.env
# Editer backend/.env avec vos cles Saxo et Telegram

# Lancer avec Docker
docker-compose up --build
```

### Option 3 : Installation manuelle

Voir [Installation](#installation) ci-dessous.

---

## Installation

### Prerequis

- **Python** 3.9+
- **Node.js** 18+
- **npm** ou **yarn**

### Backend

```bash
cd backend

# Creer l'environnement virtuel
python3 -m venv venv

# Activer l'environnement
source venv/bin/activate  # macOS/Linux
# ou
.\venv\Scripts\activate   # Windows

# Installer les dependances
pip install -r requirements.txt

# Copier et configurer l'environnement
cp .env.example .env
# Editer .env avec vos cles Saxo et Telegram

# Lancer le serveur
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Installer les dependances
npm install

# Lancer le serveur de developpement
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

## Configuration

### Saxo Bank (Optionnel)

L'integration Saxo Bank est **optionnelle**. L'application fonctionne sans pour l'analyse de stocks via Yahoo Finance.

#### 1. Creer une application Saxo

1. Allez sur [Saxo Developer Portal](https://www.developer.saxo/openapi/appmanagement)
2. Creez une nouvelle application
3. Configurez le **Redirect URI** : `http://localhost:5173`
4. Notez votre **App Key** et **App Secret**

#### 2. Configurer l'environnement

```bash
cd backend
cp .env.example .env
```

Editez `backend/.env` :

```env
SAXO_APP_KEY=votre_app_key
SAXO_APP_SECRET=votre_app_secret
SAXO_ENVIRONMENT=SIM          # SIM pour simulation, LIVE pour production
SAXO_REDIRECT_URI=http://localhost:5173
```

#### 3. Environnements Saxo

| Environnement | Description | URL Auth |
|---------------|-------------|----------|
| `SIM` | Sandbox avec donnees fictives | sim.logonvalidation.net |
| `LIVE` | Production avec argent reel | live.logonvalidation.net |

> **ATTENTION** : En mode `LIVE`, les ordres passes sont reels !

### Telegram (Optionnel)

Pour recevoir les alertes sur votre mobile :

```env
TELEGRAM_BOT_TOKEN=votre_bot_token
TELEGRAM_CHAT_ID=votre_chat_id
```

1. Creez un bot via [@BotFather](https://t.me/botfather)
2. Recuperez votre Chat ID via [@userinfobot](https://t.me/userinfobot)

### Gestion du cache de configuration

L'application utilise un systeme de cache pour stocker les configurations de maniere securisee.

| Source | Priorite | Description |
|--------|----------|-------------|
| `data/config.encrypted.json` | **Haute** | Fichier chiffre avec vos credentials |
| Variables `.env` | Basse | Utilisees uniquement si le fichier chiffre n'existe pas |

**Forcer l'utilisation des variables .env :**

```bash
# Option 1 : Ajouter dans .env
echo "FORCE_ENV_CONFIG=true" >> backend/.env

# Option 2 : Supprimer manuellement le cache
rm backend/data/config.encrypted.json
```

---

## Serveur MCP (Claude)

Le backend inclut un serveur MCP (Model Context Protocol) permettant a Claude et autres LLMs d'interagir avec l'application.

### Lancer le serveur MCP

```bash
cd backend
source venv/bin/activate
python -m src.infrastructure.mcp.mcp_server
```

### Configurer Claude Code

Ajoutez dans `~/.claude/claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "stock-analyzer": {
      "command": "python",
      "args": ["-m", "src.infrastructure.mcp.mcp_server"],
      "cwd": "/chemin/vers/stock-analyzer/backend",
      "env": {
        "PYTHONPATH": "/chemin/vers/stock-analyzer/backend"
      }
    }
  }
}
```

### Outils MCP disponibles (24 outils)

#### Analyse
| Outil | Description |
|-------|-------------|
| `analyze_stock` | Analyse complete d'une action |
| `get_stock_quote` | Prix actuel et variation |
| `get_technical_analysis` | RSI, MACD, Bollinger, supports/resistances |
| `get_fundamental_analysis` | Ratios financiers, valorisation |
| `get_news_sentiment` | News et sentiment de marche |
| `compare_stocks` | Comparaison multi-actions |
| `get_sector_performance` | Performance sectorielle |

#### Trading Saxo
| Outil | Description |
|-------|-------------|
| `get_portfolio` | Portefeuille avec positions |
| `get_position_pnl` | P&L par position |
| `search_instrument` | Recherche d'instruments Saxo |
| `get_order_book` | Carnet d'ordres |
| `place_trade` | Passer un ordre (Market/Limit/Stop) |
| `get_trade_history` | Historique des transactions |
| `get_account_summary` | Resume du compte |

#### Alertes
| Outil | Description |
|-------|-------------|
| `create_price_alert` | Alerte de prix |
| `list_alerts` | Liste des alertes actives |
| `delete_alert` | Supprimer une alerte |
| `send_telegram_message` | Envoyer un message Telegram |

#### Income Shield
| Outil | Description |
|-------|-------------|
| `get_market_regime` | Regime de marche actuel (Risk-On/Off) |
| `get_income_assets` | Analyse des actifs revenus par categorie |
| `get_income_recommendation` | Score revenus pour un ticker |
| `calculate_rebalancing` | Calcul de rebalancement |
| `simulate_income_portfolio` | Projection des revenus passifs |
| `run_portfolio_backtest` | Backtest 10 ans avec Risk-Off |
| `get_dividend_calendar` | Calendrier des dividendes |

#### Decision
| Outil | Description |
|-------|-------------|
| `get_pro_decision` | Decision de trading professionnelle |
| `get_monte_carlo_analysis` | Simulation Monte Carlo |
| `get_earnings_calendar` | Calendrier des earnings |

---

## Income Shield

Income Shield est un module de gestion de portefeuille oriente revenus passifs avec protection automatique.

### Regime de marche

Le systeme detecte automatiquement 4 regimes :

| Regime | Conditions | Action |
|--------|------------|--------|
| **Risk-On** | 0-1 signaux de stress | Allocation croissance |
| **Neutral** | 2 signaux de stress | Allocation equilibree |
| **Risk-Off** | 3+ signaux de stress | Allocation defensive |
| **High Uncertainty** | VIX spike ou 4+ signaux | Cash maximum |

### Signaux surveilles

- **Credit Stress** : HYG/LQD < SMA(50)
- **VIX Eleve** : VIX > 25 ou VIX > SMA(20)
- **SPY Tendance** : SPY < SMA(200)
- **Drawdown** : SPY drawdown > -10%
- **Yield Curve** : Courbe inversee (10Y-2Y < 0)

### Categories d'actifs revenus

| Categorie | Exemples | Rendement typique |
|-----------|----------|-------------------|
| **BDC** | ARCC, MAIN, HTGC | 8-12% |
| **Covered Call** | JEPI, JEPQ, DIVO | 7-10% |
| **CEF** | BST, UTF, PDI | 6-9% |
| **mREIT** | AGNC, NLY, STWD | 10-15% |
| **Cash-like** | SGOV, BIL, SHV | 4-5% |
| **Dividend Growth** | SCHD, VIG, DGRO | 3-4% |

### Anti-Whipsaw

Pour eviter les faux signaux :
- **Entree Risk-Off** : Confirmation apres 7 jours consecutifs
- **Sortie Risk-Off** : Confirmation apres 14 jours consecutifs

---

## Tests

### Lancer les tests

```bash
cd backend

# Tous les tests
./scripts/run_tests.sh

# Tests Income Shield uniquement
./scripts/run_tests.sh income

# Tests unitaires
./scripts/run_tests.sh unit

# Tests d'integration
./scripts/run_tests.sh integration

# Tests avec couverture de code
./scripts/run_tests.sh coverage

# Tests rapides (sans @pytest.mark.slow)
./scripts/run_tests.sh quick
```

### Structure des tests

```
backend/tests/
├── unit/
│   ├── test_income_shield.py    # 31 tests Income Shield
│   ├── test_value_objects.py    # Tests objets de valeur
│   └── test_use_cases.py        # Tests cas d'usage
├── integration/
│   └── test_api_routes.py       # Tests routes API
└── conftest.py                  # Fixtures pytest
```

### Tests Income Shield (31 tests)

- **TestIncomeCategory** (4 tests) : Enum et tickers
- **TestYieldMetrics** (2 tests) : Metriques de rendement
- **TestBacktestConfig** (2 tests) : Configuration backtest
- **TestMarketSignals** (4 tests) : Signaux de stress
- **TestAntiWhipsawState** (4 tests) : Logique anti-whipsaw
- **TestMarketRegimeProvider** (11 tests) : Detection de regime
- **TestMarketRegime** (1 test) : Serialisation

---

## API Reference

### Endpoints d'analyse

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | GET | Health check |
| `POST /api/analyze` | POST | Analyse un ticker |
| `POST /api/analyze-batch` | POST | Analyse plusieurs tickers |
| `GET /api/markets` | GET | Liste des presets de marches |
| `GET /api/markets/{id}` | GET | Tickers d'un marche |
| `POST /api/export/csv` | POST | Export CSV |

### Endpoints Saxo

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/saxo/status` | GET | Statut de configuration |
| `GET /api/saxo/auth/url` | GET | URL d'autorisation OAuth2 |
| `GET /api/saxo/auth/callback` | GET | Callback OAuth2 |
| `POST /api/saxo/auth/refresh` | POST | Rafraichir le token |
| `GET /api/saxo/portfolio` | GET | Portefeuille avec positions |
| `GET /api/saxo/orders` | GET | Liste des ordres |
| `POST /api/saxo/orders` | POST | Passer un ordre |
| `DELETE /api/saxo/orders/{id}` | DELETE | Annuler un ordre |
| `GET /api/saxo/history` | GET | Historique des transactions |
| `GET /api/saxo/search` | GET | Rechercher un instrument |
| `GET /api/saxo/positions/{symbol}/decision` | GET | Decision pour une position |
| `POST /api/saxo/positions/{symbol}/stop-loss` | POST | Configurer stop-loss |

### Endpoints Alertes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/alerts` | GET | Liste des alertes |
| `POST /api/alerts` | POST | Creer une alerte |
| `PUT /api/alerts/{id}` | PUT | Modifier une alerte |
| `DELETE /api/alerts/{id}` | DELETE | Supprimer une alerte |
| `POST /api/alerts/check` | POST | Verifier toutes les alertes |
| `POST /api/alerts/{id}/test` | POST | Tester notification |

### Endpoints Income Shield

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/income/regime` | GET | Regime de marche actuel |
| `GET /api/income/assets/{category}` | GET | Actifs par categorie |
| `POST /api/income/rebalance` | POST | Calcul rebalancement |
| `POST /api/income/simulate` | POST | Simulation revenus |
| `POST /api/income/backtest` | POST | Backtest multi-assets |
| `GET /api/income/dividend-calendar` | GET | Calendrier dividendes |

### Exemple d'appel API

```bash
# Analyser une action
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'

# Obtenir le regime de marche
curl http://localhost:8000/api/income/regime

# Creer une alerte de prix
curl -X POST http://localhost:8000/api/alerts \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "alert_type": "price_above", "target_value": 200.0}'
```

---

## Docker

### Commandes Docker

```bash
# Construire et lancer
docker-compose up --build

# Lancer en arriere-plan
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Logs d'un service specifique
docker-compose logs -f backend
docker-compose logs -f frontend

# Arreter
docker-compose down

# Arreter et supprimer les volumes
docker-compose down -v

# Reconstruire un service
docker-compose build backend
docker-compose build frontend
```

### Ports exposes

| Service | Port Host | Port Container |
|---------|-----------|----------------|
| Backend | 8000 | 8000 |
| Frontend | 5173 | 5173 |

---

## Structure du projet

```
stock-analyzer/
├── backend/
│   ├── main.py                    # FastAPI app & routes
│   ├── analyzer.py                # Logique d'analyse legacy
│   ├── markets.py                 # Presets de marches legacy
│   ├── saxo_config.py             # Configuration Saxo API
│   ├── saxo_service.py            # Service Saxo (auth, trading)
│   ├── saxo_routes.py             # Routes API Saxo
│   ├── requirements.txt           # Dependances Python
│   ├── pytest.ini                 # Configuration pytest
│   ├── src/
│   │   ├── domain/
│   │   │   ├── entities/          # Modeles de domaine
│   │   │   │   ├── stock.py
│   │   │   │   ├── alert.py
│   │   │   │   └── income_portfolio.py
│   │   │   └── services/          # Services metier
│   │   │       └── portfolio_backtest_engine.py
│   │   ├── application/
│   │   │   └── services/          # Services applicatifs
│   │   │       ├── alert_service.py
│   │   │       └── income_asset_service.py
│   │   ├── infrastructure/
│   │   │   ├── providers/         # Sources de donnees
│   │   │   │   ├── yahoo_finance_provider.py
│   │   │   │   └── market_regime_provider.py
│   │   │   ├── database/
│   │   │   │   └── repositories/  # Persistance
│   │   │   ├── notifications/
│   │   │   │   └── telegram_service.py
│   │   │   └── mcp/               # Serveur MCP
│   │   │       ├── mcp_server.py
│   │   │       └── tools/         # 24 outils MCP
│   │   │           ├── analysis_tools.py
│   │   │           ├── trading_tools.py
│   │   │           ├── alert_tools.py
│   │   │           ├── income_tools.py
│   │   │           └── decision_tools.py
│   │   └── api/
│   │       └── routes/            # Routes API REST
│   ├── tests/
│   │   ├── unit/                  # Tests unitaires
│   │   │   └── test_income_shield.py
│   │   ├── integration/           # Tests d'integration
│   │   └── conftest.py
│   ├── scripts/
│   │   └── run_tests.sh           # Script de lancement tests
│   └── data/                      # Donnees persistantes
│       ├── alerts.json
│       └── config.encrypted.json
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Composant principal
│   │   ├── api.js                 # Client API
│   │   └── components/
│   │       ├── StockTable.jsx
│   │       ├── StockRow.jsx
│   │       ├── StockChart.jsx
│   │       ├── Filters.jsx
│   │       ├── SaxoPortfolio.jsx  # Portefeuille Saxo
│   │       ├── StopLossModal.jsx  # Modal SL/TP dual-mode
│   │       ├── PositionDecisionPanel.jsx  # Panel decision
│   │       └── TickerAnalysisModal.jsx    # Modal analyse
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── docker-compose.yml
├── run.sh                         # Script de lancement
├── .gitignore
└── README.md
```

---

## Developpement

### Stack technique

| Composant | Technologies |
|-----------|--------------|
| Backend | Python 3.11, FastAPI, yfinance, pandas, numpy, pydantic |
| Frontend | React 18, Vite, Tailwind CSS, Recharts, Lucide Icons |
| Data | Yahoo Finance API, Saxo OpenAPI |
| MCP | Model Context Protocol pour LLMs |
| Notifications | Telegram Bot API |
| Tests | pytest, pytest-asyncio, pytest-mock, pytest-cov |
| Container | Docker, Docker Compose |

### Architecture

Le backend suit une **Clean Architecture** :

- **Domain** : Entites et logique metier pure
- **Application** : Cas d'usage et orchestration
- **Infrastructure** : Providers, repositories, MCP, notifications
- **API** : Routes HTTP REST

### Qu'est-ce qu'une action "Resiliente" ?

Une action est consideree **resiliente** si elle a des rendements positifs sur **TOUTES** les cinq periodes :
- 3 mois
- 6 mois
- 1 an
- 3 ans
- 5 ans

Cela indique une croissance a long terme constante sans drawdowns majeurs.

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

### Le frontend ne demarre pas

```bash
# Verifier que le port 5173 est libre
lsof -i :5173

# Tuer le processus si necessaire
kill -9 <PID>
```

### Erreur CORS

Verifiez que le backend est bien demarre sur le port 8000 et que le proxy Vite est configure.

### Saxo OAuth echoue

1. Verifiez que le `SAXO_REDIRECT_URI` correspond exactement a celui configure dans votre app Saxo
2. Verifiez que vous utilisez le bon environnement (`SIM` vs `LIVE`)
3. Consultez les logs backend : `docker-compose logs backend`

### Erreur "Invalid or unknown client_id"

Cette erreur signifie que votre App Key n'est pas reconnue par Saxo :
1. **Verifiez l'environnement** : Votre app est peut-etre configuree pour SIM uniquement
2. **Verifiez les credentials** : Assurez-vous que `SAXO_APP_KEY` correspond a votre app sur le portail Saxo
3. **Demandez l'acces LIVE** : Sur le portail Saxo, soumettez votre app pour approbation LIVE

### Les modifications de .env ne sont pas prises en compte

Le fichier `data/config.encrypted.json` a priorite sur `.env`. Solutions :
```bash
# Option 1 : Forcer l'utilisation de .env
echo "FORCE_ENV_CONFIG=true" >> backend/.env

# Option 2 : Supprimer le cache
rm backend/data/config.encrypted.json

# Puis redemarrer le backend
```

### Serveur MCP ne repond pas

1. Verifiez que le venv est active : `source backend/venv/bin/activate`
2. Verifiez les dependances : `pip install -r requirements.txt`
3. Testez manuellement : `python -m src.infrastructure.mcp.mcp_server`

### Tests qui echouent

```bash
# Verifier l'installation des dependances de test
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Lancer avec verbose
pytest tests/ -v --tb=long
```

---

## Changelog recent

### v2.0.0 - Income Shield
- Ajout du module Income Shield (regime de marche, actifs revenus)
- 8 nouveaux outils MCP pour l'analyse de revenus
- Backtest 10 ans avec mode Risk-Off automatique
- Anti-Whipsaw pour eviter les faux signaux
- 31 tests unitaires pour Income Shield

### v1.5.0 - Stop-Loss & Decision
- Stop-Loss/Take-Profit dual-mode (alertes + ordres Saxo)
- Panel d'aide a la decision par position
- Modal d'analyse complete au clic sur ticker
- Nouveaux composants frontend

### v1.0.0 - Initial
- Analyse multi-periodes
- Integration Saxo Bank
- Serveur MCP avec 16 outils
- Alertes Telegram

---

## License

MIT

---

## Contribution

Les contributions sont les bienvenues ! Ouvrez une issue ou une pull request.
