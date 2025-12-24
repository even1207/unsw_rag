"""Fetch staff list from Funnelback API."""

from __future__ import annotations

import time
from typing import Dict, List

import requests

BASE_URL = "https://unsw-search.funnelback.squiz.cloud/s/search.html"


def fetch_engineering_staff(page_size: int = 50, delay_seconds: float = 1.0) -> List[Dict[str, str]]:
    """Retrieve the engineering staff list from Funnelback."""
    params = {
        "form": "json",
        "collection": "unsw~unsw-search",
        "profile": "profiles",
        "query": "!padrenull",
        "sort": "metastaffLastName",
        "f.Faculty|staffFaculty": "Engineering",
        "gscope1": "engineeringStaff",
        "meta_staffRole_not": "casual adjunct visiting honorary",
    }

    all_staff: List[Dict[str, str]] = []
    start_rank = 1

    while True:
        params["start_rank"] = start_rank
        params["num_ranks"] = page_size

        resp = requests.get(
            BASE_URL,
            params=params,
            timeout=10,
            headers={"User-Agent": "UNSW-AI-RAG-Research-Bot/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("response", {}).get("resultPacket", {}).get("results", [])
        if not results:
            break

        for record in results:
            meta = record.get("metaData", {})
            all_staff.append(
                {
                    "full_name": record.get("title"),
                    "profile_url": record.get("liveUrl"),
                    "summary": record.get("summary"),
                    "first_name": meta.get("staffFirstName"),
                    "last_name": meta.get("staffLastName"),
                    "role": meta.get("staffRole"),
                    "faculty": meta.get("staffFaculty"),
                    "school": meta.get("staffSchool"),
                    "email": meta.get("emailAddress"),
                    "phone": meta.get("staffPhone"),
                    "photo_url": meta.get("image"),
                }
            )

        print(f"Fetched {len(results)} staff from {start_rank} to {start_rank + page_size - 1}")
        start_rank += page_size
        time.sleep(delay_seconds)

    return all_staff
