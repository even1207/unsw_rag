"""
Debug script to find why chunks are being skipped during import
"""
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent
json_file = PROJECT_ROOT / "data/processed/rag_chunks.json"

print("Loading chunks from JSON...")
with open(json_file) as f:
    chunks = json.load(f)

print(f"Total chunks in JSON: {len(chunks):,}\n")

# Simulate the import logic
skipped_reasons = defaultdict(int)
processed_chunks = 0
processed_publications = set()

for i, chunk in enumerate(chunks, 1):
    chunk_type = chunk.get('chunk_type')
    chunk_id = chunk.get('chunk_id')
    content = chunk.get('content')
    metadata = chunk.get('metadata', {})

    # Extract staff info
    person_profile_url = metadata.get('person_profile_url') or metadata.get('profile_url')

    # Check 1: Missing person_profile_url (line 99-101 in original script)
    if not person_profile_url:
        skipped_reasons['no_person_profile_url'] += 1
        continue

    # Check 2: For publication chunks, check if publication gets created
    if chunk_type in ['publication_title', 'publication_abstract', 'publication_keywords']:
        pub_title = metadata.get('pub_title')
        pub_doi = metadata.get('pub_doi')

        if not pub_title:
            skipped_reasons['publication_chunk_no_title'] += 1
            continue

        # Track unique publications
        pub_id = pub_doi if pub_doi else f"no-doi-{pub_title}"
        processed_publications.add(pub_id)

    processed_chunks += 1

print("Simulation Results:")
print("="*60)
print(f"Chunks that would be processed: {processed_chunks:,}")
print(f"Unique publications: {len(processed_publications):,}")
print(f"\nSkipped chunks breakdown:")
for reason, count in skipped_reasons.items():
    print(f"  {reason}: {count:,}")

print(f"\n Expected in DB: {processed_chunks:,}")
print(f" Actually in DB: 120,489")
print(f"    Discrepancy: {processed_chunks - 120489:,}")

# If there's still a discrepancy, check for existing chunks logic
if processed_chunks > 120489:
    print("\n" + "="*60)
    print("The discrepancy suggests chunks are being skipped due to:")
    print("  1. Duplicate chunk_ids (line 163-177 in original script)")
    print("  2. Database transaction/commit issues")
    print("\nLet's check for duplicate chunk_ids in JSON...")

    chunk_ids = [c.get('chunk_id') for c in chunks]
    unique_ids = set(chunk_ids)

    print(f"\nTotal chunk_ids in JSON: {len(chunk_ids):,}")
    print(f"Unique chunk_ids in JSON: {len(unique_ids):,}")
    print(f"Duplicates in JSON: {len(chunk_ids) - len(unique_ids):,}")

    if len(chunk_ids) != len(unique_ids):
        # Find duplicates
        from collections import Counter
        id_counts = Counter(chunk_ids)
        duplicates = {cid: count for cid, count in id_counts.items() if count > 1}

        print(f"\nSample duplicate chunk_ids:")
        for cid, count in list(duplicates.items())[:5]:
            print(f"  {cid}: appears {count} times")
