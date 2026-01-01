"""
Tests unitaires pour les Value Objects du domaine.

Couvre:
- Ticker: validation, normalisation, proprietes
- Money: operations arithmetiques, validation devise
- Percentage: formatage, calculs

Format des tests: Given/When/Then en docstrings.
"""

import pytest
from decimal import Decimal

from src.domain.value_objects.ticker import Ticker
from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage
from src.domain.exceptions import TickerInvalidError, ValidationError


# =============================================================================
# TESTS TICKER
# =============================================================================

class TestTicker:
    """Tests pour le Value Object Ticker."""

    # -------------------------------------------------------------------------
    # Tests de validation
    # -------------------------------------------------------------------------

    def test_ticker_valid_formats(self, valid_tickers):
        """
        Given: Une liste de tickers valides de differents formats
        When: On cree un Ticker pour chacun
        Then: Aucune exception n'est levee et la valeur est normalisee
        """
        for ticker_str in valid_tickers:
            ticker = Ticker(ticker_str)
            assert ticker.value == ticker_str.upper()

    def test_ticker_normalizes_to_uppercase(self):
        """
        Given: Un ticker en minuscules
        When: On cree un Ticker
        Then: La valeur est convertie en majuscules
        """
        ticker = Ticker("aapl")
        assert ticker.value == "AAPL"

    def test_ticker_strips_whitespace(self):
        """
        Given: Un ticker avec des espaces autour
        When: On cree un Ticker
        Then: Les espaces sont supprimes
        """
        ticker = Ticker("  AAPL  ")
        assert ticker.value == "AAPL"

    def test_ticker_empty_raises_error(self):
        """
        Given: Une chaine vide
        When: On essaie de creer un Ticker
        Then: TickerInvalidError est leve
        """
        with pytest.raises(TickerInvalidError) as exc_info:
            Ticker("")

        assert "vide" in exc_info.value.message.lower()

    def test_ticker_too_long_raises_error(self):
        """
        Given: Un ticker de plus de 12 caracteres
        When: On essaie de creer un Ticker
        Then: TickerInvalidError est leve
        """
        with pytest.raises(TickerInvalidError) as exc_info:
            Ticker("A" * 15)

        assert "12" in exc_info.value.message

    def test_ticker_invalid_chars_raises_error(self):
        """
        Given: Un ticker avec des caracteres non autorises
        When: On essaie de creer un Ticker
        Then: TickerInvalidError est leve
        """
        invalid_chars = ["AAPL$", "AAP L", "@AAPL", "AAPL!"]

        for ticker_str in invalid_chars:
            with pytest.raises(TickerInvalidError):
                Ticker(ticker_str)

    # -------------------------------------------------------------------------
    # Tests des proprietes
    # -------------------------------------------------------------------------

    def test_ticker_exchange_extracted(self):
        """
        Given: Un ticker avec un suffix d'exchange
        When: On accede a la propriete exchange
        Then: L'exchange est correctement extrait
        """
        assert Ticker("0700.HK").exchange == "HK"
        assert Ticker("MC.PA").exchange == "PA"
        assert Ticker("SAP.DE").exchange == "DE"

    def test_ticker_exchange_none_for_us_stocks(self):
        """
        Given: Un ticker US sans suffix
        When: On accede a la propriete exchange
        Then: None est retourne
        """
        assert Ticker("AAPL").exchange is None
        assert Ticker("MSFT").exchange is None

    def test_ticker_base_symbol(self):
        """
        Given: Un ticker avec ou sans exchange
        When: On accede a la propriete base_symbol
        Then: Le symbole de base est retourne
        """
        assert Ticker("0700.HK").base_symbol == "0700"
        assert Ticker("AAPL").base_symbol == "AAPL"

    def test_ticker_is_index(self):
        """
        Given: Des tickers d'index (commencant par ^)
        When: On accede a la propriete is_index
        Then: True pour les index, False sinon
        """
        assert Ticker("^GSPC").is_index is True
        assert Ticker("^DJI").is_index is True
        assert Ticker("AAPL").is_index is False

    def test_ticker_is_crypto(self):
        """
        Given: Des tickers de crypto (contenant -USD ou -EUR)
        When: On accede a la propriete is_crypto
        Then: True pour les cryptos, False sinon
        """
        assert Ticker("BTC-USD").is_crypto is True
        assert Ticker("ETH-USD").is_crypto is True
        assert Ticker("AAPL").is_crypto is False

    # -------------------------------------------------------------------------
    # Tests d'egalite et hash
    # -------------------------------------------------------------------------

    def test_ticker_equality_same_value(self):
        """
        Given: Deux Tickers avec la meme valeur
        When: On les compare
        Then: Ils sont egaux
        """
        ticker1 = Ticker("AAPL")
        ticker2 = Ticker("aapl")  # Minuscules
        assert ticker1 == ticker2

    def test_ticker_equality_with_string(self):
        """
        Given: Un Ticker et une string avec la meme valeur
        When: On les compare
        Then: Ils sont egaux
        """
        ticker = Ticker("AAPL")
        assert ticker == "AAPL"
        assert ticker == "aapl"

    def test_ticker_hashable(self):
        """
        Given: Des Tickers
        When: On les utilise dans un set ou dict
        Then: Ils fonctionnent comme cles
        """
        tickers = {Ticker("AAPL"), Ticker("MSFT"), Ticker("AAPL")}
        assert len(tickers) == 2  # AAPL en double

    # -------------------------------------------------------------------------
    # Tests des factory methods
    # -------------------------------------------------------------------------

    def test_ticker_try_create_valid(self):
        """
        Given: Un ticker valide
        When: On utilise try_create
        Then: Le Ticker est retourne
        """
        result = Ticker.try_create("AAPL")
        assert result is not None
        assert result.value == "AAPL"

    def test_ticker_try_create_invalid(self):
        """
        Given: Un ticker invalide
        When: On utilise try_create
        Then: None est retourne sans exception
        """
        result = Ticker.try_create("")
        assert result is None

        result = Ticker.try_create("INVALID$$$")
        assert result is None


