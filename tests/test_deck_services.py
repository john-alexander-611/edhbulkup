import json

import pytest

from commander_specific import (
    group_missing_cards_by_tag,
    rank_functional_replacements_for_tag,
)
from models.collection import Collection
from models.commander import Commander
from models.deck import Deck
from services.deck_service import analyze_deck, load_decks, search_decks


class FakeTagCache:
    def __init__(self, tags_by_card, cards_by_tag):
        self.tags_by_card = tags_by_card
        self.cards_by_tag = cards_by_tag

    def get_tags(self, card_name):
        return self.tags_by_card.get(card_name, [])

    def get_cards_with_tag(self, tag):
        return self.cards_by_tag.get(tag, set())


class FakeScryfallCache:
    def __init__(self, identities):
        self.identities = identities

    def get_color_identity(self, card_name):
        return self.identities.get(card_name)


def make_deck(name, cards, identity="BR"):
    return Deck(Commander(name, identity), frozenset(cards))


def test_search_decks_returns_match_percentage_and_deterministic_order():
    decks = [
        make_deck("Zulu", {"a", "b", "c"}),
        make_deck("Alpha", {"a", "b", "c"}),
        make_deck("Partial", {"a", "b", "c", "d"}),
    ]
    results = search_decks(decks, Collection({"a": 1, "b": 1}), limit=3)

    assert [(result.commander_name, result.match_percentage) for result in results] == [
        ("Alpha", 66.67),
        ("Zulu", 66.67),
        ("Partial", 50.0),
    ]
    assert results[0].to_dict()["owned_count"] == 2


def test_search_decks_applies_filters_and_rejects_invalid_limit():
    decks = [
        make_deck("Boros", {"a"}, "R"),
        make_deck("Dimir", {"a"}, "UB"),
    ]

    results = search_decks(
        decks,
        Collection({"a": 1}),
        filters=[lambda deck: deck.identity == "UB"],
    )

    assert [result.commander_name for result in results] == ["Dimir"]
    with pytest.raises(ValueError, match="limit must be positive"):
        search_decks(decks, Collection(), limit=0)


def test_analyze_deck_reports_sorted_missing_cards_and_counts():
    deck = make_deck("Test", {"zeta", "alpha", "owned"})

    result = analyze_deck(deck, Collection({"owned": 1}))

    assert result.missing_cards == ("alpha", "zeta")
    assert result.owned_count == 1
    assert result.missing_count == 2
    assert result.match_percentage == 33.33


def test_group_missing_cards_by_all_functional_tags():
    tag_cache = FakeTagCache(
        {
            "missing a": ["ramp", "draw"],
            "missing b": ["ramp"],
        },
        {},
    )

    assert group_missing_cards_by_tag({"missing b", "missing a"}, tag_cache) == {
        "ramp": {"missing a", "missing b"},
        "draw": {"missing a"},
    }


def test_rank_functional_replacements_filters_and_limits_by_synergy():
    deck = make_deck("Test", {"missing", "already in deck"}, "BR")
    tag_cache = FakeTagCache(
        {},
        {
            "ramp": {
                "sol ring",
                "fellwar stone",
                "off-color",
                "low synergy",
                "already in deck",
                "test",
            }
        },
    )
    scryfall_cache = FakeScryfallCache(
        {
            "sol ring": "C",
            "fellwar stone": "C",
            "off-color": "W",
            "low synergy": "B",
            "already in deck": "B",
            "test": "B",
        }
    )
    edhrec_suggestions = {
        "sol ring": 10,
        "fellwar stone": 8,
        "off-color": 100,
        "low synergy": 1,
        "already in deck": 1000,
        "test": 900,
    }

    replacements = rank_functional_replacements_for_tag(
        "ramp",
        {
            "sol ring",
            "fellwar stone",
            "off-color",
            "low synergy",
            "already in deck",
            "test",
        },
        deck,
        scryfall_cache,
        tag_cache,
        edhrec_suggestions,
    )

    assert replacements == ["sol ring", "fellwar stone", "low synergy"]


def test_load_decks_supports_empty_cache_and_reports_missing_cache(tmp_path):
    empty_cache = tmp_path / "empty.json"
    empty_cache.write_text(json.dumps({}), encoding="utf-8")

    assert load_decks(empty_cache) == {}
    with pytest.raises(FileNotFoundError):
        load_decks(tmp_path / "missing.json")
