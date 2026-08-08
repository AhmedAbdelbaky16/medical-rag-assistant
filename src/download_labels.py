"""
Phase 1a — Download drug labels from the DailyMed API.

For each drug name in config.DRUG_LIST:
  1. Search DailyMed by name -> get a `setid` (DailyMed's unique ID per label)
  2. Download the full SPL (Structured Product Labeling) XML for that setid
  3. Save it to data/raw/<drug_name>.xml

Run this once. Re-running skips drugs already downloaded (safe to re-run
after adding new drugs to the list).
"""

import time
import logging

import requests

from config import DRUG_LIST, RAW_DIR, DAILYMED_BASE_URL

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15  # seconds
SLEEP_BETWEEN_CALLS = 0.5  # be polite to the API


def search_setid(drug_name: str) -> str | None:
    """Search DailyMed by drug name, return the first matching setid."""
    url = f"{DAILYMED_BASE_URL}/spls.json"
    params = {"drug_name": drug_name, "pagesize": 1}

    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("data", [])
    if not results:
        log.warning(f"No results found for '{drug_name}'")
        return None

    return results[0]["setid"]


def download_label_xml(setid: str) -> bytes:
    """Fetch the full SPL XML for a given setid."""
    url = f"{DAILYMED_BASE_URL}/spls/{setid}.xml"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def safe_filename(drug_name: str) -> str:
    return drug_name.lower().replace(" ", "_") + ".xml"


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    downloaded, skipped, failed = 0, 0, 0

    for drug_name in DRUG_LIST:
        out_path = RAW_DIR / safe_filename(drug_name)

        if out_path.exists():
            log.info(f"Skipping '{drug_name}' (already downloaded)")
            skipped += 1
            continue

        try:
            setid = search_setid(drug_name)
            if setid is None:
                failed += 1
                continue

            xml_bytes = download_label_xml(setid)
            out_path.write_bytes(xml_bytes)
            log.info(f"Saved {drug_name} -> {out_path.name} ({len(xml_bytes)} bytes)")
            downloaded += 1

        except requests.RequestException as e:
            log.error(f"Failed to fetch '{drug_name}': {e}")
            failed += 1

        time.sleep(SLEEP_BETWEEN_CALLS)

    log.info(
        f"Done. Downloaded={downloaded}, Skipped={skipped}, Failed={failed}"
    )


if __name__ == "__main__":
    main()
