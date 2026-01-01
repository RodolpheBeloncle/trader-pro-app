"""
Value Object Percentage - Représente un pourcentage validé.

Encapsule une valeur en pourcentage avec formatage et validation.
Stocke la valeur en décimal (0.15 pour 15%) mais affiche en pourcentage.

UTILISATION:
    from src.domain.value_objects.percentage import Percentage

    perf = Percentage(0.15)  # 15%
    perf = Percentage.from_percent(15)  # Aussi 15%
    print(perf)  # "+15.00%"
    print(perf.as_decimal)  # 0.15
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Union, Optional

from src.config.constants import PERCENTAGE_DECIMAL_PLACES


@dataclass(frozen=True, slots=True)
class Percentage:
    """
    Représente un pourcentage.

    La valeur est stockée en décimal (0.15 = 15%) mais peut être
    créée et affichée en format pourcentage.

    Attributs:
        value: Valeur décimale (0.15 pour 15%)
    """

    value: Decimal

    def __post_init__(self):
        """Convertit en Decimal si nécessaire."""
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))

    def __str__(self) -> str:
        """
        Formatage avec signe et symbole %.

        Examples:
            Percentage(0.15) → "+15.00%"
            Percentage(-0.05) → "-5.00%"
        """
        percent = self.as_percent
        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent:.{PERCENTAGE_DECIMAL_PLACES}f}%"

    def __repr__(self) -> str:
        """Représentation pour debugging."""
        return f"Percentage({self.value})"

    def __hash__(self) -> int:
        """Hash pour utilisation dans dict/set."""
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        """Égalité basée sur la valeur."""
        if isinstance(other, Percentage):
            return self.value == other.value
        if isinstance(other, (int, float, Decimal)):
            return self.value == Decimal(str(other))
        return False

    def __lt__(self, other: "Percentage") -> bool:
        """Comparaison inférieur."""
        return self.value < self._to_decimal(other)

    def __le__(self, other: "Percentage") -> bool:
        """Comparaison inférieur ou égal."""
        return self.value <= self._to_decimal(other)

    def __gt__(self, other: "Percentage") -> bool:
        """Comparaison supérieur."""
        return self.value > self._to_decimal(other)

    def __ge__(self, other: "Percentage") -> bool:
        """Comparaison supérieur ou égal."""
        return self.value >= self._to_decimal(other)

    def __add__(self, other: "Percentage") -> "Percentage":
        """Addition de deux pourcentages."""
        return Percentage(self.value + self._to_decimal(other))

    def __sub__(self, other: "Percentage") -> "Percentage":
        """Soustraction de deux pourcentages."""
        return Percentage(self.value - self._to_decimal(other))

    def __mul__(self, factor: Union[int, float, Decimal]) -> "Percentage":
        """Multiplication par un scalaire."""
        return Percentage(self.value * Decimal(str(factor)))

    def __neg__(self) -> "Percentage":
        """Négation."""
        return Percentage(-self.value)

    def __abs__(self) -> "Percentage":
        """Valeur absolue."""
        return Percentage(abs(self.value))

    def _to_decimal(self, other: Union["Percentage", int, float, Decimal]) -> Decimal:
        """Convertit une valeur en Decimal."""
        if isinstance(other, Percentage):
            return other.value
        return Decimal(str(other))

    @property
    def as_percent(self) -> float:
        """
        Retourne la valeur en pourcentage (15 pour 0.15).

        Returns:
            Valeur multipliée par 100
        """
        return float(self.value * 100)

    @property
    def as_decimal(self) -> float:
        """
        Retourne la valeur décimale (0.15 pour 15%).

        Returns:
            Valeur décimale
        """
        return float(self.value)

    @property
    def is_positive(self) -> bool:
        """Vérifie si le pourcentage est positif."""
        return self.value > 0

    @property
    def is_negative(self) -> bool:
        """Vérifie si le pourcentage est négatif."""
        return self.value < 0

    @property
    def is_zero(self) -> bool:
        """Vérifie si le pourcentage est zéro."""
        return self.value == 0

    def format(
        self,
        show_sign: bool = True,
        decimal_places: int = PERCENTAGE_DECIMAL_PLACES
    ) -> str:
        """
        Formate le pourcentage avec options.

        Args:
            show_sign: Afficher le + pour les valeurs positives
            decimal_places: Nombre de décimales

        Returns:
            Chaîne formatée
        """
        percent = self.as_percent
        if show_sign and percent >= 0:
            return f"+{percent:.{decimal_places}f}%"
        return f"{percent:.{decimal_places}f}%"

    @classmethod
    def from_percent(cls, percent_value: Union[int, float]) -> "Percentage":
        """
        Crée un Percentage depuis une valeur en pourcentage.

        Args:
            percent_value: Valeur en % (15 pour 15%)

        Returns:
            Percentage avec la valeur convertie

        Example:
            Percentage.from_percent(15) → Percentage(0.15)
        """
        return cls(Decimal(str(percent_value)) / 100)

    @classmethod
    def from_ratio(
        cls,
        current: Union[int, float],
        previous: Union[int, float]
    ) -> Optional["Percentage"]:
        """
        Calcule le pourcentage de variation entre deux valeurs.

        Args:
            current: Valeur actuelle
            previous: Valeur précédente

        Returns:
            Percentage de variation ou None si previous est 0

        Example:
            Percentage.from_ratio(115, 100) → Percentage(0.15) = +15%
        """
        if previous == 0:
            return None

        change = (Decimal(str(current)) - Decimal(str(previous))) / Decimal(str(previous))
        return cls(change)

    @classmethod
    def zero(cls) -> "Percentage":
        """Factory pour créer un Percentage à zéro."""
        return cls(Decimal("0"))
