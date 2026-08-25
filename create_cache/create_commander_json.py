import sqlite3
import json


def create_commander_json():
    conn = sqlite3.connect("../cache.sqlite")

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
                "identity": set(identity),
                "decklist": set()
            }

        commander_data[name]["decklist"].add(card_name)

    conn.close()

    # Convert sets to lists for JSON
    json_data = {
        commander: {
            "identity": list(data["identity"]),
            "decklist": list(data["decklist"])
        }
        for commander, data in commander_data.items()
    }

    with open("commander_data.json", "w") as f:
        json.dump(json_data, f, indent=2)
        print("\ncommander_data.json write completed")
