import json
import io

import pytest

from app.main import build_card_details, humanize_tag_label
import services.deck_service as deck_service
from commander_specific import (
    group_missing_cards_by_tag,
    rank_functional_replacements_for_tag,
)
from models.collection import Collection
from models.commander import Commander
from models.deck import Deck
from parse_input.parse_moxfield import parse_moxfield_csv, parse_plaintext_collection
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
    def __init__(self, identities, type_lines=None):
        self.identities = identities
        self.type_lines = type_lines or {}

    def get_color_identity(self, card_name):
        return self.identities.get(card_name)

    def get_type_line(self, card_name):
        return self.type_lines.get(card_name)

    def get_primary_card_type(self, type_line):
        return type_line.split(" ", 1)[0].lower() if type_line else None


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


def test_parse_collection_csv_supports_archidekt_headers_and_extra_columns():
    export = io.StringIO(
        "Quantity,Name,Finish,Condition\n"
        "2,Sol Ring,Normal,NM\n"
        "1,Sol Ring,Foil,NM\n"
        "1,Delver of Secrets // Insectile Aberration,Normal,NM\n"
    )

    assert parse_moxfield_csv(export) == {
        "sol ring": 3,
        "delver of secrets // insectile aberration": 1,
        "delver of secrets": 1,
    }


def test_parse_collection_csv_supports_card_name_header():
    export = io.StringIO("Quantity,Card Name\n4,Rat Colony\n")

    assert parse_moxfield_csv(export) == {"rat colony": 4}


def test_parse_plaintext_collection_ignores_print_details_and_foil_markers():
    export = io.StringIO(
        "1 Aphelia, Viper Whisperer (J25) 40\n"
        "10 Forest (MH3) 318\n"
        "1 Revitalizing Repast / Old-Growth Grove (MH3) 256\n"
        "1 Phyrexian Arena (ONE) 283 *F*\n"
    )

    assert parse_plaintext_collection(export) == {
        "aphelia, viper whisperer": 1,
        "forest": 10,
        "revitalizing repast / old-growth grove": 1,
        "phyrexian arena": 1,
    }


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


def test_search_decks_can_filter_to_owned_commanders():
    decks = [
        make_deck("Owned Commander", {"a"}),
        make_deck("Unowned Commander", {"a"}),
    ]
    collection = Collection({"owned commander": 1, "a": 1})

    results = search_decks(
        decks,
        collection,
        filters=[lambda deck: deck.commander.name in collection],
    )

    assert [result.commander_name for result in results] == ["Owned Commander"]


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


def test_humanize_tag_label_formats_all_slug_variants():
    assert humanize_tag_label("burn") == "Burn"
    assert humanize_tag_label("death-trigger") == "Death Trigger"
    assert humanize_tag_label("card-advantage") == "Card Advantage"
    assert humanize_tag_label("lifegain") == "Life Gain"
    assert humanize_tag_label("ramp") == "Ramp"
    assert humanize_tag_label("recursion") == "Recursion"


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


def test_add_recommendations_adds_a_separate_land_group(monkeypatch):
    deck = make_deck("Test", {"missing land", "missing creature"}, "BR")
    deck.set_categories({})
    tag_cache = FakeTagCache(
        {
            "missing land": ["ramp"],
            "missing creature": ["ramp"],
        },
        {},
    )
    scryfall_cache = FakeScryfallCache(
        {},
        {
            "missing land": "Land",
            "missing creature": "Creature",
        },
    )
    monkeypatch.setattr(
        deck_service,
        "suggest_functional_replacements",
        lambda *args: {"ramp": ["mana rock"]},
    )
    monkeypatch.setattr(
        deck_service,
        "suggest_same_type_replacements_for_missing_cards",
        lambda *args: {
            "missing land": [
                "land one",
                "land two",
                "land three",
                "land four",
                "land five",
                "land six",
                "land seven",
                "land eight",
                "land nine",
                "land ten",
                "land eleven",
                "land twelve",
            ]
        },
    )

    result = deck_service.add_recommendations(
        analyze_deck(deck, Collection()),
        deck,
        Collection(),
        scryfall_cache,
        tag_cache,
    )

    assert [(group.tag, group.missing_cards, group.replacements) for group in result.replacements_by_tag] == [
        ("ramp", ("missing creature", "missing land"), ("mana rock",)),
        (
            "lands",
            ("missing land",),
            (
                "land eight",
                "land eleven",
                "land five",
                "land four",
                "land nine",
                "land one",
                "land seven",
                "land six",
                "land ten",
                "land three",
                "land twelve",
                "land two",
            ),
        ),
    ]


def test_build_card_details_keeps_every_missing_card():
    details = build_card_details(
        ["zeta", "alpha"],
        lambda names: {
            name: {"display_name": name.upper(), "image_url": f"https://example.com/{name}.jpg"}
            for name in names
        },
    )

    assert [card.name for card in details] == ["alpha", "zeta"]
    assert [card.display_name for card in details] == ["ALPHA", "ZETA"]


def test_load_decks_supports_empty_cache_and_reports_missing_cache(tmp_path):
    empty_cache = tmp_path / "empty.json"
    empty_cache.write_text(json.dumps({}), encoding="utf-8")

    assert load_decks(empty_cache) == {}
    with pytest.raises(FileNotFoundError):
        load_decks(tmp_path / "missing.json")
