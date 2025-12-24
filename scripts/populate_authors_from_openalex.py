"""
Populate Author and PublicationAuthor tables from OpenAlex API

This script:
1. Fetches all publications with DOIs from the database
2. For each publication, queries OpenAlex API to get complete author information
3. Creates/updates Author records in the authors table
4. Creates PublicationAuthor junction records with author positions
5. Matches UNSW staff based on institution affiliations

OpenAlex API Rate Limits:
- Polite pool: 10 requests/second (with email in User-Agent)
- Daily limit: 100,000 requests
- We'll use 5 requests/second to be conservative

Usage:
    python3 scripts/populate_authors_from_openalex.py

    # Auto-resume from last saved progress (if interrupted)
    python3 scripts/populate_authors_from_openalex.py

    # Resume from specific publication
    python3 scripts/populate_authors_from_openalex.py --resume-from <publication_id>

    # Limit number of publications to process
    python3 scripts/populate_authors_from_openalex.py --limit 100
"""
import sys
from pathlib import Path
import time
import logging
import argparse
import json
from typing import Optional, Dict, List
import requests
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from database.rag_schema import Publication, Author, PublicationAuthor, Staff

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenAlex API configuration
OPENALEX_API_BASE = "https://api.openalex.org"
USER_AGENT = "UNSW RAG System (mailto:z5241339@unsw.edu.au)"
RATE_LIMIT_DELAY = 0.2  # 5 requests per second = 0.2 seconds between requests

# UNSW institution identifiers in OpenAlex
UNSW_OPENALEX_IDS = [
    "https://openalex.org/I73205298",  # UNSW Sydney main ID
    "I73205298"  # Short form
]

# Progress tracking file
PROGRESS_FILE = PROJECT_ROOT / "scripts" / ".openalex_progress.json"


