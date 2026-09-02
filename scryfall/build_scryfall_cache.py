"""
Downloads Scryfall's "oracle_cards" bulk data file (one entry per unique
card, deduped across printings) and caches name, type_line, and cmc
locally in SQLite - so replacement matching (same type, similar mana
value) never needs a live per-card Scryfall API call.

As of Scryfall's July 20, 2026 bulk-data change, files are served as
gzipped JSONL (one JSON object per line, no enclosing array) rather than
a single JSON array - the old download_uri/array format was retired, only
jsonl_download_uri exists now. This streams and decompresses the file
incrementally rather than loading it into memory as one blob.

Run:
    pip install httpx
    python build_scryfall_cache.py
"""

import asyncio
import json
import sqlite3
import zlib

import httpx

DB_PATH = "scryfall_cache.sqlite"
BULK_DATA_INDEX_URL = "https://api.scryfall.com/bulk-data"


def resolve_image_url(card: dict) -> str | None:
    """Pick the best available image URL from a Scryfall card object, checking card faces if the card itself has none."""
    image_uris = (card.get("image_uris") or {})
    if image_uris:
        for key in ("normal", "large", "small", "png", "border_crop", "art_crop"):
            url = image_uris.get(key)
            if url:
                return url

    for face in card.get("card_faces") or []:
        uris = face.get("image_uris") or {}
        for key in ("normal", "large", "small", "png", "border_crop", "art_crop"):
            url = uris.get(key)
            if url:
                return url

    return None


def init_db(conn: sqlite3.Connection):
    """Drop and recreate the cards table."""
    conn.executescript("""
        DROP TABLE IF EXISTS cards;

        CREATE TABLE cards (
            name TEXT PRIMARY KEY,
            oracle_id TEXT,
            type_line TEXT,
            cmc REAL,
            mana_cost TEXT,
            color_identity TEXT,
            display_name TEXT,
            image_url TEXT,
            usd_price REAL
        );
        CREATE INDEX idx_cards_oracle_id ON cards(oracle_id);
    """)
    conn.commit()


async def get_oracle_cards_download_url(client: httpx.AsyncClient) -> str:
    """
    Scryfall's bulk data listing changes its download URL periodically
    (it's a fresh export each time), so this has to be looked up live
    rather than hardcoded. As of the July 2026 format change, only
    jsonl_download_uri is guaranteed to exist - download_uri (the old
    JSON-array format) was retired.
    """
    resp = await client.get(BULK_DATA_INDEX_URL)
    resp.raise_for_status()
    listing = resp.json()

    for entry in listing.get("data", []):
        if entry.get("type") == "oracle_cards":
            url = entry.get("jsonl_download_uri") or entry.get("download_uri")
            if url is None:
                raise RuntimeError(
                    f"oracle_cards entry has neither jsonl_download_uri nor "
                    f"download_uri - Scryfall's bulk-data schema may have "
                    f"changed again. Full entry: {entry}"
                )
            return url

    raise RuntimeError("oracle_cards entry not found in Scryfall bulk-data listing")


def normalize(name: str) -> str:
    """Lowercase and strip a card name for use as a lookup key."""
    return name.strip().lower()


# Scryfall's oracle_cards bulk file includes non-gameplay objects (art-only
# cards, tokens, emblems, etc.) that share a name with a real card but have
# no real type_line (e.g. art series cards have type_line "Card"). Loading
# these can overwrite the real card's cache row if they sort later in the
# file, so they're skipped entirely.
SKIP_LAYOUTS = {
    "art_series", "token", "double_faced_token", "emblem", "vanguard",
    "scheme", "planar", "phenomenon",
}


def add_split_card_aliases(card: dict, batch: list[tuple]) -> None:
    """Append a cache row for a split card's front-face name too, if it differs from the full card name.

    Lets lookups by just the front face (e.g. "Fire" for "Fire // Ice") resolve correctly.
    """
    faces = card.get("card_faces") or []
    if len(faces) < 2:
        return

    front_name = (faces[0] or {}).get("name")
    if not front_name:
        return

    full_name = card.get("name")
    if not full_name or normalize(front_name) == normalize(full_name):
        return

    batch.append((
        normalize(front_name),
        card.get("oracle_id"),
        card.get("type_line"),
        card.get("cmc"),
        card.get("mana_cost"),
        "".join(card.get("color_identity") or []) if (card.get("color_identity") or []) else "C",
        full_name,
        resolve_image_url(card),
        card.get("prices", {}).get("usd"),
    ))


async def build_cache():
    """Download the Scryfall oracle_cards bulk file and rebuild scryfall_cache.sqlite from it."""
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    async with httpx.AsyncClient(timeout=60) as client:
        download_url = await get_oracle_cards_download_url(client)
        print(f"Downloading from {download_url}")

        count = 0
        batch = []
        BATCH_SIZE = 1000

        decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        line_buffer = b""

        def process_line(line: bytes):
            nonlocal count
            if not line.strip():
                return
            card = json.loads(line)
            name = card.get("name")
            if not name:
                return
            if card.get("layout") in SKIP_LAYOUTS:
                return

            # Stored the same way Commander.identity already is - a plain
            # uppercase letter string, with "C" as the colorless sentinel
            # (never an empty string) - so every part of the app represents
            # "no colors" the same way. Scryfall's color_identity field is
            # a list like ["U", "B"]; an empty list means truly colorless.
            colors = card.get("color_identity") or []
            color_identity = "".join(colors) if colors else "C"

            batch.append((
                normalize(name),
                card.get("oracle_id"),
                card.get("type_line"),
                card.get("cmc"),
                card.get("mana_cost"),
                color_identity,
                card.get("name") or name,
                resolve_image_url(card),
                card.get("prices", {}).get("usd"),
            ))
            add_split_card_aliases(card, batch)
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR REPLACE INTO cards (name, oracle_id, type_line, cmc, mana_cost, color_identity, display_name, image_url, usd_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                conn.commit()
                batch.clear()
                print(f"  ...{count} cards processed", end="\r")

        async with client.stream("GET", download_url) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                line_buffer += decompressor.decompress(chunk)
                while b"\n" in line_buffer:
                    line, line_buffer = line_buffer.split(b"\n", 1)
                    process_line(line)

            # Flush any data still buffered in the decompressor, then
            # process whatever's left in line_buffer (the file may not
            # end with a trailing newline).
            line_buffer += decompressor.flush()
            while b"\n" in line_buffer:
                line, line_buffer = line_buffer.split(b"\n", 1)
                process_line(line)
            if line_buffer.strip():
                process_line(line_buffer)

        if batch:
            conn.executemany(
                "INSERT OR REPLACE INTO cards (name, oracle_id, type_line, cmc, mana_cost, color_identity, display_name, image_url, usd_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()

    conn.close()
    print(f"\nDone. Cached {count} cards to {DB_PATH}")


if __name__ == "__main__":
    asyncio.run(build_cache())