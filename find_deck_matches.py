import heapq
import json
from pathlib import Path

import scryfall.scryfall_api
from models.commander import Commander
from parse_input.parse_moxfield import parse_moxfield_csv, owned_card_set

face_commanders = scryfall.scryfall_api.get_face_commanders()
excluded_commanders = {"Honest Rutstein", "Dina, Soul Steeper"}

NUM_MATCHES = 20


def find_decks(filters=None):
    edhrec_data = get_decks()
    card_list = owned_card_set(parse_moxfield_csv("parse_input/collection.csv"))

    best_matches = []
    for commander in edhrec_data.values():
        if filters and not all(f(commander) for f in filters):
            continue

        match_pct = commander.match_score(card_list)
        score = (match_pct, commander.name)

        if len(best_matches) < NUM_MATCHES:
            heapq.heappush(best_matches, score)
        elif match_pct > best_matches[0][0]:
            heapq.heapreplace(best_matches, score)

    best_matches.sort(reverse=True)
    for match in best_matches:
        print(match)
    return best_matches


def get_decks() -> dict[str, Commander]:
    json_path = Path(__file__).parent / "create_cache" / "commander_data.json"
    with open(json_path, "r") as f:
        json_data = json.load(f)
    return {name: Commander.from_json(name, data) for name, data in json_data.items()}


def filter_face_commanders(commander: Commander):
    return commander.name not in face_commanders


def filter_partners(commander: Commander):
    return "//" not in commander.name


def filter_excluded_commanders(excluded):
    def _filter(commander: Commander):
        return commander.name not in excluded
    return _filter


def filter_color_identity(color_identity):
    return lambda c: c.identity == color_identity


def filter_contains_colors(colors):
    return lambda c: c.contains_colors(colors)


def filter_exclude_colors(exclude_colors):
    def _filter(commander: Commander):
        return all(c not in commander.identity for c in exclude_colors)
    return _filter


if __name__ == "__main__":
    find_decks(filters=[
        filter_face_commanders,
        filter_partners,
        filter_excluded_commanders(excluded_commanders),
        filter_exclude_colors("UB"),
    ])