class OpenAlexAuthorFetcher:
    """Fetches and populates author data from OpenAlex API"""

    def __init__(self, session):
        self.session = session
        self.request_count = 0
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def fetch_work_by_doi(self, doi: str) -> Optional[Dict]:
        """
        Fetch work data from OpenAlex by DOI

        Args:
            doi: DOI of the publication

        Returns:
            Work data dict or None if not found
        """
        self._rate_limit()

        url = f"{OPENALEX_API_BASE}/works/doi:{doi}"
        headers = {"User-Agent": USER_AGENT}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            self.request_count += 1

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Work not found in OpenAlex: {doi}")
                return None
            else:
                logger.error(f"OpenAlex API error {response.status_code} for DOI {doi}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for DOI {doi}: {e}")
            return None

    def get_or_create_author(self, author_data: Dict, is_unsw: bool = False) -> Optional[Author]:
        """
        Get existing author or create new one

        Args:
            author_data: Author data from OpenAlex API
            is_unsw: Whether this author is affiliated with UNSW

        Returns:
            Author object or None
        """
        # Extract OpenAlex ID
        openalex_id = author_data.get("author", {}).get("id")
        if not openalex_id:
            logger.warning(f"Author missing OpenAlex ID: {author_data}")
            return None

        # Check if author already exists
        stmt = select(Author).where(Author.openalex_id == openalex_id)
        existing_author = self.session.execute(stmt).scalar_one_or_none()

        if existing_author:
            # Update is_unsw_staff if needed
            if is_unsw and not existing_author.is_unsw_staff:
                existing_author.is_unsw_staff = True
                logger.info(f"  Updated UNSW affiliation for: {existing_author.name}")
            return existing_author

        # Create new author
        author_info = author_data.get("author", {})

        # Get institution info from this authorship
        institutions = author_data.get("institutions", [])
        last_institution = None
        last_institution_id = None
        if institutions:
            last_institution = institutions[0].get("display_name")
            last_institution_id = institutions[0].get("id")

        new_author = Author(
            openalex_id=openalex_id,
            name=author_info.get("display_name", "Unknown"),
            display_name=author_info.get("display_name"),
            orcid=author_info.get("orcid"),
            last_known_institution=last_institution,
            last_known_institution_id=last_institution_id,
            is_unsw_staff=is_unsw
        )

        self.session.add(new_author)
        self.session.flush()  # Get the ID

        return new_author

    def check_unsw_affiliation(self, institutions: List[Dict]) -> bool:
        """
        Check if author has UNSW affiliation

        Args:
            institutions: List of institution dicts from OpenAlex

        Returns:
            True if affiliated with UNSW
        """
        for inst in institutions:
            inst_id = inst.get("id", "")
            if any(unsw_id in inst_id for unsw_id in UNSW_OPENALEX_IDS):
                return True
        return False

    def process_publication(self, publication: Publication) -> bool:
        """
        Process a single publication: fetch authors and create relationships

        Args:
            publication: Publication object

        Returns:
            True if successful
        """
        if not publication.doi:
            logger.warning(f"Publication {publication.id} has no DOI, skipping")
            return False

        logger.info(f"Processing: {publication.title[:60]}...")
        logger.info(f"  DOI: {publication.doi}")

        # Fetch work data from OpenAlex
        work_data = self.fetch_work_by_doi(publication.doi)
        if not work_data:
            return False

        authorships = work_data.get("authorships", [])
        if not authorships:
            logger.warning(f"  No authors found in OpenAlex for {publication.doi}")
            return False

        logger.info(f"  Found {len(authorships)} authors")

        # Process each author
        for position, authorship in enumerate(authorships, start=1):
            # Check UNSW affiliation
            institutions = authorship.get("institutions", [])
            is_unsw = self.check_unsw_affiliation(institutions)

            # Get or create author
            author = self.get_or_create_author(authorship, is_unsw=is_unsw)
            if not author:
                continue

            # Check if relationship already exists
            stmt = select(PublicationAuthor).where(
                and_(
                    PublicationAuthor.publication_id == publication.id,
                    PublicationAuthor.author_id == author.id
                )
            )
            existing_rel = self.session.execute(stmt).scalar_one_or_none()

            if existing_rel:
                logger.debug(f"  Relationship already exists for author {author.name}")
                continue

            # Create publication-author relationship
            pub_author = PublicationAuthor(
                publication_id=publication.id,
                author_id=author.id,
                author_position=position,
                is_corresponding=authorship.get("is_corresponding", False),
                institutions=[
                    {
                        "id": inst.get("id"),
                        "display_name": inst.get("display_name")
                    }
                    for inst in institutions
                ]
            )

            self.session.add(pub_author)

            unsw_marker = " [UNSW]" if is_unsw else ""
            logger.info(f"  [{position}] {author.name}{unsw_marker}")

        return True


def save_progress(publication_id: str, processed_count: int, total_count: int):
    """Save progress to file for resumption"""
    progress_data = {
        "last_publication_id": publication_id,
        "processed_count": processed_count,
        "total_count": total_count,
        "timestamp": time.time()
    }
    try:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress_data, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save progress: {e}")


def load_progress() -> Optional[Dict]:
    """Load progress from file if exists"""
    if not PROGRESS_FILE.exists():
        return None

    try:
        with open(PROGRESS_FILE, 'r') as f:
            progress_data = json.load(f)
            logger.info(f"Found saved progress: {progress_data['processed_count']}/{progress_data['total_count']} publications processed")
            logger.info(f"Last publication ID: {progress_data['last_publication_id']}")
            return progress_data
    except Exception as e:
        logger.warning(f"Failed to load progress file: {e}")
        return None


