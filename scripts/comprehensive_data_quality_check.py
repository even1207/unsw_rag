"""
全面的数据质量检查脚本

检查项目:
1. Authors数据完整性
2. Publication-Author关系完整性
3. UNSW作者识别准确性
4. 数据一致性（publications.authors JSON vs publication_authors表）
5. 缺失数据统计
6. 异常数据识别

Usage:
    python3 scripts/comprehensive_data_quality_check.py
"""
import sys
from pathlib import Path
import json
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import sessionmaker
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from database.rag_schema import Publication, Author, PublicationAuthor, Staff

# Output directory
REPORTS_DIR = PROJECT_ROOT / "data" / "validation_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def check_basic_stats(session):
    """基础统计信息"""
    print("\n" + "="*80)
    print("1. 基础统计信息")
    print("="*80)

    stats = {}

    # Publications
    total_pubs = session.execute(select(func.count(Publication.id))).scalar()
    pubs_with_doi = session.execute(
        select(func.count(Publication.id)).where(Publication.doi.isnot(None))
    ).scalar()

    stats['publications'] = {
        'total': total_pubs,
        'with_doi': pubs_with_doi,
        'without_doi': total_pubs - pubs_with_doi
    }

    print(f"\nPublications:")
    print(f"  总数: {total_pubs:,}")
    print(f"  有DOI: {pubs_with_doi:,} ({pubs_with_doi/total_pubs*100:.1f}%)")
    print(f"  无DOI: {total_pubs - pubs_with_doi:,}")

    # Authors
    total_authors = session.execute(select(func.count(Author.id))).scalar()
    unsw_authors = session.execute(
        select(func.count(Author.id)).where(Author.is_unsw_staff == True)
    ).scalar()

    stats['authors'] = {
        'total': total_authors,
        'unsw_staff': unsw_authors,
        'non_unsw': total_authors - unsw_authors
    }

    print(f"\nAuthors:")
    print(f"  总数: {total_authors:,}")
    print(f"  UNSW员工: {unsw_authors:,} ({unsw_authors/total_authors*100:.1f}%)")
    print(f"  非UNSW: {total_authors - unsw_authors:,}")

    # Publication-Author relationships
    total_relationships = session.execute(select(func.count(PublicationAuthor.publication_id))).scalar()

    stats['relationships'] = {
        'total': total_relationships
    }

    print(f"\nPublication-Author关系:")
    print(f"  总数: {total_relationships:,}")
    print(f"  平均每篇论文作者数: {total_relationships/total_pubs:.1f}")

    return stats


