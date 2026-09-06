import re
import sqlite3
from collections.abc import Iterable


class ScryfallCache:
    """Read-only lookup wrapper around the local Scryfall SQLite cache (scryfall_cache.sqlite)."""

    KNOWN_SUPERTYPES = {"legendary", "basic", "snow", "world", "ongoing", "elite"}
    TYPE_PRIORITY = [
        "creature", "planeswalker", "battle", "land",
        "instant", "sorcery", "enchantment", "artifact",
    ]
    def __init__(self, db_path: str = "scryfall_cache.sqlite"):
        """Open (and create if needed) the cache database at db_path."""
        self.conn = sqlite3.connect(db_path)
        self._ensure_schema()

    @staticmethod
    def normalize_name(card_name: str) -> str:
        """Lowercase and strip a card name for use as a lookup key."""
        return card_name.strip().lower()

    @staticmethod
    def format_display_name(name: str) -> str:
        """Title-case an all-lowercase card name for display, preserving small words (e.g. "of", "the") lowercase mid-title.

        Returns name unchanged if it already has any uppercase letters.
        """
        text = (name or "").strip()
        if not text:
            return text
        if any(ch.isupper() for ch in text):
            return text

        small_words = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "nor", "of", "on", "or", "the", "to", "vs", "via", "with"}
        words = re.split(r"(\s+)", text)
        formatted = []
        for index, token in enumerate(words):
            if not token or token.isspace():
                formatted.append(token)
                continue
            if token in {"//", "—"}:
                formatted.append(token)
                continue
            lowered = token.lower()
            if lowered in small_words and index not in (0, len(words) - 1):
                formatted.append(lowered)
            else:
                formatted.append(lowered[:1].upper() + lowered[1:])
        return "".join(formatted)

    def _ensure_schema(self) -> None:
        """Create the cards table if missing and add any newer columns to an existing table."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                name TEXT PRIMARY KEY,
                oracle_id TEXT,
                type_line TEXT,
                cmc REAL,
                mana_cost TEXT,
                color_identity TEXT,
                display_name TEXT,
                image_url TEXT
            )
            """
        )
        columns = {
            row[1].lower(): row[1]
            for row in self.conn.execute("PRAGMA table_info(cards)").fetchall()
        }
        for column, definition in (("display_name", "TEXT"), ("image_url", "TEXT"), ("usd_price", "REAL"), ("tcgplayer_id", "INTEGER")):
            if column not in columns:
                self.conn.execute(
                    f"ALTER TABLE cards ADD COLUMN {column} {definition}"
                )
        self.conn.commit()

    def get_color_identity(self, card_name: str) -> str | None:
        """Cached color identity for card_name (e.g. "WU"), or None if not cached."""
        normalized = self.normalize_name(card_name)
        row = self.conn.execute(
            "SELECT color_identity FROM cards WHERE name = ?", (normalized,)
        ).fetchone()
        return row[0] if row else None

    def get_type_line(self, card_name: str) -> str | None:
        """Cached Scryfall type_line for card_name, or None if not cached.

        Falls back to a front-face prefix match for double-faced/split cards.
        """
        normalized = self.normalize_name(card_name)
        row = self.conn.execute(
            "SELECT type_line FROM cards WHERE name = ?", (normalized,)
        ).fetchone()
        if row is None:
            row = self.conn.execute(
                "SELECT type_line FROM cards WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1",
                (f"{normalized} // %",),
            ).fetchone()
        return row[0] if row else None

    def _lookup_row(self, card_name: str):
        """Find the cards row for card_name, falling back to a front-face prefix match for split/DFC cards."""
        normalized = self.normalize_name(card_name)
        row = self.conn.execute(
            "SELECT name, display_name, image_url, usd_price, tcgplayer_id FROM cards WHERE name = ?",
            (normalized,),
        ).fetchone()
        if row is not None:
            return row

        for pattern in (f"{normalized} // %",):
            row = self.conn.execute(
                "SELECT name, display_name, image_url, usd_price, tcgplayer_id FROM cards WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1",
                (pattern,),
            ).fetchone()
            if row is not None:
                return row

        return None

    def get_display_name(self, card_name: str) -> str | None:
        """Cached or reformatted human-readable display name for card_name."""
        normalized = self.normalize_name(card_name)
        row = self._lookup_row(card_name)
        if row and row[1]:
            display_name = row[1]
            if display_name.lower() == display_name:
                return self.format_display_name(display_name)
            return display_name
        return self.format_display_name(card_name.strip() or normalized)

    def get_image_url(self, card_name: str) -> str | None:
        """Cached Scryfall image URL for card_name, or None if not cached."""
        row = self._lookup_row(card_name)
        return row[2] if row else None

    def get_card_display(self, card_name: str) -> dict[str, str | None]:
        """Presentation data for one card.

        Returns:
            dict[str, str | None]: Keys "name", "display_name", "image_url", "usd_price",
                "tcgplayer_id"; falls back to a formatted name with None metadata if uncached.
        """
        normalized = self.normalize_name(card_name)
        row = self._lookup_row(card_name)
        if row is None:
            display_name = self.format_display_name(card_name.strip() or normalized)
            return {
                "name": normalized,
                "display_name": display_name,
                "image_url": None,
                "usd_price": None,
                "tcgplayer_id": None,
            }
        display_name = row[1] or (card_name.strip() or normalized)
        if display_name.lower() == display_name:
            display_name = self.format_display_name(display_name)
        return {
            "name": normalized,
            "display_name": display_name,
            "image_url": row[2],
            "usd_price": row[3],
            "tcgplayer_id": row[4],
        }

    def get_many_card_displays(self, card_names: Iterable[str]) -> dict[str, dict[str, str | None]]:
        """Batch version of get_card_display, keyed by normalized card name."""
        normalized_names = [self.normalize_name(name) for name in card_names if name and name.strip()]
        if not normalized_names:
            return {}
        placeholders = ", ".join("?" for _ in normalized_names)
        rows = self.conn.execute(
            f"SELECT name, display_name, image_url, usd_price, tcgplayer_id FROM cards WHERE name IN ({placeholders})",
            normalized_names,
        ).fetchall()
        resolved = {name: self.get_card_display(name) for name in normalized_names}
        for name, display_name, image_url, usd_price, tcgplayer_id in rows:
            final_display_name = display_name or self.normalize_name(name)
            if final_display_name.lower() == final_display_name:
                final_display_name = self.format_display_name(final_display_name)
            resolved[name] = {
                "name": name,
                "display_name": final_display_name,
                "image_url": image_url,
                "usd_price": usd_price,
                "tcgplayer_id": tcgplayer_id,
            }
        return resolved

    def get_primary_card_type(self, type_line: str) -> str | None:
        """Extract the primary type (e.g. "creature") from a full type_line (e.g. "Legendary Creature — Minotaur Wizard").

        Only the front face is used for split/DFC cards. TYPE_PRIORITY breaks
        ties for multi-type lines (e.g. "Artifact Creature" -> "creature").

        Returns:
            str | None: Lowercased primary type, or None if type_line is empty or unrecognized.
        """
        if not type_line:
            return None

        front = type_line.split(" // ")[0]
        # Scryfall uses an em dash (—) before subtypes, not a hyphen
        type_part = front.split("—")[0]
        words = {w.lower() for w in type_part.split()}
        words -= self.KNOWN_SUPERTYPES

        for candidate in self.TYPE_PRIORITY:
            if candidate in words:
                return candidate
        return None


    def close(self):
        """Close the underlying database connection."""
        self.conn.close()


class TagCache:
    """Read-only lookup wrapper around the local functional-tag SQLite cache (tag_cache.sqlite)."""

    def __init__(self, db_path: str = "tag_cache.sqlite"):
        """Open the tag cache database at db_path."""
        self.conn = sqlite3.connect(db_path)

    def get_tags(self, card_name: str) -> list[str]:
        """All functional tags associated with card_name."""
        rows = self.conn.execute(
            "SELECT tag FROM card_tags WHERE card_name = ?", (card_name,)
        ).fetchall()
        return [row[0] for row in rows]

    def get_cards_with_tag(self, tag: str) -> set[str]:
        """All card names associated with tag."""
        rows = self.conn.execute(
            "SELECT card_name FROM card_tags WHERE tag = ?", (tag,)
        ).fetchall()
        return {row[0] for row in rows}

    def close(self):
        """Close the underlying database connection."""
        self.conn.close()