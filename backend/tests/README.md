# Tests Income Shield

Ce document decrit les tests unitaires et d'integration pour les fonctionnalites Income Shield.

## Structure des Tests

```
tests/
├── unit/
│   ├── test_income_shield.py    # Tests Income Shield (31 tests)
│   ├── test_value_objects.py    # Tests objets de valeur
│   └── test_use_cases.py        # Tests cas d'usage
├── integration/
│   └── test_api_routes.py       # Tests routes API
└── conftest.py                  # Fixtures pytest
```

## Installation des Dependances de Test

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

## Lancer les Tests

### Tous les tests
```bash
./scripts/run_tests.sh
```

### Tests Income Shield uniquement
```bash
pytest tests/unit/test_income_shield.py -v
```

### Tests avec couverture de code
```bash
pytest tests/unit/test_income_shield.py --cov=src --cov-report=html
```

### Tests par marqueur
```bash
# Tests unitaires uniquement
pytest -m unit -v

# Tests d'integration
pytest -m integration -v
```

## Tests Income Shield (31 tests)

### TestIncomeCategory (4 tests)
- `test_income_category_values` - Verifie les valeurs enum
- `test_income_asset_tickers_defined` - Verifie les tickers par categorie
- `test_get_category_for_ticker` - Recherche categorie par ticker
- `test_get_tickers_for_category` - Recuperation tickers par categorie

### TestYieldMetrics (2 tests)
- `test_yield_metrics_creation` - Creation de metriques de rendement
- `test_yield_metrics_to_dict` - Serialisation JSON

### TestBacktestConfig (2 tests)
- `test_backtest_config_defaults` - Valeurs par defaut
- `test_backtest_config_custom` - Valeurs personnalisees

### TestMarketSignals (4 tests)
- `test_stress_count_no_stress` - Comptage sans stress
- `test_stress_count_partial_stress` - Comptage partiel
- `test_stress_count_high_stress` - Comptage stress eleve
- `test_signals_to_dict` - Serialisation JSON

### TestAntiWhipsawState (4 tests)
- `test_risk_off_not_confirmed_initially` - Etat initial
- `test_risk_off_confirmed_after_threshold` - Confirmation risk-off
- `test_risk_on_confirmed_after_threshold` - Confirmation risk-on
- `test_to_dict` - Serialisation JSON

### TestMarketRegimeProvider (11 tests)
- `test_provider_initialization` - Initialisation
- `test_determine_regime_risk_on` - Detection Risk-On
- `test_determine_regime_neutral` - Detection Neutral
- `test_determine_regime_risk_off` - Detection Risk-Off
- `test_determine_regime_high_uncertainty_vix_spike` - Detection High Uncertainty
- `test_calculate_confidence_risk_on` - Calcul confiance Risk-On
- `test_calculate_confidence_risk_off` - Calcul confiance Risk-Off
- `test_allocations_defined_for_all_regimes` - Allocations definies
- `test_generate_interpretation_risk_on` - Interpretation Risk-On
- `test_generate_interpretation_risk_off` - Interpretation Risk-Off
- `test_interpret_vix_*` (4 tests) - Interpretation niveaux VIX

### TestMarketRegime (1 test)
- `test_market_regime_to_dict` - Serialisation complete

## Ajout de Nouveaux Tests

Pour ajouter un nouveau test:

1. Creer le fichier dans `tests/unit/` ou `tests/integration/`
2. Utiliser le prefixe `test_` pour les fichiers et fonctions
3. Utiliser les fixtures definies dans `conftest.py`
4. Utiliser les marqueurs: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`

Exemple:
```python
import pytest
from src.my_module import MyClass

class TestMyClass:
    @pytest.mark.unit
    def test_my_function(self):
        obj = MyClass()
        result = obj.my_function()
        assert result == expected_value
```

## Rapport de Couverture

Apres avoir execute les tests avec `--cov-report=html`, ouvrir:
```bash
open htmlcov/index.html
```
