import sqlite3

from app.schemas import DeckAnalysisResponse
from scryfall.cache_wrappers import ScryfallCache


def test_scryfall_cache_adds_display_name_and_image_url_for_legacy_schema(tmp_path):
    db_path = tmp_path / "legacy_scryfall.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cards (name TEXT PRIMARY KEY, color_identity TEXT)"
    )
    conn.execute(
        "INSERT INTO cards (name, color_identity) VALUES (?, ?)",
        ("lightning bolt", "R"),
    )
    conn.commit()
    conn.close()

    cache = ScryfallCache(str(db_path))
    cache.conn.execute(
        "UPDATE cards SET display_name = ?, image_url = ?, usd_price = ?, tcgplayer_id = ? WHERE name = ?",
        ("Lightning Bolt", "https://example.com/lightning-bolt.jpg", 1.25, 12345, "lightning bolt"),
    )
    cache.conn.commit()

    assert cache.get_color_identity("Lightning Bolt") == "R"
    assert cache.get_display_name("Lightning Bolt") == "Lightning Bolt"
    assert cache.get_image_url("Lightning Bolt") == "https://example.com/lightning-bolt.jpg"
    assert cache.get_card_display("Lightning Bolt") == {
        "name": "lightning bolt",
        "display_name": "Lightning Bolt",
        "image_url": "https://example.com/lightning-bolt.jpg",
        "usd_price": 1.25,
        "tcgplayer_id": 12345,
    }
    assert cache.get_card_display("darkbore pathway") == {
        "name": "darkbore pathway",
        "display_name": "Darkbore Pathway",
        "image_url": None,
        "usd_price": None,
        "tcgplayer_id": None,
    }
    assert cache.get_many_card_displays(["Lightning Bolt", "darkbore pathway"]) == {
        "lightning bolt": {
            "name": "lightning bolt",
            "display_name": "Lightning Bolt",
            "image_url": "https://example.com/lightning-bolt.jpg",
            "usd_price": 1.25,
            "tcgplayer_id": 12345,
        },
        "darkbore pathway": {
            "name": "darkbore pathway",
            "display_name": "Darkbore Pathway",
            "image_url": None,
            "usd_price": None,
            "tcgplayer_id": None,
        },
    }

    cache.conn.execute(
        "INSERT INTO cards (name, display_name, image_url) VALUES (?, ?, ?)",
        (
            "darkbore pathway // slitherbore pathway",
            "Darkbore Pathway // Slitherbore Pathway",
            "https://scryfall.com/card/khm/254/darkbore-pathway-slitherbore-pathway",
        ),
    )
    cache.conn.commit()

    assert cache.get_card_display("darkbore pathway") == {
        "name": "darkbore pathway",
        "display_name": "Darkbore Pathway // Slitherbore Pathway",
        "image_url": "https://scryfall.com/card/khm/254/darkbore-pathway-slitherbore-pathway",
        "usd_price": None,
        "tcgplayer_id": None,
    }

    cache.close()


def test_deck_analysis_response_includes_commander_image_url():
    response = DeckAnalysisResponse(
        commander_name="The Gitrogue",
        identity="UG",
        match_score=95.0,
        match_percentage=95.0,
        owned_count=2,
        missing_count=4,
        missing_cards=["Forest", "Island"],
        missing_by_tag={},
        image_url="https://example.com/the-gitrogue.jpg",
    )

    assert response.image_url == "https://example.com/the-gitrogue.jpg"
