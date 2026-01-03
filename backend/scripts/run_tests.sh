#!/bin/bash
#
# Script de lancement des tests pour Stock Analyzer
#
# Usage:
#   ./scripts/run_tests.sh              # Tous les tests
#   ./scripts/run_tests.sh income       # Tests Income Shield uniquement
#   ./scripts/run_tests.sh unit         # Tests unitaires
#   ./scripts/run_tests.sh integration  # Tests d'integration
#   ./scripts/run_tests.sh coverage     # Tests avec couverture
#   ./scripts/run_tests.sh quick        # Tests rapides (sans slow)
#

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Repertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Aller dans le repertoire backend
cd "$BACKEND_DIR"

# Verifier que le venv existe
if [ ! -d "venv" ]; then
    echo -e "${RED}Erreur: venv non trouve. Creez-le avec: python -m venv venv${NC}"
    exit 1
fi

# Activer le venv
source venv/bin/activate

# Verifier que pytest est installe
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}Installation de pytest...${NC}"
    pip install pytest pytest-asyncio pytest-mock pytest-cov
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Stock Analyzer - Tests Backend${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Determiner le type de test
TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    income)
        echo -e "${YELLOW}Lancement des tests Income Shield...${NC}"
        pytest tests/unit/test_income_shield.py -v --tb=short
        ;;
    unit)
        echo -e "${YELLOW}Lancement des tests unitaires...${NC}"
        pytest tests/unit/ -v --tb=short
        ;;
    integration)
        echo -e "${YELLOW}Lancement des tests d'integration...${NC}"
        pytest tests/integration/ -v --tb=short
        ;;
    coverage)
        echo -e "${YELLOW}Lancement des tests avec couverture...${NC}"
        pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v
        echo ""
        echo -e "${GREEN}Rapport HTML genere: htmlcov/index.html${NC}"
        ;;
    quick)
        echo -e "${YELLOW}Lancement des tests rapides...${NC}"
        pytest tests/ -v --tb=short -m "not slow"
        ;;
    all|*)
        echo -e "${YELLOW}Lancement de tous les tests...${NC}"
        pytest tests/ -v --tb=short
        ;;
esac

# Verifier le code de sortie
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   TOUS LES TESTS SONT PASSES !${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}   CERTAINS TESTS ONT ECHOUE${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
