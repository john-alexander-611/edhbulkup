from models.deck import Deck
from scryfall.scryfall_api import get_card_type
from scryfall.cache_wrappers import ScryfallCache, TagCache


def get_missing_cards(commander_name: str, owned_cards: set[str]) -> set[str]:
    from services.deck_service import load_decks

    all_commanders = load_decks()
    deck = all_commanders.get(commander_name)
    if deck is None:
        raise ValueError(f"No cached data for commander: {commander_name!r}")

    missing = deck.missing_cards(owned_cards)
    print(missing)
    return missing


def suggest_owned_synergy_cards(deck: Deck, owned_cards: set[str]) -> list[dict]:
    high_synergy_cards = deck.get_category("high_synergy_cards")

    suggestions = []
    for card in high_synergy_cards:
        name = card["name"].strip().lower()
        if name in deck.cards:
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
    deck: Deck, owned_cards: set[str]
) -> dict[str, list[dict]]:
    """
    For each card missing from the commander's average decklist, find owned
    cards of the same broad type as replacement candidates.

    Returns {missing_card_name: [replacement_card_dict, ...], ...}, each
    inner list sorted by synergy score (highest first) when available.
    """
    missing_cards = deck.missing_cards(owned_cards)
    suggestions: dict[str, list[dict]] = {}
    scryfall_cache = ScryfallCache()

    for missing_card in missing_cards:
        card_type_full = scryfall_cache.get_type_line(missing_card)
        card_type = scryfall_cache.get_primary_card_type(card_type_full)
        category_names = TYPE_TO_CATEGORIES.get(card_type)
        if not category_names:
            continue  # unrecognized/unsupported type - skip rather than guess

        same_type_cards = []
        for category_name in category_names:
            same_type_cards.extend(deck.get_category(category_name))

        replacements = [
            card for card in same_type_cards
            if card["name"].strip().lower() in owned_cards
        ]
        replacements.sort(key=lambda c: c.get("synergy") or 0, reverse=True)

        suggestions[missing_card] = [c["name"] for c in replacements]

    return suggestions


def group_missing_cards_by_tag(
    missing_cards: set[str], tag_cache: TagCache
) -> dict[str, set[str]]:
    """Group missing cards by every functional tag associated with each card."""
    grouped: dict[str, set[str]] = {}
    for card in missing_cards:
        for tag in tag_cache.get_tags(card):
            grouped.setdefault(tag, set()).add(card)
    return grouped


def rank_functional_replacements_for_tag(
    tag: str,
    owned_cards: set[str],
    deck: Deck,
    scryfall_cache: ScryfallCache,
    tag_cache: TagCache,
    edhrec_suggestions: dict[str, float],
) -> list[str]:
    """Return the top five legal, owned EDHREC suggestions for one tag."""
    candidates = tag_cache.get_cards_with_tag(tag)
    excluded_cards = set(deck.cards) | {deck.name.strip().lower()}
    legal_owned = [
        card
        for card in candidates & owned_cards & edhrec_suggestions.keys()
        if card not in excluded_cards
        if deck.is_card_legal(scryfall_cache.get_color_identity(card) or "")
    ]
    legal_owned.sort(
        key=lambda card: (-edhrec_suggestions[card], card),
    )
    return legal_owned[:5]


def suggest_functional_replacements(
    deck: Deck,
    owned_cards: set[str],
    scryfall_cache: ScryfallCache,
    tag_cache: TagCache,
) -> dict[str, list[str]]:
    edhrec_suggestions = deck.get_all_edhrec_suggestions()
    missing_by_tag = group_missing_cards_by_tag(
        deck.missing_cards(owned_cards), tag_cache
    )
    return {
        tag: replacements
        for tag in missing_by_tag
        if (
            replacements := rank_functional_replacements_for_tag(
                tag,
                owned_cards,
                deck,
                scryfall_cache,
                tag_cache,
                edhrec_suggestions,
            )
        )
    }
