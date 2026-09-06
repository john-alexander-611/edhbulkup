import json
import os
import tempfile
import urllib.request
from pathlib import Path

REPO = "john-alexander-611/edhbulkup"
RELEASE_TAG = "latest-caches"
TOKEN = os.getenv("GITHUB_TOKEN")

CACHE_FILES = {
    "scryfall_cache.sqlite": Path("scryfall_cache.sqlite"),
    "tag_cache.sqlite": Path("tag_cache.sqlite"),
    "cache.sqlite": Path("cache.sqlite"),
    "commander_data.json": Path("create_cache/commander_data.json"),
}


def get_latest_release() -> dict:
    """Fetch the current cache release metadata from GitHub."""
    api_url = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "edhbulkup-downloader",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(
                f"Release '{RELEASE_TAG}' not found. Ensure the GitHub Action has run and created the release."
            ) from e
        raise
def get_latest_release_id() -> int:
    """Return the GitHub ID for the current cache release."""
    return int(get_latest_release()["id"])


def download_from_github_api(force: bool = False) -> int:
    """Download cache assets from GitHub, replacing local files when force is true."""
    data = get_latest_release()

    assets = {asset["name"]: asset["url"] for asset in data.get("assets", [])}

    for filename, path in CACHE_FILES.items():
        if path.exists() and not force:
            print(f"{filename} already present.")
            continue

        asset_url = assets.get(filename)
        if not asset_url:
            print(f"Warning: {filename} not found in release assets.")
            continue

        print(f"Downloading {filename}...")
        download_headers = {
            "Accept": "application/octet-stream",
            "User-Agent": "edhbulkup-downloader",
        }
        if TOKEN:
            download_headers["Authorization"] = f"Bearer {TOKEN}"

        download_req = urllib.request.Request(asset_url, headers=download_headers)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with urllib.request.urlopen(download_req) as resp, tempfile.NamedTemporaryFile(
                mode="wb", delete=False, dir=path.parent, prefix=f"{path.name}.", suffix=".download"
            ) as out_file:
                temporary_path = Path(out_file.name)
                while chunk := resp.read(1024 * 1024):
                    out_file.write(chunk)
            temporary_path.replace(path)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

        print(f"Downloaded {filename} ({path.stat().st_size / (1024*1024):.1f} MB)")
    return int(data["id"])


def ensure_caches(force: bool = False) -> int:
    """Download cache files from the GitHub release and return its ID."""
    return download_from_github_api(force=force)


if __name__ == "__main__":
    ensure_caches()
