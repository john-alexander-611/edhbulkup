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


if __name__ == "__main__":
    find_decks(filters=[
        filter_face_commanders,
        filter_partners,
        filter_excluded_commanders(excluded_commanders),
        filter_exclude_colors("UB"),
    ])