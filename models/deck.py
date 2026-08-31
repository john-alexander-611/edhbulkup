from dataclasses import dataclass
from collections import Counter

from create_cache.edhrec_raw import CARD_CATEGORY_TAGS
from models.commander import Commander

BASIC_LANDS = frozenset({"plains", "island", "swamp", "mountain", "forest"})


@dataclass
class Deck:
    commander: Commander
    cards: frozenset[str]
    categories: dict[str, list[dict]] | None = None
    average_decklist: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, name: str, data: dict) -> "Deck":
        commander = Commander(name=name, identity=data["identity"])
        average_decklist = tuple(data["decklist"])
        cards = frozenset(average_decklist) - BASIC_LANDS
        return cls(
            commander=commander,
            cards=cards,
            average_decklist=average_decklist,
        )

    @property
    def name(self) -> str:
        return self.commander.name

    @property
    def decklist(self) -> frozenset[str]:
        return self.cards

    @property
    def average_decklist_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(self.average_decklist).items()))

    @property
    def identity(self) -> str:
        return self.commander.identity

    def set_categories(self, categories: dict[str, list[dict]]) -> None:
        self.categories = categories

    def get_category(self, friendly_name: str) -> list[dict]:
        if self.categories is None:
            raise ValueError(
                f"{self.name}: categories not fetched yet - call set_categories() first"
            )
        tag = CARD_CATEGORY_TAGS.get(friendly_name, friendly_name)
        return self.categories.get(tag, [])

    def get_all_edhrec_suggestions(self) -> dict[str, float]:
        if self.categories is None:
            raise ValueError(
                f"{self.name}: categories not fetched yet - call set_categories() first"
            )
        return {
            card["name"].lower(): card["synergy"]
            for tag in CARD_CATEGORY_TAGS.values()
            for card in self.categories.get(tag, [])
        }

    def match_score(self, owned_cards: set[str]) -> float:
        if not self.cards:
            return 0.0
        return len(owned_cards & self.cards) / len(self.cards)

    def missing_cards(self, owned_cards: set[str]) -> set[str]:
        return self.cards - owned_cards

    def is_card_legal(self, card_color_identity: str) -> bool:
        return self.commander.is_card_legal(card_color_identity)
