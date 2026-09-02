import json
import os
import urllib.request
from pathlib import Path

REPO = "john-alexander-611/edhbulkup"
RELEASE_TAG = "latest-caches"
TOKEN = os.getenv("GITHUB_TOKEN")

CACHE_FILES = [
    "scryfall_cache.sqlite",
    "tag_cache.sqlite",
    "cache.sqlite",
]


def download_from_github_api():
    """Fetch release asset URLs via the GitHub API and download them with auth."""
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
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(
                f"Release '{RELEASE_TAG}' not found. Ensure the GitHub Action has run and created the release."
            ) from e
        raise

    assets = {asset["name"]: asset["url"] for asset in data.get("assets", [])}

    for filename in CACHE_FILES:
        path = Path(filename)
        if path.exists():
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
        with urllib.request.urlopen(download_req) as resp, open(path, "wb") as out_file:
            while chunk := resp.read(1024 * 1024):
                out_file.write(chunk)

        print(f"Downloaded {filename} ({path.stat().st_size / (1024*1024):.1f} MB)")


def ensure_caches():
    download_from_github_api()


if __name__ == "__main__":
    ensure_caches()
