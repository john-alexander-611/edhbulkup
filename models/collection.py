from collections.abc import Iterator, Mapping

from models.card import Card


class Collection:
    """A user's owned cards, indexed by normalized name and quantity."""

    def __init__(self, cards: Mapping[str, int] | None = None) -> None:
        """Build a Collection, optionally pre-populated from a name-to-quantity mapping."""
        self._quantities: dict[str, int] = {}
        for name, quantity in (cards or {}).items():
            self.add(name, quantity)

    def add(self, card: Card | str, quantity: int = 1) -> None:
        """Add quantity copies of card, accumulating with any existing quantity.

        Raises:
            ValueError: If quantity is negative.
        """
        name = card.name if isinstance(card, Card) else Card(card).name
        if quantity < 0:
            raise ValueError("Card quantity cannot be negative")
        self._quantities[name] = self._quantities.get(name, 0) + quantity

    def quantity(self, card: Card | str) -> int:
        """Number of copies owned of card (0 if not owned)."""
        name = card.name if isinstance(card, Card) else Card(card).name
        return self._quantities.get(name, 0)

    @property
    def names(self) -> frozenset[str]:
        """All owned card names (normalized, quantity-agnostic)."""
        return frozenset(self._quantities)

    def as_dict(self) -> dict[str, int]:
        """Copy of the underlying name-to-quantity mapping."""
        return self._quantities.copy()

    def __contains__(self, card: Card | str) -> bool:
        """True if at least one copy of card is owned."""
        return self.quantity(card) > 0

    def __len__(self) -> int:
        """Number of distinct card names owned."""
        return len(self._quantities)

    def __iter__(self) -> Iterator[str]:
        """Iterate over owned card names."""
        return iter(self._quantities)
