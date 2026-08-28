"""
Caches which cards carry which functional oracle tags (removal, ramp,
card-advantage, etc), via one otag: search per category - not one search
per card. Reuses the same scrython pattern already used in
get_face_commanders().

Tag slugs aren't guaranteed permanent (Scryfall's own docs warn Tagger
data can be renamed/reorganized by the community), so this is meant to be
re-run periodically, same cadence as the EDHREC and bulk-card caches -
not treated as a one-time hardcode.

Run:
    python build_tag_cache.py
"""

import sqlite3

import scrython

DB_PATH = "tag_cache.sqlite"

# Confirmed real via EDHREC's own Scryfall-syntax guide, which explicitly
# names these three as the staple categories to check before finishing a
# deck. Add more once you've verified them the same way (search
# "scryfall otag <name>" or run the query on scryfall.com directly and
# confirm it returns real results before trusting it here).
TAG_CATEGORIES = [
    "ramp",
    "removal",
    "card-advantage",
]


def init_db(conn: sqlite3.Connection):
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


def normalize(name: str) -> str:
    return name.strip().lower()


def fetch_all_cards_for_tag(tag: str) -> list[str]:
    """
    Returns every card name tagged with the given otag.

    Uses scrython's iter_all() generator, which internally follows
    next_page until has_more is false - confirmed by reading scrython's
    installed source directly (scrython/base_mixins.py), not guessed.
    has_more and data are properties there, not callable methods.
    """
    result = scrython.cards.Search(q=f"otag:{tag}")
    return [card.name for card in result.iter_all()]


def build_cache():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    for tag in TAG_CATEGORIES:
        print(f"Fetching otag:{tag} ...")
        names = fetch_all_cards_for_tag(tag)
        print(f"  {len(names)} cards tagged '{tag}'")

        conn.executemany(
            "INSERT INTO card_tags (card_name, tag) VALUES (?, ?)",
            [(normalize(name), tag) for name in names],
        )
        conn.commit()

    conn.close()
    print(f"\nDone. Cache written to {DB_PATH}")


if __name__ == "__main__":
    build_cache()