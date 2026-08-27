from dataclasses import dataclass, field
from create_cache.edhrec_raw import CARD_CATEGORY_TAGS
BASIC_LANDS = frozenset({"plains", "island", "swamp", "mountain", "forest"})


@dataclass
class Commander:
    name: str
    identity: str
    decklist: frozenset[str]
    categories: dict[str, list[dict]] | None = None

    @classmethod
    def from_json(cls, name: str, data: dict) -> "Commander":
        return cls(
            name=name,
            identity=data["identity"],
            decklist=frozenset(data["decklist"]) - BASIC_LANDS,
        )

    def set_categories(self, categories: dict[str, list[dict]]) -> None:
        self.categories = categories

    def get_category(self, friendly_name: str) -> list[dict]:
        if self.categories is None:
            raise ValueError(f"{self.name}: categories not fetched yet - call set_categories() first")
        tag = CARD_CATEGORY_TAGS.get(friendly_name, friendly_name)
        return self.categories.get(tag, [])

    def contains_color(self, color: str) -> bool:
        return color in self.identity

    def contains_colors(self, colors) -> bool:
        return all(c in self.identity for c in colors)

    def is_colorless(self) -> bool:
        return self.identity == "C"

    def match_score(self, owned_cards: set[str]) -> float:
        if not self.decklist:
            return 0.0
        return len(owned_cards & self.decklist) / len(self.decklist)

    def missing_cards(self, owned_cards: set[str]) -> set[str]:
        return self.decklist - owned_cards