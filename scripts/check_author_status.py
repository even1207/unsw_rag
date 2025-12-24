"""
检查作者数据填充状态
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from config.settings import settings

engine = create_engine(settings.postgres_dsn, echo=False)

print("\n" + "="*80)
print("作者数据填充状态检查")
print("="*80 + "\n")

with engine.connect() as conn:
    # 总体统计
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pubs,
            COUNT(DISTINCT CASE
                WHEN EXISTS (
                    SELECT 1 FROM publication_authors pa
                    WHERE pa.publication_id = p.id
                ) THEN p.id
            END) as pubs_with_authors,
            COUNT(*) - COUNT(DISTINCT CASE
                WHEN EXISTS (
                    SELECT 1 FROM publication_authors pa
                    WHERE pa.publication_id = p.id
                ) THEN p.id
            END) as pubs_without_authors
        FROM publications p
    """))

    row = result.fetchone()
    total = row[0]
    with_authors = row[1]
    without_authors = row[2]

    print(f"总文献数：{total:,}")
    print(f"已有作者：{with_authors:,} ({with_authors/total*100:.1f}%)")
    print(f"缺少作者：{without_authors:,} ({without_authors/total*100:.1f}%)")

    # 作者表统计
    result = conn.execute(text("SELECT COUNT(*) FROM authors"))
    author_count = result.fetchone()[0]

    result = conn.execute(text("SELECT COUNT(*) FROM authors WHERE is_unsw_staff = true"))
    unsw_count = result.fetchone()[0]

    print(f"\n作者总数：{author_count:,}")
    print(f"UNSW作者：{unsw_count:,}")

    # 预估时间
    print(f"\n" + "="*80)
    print("预估处理时间（按5请求/秒）")
    print("="*80)

    # OpenAlex API 限制：5请求/秒
    requests_per_second = 5
    seconds_needed = without_authors / requests_per_second
    hours = seconds_needed / 3600

    print(f"待处理文献：{without_authors:,}")
    print(f"预估时间：{hours:.1f} 小时")
    print(f"建议分批处理：每次1000篇，分{without_authors//1000}次")

    print("\n运行命令：")
    print("  测试模式：python3 scripts/populate_authors_from_openalex.py --test")
    print("  处理100篇：python3 scripts/populate_authors_from_openalex.py --limit 100")
    print("  处理1000篇：python3 scripts/populate_authors_from_openalex.py --limit 1000")
    print("  处理全部：python3 scripts/populate_authors_from_openalex.py")
    print("="*80 + "\n")

engine.dispose()