# =============================================================================
# TESTS MONEY
# =============================================================================

class TestMoney:
    """Tests pour le Value Object Money."""

    # -------------------------------------------------------------------------
    # Tests de creation
    # -------------------------------------------------------------------------

    def test_money_creation(self):
        """
        Given: Un montant et une devise valides
        When: On cree un Money
        Then: Les valeurs sont correctement stockees
        """
        money = Money(100.50, "USD")
        assert money.amount == Decimal("100.50")
        assert money.currency == "USD"

    def test_money_currency_normalized(self):
        """
        Given: Une devise en minuscules
        When: On cree un Money
        Then: La devise est convertie en majuscules
        """
        money = Money(100, "usd")
        assert money.currency == "USD"

    def test_money_invalid_currency_raises_error(self):
        """
        Given: Une devise non supportee
        When: On essaie de creer un Money
        Then: ValidationError est leve
        """
        with pytest.raises(ValidationError):
            Money(100, "XYZ")

    # -------------------------------------------------------------------------
    # Tests des operations arithmetiques
    # -------------------------------------------------------------------------

    def test_money_addition(self):
        """
        Given: Deux Money de meme devise
        When: On les additionne
        Then: Le resultat est correct
        """
        m1 = Money(100, "USD")
        m2 = Money(50.50, "USD")
        result = m1 + m2
        assert result.amount == Decimal("150.50")
        assert result.currency == "USD"

    def test_money_subtraction(self):
        """
        Given: Deux Money de meme devise
        When: On les soustrait
        Then: Le resultat est correct
        """
        m1 = Money(100, "USD")
        m2 = Money(30, "USD")
        result = m1 - m2
        assert result.amount == Decimal("70")

    def test_money_multiplication(self):
        """
        Given: Un Money et un scalaire
        When: On les multiplie
        Then: Le resultat est correct
        """
        money = Money(100, "USD")
        result = money * 3
        assert result.amount == Decimal("300")

    def test_money_division(self):
        """
        Given: Un Money et un scalaire
        When: On divise
        Then: Le resultat est correct
        """
        money = Money(100, "USD")
        result = money / 4
        assert result.amount == Decimal("25")

    def test_money_division_by_zero_raises_error(self):
        """
        Given: Un Money
        When: On divise par zero
        Then: ValidationError est leve
        """
        money = Money(100, "USD")
        with pytest.raises(ValidationError):
            money / 0

    def test_money_different_currencies_raises_error(self):
        """
        Given: Deux Money de devises differentes
        When: On essaie de les additionner
        Then: ValidationError est leve
        """
        m1 = Money(100, "USD")
        m2 = Money(100, "EUR")

        with pytest.raises(ValidationError):
            m1 + m2

    # -------------------------------------------------------------------------
    # Tests des comparaisons
    # -------------------------------------------------------------------------

    def test_money_comparison(self):
        """
        Given: Deux Money de meme devise
        When: On les compare
        Then: Les comparaisons sont correctes
        """
        m1 = Money(100, "USD")
        m2 = Money(50, "USD")
        m3 = Money(100, "USD")

        assert m1 > m2
        assert m2 < m1
        assert m1 >= m3
        assert m1 <= m3
        assert m1 == m3

    # -------------------------------------------------------------------------
    # Tests des proprietes
    # -------------------------------------------------------------------------

    def test_money_is_positive(self):
        """
        Given: Un Money positif
        When: On verifie is_positive
        Then: True est retourne
        """
        assert Money(100, "USD").is_positive is True
        assert Money(-100, "USD").is_positive is False
        assert Money(0, "USD").is_positive is False

    def test_money_is_zero(self):
        """
        Given: Un Money a zero
        When: On verifie is_zero
        Then: True est retourne
        """
        assert Money(0, "USD").is_zero is True
        assert Money(100, "USD").is_zero is False

    def test_money_round(self):
        """
        Given: Un Money avec beaucoup de decimales
        When: On arrondit
        Then: Le resultat est correct
        """
        money = Money(100.5678, "USD")
        rounded = money.round(2)
        assert rounded.amount == Decimal("100.57")


