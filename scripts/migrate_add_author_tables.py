"""
Database Migration: Add Author and PublicationAuthor tables

This creates the new author relationship tables without dropping existing data.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from config.settings import settings
from database.rag_schema import Author, PublicationAuthor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run migration"""

    print("\n" + "="*80)
    print("DATABASE MIGRATION: ADD AUTHOR TABLES")
    print("="*80 + "\n")

    logger.info(f"Connecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn)

    try:
        # Create Author table
        logger.info("Creating authors table...")
        Author.__table__.create(engine, checkfirst=True)
        logger.info("✓ authors table created")

        # Create PublicationAuthor table
        logger.info("Creating publication_authors table...")
        PublicationAuthor.__table__.create(engine, checkfirst=True)
        logger.info("✓ publication_authors table created")

        # Verify tables exist
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('authors', 'publication_authors')
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]

        print("\n" + "="*80)
        print("MIGRATION COMPLETE")
        print("="*80)
        print(f"Created tables: {', '.join(tables)}")
        print("\nNext steps:")
        print("1. Run: python3 scripts/populate_authors_from_openalex.py")
        print("2. This will fetch author data from OpenAlex and populate the tables")
        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
