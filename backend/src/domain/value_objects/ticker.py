"""
Value Object Ticker - Représente un symbole boursier validé.

Un Value Object est immuable et défini par ses attributs, pas par son identité.
Deux Tickers avec le même symbole sont considérés comme égaux.

ARCHITECTURE:
- Les Value Objects appartiennent à la couche DOMAINE
- Ils encapsulent la validation et les règles métier
- Ils sont immuables (frozen=True dans dataclass)

UTILISATION:
    from src.domain.value_objects.ticker import Ticker

    ticker = Ticker("AAPL")  # Valide et normalise
    ticker = Ticker("aapl")  # Devient "AAPL"
    ticker = Ticker("")      # Lève TickerInvalidError

RÈGLES DE VALIDATION:
    - Longueur entre 1 et 12 caractères
    - Caractères autorisés: A-Z, 0-9, ., -, :, ^
    - Converti en majuscules
"""

from dataclasses import dataclass
import re
from typing import Optional

from src.domain.exceptions import TickerInvalidError


# Regex pour valider le format d'un ticker
# Exemples valides: AAPL, BRK.A, 0700.HK, ^GSPC, BTC-USD
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-:^]{0,11}$")

# Longueurs min/max
TICKER_MIN_LENGTH = 1
TICKER_MAX_LENGTH = 12


@dataclass(frozen=True, slots=True)
class Ticker:
    """
    Représente un symbole boursier (ticker) validé et normalisé.

    Attributs:
        value: Le symbole en majuscules (ex: "AAPL", "0700.HK")

    Exemples de tickers valides:
        - US: AAPL, MSFT, GOOGL, BRK.A, BRK.B
        - Hong Kong: 0700.HK, 9988.HK
        - Paris: MC.PA, OR.PA
        - Index: ^GSPC, ^DJI
        - Crypto: BTC-USD, ETH-USD

    Raises:
        TickerInvalidError: Si le ticker est vide ou contient des caractères invalides
    """

    value: str

    def __post_init__(self):
        """Valide et normalise le ticker après création."""
        # Normaliser en majuscules
        normalized = self.value.strip().upper()

        # Vérifier la longueur
        if len(normalized) < TICKER_MIN_LENGTH:
            raise TickerInvalidError(
                ticker=self.value,
                reason="Le ticker ne peut pas être vide"
            )

        if len(normalized) > TICKER_MAX_LENGTH:
            raise TickerInvalidError(
                ticker=self.value,
                reason=f"Le ticker dépasse {TICKER_MAX_LENGTH} caractères"
            )

        # Vérifier le format
        if not TICKER_PATTERN.match(normalized):
            raise TickerInvalidError(
                ticker=self.value,
                reason="Caractères invalides (autorisés: A-Z, 0-9, ., -, :, ^)"
            )

        # Utiliser object.__setattr__ car frozen=True
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        """Retourne le symbole comme chaîne."""
        return self.value

    def __repr__(self) -> str:
        """Représentation pour debugging."""
        return f"Ticker('{self.value}')"

    def __hash__(self) -> int:
        """Hash basé sur la valeur pour utilisation dans dict/set."""
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        """Deux tickers sont égaux si leur valeur est identique."""
        if isinstance(other, Ticker):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other.upper()
        return False

    @property
    def exchange(self) -> Optional[str]:
        """
        Extrait l'exchange du ticker si présent.

        Returns:
            Code de l'exchange ou None

        Examples:
            Ticker("0700.HK").exchange → "HK"
            Ticker("MC.PA").exchange → "PA"
            Ticker("AAPL").exchange → None
        """
        if "." in self.value:
            parts = self.value.split(".")
            if len(parts) == 2 and len(parts[1]) <= 4:
                return parts[1]
        return None

    @property
    def base_symbol(self) -> str:
        """
        Retourne le symbole sans l'exchange.

        Examples:
            Ticker("0700.HK").base_symbol → "0700"
            Ticker("AAPL").base_symbol → "AAPL"
        """
        if "." in self.value:
            return self.value.split(".")[0]
        return self.value

    @property
    def is_index(self) -> bool:
        """
        Vérifie si le ticker est un index (commence par ^).

        Examples:
            Ticker("^GSPC").is_index → True
            Ticker("AAPL").is_index → False
        """
        return self.value.startswith("^")

    @property
    def is_crypto(self) -> bool:
        """
        Vérifie si le ticker semble être une crypto (contient -USD).

        Examples:
            Ticker("BTC-USD").is_crypto → True
            Ticker("AAPL").is_crypto → False
        """
        return "-USD" in self.value or "-EUR" in self.value

    @classmethod
    def from_string(cls, value: str) -> "Ticker":
        """
        Factory method pour créer un Ticker depuis une chaîne.

        Identique au constructeur mais plus explicite.

        Args:
            value: Le symbole boursier

        Returns:
            Instance de Ticker validée
        """
        return cls(value)

    @classmethod
    def try_create(cls, value: str) -> Optional["Ticker"]:
        """
        Tente de créer un Ticker, retourne None si invalide.

        Utile quand on veut filtrer sans lever d'exception.

        Args:
            value: Le symbole boursier

        Returns:
            Instance de Ticker ou None si invalide
        """
        try:
            return cls(value)
        except TickerInvalidError:
            return None
