import sqlite3
import json
from pathlib import Path

# Resolved relative to this file, not the caller's cwd, so the output always
# lands in create_cache/ regardless of where the script is invoked from.
_DIR = Path(__file__).parent


def create_commander_json():
    """Export cache.sqlite's commanders/decklist_cards tables to commander_data.json."""
    conn = sqlite3.connect(str(_DIR.parent / "cache.sqlite"))

    commander_data = {}

    query = """
        SELECT c.name, c.identity, dc.card_name
        FROM commanders AS c
        JOIN decklist_cards AS dc
            ON dc.commander = c.name
    """

    for name, identity, card_name in conn.execute(query):
        if name not in commander_data:
            commander_data[name] = {
                "identity": identity,
                "decklist": []
            }

        commander_data[name]["decklist"].append(card_name)

    conn.close()

    json_data = {
        commander: {
            "identity": data["identity"],
            "decklist": data["decklist"]
        }
        for commander, data in commander_data.items()
    }

    with open(_DIR / "commander_data.json", "w") as f:
        json.dump(json_data, f, indent=2)
        print("\ncommander_data.json write completed")


