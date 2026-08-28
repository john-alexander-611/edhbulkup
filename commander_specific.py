from find_deck_matches import get_decks
from models.commander import Commander
from scryfall.scryfall_api import get_card_type
from scryfall.cache_wrappers import ScryfallCache, TagCache


def get_missing_cards(commander_name: str, owned_cards: set[str]) -> set[str]:
    all_commanders = get_decks()
    commander = all_commanders.get(commander_name)
    if commander is None:
        raise ValueError(f"No cached data for commander: {commander_name!r}")

    missing = commander.missing_cards(owned_cards)
    print(missing)
    return missing


def suggest_owned_synergy_cards(commander: Commander, owned_cards: set[str]) -> list[dict]:
    high_synergy_cards = commander.get_category("high_synergy_cards")

    suggestions = []
    for card in high_synergy_cards:
        name = card["name"].strip().lower()
        if name in commander.decklist:
            continue
        if name not in owned_cards:
            continue
        suggestions.append(card)

    suggestions.sort(key=lambda c: c.get("synergy") or 0, reverse=True)
    return suggestions


TYPE_TO_CATEGORIES = {
    "creature": ["creatures"],
    "instant": ["instants"],
    "sorcery": ["sorceries"],
    "enchantment": ["enchantments"],
    "planeswalker": ["planeswalkers"],
    "land": ["lands"],
    "artifact": ["utility_artifacts", "mana_artifacts"],
}


def suggest_same_type_replacements_for_missing_cards(
    commander: Commander, owned_cards: set[str]
) -> dict[str, list[dict]]:
    """
    For each card missing from the commander's average decklist, find owned
    cards of the same broad type as replacement candidates.

    Returns {missing_card_name: [replacement_card_dict, ...], ...}, each
    inner list sorted by synergy score (highest first) when available.
    """
    missing_cards = commander.missing_cards(owned_cards)
    suggestions: dict[str, list[dict]] = {}

    for missing_card in missing_cards:
        card_type = get_card_type(missing_card)
        category_names = TYPE_TO_CATEGORIES.get(card_type)
        if not category_names:
            continue  # unrecognized/unsupported type - skip rather than guess

        same_type_cards = []
        for category_name in category_names:
            same_type_cards.extend(commander.get_category(category_name))

        replacements = [
            card for card in same_type_cards
            if card["name"].strip().lower() in owned_cards
        ]
        replacements.sort(key=lambda c: c.get("synergy") or 0, reverse=True)

        suggestions[missing_card] = replacements

    return suggestions


def suggest_functional_replacements(
    commander: Commander,
    owned_cards: set[str],
    scryfall_cache: ScryfallCache,
    tag_cache: TagCache,
) -> dict[str, list[str]]:
    all_suggestions = commander.get_all_edhrec_suggestions()
    suggestions = {}

    for missing_card in commander.missing_cards(owned_cards):
        tags = tag_cache.get_tags(missing_card)
        candidates = set()
        for tag in tags:
            candidates |= tag_cache.get_cards_with_tag(tag)
        legal_owned = [
            c for c in (candidates & owned_cards & all_suggestions.keys())
            if commander.is_card_legal(
                scryfall_cache.get_color_identity(c) or ""
            )
        ]
        # Sort by EDHREC synergy, highest first, then take 5
        legal_owned.sort(
            key=lambda card: all_suggestions[card],
            reverse=True
        )
        if legal_owned:
            suggestions[missing_card] = legal_owned[:5]

    return suggestions
