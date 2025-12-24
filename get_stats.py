"""Get database statistics for weekly report"""
from sqlalchemy import create_engine, text
from config.settings import settings

engine = create_engine(settings.postgres_dsn)

with engine.connect() as conn:
    # Staff count
    staff_count = conn.execute(text('SELECT COUNT(*) FROM staff_profiles')).scalar()
    print(f'Total staff profiles: {staff_count}')

    # Publications count
    pub_count = conn.execute(text('SELECT COUNT(*) FROM publications')).scalar()
    print(f'Total publications: {pub_count}')

    # Chunks count
    chunk_count = conn.execute(text('SELECT COUNT(*) FROM chunks')).scalar()
    print(f'Total text chunks: {chunk_count}')

    # Staff with publications
    staff_with_pubs = conn.execute(text('SELECT COUNT(DISTINCT staff_profile_url) FROM publications WHERE staff_profile_url IS NOT NULL')).scalar()
    print(f'Staff with publications: {staff_with_pubs}')

    # Average publications per staff
    if staff_with_pubs > 0:
        avg_pubs = pub_count / staff_with_pubs
        print(f'Average publications per staff: {avg_pubs:.1f}')

    # Publications with abstracts
    pubs_with_abstract = conn.execute(text("SELECT COUNT(*) FROM publications WHERE abstract IS NOT NULL AND abstract != ''")).scalar()
    print(f'Publications with abstracts: {pubs_with_abstract}')

    # Publication coverage percentage
    if pub_count > 0:
        coverage = (pubs_with_abstract / pub_count) * 100
        print(f'Abstract coverage: {coverage:.1f}%')

    # School distribution
    print('\nSchool Distribution:')
    schools = conn.execute(text('SELECT school, COUNT(*) as cnt FROM staff_profiles GROUP BY school ORDER BY cnt DESC LIMIT 10')).fetchall()
    for school, cnt in schools:
        print(f'  {school}: {cnt}')

    # Year distribution of publications
    print('\nPublication Year Distribution (last 5 years):')
    years = conn.execute(text('SELECT publication_year, COUNT(*) as cnt FROM publications WHERE publication_year >= 2020 GROUP BY publication_year ORDER BY publication_year DESC')).fetchall()
    for year, cnt in years:
        if year:
            print(f'  {year}: {cnt}')
