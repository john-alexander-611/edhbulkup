"""
Minimal, defensive EDHREC client.

Mightstone's pydantic models can fail to parse live EDHREC responses when a
card entry is missing a field the model expects (e.g. `sanitized_wo` on
double-faced or special cards). Rather than fight that fragility, this module
talks to the same json.edhrec.com endpoints directly and pulls out only the
handful of fields the cache builder actually needs, tolerating missing/odd
entries instead of raising on them.

Install:
    pip install httpx python-slugify
"""

import httpx
import slugify as _slugify_lib

BASE_URL = "https://json.edhrec.com/pages"

# Same 32 color identity codes EDHREC/mightstone use.
COLOR_IDENTITIES = [
    "colorless", "w", "u", "b", "r", "g",
    "wu", "ub", "br", "rg", "gw", "wb", "ur", "bg", "rw", "gu",
    "wub", "ubr", "brg", "rgw", "gwu", "wbg", "urw", "bgu", "rwb", "gur",
    "wubr", "ubrg", "brgw", "rgwu", "gwub",
    "wubrg",
]


def slugify(name: str) -> str:
    """
    Match EDHREC's slug format so URLs resolve correctly.

    Some characters must be deleted outright rather than treated as word
    separators, because python-slugify's default behavior turns them into
    a hyphen even when they sit inside a single word:
      - "." as in "H.E.R.B.I.E. Scout Unit" -> "herbie-scout-unit"
        (not "h-e-r-b-i-e-scout-unit")
      - "," as in "Nick Fury, Agent of S.H.I.E.L.D" -> "nick-fury-agent-of-shield"
      - "\ua789" (MODIFIER LETTER COLON) as in "Ratonhnhaké\ua789ton"
        (Mohawk orthography) -> "ratonhnhaketon" (not "ratonhnhake-ton")

    If another commander 404s/403s, check whether its name has an unusual
    character in this same position (mid-word, no surrounding space) before
    assuming it's a rate-limit issue - it's likely another one of these.
    """
    return _slugify_lib.slugify(
        name,
        separator="-",
        replacements=[(".", ""), ("'", ""), ("+", "plus-"), ("\ua789", "")],
    )


def normalize_identity(bucket_key: str) -> str:
    return "C" if bucket_key == "colorless" else bucket_key.upper()


