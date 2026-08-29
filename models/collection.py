from collections.abc import Iterator, Mapping

from models.card import Card


class Collection:
    """A user's owned cards, indexed by normalized name and quantity."""

    def __init__(self, cards: Mapping[str, int] | None = None) -> None:
        self._quantities: dict[str, int] = {}
        for name, quantity in (cards or {}).items():
            self.add(name, quantity)

    def add(self, card: Card | str, quantity: int = 1) -> None:
        name = card.name if isinstance(card, Card) else Card(card).name
        if quantity < 0:
            raise ValueError("Card quantity cannot be negative")
        self._quantities[name] = self._quantities.get(name, 0) + quantity

    def quantity(self, card: Card | str) -> int:
        name = card.name if isinstance(card, Card) else Card(card).name
        return self._quantities.get(name, 0)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._quantities)

    def as_dict(self) -> dict[str, int]:
        return self._quantities.copy()

    def __contains__(self, card: Card | str) -> bool:
        return self.quantity(card) > 0

    def __len__(self) -> int:
        return len(self._quantities)

    def __iter__(self) -> Iterator[str]:
        return iter(self._quantities)
