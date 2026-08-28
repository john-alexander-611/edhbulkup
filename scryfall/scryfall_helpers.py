import sqlite3
from models.commander import Commander
from scryfall.cache_wrappers import ScryfallCache


def filter_legal_cards(scryfall_cache: ScryfallCache, candidates: list[str], commander: Commander) -> list[str]:
    return [
        name for name in candidates
        if commander.is_card_legal(scryfall_cache.get_color_identity(name) or "")
    ]