# =============================================================================
# TESTS PERCENTAGE
# =============================================================================

class TestPercentage:
    """Tests pour le Value Object Percentage."""

    # -------------------------------------------------------------------------
    # Tests de creation
    # -------------------------------------------------------------------------

    def test_percentage_creation_decimal(self):
        """
        Given: Une valeur decimale (0.15 pour 15%)
        When: On cree un Percentage
        Then: La valeur est correctement stockee
        """
        perf = Percentage(0.15)
        assert perf.value == Decimal("0.15")
        assert perf.as_percent == 15.0

    def test_percentage_from_percent(self):
        """
        Given: Une valeur en pourcentage (15 pour 15%)
        When: On utilise from_percent
        Then: La valeur decimale est calculee
        """
        perf = Percentage.from_percent(15)
        assert perf.as_percent == 15.0
        assert perf.as_decimal == 0.15

    def test_percentage_from_ratio(self):
        """
        Given: Deux valeurs (avant/apres)
        When: On utilise from_ratio
        Then: Le pourcentage de variation est calcule
        """
        perf = Percentage.from_ratio(115, 100)  # +15%
        assert abs(perf.as_percent - 15.0) < 0.01

        perf = Percentage.from_ratio(80, 100)  # -20%
        assert abs(perf.as_percent - (-20.0)) < 0.01

    def test_percentage_from_ratio_zero_previous(self):
        """
        Given: Une valeur precedente de zero
        When: On utilise from_ratio
        Then: None est retourne (division par zero evitee)
        """
        result = Percentage.from_ratio(100, 0)
        assert result is None

    # -------------------------------------------------------------------------
    # Tests de formatage
    # -------------------------------------------------------------------------

    def test_percentage_str_positive(self):
        """
        Given: Un pourcentage positif
        When: On le convertit en string
        Then: Le format inclut le signe +
        """
        perf = Percentage(0.15)
        assert str(perf) == "+15.00%"

    def test_percentage_str_negative(self):
        """
        Given: Un pourcentage negatif
        When: On le convertit en string
        Then: Le format inclut le signe -
        """
        perf = Percentage(-0.05)
        assert str(perf) == "-5.00%"

    def test_percentage_format_options(self):
        """
        Given: Un pourcentage
        When: On utilise format avec options
        Then: Le format respecte les options
        """
        perf = Percentage(0.15)

        # Sans signe
        assert perf.format(show_sign=False) == "15.00%"

        # Avec decimales personnalisees
        assert perf.format(decimal_places=1) == "+15.0%"

    # -------------------------------------------------------------------------
    # Tests des operations
    # -------------------------------------------------------------------------

    def test_percentage_addition(self):
        """
        Given: Deux pourcentages
        When: On les additionne
        Then: Le resultat est correct
        """
        p1 = Percentage(0.10)
        p2 = Percentage(0.05)
        result = p1 + p2
        assert result.as_percent == 15.0

    def test_percentage_subtraction(self):
        """
        Given: Deux pourcentages
        When: On les soustrait
        Then: Le resultat est correct
        """
        p1 = Percentage(0.10)
        p2 = Percentage(0.05)
        result = p1 - p2
        assert result.as_percent == 5.0

    def test_percentage_multiplication(self):
        """
        Given: Un pourcentage et un scalaire
        When: On les multiplie
        Then: Le resultat est correct
        """
        perf = Percentage(0.10)
        result = perf * 2
        assert result.as_percent == 20.0

    # -------------------------------------------------------------------------
    # Tests des proprietes
    # -------------------------------------------------------------------------

    def test_percentage_is_positive(self):
        """
        Given: Differents pourcentages
        When: On verifie is_positive/is_negative
        Then: Les valeurs sont correctes
        """
        assert Percentage(0.15).is_positive is True
        assert Percentage(-0.05).is_negative is True
        assert Percentage(0).is_zero is True
