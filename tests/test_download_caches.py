import json

import download_caches


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.content) - self.offset
        chunk = self.content[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


def test_ensure_caches_only_replaces_existing_files_when_forced(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        download_caches,
        "CACHE_FILES",
        {
            "scryfall_cache.sqlite": tmp_path / "scryfall_cache.sqlite",
            "commander_data.json": tmp_path / "create_cache" / "commander_data.json",
        },
    )
    sqlite_path = tmp_path / "scryfall_cache.sqlite"
    json_path = tmp_path / "create_cache" / "commander_data.json"
    sqlite_path.write_bytes(b"old sqlite")
    json_path.parent.mkdir()
    json_path.write_bytes(b"old json")

    release = json.dumps(
        {
            "id": 42,
            "assets": [
                {"name": "scryfall_cache.sqlite", "url": "https://assets/sqlite"},
                {"name": "commander_data.json", "url": "https://assets/json"},
            ],
        }
    ).encode()
    contents = {
        "https://assets/sqlite": b"new sqlite",
        "https://assets/json": b"new json",
    }

    def fake_urlopen(request):
        url = request.full_url
        return FakeResponse(release if "api.github.com" in url else contents[url])

    monkeypatch.setattr(download_caches.urllib.request, "urlopen", fake_urlopen)

    assert download_caches.ensure_caches() == 42
    assert sqlite_path.read_bytes() == b"old sqlite"
    assert json_path.read_bytes() == b"old json"

    assert download_caches.ensure_caches(force=True) == 42
    assert sqlite_path.read_bytes() == b"new sqlite"
    assert json_path.read_bytes() == b"new json"