import sqlite3


class ScryfallCache:
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