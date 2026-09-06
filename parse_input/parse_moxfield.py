"""Parse supported collection exports into normalized card quantities.

Only a card-name field (``Name`` or ``Card Name``) and a quantity field
(``Count`` or ``Quantity``) are required. Other export-specific columns are
ignored, so Moxfield and Archidekt exports can be read without conversion.
"""
import csv
import re
from collections import defaultdict
from models.collection import Collection


NAME_HEADERS = ("Name", "Card Name")
QUANTITY_HEADERS = ("Count", "Quantity")
TEXT_COLLECTION_LINE = re.compile(
    r"^\s*(?P<quantity>\d+)\s+(?P<name>.+?)(?:\s+\([^)]+\)\s+\S+)?(?:\s+\*F\*)?\s*$"
)


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


def parse_moxfield_csv(path_or_fileobj, skipped: list[str] | None = None) -> dict[str, int]:
    """
    Returns {normalized_card_name: total_quantity_owned}.

    Accepts a file path (str) or an already-open file-like object. Supported
    exports must include a name column (``Name`` or ``Card Name``) and a
    quantity column (``Count`` or ``Quantity``). If ``skipped`` is given, rows
    missing a name or quantity are appended to it for warning purposes.
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
        fieldnames = reader.fieldnames or []
        name_header = next((header for header in NAME_HEADERS if header in fieldnames), None)
        quantity_header = next(
            (header for header in QUANTITY_HEADERS if header in fieldnames), None
        )
        if not name_header or not quantity_header:
            found = ", ".join(fieldnames) if fieldnames else "no columns"
            raise ValueError(
                f"CSV is missing a name column ({'/'.join(NAME_HEADERS)}) and/or a quantity "
                f"column ({'/'.join(QUANTITY_HEADERS)}). Found columns: {found}."
            )

        for row_number, row in enumerate(reader, start=2):
            raw_name = row.get(name_header)
            raw_count = row.get(quantity_header)
            if not raw_name or not raw_count:
                if skipped is not None:
                    skipped.append(f"row {row_number}: {row}")
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

    if not collection:
        raise ValueError("No card rows could be parsed from this CSV. Check that it has card names and quantities.")

    return dict(collection)


def parse_plaintext_collection(fileobj, skipped: list[str] | None = None) -> dict[str, int]:
    """Parse ``quantity card name`` lines; trailing ``(set) collector-number`` and ``*F*`` are optional.

    If ``skipped`` is given, non-blank lines that don't match the expected
    format are appended to it for warning purposes.
    """
    collection: dict[str, int] = defaultdict(int)

    for line_number, line in enumerate(fileobj, start=1):
        match = TEXT_COLLECTION_LINE.match(line)
        if not match:
            if skipped is not None and line.strip():
                skipped.append(f"line {line_number}: {line.strip()}")
            continue

        for key in split_dfc_names(match["name"]):
            collection[key] += int(match["quantity"])

    if not collection:
        raise ValueError(
            "No card lines could be parsed from this file. Expected lines like '1 Sol Ring'."
        )

    return dict(collection)


def owned_card_set(collection: dict[str, int] | Collection) -> set[str]:
    """Return just the set of normalized card names owned, discarding quantity."""
    return set(collection if isinstance(collection, dict) else collection.names)


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else "collection.csv"
    result = parse_moxfield_csv(path)
    print(f"Parsed {len(result)} unique card names")
    print(json.dumps(result, indent=2, ensure_ascii=False))