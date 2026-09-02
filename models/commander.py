from dataclasses import dataclass
from card_legality import is_card_legal_in_identity


@dataclass
class Commander:
    """A commander's name and color identity, with legality checks against it."""

    name: str
    identity: str

    def contains_color(self, color: str) -> bool:
        """True if color is part of this commander's identity."""
        return color in self.identity

    def contains_colors(self, colors) -> bool:
        """True if every color in colors is part of this commander's identity."""
        return all(c in self.identity for c in colors)

    def is_colorless(self) -> bool:
        """True if this commander's identity is colorless ("C")."""
        return self.identity == "C"

    def is_card_legal(self, card_color_identity: str) -> bool:
        """True if a card with this color identity is legal in this commander's deck."""
        return is_card_legal_in_identity(card_color_identity, self.identity)
