"""
Fix missing authors in publications table

Extracts authors from chunk content and updates the publications table
"""
import sys
from pathlib import Path
import re
import json
from tqdm import tqdm

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from database.rag_schema import Publication

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_authors_from_content(content: str) -> list:
    """
    Extract authors from publication title chunk content

    Content format:
    Title: ...
    Authors: Author1, Author2, Author3
    Published: ...
    """
    authors = []

    # Find authors line
    match = re.search(r'Authors:\s*([^\n]+)', content)
    if match:
        authors_str = match.group(1).strip()
        # Split by comma
        author_names = [name.strip() for name in authors_str.split(',')]
        # Convert to list of dicts
        authors = [{"name": name} for name in author_names if name]

    return authors


def main():
    """Main function"""

    print("\n" + "="*80)
    print("FIX MISSING AUTHORS IN PUBLICATIONS")
    print("="*80 + "\n")

    # Load chunks
    chunks_file = PROJECT_ROOT / "data" / "processed" / "rag_chunks.json"

    logger.info(f"Loading chunks from: {chunks_file}")
    with open(chunks_file, 'r') as f:
        chunks = json.load(f)

    # Filter publication_title chunks (they have author info)
    pub_title_chunks = [
        c for c in chunks
        if c.get("chunk_type") == "publication_title"
    ]

    logger.info(f"Found {len(pub_title_chunks):,} publication_title chunks")

    # Extract DOI -> authors mapping
    doi_to_authors = {}

    for chunk in tqdm(pub_title_chunks, desc="Extracting authors"):
        content = chunk.get("content", "")
        metadata = chunk.get("metadata", {})
        doi = metadata.get("pub_doi")

        if doi:
            authors = extract_authors_from_content(content)
            if authors:
                doi_to_authors[doi] = authors

    logger.info(f"Extracted authors for {len(doi_to_authors):,} publications")

    # Connect to database
    logger.info(f"Connecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Update publications
        updated_count = 0

        for doi, authors in tqdm(doi_to_authors.items(), desc="Updating database"):
            pub = session.query(Publication).filter_by(doi=doi).first()
            if pub:
                pub.authors = authors
                updated_count += 1

        # Commit changes
        session.commit()

        logger.info(f"\n✓ Updated {updated_count:,} publications with authors")

        # Verify
        result = session.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN jsonb_array_length(authors::jsonb) > 0 THEN 1 END) as with_authors
            FROM publications
        """))
        row = result.fetchone()

        print("\n" + "="*80)
        print("VERIFICATION")
        print("="*80)
        print(f"Total publications: {row.total:,}")
        print(f"With authors: {row.with_authors:,}")
        print(f"Coverage: {row.with_authors/row.total*100:.1f}%")
        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"Error: {e}")
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
