from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    """A normalized card identity with optional Scryfall metadata."""

    name: str
    color_identity: str | None = None
    type_line: str | None = None

    def __post_init__(self) -> None:
        normalized_name = self.name.strip().lower()
        if not normalized_name:
            raise ValueError("Card name cannot be empty")
        object.__setattr__(self, "name", normalized_name)
