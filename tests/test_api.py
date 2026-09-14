from fastapi.testclient import TestClient

import app.main as main
from models.commander import Commander
from models.deck import Deck


class FakeScryfallCache:
    def get_card_display(self, card_name):
        return {
            "name": card_name.lower(),
            "display_name": card_name.title(),
            "image_url": f"https://example.com/{card_name.lower()}.jpg",
            "usd_price": None,
            "tcgplayer_id": None,
        }

    def close(self):
        pass


class PartnerScryfallCache(FakeScryfallCache):
    def get_card_display(self, card_name):
        if " // " in card_name:
            return {
                "name": card_name.lower(),
                "display_name": card_name,
                "image_url": None,
                "usd_price": None,
                "tcgplayer_id": None,
            }
        return super().get_card_display(card_name)


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


def test_commander_analysis_route_accepts_encoded_partner_separator(monkeypatch):
    partner_name = "Alena, Kessig Trapper // Kydele, Chosen of Kruphix"
    monkeypatch.setattr(main, "get_decks", lambda: {})

    with TestClient(main.app) as client:
        response = client.get(f"/api/commanders/{partner_name.replace(' ', '%20').replace('/', '%2F')}")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Commander not found: {partner_name}"


def test_upload_then_clear_manages_collection_state():
    main.clear_uploaded_collection()

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n2,Sol Ring\n1,Arcane Signet\n")},
        )

        assert upload.status_code == 200
        assert upload.json() == {"owned_count": 2, "warnings": []}

        assert client.post("/api/collection/clear").json() == {"status": "success"}
        assert client.get("/api/search").status_code == 400


def test_collections_are_isolated_between_clients(monkeypatch):
    decks = {
        "Alpha": make_deck("Alpha", {"alpha"}),
        "Beta": make_deck("Beta", {"beta"}),
    }
    monkeypatch.setattr(main, "get_decks", lambda: decks)
    monkeypatch.setattr(main, "ScryfallCache", FakeScryfallCache)

    with TestClient(main.app) as first_client, TestClient(main.app) as second_client:
        first_client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n1,Alpha\n")},
        )
        second_client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n1,Beta\n")},
        )

        first_results = first_client.get("/api/search").json()["results"]
        second_results = second_client.get("/api/search").json()["results"]

    assert first_results[0]["commander_name"] == "Alpha"
    assert second_results[0]["commander_name"] == "Beta"


def test_collection_expires_after_session_ttl(monkeypatch):
    current_time = [100.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: current_time[0])

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n1,Sol Ring\n")},
        )
        assert upload.status_code == 200

        current_time[0] += main.SESSION_TTL_SECONDS

        assert client.get("/api/search").status_code == 400


def test_https_session_cookie_allows_cross_site_requests():
    with TestClient(main.app, base_url="https://testserver") as client:
        response = client.get("/health")

    cookie = response.headers["set-cookie"].lower()
    assert "samesite=none" in cookie
    assert "secure" in cookie


def test_forwarded_https_session_cookie_allows_cross_site_requests():
    with TestClient(main.app) as client:
        response = client.get("/health", headers={"x-forwarded-proto": "https"})

    cookie = response.headers["set-cookie"].lower()
    assert "samesite=none" in cookie
    assert "secure" in cookie


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
    decks = {
        "Alpha Mage": make_deck("Alpha Mage", {"shared", "alpha"}, "U"),
        "Alpha Dragon": make_deck("Alpha Dragon", {"shared"}, "R"),
        "Beta Mage": make_deck("Beta Mage", {"shared"}, "U"),
    }
    monkeypatch.setattr(main, "get_decks", lambda: decks)
    monkeypatch.setattr(main, "ScryfallCache", FakeScryfallCache)

    with TestClient(main.app) as client:
        client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n1,Shared\n")},
        )
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


def test_search_uses_first_partner_image_when_pair_has_no_scryfall_record(monkeypatch):
    partner_name = "Alena, Kessig Trapper // Kydele, Chosen of Kruphix"
    monkeypatch.setattr(main, "get_decks", lambda: {
        partner_name: make_deck(partner_name, {"shared"}, "URG"),
    })
    monkeypatch.setattr(main, "ScryfallCache", PartnerScryfallCache)

    with TestClient(main.app) as client:
        client.post(
            "/api/collection/upload",
            files={"file": ("collection.csv", b"Quantity,Name\n1,Shared\n")},
        )
        response = client.get("/api/search")

    assert response.status_code == 200
    assert response.json()["results"][0]["image_url"] == (
        "https://example.com/alena, kessig trapper.jpg"
    )