import heapq
from parse_input.parse_moxfield import parse_moxfield_csv, owned_card_set
import json
from pathlib import Path


def find_decks():
    edhrec_data = get_decks()
    card_list = owned_card_set(parse_moxfield_csv("parse_input/collection.csv"))

    best_matches = []
    num_matches = 20

    for commander, data in edhrec_data.items():
        decklist = data["decklist"]
        match_pct = len(card_list & decklist) / len(decklist) if decklist else 0

        score = (match_pct, commander)

        if len(best_matches) < num_matches:
            heapq.heappush(best_matches, score)
        elif match_pct > best_matches[0][0]:
            heapq.heapreplace(best_matches, score)
    best_matches.sort(reverse=True)
    for match in best_matches:
        print(match)
    return best_matches


def get_decks():
    json_path = Path(__file__).parent / "create_cache" / "commander_data.json"
    with open(json_path, "r") as f:
        json_data = json.load(f)

    commander_data = {
        commander: {
            "identity": set(data["identity"]),
            "decklist": set(data["decklist"])
        }
        for commander, data in json_data.items()
    }
    return commander_data


if __name__ == "__main__":
    find_decks()