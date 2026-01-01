"""
Value Object Money - Représente une valeur monétaire avec sa devise.

Encapsule un montant et une devise pour éviter les erreurs de calcul
entre devises différentes.

ARCHITECTURE:
- Immuable (frozen=True)
- Opérations arithmétiques sécurisées (vérifient la devise)
- Formatage intégré

UTILISATION:
    from src.domain.value_objects.money import Money

    price = Money(100.50, "USD")
    total = price * 10  # Money(1005.00, "USD")
    print(price)  # "100.50 USD"
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Union

from src.domain.exceptions import ValidationError
from src.config.constants import PRICE_DECIMAL_PLACES


# Devises supportées (ISO 4217)
SUPPORTED_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "CHF", "JPY", "HKD", "CNY", "CAD", "AUD",
    "SGD", "KRW", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF"
})


@dataclass(frozen=True, slots=True)
class Money:
    """
    Représente une valeur monétaire avec sa devise.

    Attributs:
        amount: Le montant (Decimal pour précision)
        currency: Code devise ISO 4217 (ex: "USD", "EUR")

    Opérations supportées:
        - Addition/soustraction avec Money de même devise
        - Multiplication/division par un nombre
        - Comparaisons (<, >, ==, etc.)
    """

    amount: Decimal
    currency: str

    def __post_init__(self):
        """Valide et normalise le Money après création."""
        # Convertir amount en Decimal si nécessaire
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))

        # Normaliser la devise en majuscules
        normalized_currency = self.currency.upper().strip()

        # Valider la devise
        if normalized_currency not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                field="currency",
                message=f"Devise '{self.currency}' non supportée"
            )

        object.__setattr__(self, "currency", normalized_currency)

    def __str__(self) -> str:
        """Formatage lisible: '100.50 USD'."""
        return f"{self.amount:.{PRICE_DECIMAL_PLACES}f} {self.currency}"

    def __repr__(self) -> str:
        """Représentation pour debugging."""
        return f"Money({self.amount}, '{self.currency}')"

    def __hash__(self) -> int:
        """Hash pour utilisation dans dict/set."""
        return hash((self.amount, self.currency))

    def __eq__(self, other: object) -> bool:
        """Égalité: même montant ET même devise."""
        if isinstance(other, Money):
            return self.amount == other.amount and self.currency == other.currency
        return False

    def __lt__(self, other: "Money") -> bool:
        """Comparaison inférieur (même devise requise)."""
        self._check_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        """Comparaison inférieur ou égal."""
        self._check_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        """Comparaison supérieur."""
        self._check_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        """Comparaison supérieur ou égal."""
        self._check_same_currency(other)
        return self.amount >= other.amount

    def __add__(self, other: "Money") -> "Money":
        """Addition de deux Money (même devise)."""
        self._check_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        """Soustraction de deux Money (même devise)."""
        self._check_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Union[int, float, Decimal]) -> "Money":
        """Multiplication par un scalaire."""
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def __rmul__(self, factor: Union[int, float, Decimal]) -> "Money":
        """Multiplication par un scalaire (ordre inversé)."""
        return self.__mul__(factor)

    def __truediv__(self, divisor: Union[int, float, Decimal]) -> "Money":
        """Division par un scalaire."""
        if divisor == 0:
            raise ValidationError(field="divisor", message="Division par zéro")
        return Money(self.amount / Decimal(str(divisor)), self.currency)

    def __neg__(self) -> "Money":
        """Négation: -Money."""
        return Money(-self.amount, self.currency)

    def __abs__(self) -> "Money":
        """Valeur absolue."""
        return Money(abs(self.amount), self.currency)

    def _check_same_currency(self, other: "Money") -> None:
        """Vérifie que les deux Money ont la même devise."""
        if not isinstance(other, Money):
            raise TypeError(f"Opération impossible entre Money et {type(other)}")
        if self.currency != other.currency:
            raise ValidationError(
                field="currency",
                message=f"Devises incompatibles: {self.currency} vs {other.currency}"
            )

    def round(self, decimal_places: int = PRICE_DECIMAL_PLACES) -> "Money":
        """
        Arrondit le montant au nombre de décimales spécifié.

        Args:
            decimal_places: Nombre de décimales (défaut: 2)

        Returns:
            Nouveau Money arrondi
        """
        quantize_str = "0." + "0" * decimal_places
        rounded = self.amount.quantize(
            Decimal(quantize_str),
            rounding=ROUND_HALF_UP
        )
        return Money(rounded, self.currency)

    @property
    def is_positive(self) -> bool:
        """Vérifie si le montant est positif."""
        return self.amount > 0

    @property
    def is_negative(self) -> bool:
        """Vérifie si le montant est négatif."""
        return self.amount < 0

    @property
    def is_zero(self) -> bool:
        """Vérifie si le montant est zéro."""
        return self.amount == 0

    def as_float(self) -> float:
        """Convertit en float (perte de précision possible)."""
        return float(self.amount)

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Factory pour créer un Money à zéro."""
        return cls(Decimal("0"), currency)

    @classmethod
    def from_cents(cls, cents: int, currency: str = "USD") -> "Money":
        """
        Crée un Money depuis un montant en centimes.

        Args:
            cents: Montant en centimes (ex: 10050 pour 100.50)
            currency: Code devise

        Returns:
            Money avec le montant converti
        """
        return cls(Decimal(cents) / 100, currency)
