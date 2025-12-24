"""Script to fetch engineering staff basic information."""

from __future__ import annotations

import json

from ingestor.staff_fetcher import fetch_engineering_staff


def main() -> None:
    staff_list = fetch_engineering_staff()
    print(f"Total staff fetched: {len(staff_list)}")

    with open("engineering_staff_basic.json", "w", encoding="utf-8") as file:
        json.dump(staff_list, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
