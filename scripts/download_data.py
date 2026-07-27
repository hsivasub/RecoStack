"""
download_data.py — Phase 2: Data Acquisition

Downloads the MovieLens "ml-latest-small" dataset (100K ratings, 900+ movies)
from the GroupLens research group and unpacks it into data/raw/.
"""

import os
import urllib.request
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
ZIP_PATH = DATA_DIR / "ml-latest-small.zip"
EXTRACTED_DIR = DATA_DIR / "ml-latest-small"


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    if EXTRACTED_DIR.exists():
        print(f"✅ Dataset already extracted at {EXTRACTED_DIR}")
        return

    print(f"⬇️  Downloading MovieLens ml-latest-small from:\n   {URL}")
    urllib.request.urlretrieve(URL, ZIP_PATH)
    print(f"   Saved to {ZIP_PATH}")

    print(f"📦 Extracting to {DATA_DIR} ...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(DATA_DIR)
    ZIP_PATH.unlink()  # remove zip after extraction
    print(f"✅ Extracted to {EXTRACTED_DIR}")

    # List the files
    for f in sorted(EXTRACTED_DIR.iterdir()):
        print(f"   {f.name}")


if __name__ == "__main__":
    main()