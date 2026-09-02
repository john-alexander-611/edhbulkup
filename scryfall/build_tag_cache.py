"""
Caches which owned-collection-relevant cards carry which functional oracle
tags (removal, ramp, card-advantage, etc), sourced entirely from Scryfall's
oracle_tags bulk file rather than live otag: search.

Live search was the original approach, but broad tags like "removal"
(2000+ cards, many pages) hit Scryfall's rate limit mid-run - and
Scryfall's own error message for that points directly at bulk data as the
correct approach for "a large amount of card data". This also reuses the
subtree-reach logic from explore_oracle_tags.py: since we're resolving
tags ourselves now instead of letting Scryfall's search engine roll up
child tags server-side, we have to do that rollup manually (e.g. removal's
real cards mostly live on removal-creature, repeatable-removal, etc, not
on removal directly).

Requires scryfall_cache.sqlite to already exist (build_scryfall_cache.py)
with its oracle_id column, since tag taggings reference cards by
oracle_id, not name - this is how we resolve one to the other locally.

Run:
    python build_scryfall_cache.py    # if not already run
    python build_tag_cache.py
"""

import asyncio
import json
import sqlite3
import sys
import zlib

import httpx

DB_PATH = "tag_cache.sqlite"
SCRYFALL_DB_PATH = "scryfall_cache.sqlite"
BULK_DATA_INDEX_URL = "https://api.scryfall.com/bulk-data"

# The parent/root slug for each category - live search used to roll up
# all descendant tags automatically; now we do that ourselves via
# compute_subtree_reach, so only the root slug needs to be listed here.
TAG_CATEGORIES = [
    "ramp",
    "removal",
    "card-advantage",
    "hate",
    "burn",
    "lifegain",
    "death-trigger",
    "recursion",
]


def init_db(conn: sqlite3.Connection):
    """Drop and recreate the card_tags table."""
    conn.executescript("""
        DROP TABLE IF EXISTS card_tags;

        CREATE TABLE card_tags (
            card_name TEXT NOT NULL,
            tag TEXT NOT NULL
        );
        CREATE INDEX idx_card_tags_name ON card_tags(card_name);
        CREATE INDEX idx_card_tags_tag ON card_tags(tag);
    """)
    conn.commit()


async def get_oracle_tags_url(client: httpx.AsyncClient) -> str:
    """Look up the current download URL for Scryfall's oracle_tags bulk file.

    Raises:
        RuntimeError: If no oracle_tags entry is found in the bulk-data listing.
    """
    resp = await client.get(BULK_DATA_INDEX_URL)
    resp.raise_for_status()
    for entry in resp.json().get("data", []):
        if entry.get("type") == "oracle_tags":
            return entry["jsonl_download_uri"]
    raise RuntimeError("oracle_tags entry not found")


async def download_all_tags(client: httpx.AsyncClient, url: str) -> list[dict]:
    """Stream and decompress the gzipped JSONL oracle_tags file into a list of tag dicts."""
    entries = []
    decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
    line_buffer = b""

    def process_line(line: bytes):
        if line.strip():
            entries.append(json.loads(line))

    async with client.stream("GET", url) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes():
            line_buffer += decompressor.decompress(chunk)
            while b"\n" in line_buffer:
                line, line_buffer = line_buffer.split(b"\n", 1)
                process_line(line)
        line_buffer += decompressor.flush()
        while b"\n" in line_buffer:
            line, line_buffer = line_buffer.split(b"\n", 1)
            process_line(line)
        if line_buffer.strip():
            process_line(line_buffer)

    return entries


def compute_subtree_reach(tags_by_id: dict[str, dict]) -> dict[str, set[str]]:
    """Same logic as explore_oracle_tags.py, tested there against a
    synthetic graph matching removal/removal-creature's real shape."""
    sys.setrecursionlimit(10000)
    reach_cache: dict[str, set[str]] = {}
    in_progress: set[str] = set()

    def reach(tag_id: str) -> set[str]:
        if tag_id in reach_cache:
            return reach_cache[tag_id]
        if tag_id in in_progress:
            return set()
        if tag_id not in tags_by_id:
            return set()

        in_progress.add(tag_id)
        tag = tags_by_id[tag_id]

        own_ids = {t["oracle_id"] for t in (tag.get("taggings") or []) if t.get("oracle_id")}
        combined = set(own_ids)
        for child_id in tag.get("child_ids") or []:
            combined |= reach(child_id)

        in_progress.discard(tag_id)
        reach_cache[tag_id] = combined
        return combined

    for tag_id in tags_by_id:
        reach(tag_id)

    return reach_cache


def build_oracle_id_to_name(scryfall_conn: sqlite3.Connection) -> dict[str, str]:
    """Build an oracle_id-to-card-name mapping from the Scryfall cache, used to resolve tag taggings to names."""
    rows = scryfall_conn.execute(
        "SELECT oracle_id, name FROM cards WHERE oracle_id IS NOT NULL"
    ).fetchall()
    return {oracle_id: name for oracle_id, name in rows}


async def build_cache():
    """Download Scryfall's oracle_tags bulk file and rebuild tag_cache.sqlite from it, for each tag in TAG_CATEGORIES."""
    scryfall_conn = sqlite3.connect(SCRYFALL_DB_PATH)
    oracle_id_to_name = build_oracle_id_to_name(scryfall_conn)
    scryfall_conn.close()
    print(f"Loaded {len(oracle_id_to_name)} oracle_id -> name mappings from {SCRYFALL_DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    async with httpx.AsyncClient(timeout=60) as client:
        url = await get_oracle_tags_url(client)
        print(f"Downloading oracle_tags from {url}")
        entries = await download_all_tags(client, url)

    print(f"Downloaded {len(entries)} tags, computing subtree reach...")
    tags_by_id = {e["id"]: e for e in entries if e.get("id")}
    slug_to_id = {t["slug"]: tid for tid, t in tags_by_id.items() if t.get("slug")}
    reach_by_id = compute_subtree_reach(tags_by_id)

    for slug in TAG_CATEGORIES:
        tag_id = slug_to_id.get(slug)
        if tag_id is None:
            print(f"  ! tag slug {slug!r} not found in oracle_tags - skipping")
            continue

        oracle_ids = reach_by_id.get(tag_id, set())
        card_names = {oracle_id_to_name[oid] for oid in oracle_ids if oid in oracle_id_to_name}
        missing = len(oracle_ids) - len(card_names)

        print(f"otag:{slug} -> {len(oracle_ids)} cards in subtree, {len(card_names)} resolved to names"
              + (f" ({missing} oracle_ids not found in {SCRYFALL_DB_PATH})" if missing else ""))

        conn.executemany(
            "INSERT INTO card_tags (card_name, tag) VALUES (?, ?)",
            [(name, slug) for name in card_names],
        )
        conn.commit()

    conn.close()
    print(f"\nDone. Cache written to {DB_PATH}")


if __name__ == "__main__":
    asyncio.run(build_cache())