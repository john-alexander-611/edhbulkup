import asyncio

import httpx

from create_cache.edhrec_raw import fetch_commander_page_categories
from find_deck_matches import get_decks
from models.commander import Commander
from parse_input.parse_moxfield import owned_card_set, parse_moxfield_csv
from commander_specific import (suggest_owned_synergy_cards, suggest_same_type_replacements_for_missing_cards,
                                suggest_functional_replacements)
from scryfall.cache_wrappers import ScryfallCache, TagCache


async def inspect_commander(commander: Commander, owned_cards: set[str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        categories = await fetch_commander_page_categories(client, commander.name)
    commander.set_categories(categories)
    return suggest_owned_synergy_cards(commander, owned_cards)


if __name__ == "__main__":
    owned = owned_card_set(parse_moxfield_csv("parse_input/collection.csv"))
    all_commanders = get_decks()
    scryfall_cache = ScryfallCache()
    tag_cache = TagCache()

    commander_name = "Mahadi, Emporium Master"
    commander = all_commanders[commander_name]

    print("Missing cards:")
    print(commander.missing_cards(owned))

    synergy_suggestions = asyncio.run(inspect_commander(commander, owned))
    print("\nHigh synergy cards you own but aren't in the average deck:")
    print(synergy_suggestions)

    print("\nFunctional replacements for missing cards:")
    replacements = suggest_functional_replacements(commander, owned, scryfall_cache, tag_cache)
    for card, suggestions in replacements.items():
        print(f"\nMissing card: {card}")
        if not suggestions:
            print("  (no owned replacements found)")
        print("Possible replacements:")
        for s in suggestions:
            print(f"  - {s}")