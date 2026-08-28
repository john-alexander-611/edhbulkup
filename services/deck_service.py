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
) -> list[DeckMatchResult]:
    if limit < 1:
        raise ValueError("Search result limit must be positive")
    filters = tuple(filters)
    matches = [
        DeckMatchResult(
            commander_name=deck.name,
            identity=deck.identity,
            match_score=deck.match_score(collection.names),
            owned_count=len(deck.cards & collection.names),
            deck_size=len(deck.cards),
        )
        for deck in decks
        if all(deck_filter(deck) for deck_filter in filters)
    ]
    matches.sort(key=lambda match: (-match.match_score, match.commander_name))
    return matches[:limit]


def analyze_deck(deck: Deck, collection: Collection) -> DeckAnalysisResult:
    missing_cards = deck.missing_cards(collection.names)
    return DeckAnalysisResult(
        commander_name=deck.name,
        identity=deck.identity,
        match_score=deck.match_score(collection.names),
        owned_count=len(deck.cards & collection.names),
        missing_count=len(missing_cards),
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
        replacements_by_tag=tuple(
            ReplacementGroupResult(
                tag=tag,
                missing_cards=tuple(sorted(missing_by_tag[tag])),
                replacements=tuple(replacements[tag]),
            )
            for tag in sorted(replacements)
        ),
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
                suggest_same_type_replacements_for_missing_cards(
                    deck, owned_cards
                ).items()
            )
        },
    )
