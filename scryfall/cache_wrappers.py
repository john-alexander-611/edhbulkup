import re
import sqlite3
from collections.abc import Iterable


class ScryfallCache:
    KNOWN_SUPERTYPES = {"legendary", "basic", "snow", "world", "ongoing", "elite"}
    TYPE_PRIORITY = [
        "creature", "planeswalker", "battle", "land",
        "instant", "sorcery", "enchantment", "artifact",
    ]
    def __init__(self, db_path: str = "scryfall_cache.sqlite"):
        self.conn = sqlite3.connect(db_path)
        self._ensure_schema()

    @staticmethod
    def normalize_name(card_name: str) -> str:
        return card_name.strip().lower()

    @staticmethod
    def format_display_name(name: str) -> str:
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
        for column in ("display_name", "image_url"):
            if column not in columns:
                self.conn.execute(
                    f"ALTER TABLE cards ADD COLUMN {column} TEXT"
                )
        self.conn.commit()

    def get_color_identity(self, card_name: str) -> str | None:
        normalized = self.normalize_name(card_name)
        row = self.conn.execute(
            "SELECT color_identity FROM cards WHERE name = ?", (normalized,)
        ).fetchone()
        return row[0] if row else None

    def get_type_line(self, card_name: str) -> str | None:
        normalized = self.normalize_name(card_name)
        row = self.conn.execute(
            "SELECT type_line FROM cards WHERE name = ?", (normalized,)
        ).fetchone()
        return row[0] if row else None

    def _lookup_row(self, card_name: str):
        normalized = self.normalize_name(card_name)
        row = self.conn.execute(
            "SELECT name, display_name, image_url FROM cards WHERE name = ?",
            (normalized,),
        ).fetchone()
        if row is not None:
            return row

        for pattern in (f"{normalized} // %",):
            row = self.conn.execute(
                "SELECT name, display_name, image_url FROM cards WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1",
                (pattern,),
            ).fetchone()
            if row is not None:
                return row

        return None

    def get_display_name(self, card_name: str) -> str | None:
        normalized = self.normalize_name(card_name)
        row = self._lookup_row(card_name)
        if row and row[1]:
            display_name = row[1]
            if display_name.lower() == display_name:
                return self.format_display_name(display_name)
            return display_name
        return self.format_display_name(card_name.strip() or normalized)

    def get_image_url(self, card_name: str) -> str | None:
        row = self._lookup_row(card_name)
        return row[2] if row else None

    def get_card_display(self, card_name: str) -> dict[str, str | None]:
        normalized = self.normalize_name(card_name)
        row = self._lookup_row(card_name)
        if row is None:
            display_name = self.format_display_name(card_name.strip() or normalized)
            return {
                "name": normalized,
                "display_name": display_name,
                "image_url": None,
            }
        display_name = row[1] or (card_name.strip() or normalized)
        if display_name.lower() == display_name:
            display_name = self.format_display_name(display_name)
        return {
            "name": normalized,
            "display_name": display_name,
            "image_url": row[2],
        }

    def get_many_card_displays(self, card_names: Iterable[str]) -> dict[str, dict[str, str | None]]:
        normalized_names = [self.normalize_name(name) for name in card_names if name and name.strip()]
        if not normalized_names:
            return {}
        placeholders = ", ".join("?" for _ in normalized_names)
        rows = self.conn.execute(
            f"SELECT name, display_name, image_url FROM cards WHERE name IN ({placeholders})",
            normalized_names,
        ).fetchall()
        resolved = {name: self.get_card_display(name) for name in normalized_names}
        for name, display_name, image_url in rows:
            final_display_name = display_name or self.normalize_name(name)
            if final_display_name.lower() == final_display_name:
                final_display_name = self.format_display_name(final_display_name)
            resolved[name] = {
                "name": name,
                "display_name": final_display_name,
                "image_url": image_url,
            }
        return resolved
 
    # Priority order used when a card has multiple types on one line (e.g.
    # "Artifact Creature — Golem"). Creature-ness takes priority over
    # artifact-ness for matching purposes - a mana rock and a creature don't
    # fill the same deck slot even though both are technically "Artifact".
    # This is a judgment call, not a Scryfall-defined ordering.
 
    def get_primary_card_type(self, type_line: str) -> str | None:
        """
        Extracts just the primary type (e.g. "creature") from a full Scryfall
        type_line (e.g. "Legendary Creature — Minotaur Wizard"), which is what
        TYPE_TO_CATEGORIES actually needs to key off of.
 
        For double-faced/split cards, type_line combines both faces separated
        by " // " - only the front face is used, matching the front-face
        naming convention already used for card names elsewhere.
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
        self.conn.close()


class TagCache:
    def __init__(self, db_path: str = "tag_cache.sqlite"):
        self.conn = sqlite3.connect(db_path)

    def get_tags(self, card_name: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT tag FROM card_tags WHERE card_name = ?", (card_name,)
        ).fetchall()
        return [row[0] for row in rows]

    def get_cards_with_tag(self, tag: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT card_name FROM card_tags WHERE tag = ?", (tag,)
        ).fetchall()
        return {row[0] for row in rows}

    def close(self):
        self.conn.close()