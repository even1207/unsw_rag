"""
Quick script to populate authors for publications that are missing them

This is useful when you have search results showing publications without authors.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from database.rag_schema import Publication
import logging

# Import the author fetcher from the populate script
from scripts.populate_authors_from_openalex import OpenAlexAuthorFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Populate authors for specific DOIs"""

    # List of DOIs that are showing up without authors
    dois_to_fix = [
        "10.1109/TII.2018.2873186",
        "10.1080/00207543.2018.1443229",
        "10.12688/digitaltwin.17489.1"
    ]

    print("\n" + "="*80)
    print("POPULATE AUTHORS FOR SPECIFIC PUBLICATIONS")
    print("="*80 + "\n")

    # Connect to database
    engine = create_engine(settings.postgres_dsn, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        fetcher = OpenAlexAuthorFetcher(session)

        success_count = 0
        fail_count = 0

        for doi in dois_to_fix:
            print(f"\nProcessing DOI: {doi}")

            # Find publication
            stmt = select(Publication).where(Publication.doi == doi)
            pub = session.execute(stmt).scalar_one_or_none()

            if not pub:
                logger.warning(f"  Publication not found: {doi}")
                fail_count += 1
                continue

            try:
                if fetcher.process_publication(pub):
                    session.commit()
                    logger.info("  ✓ Authors populated successfully")
                    success_count += 1
                else:
                    logger.warning("  ✗ Failed to fetch authors")
                    fail_count += 1
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
                session.rollback()
                fail_count += 1

        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total DOIs processed: {len(dois_to_fix)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {fail_count}")
        print("="*80 + "\n")

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
