import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeAlias

from commander_specific import (
    group_missing_cards_by_tag,
    suggest_functional_replacements,
    suggest_owned_synergy_cards,
    suggest_same_type_replacements_for_missing_cards,
)
from models.collection import Collection
from models.deck import Deck
from parse_input.parse_moxfield import parse_moxfield_csv
from scryfall.cache_wrappers import ScryfallCache, TagCache
from services.results import (
    DeckAnalysisResult,
    DeckMatchResult,
    ReplacementGroupResult,
)

DeckFilter: TypeAlias = Callable[[Deck], bool]


def load_decks(json_path: Path | None = None) -> dict[str, Deck]:
    path = json_path or Path(__file__).parent.parent / "create_cache" / "commander_data.json"
    with open(path, "r") as file:
        json_data = json.load(file)
    return {name: Deck.from_json(name, data) for name, data in json_data.items()}


def load_collection(path: str) -> Collection:
    return Collection(parse_moxfield_csv(path))


def search_decks(
    decks: Iterable[Deck],
    collection: Collection,
    filters: Iterable[DeckFilter] = (),
    limit: int = 20,
    offset: int = 0,
) -> list[DeckMatchResult]:
    if limit < 1:
        raise ValueError("Search result limit must be positive")
    if offset < 0:
        raise ValueError("Search result offset must not be negative")
    filters = tuple(filters)
    matches = [
        DeckMatchResult(
            commander_name=deck.name,
            identity=deck.identity,
            match_score=deck.match_score(collection),
            owned_count=deck.owned_card_weight(collection),
            deck_size=deck.total_card_weight,
        )
        for deck in decks
        if all(deck_filter(deck) for deck_filter in filters)
    ]
    matches.sort(key=lambda match: (-match.match_score, match.commander_name))
    return matches[offset:offset + limit]


def count_deck_matches(decks: Iterable[Deck], filters: Iterable[DeckFilter] = ()) -> int:
    filters = tuple(filters)
    return sum(1 for deck in decks if all(deck_filter(deck) for deck_filter in filters))


def analyze_deck(deck: Deck, collection: Collection) -> DeckAnalysisResult:
    missing_cards = deck.missing_cards(collection.names)
    return DeckAnalysisResult(
        commander_name=deck.name,
        identity=deck.identity,
        match_score=deck.match_score(collection),
        owned_count=deck.owned_card_weight(collection),
        missing_count=deck.missing_card_weight(collection),
        missing_cards=tuple(sorted(missing_cards)),
        missing_by_tag={},
    )


def add_recommendations(
    analysis: DeckAnalysisResult,
    deck: Deck,
    collection: Collection,
    scryfall_cache: ScryfallCache,
    tag_cache: TagCache,
) -> DeckAnalysisResult:
    owned_cards = collection.names
    missing_by_tag = group_missing_cards_by_tag(
        set(analysis.missing_cards), tag_cache
    )
    replacements = suggest_functional_replacements(
        deck, owned_cards, scryfall_cache, tag_cache
    )
    same_type_replacements = suggest_same_type_replacements_for_missing_cards(
        deck, owned_cards
    )
    land_replacements = {
        card: names
        for card, names in same_type_replacements.items()
        if scryfall_cache.get_primary_card_type(
            scryfall_cache.get_type_line(card) or ""
        ) == "land"
    }
    replacement_groups = [
        ReplacementGroupResult(
            tag=tag,
            missing_cards=tuple(sorted(missing_by_tag[tag])),
            replacements=tuple(replacements[tag]),
        )
        for tag in sorted(replacements)
    ]
    if land_replacements:
        replacement_groups.append(
            ReplacementGroupResult(
                tag="lands",
                missing_cards=tuple(sorted(land_replacements)),
                replacements=tuple(
                    sorted(
                        {
                            name
                            for names in land_replacements.values()
                            for name in names
                        }
                    )
                ),
            )
        )
    return DeckAnalysisResult(
        commander_name=analysis.commander_name,
        identity=analysis.identity,
        match_score=analysis.match_score,
        owned_count=analysis.owned_count,
        missing_count=analysis.missing_count,
        missing_cards=analysis.missing_cards,
        missing_by_tag={
            tag: tuple(sorted(cards))
            for tag, cards in sorted(missing_by_tag.items())
        },
        replacements_by_tag=tuple(replacement_groups),
        owned_synergy_cards=tuple(
            card["name"].strip().lower()
            for card in sorted(
                suggest_owned_synergy_cards(deck, owned_cards),
                key=lambda card: (
                    -(card.get("synergy") or 0),
                    card["name"].strip().lower(),
                ),
            )
        ),
        same_type_replacements={
            card: tuple(sorted(names))
            for card, names in sorted(
                same_type_replacements.items()
            )
        },
    )
