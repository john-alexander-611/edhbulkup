import asyncio

import httpx

from create_cache.edhrec_raw import fetch_commander_page_categories
from models.deck import Deck
from commander_specific import (
    group_missing_cards_by_tag,
    suggest_functional_replacements,
    suggest_owned_synergy_cards,
    suggest_same_type_replacements_for_missing_cards,
)
from scryfall.cache_wrappers import ScryfallCache, TagCache
from services.deck_service import analyze_deck, load_collection, load_decks


async def inspect_commander(deck: Deck, owned_cards: set[str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        categories = await fetch_commander_page_categories(client, deck.name)
    deck.set_categories(categories)
    return suggest_owned_synergy_cards(deck, owned_cards)


if __name__ == "__main__":
    collection = load_collection("parse_input/collection.csv")
    owned = collection.names
    all_commanders = load_decks()
    scryfall_cache = ScryfallCache()
    tag_cache = TagCache()

    commander_name = "Mahadi, Emporium Master"
    deck = all_commanders[commander_name]

    print("Missing cards:")
    analysis = analyze_deck(deck, collection)
    print(analysis.missing_cards)

    synergy_suggestions = asyncio.run(inspect_commander(deck, owned))
    print("\nHigh synergy cards you own but aren't in the average deck:")
    print(synergy_suggestions)

    print("\nFunctional replacements for missing cards:")
    replacements = suggest_functional_replacements(deck, owned, scryfall_cache, tag_cache)
    missing_by_tag = group_missing_cards_by_tag(deck.missing_cards(owned), tag_cache)
    for tag, suggestions in replacements.items():
        print(f"\nFunction: {tag}")
        print(f"Missing cards: {sorted(missing_by_tag[tag])}")
        print("Possible replacements:")
        for s in suggestions:
            print(f"  - {s}")
    print("\nSame type replacements for missing cards:")
    same_type_replacements = suggest_same_type_replacements_for_missing_cards(deck, owned)
    for missing_card, suggestions in same_type_replacements.items():
        print(f"\nMissing card: {missing_card}")
        print("Possible replacements:")
        for s in suggestions:
            print(f"  - {s}")