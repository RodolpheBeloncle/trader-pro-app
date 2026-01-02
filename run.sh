#!/bin/bash

# Stock Analyzer - Launch Script
# Usage:
#   ./run.sh          - Start both backend and frontend
#   ./run.sh setup    - Interactive setup for Telegram, Finnhub, etc.
#   ./run.sh backend  - Start only backend
#   ./run.sh frontend - Start only frontend
#   ./run.sh status   - Check configuration status

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
ENV_FILE="$BACKEND_DIR/.env"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
VENV_PIP="$BACKEND_DIR/venv/bin/pip"
VENV_UVICORN="$BACKEND_DIR/venv/bin/uvicorn"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

check_dependencies() {
    local missing=0

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        missing=1
    fi

    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js is not installed${NC}"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        echo "Please install missing dependencies and try again."
        exit 1
    fi
}

ensure_venv() {
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        echo -e "${BLUE}Creating Python virtual environment...${NC}"
        cd "$BACKEND_DIR"
        python3 -m venv venv
    fi

    if [ ! -f "$VENV_PYTHON" ]; then
        echo -e "${RED}❌ Virtual environment is broken. Recreating...${NC}"
        rm -rf "$BACKEND_DIR/venv"
        cd "$BACKEND_DIR"
        python3 -m venv venv
    fi
}

install_backend_deps() {
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    cd "$BACKEND_DIR"
    "$VENV_PIP" install -r requirements.txt --quiet
    echo -e "${GREEN}✅ Backend dependencies installed${NC}"
}

install_frontend_deps() {
    echo -e "${BLUE}Installing Node.js dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install --silent 2>/dev/null || npm install
    echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
}

get_env_value() {
    local key=$1
    if [ -f "$ENV_FILE" ]; then
        grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'"
    fi
}

