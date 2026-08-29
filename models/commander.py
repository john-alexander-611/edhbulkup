from dataclasses import dataclass
from card_legality import is_card_legal_in_identity


@dataclass
class Commander:
    name: str
    identity: str

    def contains_color(self, color: str) -> bool:
        return color in self.identity

    def contains_colors(self, colors) -> bool:
        return all(c in self.identity for c in colors)

    def is_colorless(self) -> bool:
        return self.identity == "C"

    def is_card_legal(self, card_color_identity: str) -> bool:
        return is_card_legal_in_identity(card_color_identity, self.identity)
