from dataclasses import dataclass, field

from models.collection import Collection
from models.deck import Deck


@dataclass
class DeckAnalysis:
    deck: Deck
    collection: Collection
    missing_cards: set[str] = field(default_factory=set)
    missing_by_tag: dict[str, set[str]] = field(default_factory=dict)
    replacements_by_tag: dict[str, list[str]] = field(default_factory=dict)
    owned_synergy_cards: list[dict] = field(default_factory=list)
    same_type_replacements: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.missing_cards:
            self.missing_cards = self.deck.missing_cards(self.collection.names)

    @property
    def owned_count(self) -> int:
        return len(self.deck.cards) - len(self.missing_cards)

    @property
    def missing_count(self) -> int:
        return len(self.missing_cards)

    @property
    def match_score(self) -> float:
        return self.deck.match_score(self.collection.names)