async def fetch_json(client: httpx.AsyncClient, path: str, _redirects_followed: int = 0) -> dict | None:
    """
    GET a page path, returning None (not raising) on 404 or bad JSON.

    EDHREC's static JSON host sometimes returns a soft redirect instead of
    content - e.g. requesting commanders/gu.json returns
    {"redirect": "/commanders/simic"} rather than the actual commander list,
    because multi-color identities are keyed by guild/shard/wedge name
    (simic, azorius, jund, ...) rather than letter codes. Follow those
    redirects automatically, capped at a few hops to avoid any loop.
    """
    try:
        resp = await client.get(f"{BASE_URL}/{path}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
        print(f"  ! failed to fetch {path}: {e}")
        return None

    if isinstance(data, dict) and set(data.keys()) == {"redirect"}:
        if _redirects_followed >= 3:
            print(f"  ! too many redirects starting from {path}")
            return None
        target = data["redirect"].lstrip("/")
        return await fetch_json(client, f"{target}.json", _redirects_followed + 1)

    return data


async def fetch_average_deck(client: httpx.AsyncClient, commander_name: str) -> list[str] | None:
    """
    Returns the flat list of ~99 card names for a commander's average deck,
    or None if the page couldn't be fetched.

    The real shape of data["deck"] is:
        {
            "commander": ["Kozilek, the Great Distortion"],
            "commander_v2": [["Kozilek, the Great Distortion", 1]],
            "cards": {
                "Artifact": [["Sol Ring", 1], ["Mana Vault", 1], ...],
                "Land": [["Ancient Tomb", 1], ["Wastes", 10], ...],
                ...one key per card type...
            }
        }
    "Wastes" with count 10 means ten copies of that basic land - each
    [name, count] pair is expanded to `count` copies of `name` below so
    a set-intersection match later correctly weighs basics.
    """
    slug = slugify(commander_name)
    data = await fetch_json(client, f"average-decks/{slug}.json")
    if data is None:
        return None

    deck = data.get("deck") or {}
    cards_by_type = deck.get("cards") or {}

    card_names: list[str] = []
    for entries in cards_by_type.values():
        for entry in entries:
            if not entry:
                continue
            name = entry[0]
            count = entry[1] if len(entry) > 1 else 1
            card_names.extend([name] * count)

    return card_names


# Maps a friendly name to EDHREC's real category tag, so callers don't need
# to remember exact strings like "highsynergycards".
CARD_CATEGORY_TAGS = {
    "new_cards": "newcards",
    "high_synergy_cards": "highsynergycards",
    "top_cards": "topcards",
    "game_changers": "gamechangers",
    "creatures": "creatures",
    "instants": "instants",
    "sorceries": "sorceries",
    "utility_artifacts": "utilityartifacts",
    "enchantments": "enchantments",
    "planeswalkers": "planeswalkers",
    "utility_lands": "utilitylands",
    "mana_artifacts": "manaartifacts",
    "lands": "lands",
}


async def fetch_commander_page_categories(client: httpx.AsyncClient, commander_name: str) -> dict[str, list[dict]]:
    """
    One HTTP call per commander. Returns every category on the commander
    page keyed by its real tag, e.g.:
        {"highsynergycards": [{"name": ..., "synergy": ..., ...}, ...],
         "topcards": [...], ...}

    Call this once per commander (e.g. when the user clicks into one) and
    reuse the result - don't call it separately per category, that would
    re-fetch the same page multiple times for no reason.
    """
    slug = slugify(commander_name)
    data = await fetch_json(client, f"commanders/{slug}.json")
    if data is None:
        return {}

    try:
        collections = data["container"]["json_dict"].get("cardlists") or []
    except (KeyError, TypeError):
        return {}

    categories: dict[str, list[dict]] = {}
    for collection in collections:
        tag = collection.get("tag")
        if not tag:
            continue
        cards = []
        for view in collection.get("cardviews", []):
            name = view.get("name")
            if not name:
                continue
            cards.append({
                "name": name,
                "num_decks": view.get("num_decks"),
                "synergy": view.get("synergy"),
                "inclusion": view.get("inclusion"),
            })
        categories[tag] = cards

    return categories


def get_category(categories: dict[str, list[dict]], friendly_name: str) -> list[dict]:
    """
    Look up a category by friendly name against an already-fetched
    categories dict (from fetch_commander_page_categories). Free - no API
    call happens here.
        get_category(categories, "high_synergy_cards")
    """
    tag = CARD_CATEGORY_TAGS.get(friendly_name, friendly_name)
    return categories.get(tag, [])


def _extract_cardviews(raw_page: dict) -> list[dict]:
    """
    Defensively pull card entries out of container.json_dict.cardlists[*].cardviews,
    tolerating entries that are missing fields mightstone's strict models require.
    """
    items = []
    try:
        collections = raw_page["container"]["json_dict"].get("cardlists") or []
    except (KeyError, TypeError):
        return items

    for collection in collections:
        for view in collection.get("cardviews", []):
            name = view.get("name")
            if not name:
                continue  # skip malformed entries instead of crashing
            items.append({
                "name": name,
                "num_decks": view.get("num_decks"),
                "label": collection.get("header"),
            })
    return items


async def fetch_commanders_by_identity(client: httpx.AsyncClient, identity: str) -> list[dict]:
    """
    Returns [{"name": ..., "num_decks": ...}, ...] for all commanders in a
    given color identity (e.g. "wub", "colorless", "wubrg").
    """
    data = await fetch_json(client, f"commanders/{identity}.json")
    if data is None:
        return []

    # Top-level "cardlist" holds the actual commander list on this page type;
    # fall back to scanning container cardlists if that's empty.
    top_level = data.get("cardlist") or []
    if top_level:
        results = []
        for view in top_level:
            name = view.get("name")
            if not name:
                continue
            results.append({"name": name, "num_decks": view.get("num_decks")})
        return results

    return _extract_cardviews(data)