def clear_progress():
    """Clear progress file when processing completes"""
    try:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            logger.info("Progress file cleared")
    except Exception as e:
        logger.warning(f"Failed to clear progress file: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Populate authors from OpenAlex")
    parser.add_argument(
        "--resume-from",
        help="Resume from specific publication ID"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of publications to process"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: process only first 5 publications"
    )
    parser.add_argument(
        "--clear-progress",
        action="store_true",
        help="Clear saved progress and start from beginning"
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("POPULATE AUTHORS FROM OPENALEX")
    print("="*80 + "\n")

    # Handle clear progress flag
    if args.clear_progress:
        clear_progress()
        logger.info("Progress cleared. Starting from beginning.")

    # Connect to database
    logger.info(f"Connecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Get publications with DOIs
        stmt = select(Publication).where(Publication.doi.isnot(None))

        # Check for saved progress (if no explicit resume-from)
        resume_from_id = args.resume_from
        if not resume_from_id and not args.clear_progress:
            saved_progress = load_progress()
            if saved_progress:
                resume_from_id = saved_progress['last_publication_id']
                logger.info(f"Auto-resuming from saved progress")

        if resume_from_id:
            logger.info(f"Resuming from publication: {resume_from_id}")
            # Skip all publications up to and including the resume point
            resume_pub = session.execute(
                select(Publication).where(Publication.id == resume_from_id)
            ).scalar_one_or_none()

            if resume_pub:
                # Get publications after this one by ID (more precise than timestamp)
                stmt = stmt.where(Publication.id > resume_from_id)
            else:
                logger.error(f"Resume publication not found: {resume_from_id}")
                return

        stmt = stmt.order_by(Publication.id)

        if args.limit:
            stmt = stmt.limit(args.limit)
        elif args.test:
            stmt = stmt.limit(5)
            logger.info("TEST MODE: Processing only first 5 publications")

        publications = session.execute(stmt).scalars().all()

        total = len(publications)
        logger.info(f"Found {total} publications to process\n")

        if total == 0:
            logger.info("No publications to process")
            return

        # Create fetcher
        fetcher = OpenAlexAuthorFetcher(session)

        # Process each publication
        success_count = 0
        fail_count = 0

        start_time = time.time()

        for i, pub in enumerate(publications, 1):
            print(f"\n[{i}/{total}] Processing publication ID: {pub.id}")

            try:
                if fetcher.process_publication(pub):
                    success_count += 1
                    # Commit after each publication
                    session.commit()
                    logger.info("  ✓ Committed to database")

                    # Save progress after each successful processing
                    save_progress(pub.id, i, total)
                else:
                    fail_count += 1

            except KeyboardInterrupt:
                logger.warning("\n\nInterrupted by user (Ctrl+C)")
                logger.info(f"Progress saved at publication ID: {pub.id}")
                logger.info(f"Processed: {i}/{total} publications")
                logger.info(f"To resume, simply run the script again (will auto-resume)")
                session.rollback()
                return

            except Exception as e:
                logger.error(f"  ✗ Error processing publication: {e}")
                import traceback
                traceback.print_exc()
                session.rollback()
                fail_count += 1

            # Progress report every 10 publications
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                eta = (total - i) / rate if rate > 0 else 0
                logger.info(f"\nProgress: {i}/{total} ({i/total*100:.1f}%)")
                logger.info(f"Rate: {rate:.2f} pubs/sec")
                logger.info(f"ETA: {eta/60:.1f} minutes")
                logger.info(f"API requests: {fetcher.request_count}")

        # Final summary
        elapsed = time.time() - start_time

        print("\n" + "="*80)
        print("PROCESSING COMPLETE")
        print("="*80)
        print(f"Total publications: {total}")
        print(f"Successful: {success_count}")
        print(f"Failed: {fail_count}")
        print(f"Time elapsed: {elapsed/60:.1f} minutes")
        print(f"API requests made: {fetcher.request_count}")

        # Count authors created
        author_count = session.execute(select(Author)).scalars().all()
        unsw_author_count = session.execute(
            select(Author).where(Author.is_unsw_staff == True)
        ).scalars().all()

        print(f"\nAuthors in database: {len(author_count)}")
        print(f"UNSW-affiliated authors: {len(unsw_author_count)}")

        print("="*80 + "\n")

        # Clear progress file on successful completion
        clear_progress()

    except KeyboardInterrupt:
        logger.warning("\n\nScript interrupted by user")
        logger.info("Progress has been saved. Run the script again to resume.")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
