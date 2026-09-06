from fastapi.testclient import TestClient

import app.main as main
from models.collection import Collection
from models.commander import Commander
from models.deck import Deck


class FakeScryfallCache:
    def get_card_display(self, card_name):
        return {
            "name": card_name.lower(),
            "display_name": card_name.title(),
            "image_url": f"https://example.com/{card_name.lower()}.jpg",
            "usd_price": None,
        }

    def close(self):
        pass


def make_deck(name, cards, identity="BR"):
    return Deck(Commander(name, identity), frozenset(cards))


def test_health_reports_ok():
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_search_requires_an_uploaded_collection():
    main.clear_uploaded_collection()

    with TestClient(main.app) as client:
        response = client.get("/api/search")

    assert response.status_code == 400
    assert response.json()["detail"] == "Upload a collection CSV before searching or analyzing commanders."


def test_upload_then_clear_manages_collection_state():
    main.clear_uploaded_collection()

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n2,Sol Ring\n1,Arcane Signet\n")},
        )

        assert upload.status_code == 200
        assert upload.json() == {"owned_count": 2, "warnings": []}
        assert main.app.state.collection.quantity("sol ring") == 2
        assert main.app.state.collection.quantity("arcane signet") == 1

        assert client.post("/api/collection/clear").json() == {"status": "success"}
        assert client.get("/api/search").status_code == 400


def test_upload_reports_warnings_for_skipped_rows():
    main.clear_uploaded_collection()

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n2,Sol Ring\n,\n1,Arcane Signet\n")},
        )

    assert upload.status_code == 200
    body = upload.json()
    assert body["owned_count"] == 2
    assert len(body["warnings"]) == 1
    assert "1 row(s)" in body["warnings"][0]


def test_upload_rejects_file_with_no_parseable_rows():
    main.clear_uploaded_collection()

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/collection/upload",
            files={"file": ("collection.txt", b"not a valid line\nanother bad one\n")},
        )

    assert upload.status_code == 400
    assert "collection.txt" in upload.json()["detail"]


def test_upload_rejects_csv_with_wrong_columns():
    main.clear_uploaded_collection()

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Foo,Bar\n1,Sol Ring\n")},
        )

    assert upload.status_code == 400
    assert "missing a name column" in upload.json()["detail"]


def test_search_applies_filters_pagination_and_commander_presentation(monkeypatch):
    main.app.state.collection = Collection({"shared": 1})
    decks = {
        "Alpha Mage": make_deck("Alpha Mage", {"shared", "alpha"}, "U"),
        "Alpha Dragon": make_deck("Alpha Dragon", {"shared"}, "R"),
        "Beta Mage": make_deck("Beta Mage", {"shared"}, "U"),
    }
    monkeypatch.setattr(main, "get_decks", lambda: decks)
    monkeypatch.setattr(main, "ScryfallCache", FakeScryfallCache)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/search",
            params={"name": "alpha", "limit": 1, "offset": 1},
        )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "commander_name": "Alpha Mage",
                "identity": "U",
                "match_score": 0.5,
                "match_percentage": 50.0,
                "owned_count": 1,
                "deck_size": 2,
                "image_url": "https://example.com/alpha mage.jpg",
            }
        ],
        "total": 2,
    }