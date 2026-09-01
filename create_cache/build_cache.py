"""
Builds the local commander/average-decklist cache used by the matching engine.

Run:
    pip install httpx python-slugify
    python build_cache.py

Produces cache.sqlite with two tables:
    commanders(name, identity, num_decks)
    decklist_cards(commander, card_name)
"""

import asyncio
import sqlite3
from pathlib import Path

import httpx

from edhrec_raw import COLOR_IDENTITIES, fetch_average_deck, fetch_commanders_by_identity, normalize_identity
from create_commander_json import create_commander_json

# Resolved relative to this file, not the caller's cwd, so the cache always
# lands in the repo root regardless of where `python build_cache.py` is run from.
DB_PATH = str(Path(__file__).parent.parent / "cache.sqlite")

# Skip commanders with fewer decks than this - keeps the cache focused on
# commanders popular enough to be worth matching against, and avoids
# spending calls on obscure one-off pages.
MIN_DECKS = 20

CONCURRENCY = 5


def init_db(conn: sqlite3.Connection):
    # Drop and recreate on every run - build_cache.py is meant to be re-run
    # (weekly refresh, or after a bug fix like this one), and without this
    # old rows just accumulate underneath the new ones.
    conn.executescript("""
        DROP TABLE IF EXISTS decklist_cards;
        DROP TABLE IF EXISTS commanders;

        CREATE TABLE commanders (
            name TEXT PRIMARY KEY,
            identity TEXT NOT NULL,
            num_decks INTEGER
        );
        CREATE TABLE decklist_cards (
            commander TEXT NOT NULL,
            card_name TEXT NOT NULL,
            FOREIGN KEY (commander) REFERENCES commanders(name)
        );
        CREATE INDEX idx_decklist_commander
            ON decklist_cards(commander);
    """)
    conn.commit()


async def gather_commanders(client: httpx.AsyncClient) -> dict[str, dict]:
    """Enumerate commanders across all 32 color identities, deduped by name."""
    commanders: dict[str, dict] = {}

    for identity in COLOR_IDENTITIES:
        results = await fetch_commanders_by_identity(client, identity)
        for entry in results:
            name = entry["name"]
            num_decks = entry.get("num_decks") or 0
            if name not in commanders or num_decks > commanders[name]["num_decks"]:
                commanders[name] = {"identity": identity, "num_decks": num_decks}

    return commanders


async def fetch_decklist_worker(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    conn: sqlite3.Connection,
    name: str,
):
    async with sem:
        cards = await fetch_average_deck(client, name)

    if not cards:
        print(f"  ! no average deck data for {name}")
        return

    normalized = [c.strip().lower() for c in cards]
    conn.executemany(
        "INSERT INTO decklist_cards (commander, card_name) VALUES (?, ?)",
        [(name, c) for c in normalized],
    )
    conn.commit()
    print(f"  cached {name}: {len(normalized)} cards")


async def main():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    async with httpx.AsyncClient(timeout=20) as client:
        commanders = await gather_commanders(client)
        print(f"\nFound {len(commanders)} unique commanders")

        eligible = {
            name: meta
            for name, meta in commanders.items()
            if meta["num_decks"] >= MIN_DECKS
        }
        print(f"{len(eligible)} commanders meet the {MIN_DECKS}-deck threshold\n")

        for name, meta in eligible.items():
            identity = normalize_identity(meta["identity"])
            conn.execute(
                "INSERT OR REPLACE INTO commanders (name, identity, num_decks) VALUES (?, ?, ?)",
                (name, identity, meta["num_decks"]),
            )
        conn.commit()

        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [
            fetch_decklist_worker(client, sem, conn, name)
            for name in eligible
        ]
        await asyncio.gather(*tasks)


    conn.close()
    create_commander_json()
    print("\nDone. Cache written to", DB_PATH)


if __name__ == "__main__":
    asyncio.run(main())