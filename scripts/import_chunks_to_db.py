"""
将 V2 生成的 chunks JSON 导入到数据库

使用方法:
    python3 scripts/import_chunks_to_db.py
"""
import json
import sys
from pathlib import Path
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.rag_schema import Base, Staff, Publication, Chunk, create_tables
from config.settings import settings


def generate_publication_id(title: str, doi: str = None) -> str:
    """生成 publication ID"""
    if doi:
        return doi
    # 无 DOI 时使用 title 的 hash
    return f"no-doi-{hashlib.md5(title.encode()).hexdigest()}"


def import_chunks_from_json(json_file: str, engine):
    """
    从 JSON 文件导入 chunks 到数据库

    Args:
        json_file: chunks JSON 文件路径
        engine: SQLAlchemy engine
    """
    print("="*80)
    print("导入 Chunks 到数据库")
    print("="*80)

    # 读取 JSON
    print(f"\n1. 读取 JSON 文件: {json_file}")
    with open(json_file, 'r') as f:
        chunks = json.load(f)

    print(f"   ✓ 读取了 {len(chunks)} 个 chunks")

    # 创建 session
    Session = sessionmaker(bind=engine)
    session = Session()

    # 统计
    stats = {
        'staff_added': 0,
        'staff_updated': 0,
        'publications_added': 0,
        'publications_updated': 0,
        'chunks_added': 0,
        'chunks_skipped': 0,
    }

    # 缓存（避免重复处理）
    processed_staff = set()
    processed_publications = set()

    print(f"\n2. 开始导入...")

    try:
        for i, chunk in enumerate(chunks, 1):
            if i % 500 == 0:
                print(f"   处理进度: {i}/{len(chunks)} ({i/len(chunks)*100:.1f}%)")

            chunk_type = chunk.get('chunk_type')
            chunk_id = chunk.get('chunk_id')
            content = chunk.get('content')
            metadata = chunk.get('metadata', {})

            # 提取 staff 信息
            person_email = metadata.get('person_email')
            person_name = metadata.get('person_name')

            if not person_email:
                stats['chunks_skipped'] += 1
                continue

            # 1. 处理 Staff
            if person_email not in processed_staff:
                # 检查是否已存在
                existing_staff = session.query(Staff).filter_by(email=person_email).first()

                if not existing_staff:
                    # 创建新 staff
                    staff = Staff(
                        email=person_email,
                        full_name=person_name or 'Unknown',
                        role=metadata.get('role'),
                        school=metadata.get('person_school') or metadata.get('school'),
                        faculty=metadata.get('faculty'),
                        profile_url=metadata.get('person_profile_url') or metadata.get('profile_url'),
                    )
                    session.add(staff)
                    stats['staff_added'] += 1
                else:
                    stats['staff_updated'] += 1

                processed_staff.add(person_email)

            # 2. 处理 Publication (如果是 publication chunk)
            publication_id = None
            if chunk_type in ['publication_title', 'publication_abstract', 'publication_keywords']:
                pub_title = metadata.get('pub_title')
                pub_doi = metadata.get('pub_doi')

                if pub_title:
                    publication_id = generate_publication_id(pub_title, pub_doi)

                    if publication_id not in processed_publications:
                        # 检查是否已存在
                        existing_pub = session.query(Publication).filter_by(id=publication_id).first()

                        if not existing_pub:
                            # 创建新 publication
                            publication = Publication(
                                id=publication_id,
                                title=pub_title,
                                doi=pub_doi,
                                publication_year=metadata.get('pub_year'),
                                pub_type=metadata.get('pub_type'),
                                venue=metadata.get('pub_venue'),
                                abstract=content if chunk_type == 'publication_abstract' else None,
                                abstract_source=metadata.get('abstract_source', 'none'),
                                citations_count=metadata.get('citations_count', 0),
                                is_open_access=metadata.get('is_open_access', False),
                                has_doi=pub_doi is not None,
                                staff_email=person_email,
                                authors=[]  # 可以从 chunk content 解析
                            )
                            session.add(publication)
                            stats['publications_added'] += 1
                        else:
                            # 更新 abstract（如果这是 abstract chunk）
                            if chunk_type == 'publication_abstract' and not existing_pub.abstract:
                                existing_pub.abstract = content
                                existing_pub.abstract_source = metadata.get('abstract_source', 'none')
                            stats['publications_updated'] += 1

                        processed_publications.add(publication_id)

            # 3. 创建 Chunk
            # 检查是否已存在
            existing_chunk = session.query(Chunk).filter_by(chunk_id=chunk_id).first()

            if not existing_chunk:
                chunk_record = Chunk(
                    chunk_id=chunk_id,
                    chunk_type=chunk_type,
                    content=content,
                    chunk_metadata=metadata,  # 注意：使用 chunk_metadata 而不是 metadata
                    staff_email=person_email,
                    publication_id=publication_id
                )
                session.add(chunk_record)
                stats['chunks_added'] += 1
            else:
                stats['chunks_skipped'] += 1

            # 定期提交（每 1000 条）
            if i % 1000 == 0:
                session.commit()
                print(f"   💾 已提交 {i} 条数据")

        # 最终提交
        session.commit()
        print(f"\n   ✓ 最终提交完成")

    except Exception as e:
        print(f"\n   ❌ 错误: {e}")
        session.rollback()
        raise
    finally:
        session.close()

    # 打印统计
    print(f"\n3. 导入完成")
    print("="*80)
    print("统计:")
    print(f"  Staff:")
    print(f"    新增: {stats['staff_added']}")
    print(f"    更新: {stats['staff_updated']}")
    print(f"  Publications:")
    print(f"    新增: {stats['publications_added']}")
    print(f"    更新: {stats['publications_updated']}")
    print(f"  Chunks:")
    print(f"    新增: {stats['chunks_added']}")
    print(f"    跳过: {stats['chunks_skipped']}")
    print("="*80)

    return stats


def main():
    """主函数"""
    # 配置
    chunks_file = project_root / "rag_chunks_multisource_v2.json"

    if not chunks_file.exists():
        print(f"❌ 错误: 文件不存在: {chunks_file}")
        print(f"   请先运行 parse_publications_multisource_v2.py 生成 chunks")
        return

    # 创建数据库引擎
    print(f"连接数据库: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)

    # 创建表
    print("创建数据库表...")
    create_tables(engine)
    print("✓ 表创建完成")

    # 导入数据
    import_chunks_from_json(str(chunks_file), engine)


if __name__ == "__main__":
    main()