set_env_value() {
    local key=$1
    local value=$2

    # Create .env if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        touch "$ENV_FILE"
    fi

    # Check if key exists
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Update existing value (macOS compatible sed)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        else
            sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        fi
    else
        # Add new key
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

# =============================================================================
# SETUP COMMAND
# =============================================================================

setup_telegram() {
    print_header "Configuration Telegram"

    echo -e "${YELLOW}Pour configurer les alertes Telegram:${NC}"
    echo ""
    echo "  1. Ouvrez Telegram et cherchez @BotFather"
    echo "  2. Envoyez /newbot et suivez les instructions"
    echo "  3. Copiez le token du bot"
    echo ""
    echo "  4. Pour obtenir votre Chat ID:"
    echo "     - Cherchez @userinfobot sur Telegram"
    echo "     - Envoyez /start pour obtenir votre ID"
    echo ""

    current_token=$(get_env_value "TELEGRAM_BOT_TOKEN")
    current_chat=$(get_env_value "TELEGRAM_CHAT_ID")

    if [ -n "$current_token" ]; then
        echo -e "Token actuel: ${GREEN}${current_token:0:20}...${NC}"
    fi

    read -p "Token du bot Telegram (laisser vide pour garder l'actuel): " token
    if [ -n "$token" ]; then
        set_env_value "TELEGRAM_BOT_TOKEN" "$token"
        echo -e "${GREEN}✅ Token enregistré${NC}"
    fi

    if [ -n "$current_chat" ]; then
        echo -e "Chat ID actuel: ${GREEN}${current_chat}${NC}"
    fi

    read -p "Chat ID Telegram (laisser vide pour garder l'actuel): " chat_id
    if [ -n "$chat_id" ]; then
        set_env_value "TELEGRAM_CHAT_ID" "$chat_id"
        echo -e "${GREEN}✅ Chat ID enregistré${NC}"
    fi

    # Test connection
    final_token=$(get_env_value "TELEGRAM_BOT_TOKEN")
    final_chat=$(get_env_value "TELEGRAM_CHAT_ID")

    if [ -n "$final_token" ] && [ -n "$final_chat" ]; then
        echo ""
        read -p "Voulez-vous envoyer un message de test? (o/N): " test_msg
        if [[ "$test_msg" =~ ^[oOyY]$ ]]; then
            echo "Envoi du message de test..."
            response=$(curl -s "https://api.telegram.org/bot${final_token}/sendMessage" \
                -d "chat_id=${final_chat}" \
                -d "text=🎉 Stock Analyzer connecté avec succès!" \
                -d "parse_mode=HTML")

            if echo "$response" | grep -q '"ok":true'; then
                echo -e "${GREEN}✅ Message envoyé avec succès!${NC}"
            else
                echo -e "${RED}❌ Erreur: vérifiez vos identifiants${NC}"
                echo "$response"
            fi
        fi
    fi
}

setup_finnhub() {
    print_header "Configuration Finnhub (News)"

    echo -e "${YELLOW}Pour les actualités financières:${NC}"
    echo ""
    echo "  1. Allez sur https://finnhub.io"
    echo "  2. Créez un compte gratuit"
    echo "  3. Copiez votre API Key depuis le dashboard"
    echo ""
    echo -e "  ${CYAN}Note: Le plan gratuit permet 60 requêtes/minute${NC}"
    echo ""

    current_key=$(get_env_value "FINNHUB_API_KEY")

    if [ -n "$current_key" ]; then
        echo -e "Clé actuelle: ${GREEN}${current_key:0:10}...${NC}"
    fi

    read -p "Clé API Finnhub (laisser vide pour garder l'actuelle): " api_key
    if [ -n "$api_key" ]; then
        set_env_value "FINNHUB_API_KEY" "$api_key"
        echo -e "${GREEN}✅ Clé API enregistrée${NC}"
    fi
}

setup_saxo() {
    print_header "Configuration Saxo Bank"

    echo -e "${YELLOW}Pour connecter votre compte Saxo Bank:${NC}"
    echo ""
    echo "  1. Allez sur https://www.developer.saxo/openapi/appmanagement"
    echo "  2. Créez une application"
    echo "  3. Copiez App Key et App Secret"
    echo ""

    current_key=$(get_env_value "SAXO_APP_KEY")
    current_env=$(get_env_value "SAXO_ENVIRONMENT")

    if [ -n "$current_key" ]; then
        echo -e "App Key actuelle: ${GREEN}${current_key:0:10}...${NC}"
        echo -e "Environnement: ${GREEN}${current_env}${NC}"
    fi

    read -p "App Key Saxo (laisser vide pour garder l'actuelle): " app_key
    if [ -n "$app_key" ]; then
        set_env_value "SAXO_APP_KEY" "$app_key"
        echo -e "${GREEN}✅ App Key enregistrée${NC}"
    fi

    read -p "App Secret Saxo (laisser vide pour garder l'actuel): " app_secret
    if [ -n "$app_secret" ]; then
        set_env_value "SAXO_APP_SECRET" "$app_secret"
        echo -e "${GREEN}✅ App Secret enregistré${NC}"
    fi

    echo ""
    echo "Environnement:"
    echo "  1. SIM (Simulation - recommandé pour tester)"
    echo "  2. LIVE (Production - trading réel)"
    read -p "Choix [1]: " env_choice

    if [ "$env_choice" == "2" ]; then
        set_env_value "SAXO_ENVIRONMENT" "LIVE"
        echo -e "${YELLOW}⚠️  Mode LIVE activé - Trading réel!${NC}"
    else
        set_env_value "SAXO_ENVIRONMENT" "SIM"
        echo -e "${GREEN}✅ Mode SIM (simulation) activé${NC}"
    fi
}

run_setup() {
    print_header "Stock Analyzer - Configuration"

    echo "Que souhaitez-vous configurer?"
    echo ""
    echo "  1. Telegram (alertes de prix)"
    echo "  2. Finnhub (actualités financières)"
    echo "  3. Saxo Bank (broker)"
    echo "  4. Tout configurer"
    echo "  5. Voir le statut actuel"
    echo "  0. Quitter"
    echo ""

    read -p "Votre choix: " choice

    case $choice in
        1) setup_telegram ;;
        2) setup_finnhub ;;
        3) setup_saxo ;;
        4)
            setup_saxo
            setup_telegram
            setup_finnhub
            ;;
        5) show_status ;;
        0) exit 0 ;;
        *) echo -e "${RED}Choix invalide${NC}" ;;
    esac

    echo ""
    read -p "Configurer autre chose? (o/N): " again
    if [[ "$again" =~ ^[oOyY]$ ]]; then
        run_setup
    fi
}

# =============================================================================
# STATUS COMMAND
# =============================================================================

