"""
Parses a Moxfield collection CSV export into a normalized card-name -> quantity
mapping, ready to compare against the decklist_cards cache.

Moxfield's export format (relevant columns):
    Count, Tradelist Count, Name, Edition, Condition, Language, Foil, Tags,
    Last Modified, Collector Number, Alter, Proxy, Purchase Price

Only Count and Name matter for deck matching. Everything else (edition,
condition, foil, etc.) is ignored - the same card in two different sets
or foil/non-foil both just count as "you own this card".
"""
#TODO: create a collection class with different input methods
import csv
from collections import defaultdict
from models.collection import Collection


def normalize(name: str) -> str:
    """Match the normalization used when building decklist_cards (build_cache.py)."""
    return name.strip().lower()


def split_dfc_names(name: str) -> list[str]:
    """
    Double-faced/split cards are exported as "Front // Back". EDHREC decklists
    reference these by the front-face name only, so index the card under both
    the full combined name and the front face alone - whichever one shows up
    in a decklist will match.
    """
    name = name.strip()
    if " // " in name:
        front, _, _ = name.partition(" // ")
        return [normalize(name), normalize(front.strip())]
    return [normalize(name)]


def parse_moxfield_csv(path_or_fileobj) -> dict[str, int]:
    """
    Returns {normalized_card_name: total_quantity_owned}.

    Accepts a file path (str) or an already-open file-like object, so it
    works the same way whether you're reading from disk or from an
    in-memory upload (e.g. a Streamlit file uploader).
    """
    collection: dict[str, int] = defaultdict(int)

    if isinstance(path_or_fileobj, str):
        f = open(path_or_fileobj, newline="", encoding="utf-8-sig")
        should_close = True
    else:
        f = path_or_fileobj
        should_close = False

    try:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = row.get("Name")
            raw_count = row.get("Count")
            if not raw_name or not raw_count:
                continue

            try:
                count = int(raw_count)
            except ValueError:
                count = 1

            for key in split_dfc_names(raw_name):
                collection[key] += count
    finally:
        if should_close:
            f.close()

    return dict(collection)


def owned_card_set(collection: dict[str, int] | Collection) -> set[str]:
    """
    Returns just the set of normalized card names owned, discarding quantity.

    Commander decks are singleton, so for the vast majority of cards only
    presence matters - "do they own this card at all". Quantity only
    matters for a small, specific list of cards that allow multiples in a
    single deck (Relentless Rats, Dragon's Approach, Rat Colony, Persistent
    Petitioners, Shadowborn Apostle, Nazgul, etc). That list isn't handled
    yet - `collection` (the full dict with counts) is kept around so the
    matcher can special-case those specific cards later without needing to
    re-parse the CSV.
    """
    return set(collection if isinstance(collection, dict) else collection.names)


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else "collection.csv"
    result = parse_moxfield_csv(path)
    print(f"Parsed {len(result)} unique card names")
    print(json.dumps(result, indent=2, ensure_ascii=False))