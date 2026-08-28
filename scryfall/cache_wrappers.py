import sqlite3


class ScryfallCache:
    KNOWN_SUPERTYPES = {"legendary", "basic", "snow", "world", "ongoing", "elite"}
    TYPE_PRIORITY = [
        "creature", "planeswalker", "battle", "land",
        "instant", "sorcery", "enchantment", "artifact",
    ]
    def __init__(self, db_path: str = "scryfall_cache.sqlite"):
        self.conn = sqlite3.connect(db_path)

    def get_color_identity(self, card_name: str) -> str | None:
        row = self.conn.execute(
            "SELECT color_identity FROM cards WHERE name = ?", (card_name,)
        ).fetchone()
        return row[0] if row else None

    def get_type_line(self, card_name: str) -> str | None:
        row = self.conn.execute(
            "SELECT type_line FROM cards WHERE name = ?", (card_name,)
        ).fetchone()
        return row[0] if row else None
 
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