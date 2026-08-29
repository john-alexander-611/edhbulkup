import scryfall.scryfall_api
from models.deck import Deck
from services.deck_service import load_collection, load_decks, search_decks

face_commanders = scryfall.scryfall_api.get_face_commanders()
excluded_commanders = {"Honest Rutstein", "Dina, Soul Steeper"}

NUM_MATCHES = 20


def find_decks(filters=None):
    matches = search_decks(
        load_decks().values(),
        load_collection("parse_input/collection.csv"),
        filters or (),
        NUM_MATCHES,
    )
    for match in matches:
        print((match.match_score, match.commander_name))
    return matches


def get_decks():
    return load_decks()


def filter_face_commanders(deck: Deck):
    return deck.name not in face_commanders


def filter_partners(deck: Deck):
    return "//" not in deck.name


def filter_unlimited_commanders(deck: Deck):
    return "unlimited" not in deck.name.lower()


def filter_excluded_commanders(excluded):
    def _filter(deck: Deck):
        return deck.name not in excluded
    return _filter


def filter_color_identity(color_identity):
    return lambda deck: deck.identity == color_identity


def filter_contains_colors(colors):
    return lambda deck: deck.commander.contains_colors(colors)


def filter_exclude_colors(exclude_colors):
    def _filter(deck: Deck):
        return all(c not in deck.identity for c in exclude_colors)
    return _filter


def filter_commander_name(name):
    if not name or not name.strip():
        return lambda deck: True
    search_term = name.strip().lower()
    return lambda deck: search_term in deck.name.lower()


def get_commander_suggestions(query: str, limit: int = 10) -> list[str]:
    if not query or not query.strip():
        return []
    search_term = query.strip().lower()
    decks = get_decks()
    matches = [
        deck.name
        for deck in sorted(decks.values(), key=lambda d: d.name)
        if search_term in deck.name.lower()
    ]
    return matches[:limit]


if __name__ == "__main__":
    find_decks(filters=[
        filter_face_commanders,
        filter_partners,
        filter_excluded_commanders(excluded_commanders),
        filter_exclude_colors("UB"),
    ])