import os
import urllib.request
from pathlib import Path

REPO = "john-alexander-611/edhbulkup"
RELEASE_TAG = "latest-caches"
BASE_URL = f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}"
TOKEN = os.getenv("GITHUB_TOKEN")

CACHE_FILES = [
    "scryfall_cache.sqlite",
    "tag_cache.sqlite",
    "cache.sqlite",
]

def ensure_caches():
    for filename in CACHE_FILES:
        path = Path(filename)
        if not path.exists():
            print(f"Downloading {filename}...")
            url = f"{BASE_URL}/{filename}"
            urllib.request.urlretrieve(url, path)
            print(f"Downloaded {filename} ({path.stat().st_size / (1024*1024):.1f} MB)")
        else:
            print(f"{filename} already present.")

if __name__ == "__main__":
    ensure_caches()