#!/usr/bin/env python3
"""
Script to import staff data from JSON file to PostgreSQL database.

Usage:
    PYTHONPATH=/Users/z5241339/Documents/unsw_ai_rag python3 scripts/import_to_database.py
"""

import json
import sys
from pathlib import Path

from database.db import init_database, upsert_staff


def load_json_file(file_path: str) -> list:
    """Load staff data from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def main():
    """Main function to import staff data to database."""
    # Default to engineering_staff_full.json
    json_file = "engineering_staff_full.json"

    # Allow custom file path as command line argument
    if len(sys.argv) > 1:
        json_file = sys.argv[1]

    json_path = Path(json_file)

    if not json_path.exists():
        print(f"Error: File not found: {json_file}")
        print("\nUsage: python3 scripts/import_to_database.py [json_file_path]")
        print("Example: python3 scripts/import_to_database.py engineering_staff_full.json")
        sys.exit(1)

    print(f"Loading data from: {json_file}")
    staff_data = load_json_file(json_file)
    print(f"Loaded {len(staff_data)} staff records")

    print("\nInitializing database...")
    init_database()
    print("Database initialized successfully")

    print("\nImporting staff data to database...")
    result = upsert_staff(staff_data)

    print("\n" + "=" * 60)
    print("Import completed successfully!")
    print("=" * 60)
    print(f"Total records processed: {result['total']}")
    print(f"Records inserted/updated: {result['inserted']}")
    print("\nYou can now query the staff_profiles table in your PostgreSQL database.")


if __name__ == "__main__":
    main()