show_status() {
    print_header "Stock Analyzer - Statut Configuration"

    ensure_venv

    echo -e "${BLUE}Vérification de la configuration...${NC}"
    echo ""

    # Run Python to check status
    cd "$BACKEND_DIR"
    "$VENV_PYTHON" << 'PYTHON_SCRIPT'
import sys
sys.path.insert(0, '.')
from src.config.settings import get_settings

get_settings.cache_clear()
settings = get_settings()

def status_icon(configured):
    return "✅" if configured else "❌"

print("┌─────────────────────────────────────────────────────────────┐")
print("│ Service              │ Status      │ Details               │")
print("├─────────────────────────────────────────────────────────────┤")

# Saxo
saxo_status = status_icon(settings.is_saxo_configured)
saxo_env = settings.SAXO_ENVIRONMENT if settings.is_saxo_configured else "Non configuré"
print(f"│ Saxo Bank            │ {saxo_status} Configuré │ Env: {saxo_env:<16} │")

# Telegram
tg_status = status_icon(settings.is_telegram_configured)
tg_detail = "Prêt" if settings.is_telegram_configured else "Non configuré"
print(f"│ Telegram (Alertes)   │ {tg_status} Configuré │ {tg_detail:<21} │")

# Finnhub
fh_status = status_icon(settings.is_finnhub_configured)
fh_detail = "Prêt" if settings.is_finnhub_configured else "Non configuré"
print(f"│ Finnhub (News)       │ {fh_status} Configuré │ {fh_detail:<21} │")

print("└─────────────────────────────────────────────────────────────┘")

if not all([settings.is_saxo_configured, settings.is_telegram_configured, settings.is_finnhub_configured]):
    print("")
    print("💡 Utilisez './run.sh setup' pour configurer les services manquants")
PYTHON_SCRIPT
}

# =============================================================================
# START COMMANDS
# =============================================================================

start_backend() {
    echo -e "${BLUE}Starting backend server on port 8000...${NC}"
    cd "$BACKEND_DIR"
    "$VENV_UVICORN" src.api.app:app --host 0.0.0.0 --port 8000 --reload
}

start_frontend() {
    echo -e "${BLUE}Starting frontend on port 5173...${NC}"
    cd "$FRONTEND_DIR"
    npm run dev
}

start_all() {
    print_header "Stock Analyzer - Démarrage"

    check_dependencies
    ensure_venv
    install_backend_deps
    install_frontend_deps

    # Show status
    show_status
    echo ""

    # Start backend in background
    echo -e "${BLUE}Démarrage du backend...${NC}"
    cd "$BACKEND_DIR"
    "$VENV_UVICORN" src.api.app:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!

    # Wait for backend
    sleep 3

    # Start frontend in background
    echo -e "${BLUE}Démarrage du frontend...${NC}"
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!

    # Wait for frontend
    sleep 3

    # Open browser
    echo -e "${GREEN}Ouverture du navigateur...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://localhost:5173"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "http://localhost:5173" 2>/dev/null || true
    fi

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✨ Stock Analyzer est lancé!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  Frontend: http://localhost:5173"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/api/docs"
    echo ""
    echo "  Commandes:"
    echo "    ./run.sh setup  - Configurer Telegram, Finnhub..."
    echo "    ./run.sh status - Voir la configuration"
    echo ""
    echo -e "  ${YELLOW}Ctrl+C pour arrêter${NC}"
    echo ""

    # Handle shutdown
    cleanup() {
        echo ""
        echo "Arrêt des serveurs..."
        kill $BACKEND_PID 2>/dev/null
        kill $FRONTEND_PID 2>/dev/null
        exit 0
    }

    trap cleanup SIGINT SIGTERM

    # Wait for processes
    wait
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-}" in
    setup)
        run_setup
        ;;
    status)
        ensure_venv
        show_status
        ;;
    backend)
        check_dependencies
        ensure_venv
        install_backend_deps
        start_backend
        ;;
    frontend)
        check_dependencies
        install_frontend_deps
        start_frontend
        ;;
    help|--help|-h)
        echo "Stock Analyzer - Script de lancement"
        echo ""
        echo "Usage: ./run.sh [command]"
        echo ""
        echo "Commands:"
        echo "  (none)    Démarre le backend et le frontend"
        echo "  setup     Configuration interactive (Telegram, Finnhub, Saxo)"
        echo "  status    Affiche le statut de la configuration"
        echo "  backend   Démarre uniquement le backend"
        echo "  frontend  Démarre uniquement le frontend"
        echo "  help      Affiche cette aide"
        ;;
    *)
        start_all
        ;;
esac
