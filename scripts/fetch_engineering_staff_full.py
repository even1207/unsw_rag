"""Fetch staff list and enrich with profile data."""

from __future__ import annotations

import json
import time

from ingestor.staff_fetcher import fetch_engineering_staff
from ingestor.staff_profile import parse_staff_profile


def main() -> None:
    staff_basic = fetch_engineering_staff()
    enriched = []

    for idx, staff in enumerate(staff_basic, start=1):
        url = staff.get("profile_url")
        print(f"[{idx}/{len(staff_basic)}] Fetching profile: {url}")
        try:
            extra = parse_staff_profile(url)
            staff.update(extra)
        except Exception as exc:  # pragma: no cover - error logging only
            print(f"Error parsing {url}: {exc}")
        enriched.append(staff)
        time.sleep(1)

    with open("engineering_staff_full.json", "w", encoding="utf-8") as file:
        json.dump(enriched, file, ensure_ascii=False, indent=2)

    print("Done. Saved to engineering_staff_full.json")


if __name__ == "__main__":
    main()
