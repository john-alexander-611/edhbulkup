from dataclasses import dataclass
from collections import Counter
from typing import TYPE_CHECKING

from create_cache.edhrec_raw import CARD_CATEGORY_TAGS
from models.commander import Commander

if TYPE_CHECKING:
    from models.collection import Collection

BASIC_LANDS = frozenset({"plains", "island", "swamp", "mountain", "forest"})

# Cards with official rules text allowing more than one copy in a
# singleton deck (some capped, e.g. Nazgul at 9 or Seven Dwarves at 7,
# others truly unbounded). A single owned copy of these doesn't satisfy
# the average decklist's need for many copies, so match_score weights
# them by quantity instead of binary presence.
MULTI_COPY_CARDS = frozenset({
    "dragon's approach",
    "hare apparent",
    "nazgûl",
    "persistent petitioners",
    "rat colony",
    "relentless rats",
    "seven dwarves",
    "shadowborn apostle",
    "slime against humanity",
    "templar knight",
    "tempest hawk",
    "war elephant",
    "the ten thousand",
})


@dataclass
class Deck:
    """A commander plus its average EDHREC decklist and (optionally) EDHREC category data."""

    commander: Commander
    cards: frozenset[str]
    categories: dict[str, list[dict]] | None = None
    average_decklist: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, name: str, data: dict) -> "Deck":
        """Build a Deck from cached commander JSON (name, identity, decklist).

        Args:
            name: Commander name.
            data: Dict with "identity" and "decklist" (list of card names).

        Returns:
            Deck: Deck with cards deduped and basic lands excluded from cards.
        """
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
        """Commander's name."""
        return self.commander.name

    @property
    def decklist(self) -> frozenset[str]:
        """Alias for cards."""
        return self.cards

    @property
    def average_decklist_counts(self) -> tuple[tuple[str, int], ...]:
        """Card name to copy count in the average decklist, sorted by name."""
        return tuple(sorted(Counter(self.average_decklist).items()))

    @property
    def identity(self) -> str:
        """Commander's color identity."""
        return self.commander.identity

    def set_categories(self, categories: dict[str, list[dict]]) -> None:
        """Attach fetched EDHREC category data (see fetch_commander_page_categories)."""
        self.categories = categories

    def get_category(self, friendly_name: str) -> list[dict]:
        """Return cards for one EDHREC category.

        Args:
            friendly_name: Category name, e.g. "high_synergy_cards" (see CARD_CATEGORY_TAGS).

        Returns:
            list[dict]: Card dicts for that category, or [] if the tag has no entries.

        Raises:
            ValueError: If set_categories() hasn't been called yet.
        """
        if self.categories is None:
            raise ValueError(
                f"{self.name}: categories not fetched yet - call set_categories() first"
            )
        tag = CARD_CATEGORY_TAGS.get(friendly_name, friendly_name)
        return self.categories.get(tag, [])

    def get_all_edhrec_suggestions(self) -> dict[str, float]:
        """Return every category card's name (lowercased) mapped to its EDHREC synergy score.

        Raises:
            ValueError: If set_categories() hasn't been called yet.
        """
        if self.categories is None:
            raise ValueError(
                f"{self.name}: categories not fetched yet - call set_categories() first"
            )
        return {
            card["name"].lower(): card["synergy"]
            for tag in CARD_CATEGORY_TAGS.values()
            for card in self.categories.get(tag, [])
        }

    def match_score(self, collection: "Collection | set[str]") -> float:
        """Fraction (0-1) of the average decklist's weighted card slots the collection owns."""
        total = self.total_card_weight
        if not total:
            return 0.0
        return self.owned_card_weight(collection) / total

    def _card_weight(self, card: str) -> int:
        """How many of the 99 average-deck slots this card occupies."""
        if card in MULTI_COPY_CARDS:
            return dict(self.average_decklist_counts).get(card, 1)
        return 1

    @property
    def total_card_weight(self) -> int:
        """Total weighted slot count across all cards (see _card_weight)."""
        return sum(self._card_weight(card) for card in self.cards)

    def owned_card_weight(self, collection: "Collection | set[str]") -> int:
        """Weighted count of the deck's slots covered by collection.

        A plain set of names has no quantity data, so multi-copy cards fall
        back to binary present/absent matching.
        """
        quantity = getattr(collection, "quantity", None)
        owned = 0
        for card in self.cards:
            weight = self._card_weight(card)
            if quantity is None:
                owned += weight if card in collection else 0
            elif card in MULTI_COPY_CARDS:
                owned += min(quantity(card), weight)
            elif quantity(card) > 0:
                owned += weight
        return owned

    def missing_card_weight(self, collection: "Collection | set[str]") -> int:
        """Weighted count of deck slots not covered by collection."""
        return self.total_card_weight - self.owned_card_weight(collection)

    def missing_cards(self, owned_cards: set[str]) -> set[str]:
        """Deck cards not present in owned_cards."""
        return self.cards - owned_cards

    def is_card_legal(self, card_color_identity: str) -> bool:
        """True if a card with this color identity is legal under the commander (see is_card_legal_in_identity)."""
        return self.commander.is_card_legal(card_color_identity)