def check_author_coverage(session):
    """检查作者数据覆盖率"""
    print("\n" + "="*80)
    print("2. 作者数据覆盖率")
    print("="*80)

    coverage = {}

    # Publications with authors
    result = session.execute(text("""
        SELECT
            COUNT(DISTINCT p.id) as total,
            COUNT(DISTINCT CASE
                WHEN EXISTS (
                    SELECT 1 FROM publication_authors pa
                    WHERE pa.publication_id = p.id
                ) THEN p.id
            END) as with_authors
        FROM publications p
        WHERE p.doi IS NOT NULL
    """))
    row = result.fetchone()

    coverage['publications_with_doi'] = {
        'total': row[0],
        'with_authors': row[1],
        'without_authors': row[0] - row[1],
        'coverage_rate': row[1] / row[0] if row[0] > 0 else 0
    }

    print(f"\n有DOI的论文:")
    print(f"  总数: {row[0]:,}")
    print(f"  已有作者数据: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"  缺少作者数据: {row[0] - row[1]:,} ({(row[0]-row[1])/row[0]*100:.1f}%)")

    # Author metadata completeness
    result = session.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN openalex_id IS NOT NULL THEN 1 END) as with_openalex,
            COUNT(CASE WHEN orcid IS NOT NULL THEN 1 END) as with_orcid,
            COUNT(CASE WHEN last_known_institution IS NOT NULL THEN 1 END) as with_institution
        FROM authors
    """))
    row = result.fetchone()

    coverage['author_metadata'] = {
        'total': row[0],
        'with_openalex_id': row[1],
        'with_orcid': row[2],
        'with_institution': row[3]
    }

    print(f"\n作者元数据完整性:")
    print(f"  总作者数: {row[0]:,}")
    print(f"  有OpenAlex ID: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"  有ORCID: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    print(f"  有机构信息: {row[3]:,} ({row[3]/row[0]*100:.1f}%)")

    return coverage


def check_data_consistency(session):
    """检查数据一致性"""
    print("\n" + "="*80)
    print("3. 数据一致性检查")
    print("="*80)

    issues = []

    # Check: publications.authors JSON vs publication_authors table
    print("\n检查 publications.authors JSON 与 publication_authors 表的一致性...")

    result = session.execute(text("""
        SELECT
            p.id,
            p.doi,
            p.title,
            COALESCE(jsonb_array_length(p.authors::jsonb), 0) as json_author_count,
            COUNT(pa.author_id) as table_author_count
        FROM publications p
        LEFT JOIN publication_authors pa ON p.id = pa.publication_id
        WHERE p.doi IS NOT NULL
        GROUP BY p.id, p.doi, p.title
        HAVING COALESCE(jsonb_array_length(p.authors::jsonb), 0) != COUNT(pa.author_id)
        LIMIT 20
    """))

    inconsistent = result.fetchall()

    if inconsistent:
        print(f"  ✗ 发现 {len(inconsistent)} 篇论文的作者数据不一致")
        for row in inconsistent[:5]:
            print(f"    - {row[1]}: JSON={row[3]}, Table={row[4]}")
        issues.append({
            'type': 'author_count_mismatch',
            'count': len(inconsistent),
            'severity': 'medium'
        })
    else:
        print(f"  ✓ 数据一致性良好")

    # Check: duplicate author relationships
    print("\n检查重复的作者关系...")

    result = session.execute(text("""
        SELECT publication_id, author_id, COUNT(*) as cnt
        FROM publication_authors
        GROUP BY publication_id, author_id
        HAVING COUNT(*) > 1
    """))

    duplicates = result.fetchall()

    if duplicates:
        print(f"  ✗ 发现 {len(duplicates)} 个重复的作者关系")
        issues.append({
            'type': 'duplicate_relationships',
            'count': len(duplicates),
            'severity': 'high'
        })
    else:
        print(f"  ✓ 无重复作者关系")

    # Check: orphaned authors (authors not linked to any publication)
    print("\n检查孤立作者（未关联任何论文）...")

    result = session.execute(text("""
        SELECT COUNT(*) FROM authors a
        WHERE NOT EXISTS (
            SELECT 1 FROM publication_authors pa
            WHERE pa.author_id = a.id
        )
    """))

    orphaned = result.scalar()

    if orphaned > 0:
        print(f"  ⚠ 发现 {orphaned} 个孤立作者")
        issues.append({
            'type': 'orphaned_authors',
            'count': orphaned,
            'severity': 'low'
        })
    else:
        print(f"  ✓ 无孤立作者")

    return issues


def check_unsw_author_accuracy(session):
    """检查UNSW作者识别准确性"""
    print("\n" + "="*80)
    print("4. UNSW作者识别准确性")
    print("="*80)

    accuracy = {}

    # Get total UNSW staff
    total_staff = session.execute(select(func.count(Staff.profile_url))).scalar()

    # Get authors marked as UNSW
    unsw_authors = session.execute(
        select(func.count(Author.id)).where(Author.is_unsw_staff == True)
    ).scalar()

    print(f"\nUNSW Staff数据库: {total_staff:,} 人")
    print(f"标记为UNSW的作者: {unsw_authors:,} 人")

    # Check if UNSW authors are linked to staff profiles
    result = session.execute(text("""
        SELECT
            COUNT(*) as total_unsw_authors,
            COUNT(CASE WHEN unsw_staff_profile_url IS NOT NULL THEN 1 END) as linked_to_staff
        FROM authors
        WHERE is_unsw_staff = true
    """))
    row = result.fetchone()

    accuracy['unsw_authors'] = {
        'total': row[0],
        'linked_to_staff': row[1],
        'not_linked': row[0] - row[1]
    }

    print(f"\nUNSW作者关联到Staff:")
    print(f"  已关联: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"  未关联: {row[0] - row[1]:,} ({(row[0]-row[1])/row[0]*100:.1f}%)")

    # Sample some UNSW authors
    print(f"\nUNSW作者样本:")
    result = session.execute(text("""
        SELECT a.name, a.last_known_institution, COUNT(pa.publication_id) as pub_count
        FROM authors a
        LEFT JOIN publication_authors pa ON a.id = pa.author_id
        WHERE a.is_unsw_staff = true
        GROUP BY a.id, a.name, a.last_known_institution
        ORDER BY pub_count DESC
        LIMIT 10
    """))

    for row in result:
        print(f"  - {row[0]} ({row[1]}): {row[2]} 篇论文")

    return accuracy


def check_missing_data(session):
    """检查缺失数据"""
    print("\n" + "="*80)
    print("5. 缺失数据分析")
    print("="*80)

    missing = {}

    # Publications without authors (with DOI)
    result = session.execute(text("""
        SELECT COUNT(*)
        FROM publications p
        WHERE p.doi IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM publication_authors pa
            WHERE pa.publication_id = p.id
        )
    """))

    pubs_no_authors = result.scalar()
    missing['publications_without_authors'] = pubs_no_authors

    print(f"\n有DOI但缺少作者的论文: {pubs_no_authors:,}")

    # Sample some
    if pubs_no_authors > 0:
        print("\n样本:")
        result = session.execute(text("""
            SELECT p.doi, p.title, p.publication_year
            FROM publications p
            WHERE p.doi IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM publication_authors pa
                WHERE pa.publication_id = p.id
            )
            LIMIT 5
        """))

        for row in result:
            print(f"  - [{row[2]}] {row[0]}")
            print(f"    {row[1][:70]}")

    # Publications with very few/many authors (potential data quality issues)
    print("\n\n作者数异常的论文:")

    result = session.execute(text("""
        SELECT
            SUM(CASE WHEN author_count = 0 THEN 1 ELSE 0 END) as zero_authors,
            SUM(CASE WHEN author_count = 1 THEN 1 ELSE 0 END) as one_author,
            SUM(CASE WHEN author_count BETWEEN 2 AND 10 THEN 1 ELSE 0 END) as normal,
            SUM(CASE WHEN author_count > 50 THEN 1 ELSE 0 END) as very_many,
            SUM(CASE WHEN author_count > 100 THEN 1 ELSE 0 END) as extreme
        FROM (
            SELECT p.id, COUNT(pa.author_id) as author_count
            FROM publications p
            LEFT JOIN publication_authors pa ON p.id = pa.publication_id
            WHERE p.doi IS NOT NULL
            GROUP BY p.id
        ) t
    """))

    row = result.fetchone()

    print(f"  无作者: {row[0]:,}")
    print(f"  单作者: {row[1]:,}")
    print(f"  正常(2-10人): {row[2]:,}")
    print(f"  很多(>50人): {row[3]:,}")
    print(f"  极多(>100人): {row[4]:,}")

    missing['author_count_distribution'] = {
        'zero': row[0],
        'one': row[1],
        'normal': row[2],
        'many': row[3],
        'extreme': row[4]
    }

    return missing


def check_collaboration_graph(session):
    """检查合作网络图质量"""
    print("\n" + "="*80)
    print("6. 合作网络图质量")
    print("="*80)

    graph_stats = {}

    # Top collaborators
    print("\n最活跃的合作者（论文数最多）:")

    result = session.execute(text("""
        SELECT a.name, a.is_unsw_staff, COUNT(DISTINCT pa.publication_id) as pub_count
        FROM authors a
        JOIN publication_authors pa ON a.id = pa.author_id
        GROUP BY a.id, a.name, a.is_unsw_staff
        ORDER BY pub_count DESC
        LIMIT 10
    """))

    for i, row in enumerate(result, 1):
        unsw_marker = " [UNSW]" if row[1] else ""
        print(f"  {i}. {row[0]}{unsw_marker}: {row[2]} 篇论文")

    # Most common collaboration pairs (UNSW authors)
    print("\n\nUNSW作者最常见的合作关系:")

    result = session.execute(text("""
        SELECT
            a1.name as author1,
            a2.name as author2,
            COUNT(DISTINCT pa1.publication_id) as collaboration_count
        FROM publication_authors pa1
        JOIN publication_authors pa2 ON pa1.publication_id = pa2.publication_id
        JOIN authors a1 ON pa1.author_id = a1.id
        JOIN authors a2 ON pa2.author_id = a2.id
        WHERE a1.is_unsw_staff = true
        AND a2.is_unsw_staff = true
        AND a1.id < a2.id
        GROUP BY a1.name, a2.name
        ORDER BY collaboration_count DESC
        LIMIT 10
    """))

    for i, row in enumerate(result, 1):
        print(f"  {i}. {row[0]} ↔ {row[1]}: {row[2]} 篇合作论文")

    return graph_stats


def generate_recommendations(stats, coverage, issues, missing):
    """生成改进建议"""
    print("\n" + "="*80)
    print("7. 改进建议")
    print("="*80)

    recommendations = []

    # Check coverage
    coverage_rate = coverage['publications_with_doi']['coverage_rate']

    if coverage_rate < 0.95:
        pct = (1 - coverage_rate) * 100
        recommendations.append({
            'priority': 'high',
            'issue': f'{pct:.1f}% 的论文缺少作者数据',
            'action': '继续运行 populate_authors_from_openalex.py 完成剩余论文'
        })

    # Check ORCID coverage
    orcid_rate = coverage['author_metadata']['with_orcid'] / coverage['author_metadata']['total']

    if orcid_rate < 0.3:
        recommendations.append({
            'priority': 'medium',
            'issue': f'只有 {orcid_rate*100:.1f}% 的作者有ORCID',
            'action': '考虑从其他数据源补充ORCID信息'
        })

    # Check data consistency issues
    for issue in issues:
        if issue['severity'] == 'high':
            recommendations.append({
                'priority': 'high',
                'issue': issue['type'],
                'action': '需要修复数据不一致问题'
            })

    # Check missing data
    if missing.get('publications_without_authors', 0) > 1000:
        recommendations.append({
            'priority': 'high',
            'issue': f"{missing['publications_without_authors']} 篇论文缺少作者",
            'action': '检查这些论文的DOI是否有效，考虑使用备用数据源'
        })

    print("\n优先级排序:")

    for rec in sorted(recommendations, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}[x['priority']]):
        priority_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[rec['priority']]
        print(f"\n{priority_icon} [{rec['priority'].upper()}]")
        print(f"  问题: {rec['issue']}")
        print(f"  建议: {rec['action']}")

    return recommendations


def main():
    """主函数"""
    print("\n" + "="*80)
    print("数据质量全面检查")
    print("="*80)

    # Connect to database
    engine = create_engine(settings.postgres_dsn, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Run all checks
        stats = check_basic_stats(session)
        coverage = check_author_coverage(session)
        issues = check_data_consistency(session)
        accuracy = check_unsw_author_accuracy(session)
        missing = check_missing_data(session)
        graph_stats = check_collaboration_graph(session)

        # Generate recommendations
        recommendations = generate_recommendations(stats, coverage, issues, missing)

        # Save full report
        full_report = {
            'basic_stats': stats,
            'coverage': coverage,
            'consistency_issues': issues,
            'unsw_accuracy': accuracy,
            'missing_data': missing,
            'graph_stats': graph_stats,
            'recommendations': recommendations
        }

        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"data_quality_report_{timestamp}.json"

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False)

        print("\n" + "="*80)
        print(f"完整报告已保存到: {report_file}")
        print("="*80 + "\n")

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
