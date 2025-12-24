"""
Step 3: 导入 Chunks 到数据库

功能:
1. 创建数据库表结构
2. 从 data/processed/rag_chunks.json 读取数据
3. 导入到 PostgreSQL 数据库

使用方法:
    python3 pipeline/step3_import_to_database.py

数据库连接配置在 config/settings.py 中设置
"""
import json
import sys
from pathlib import Path
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.rag_schema import Base, Staff, Publication, Chunk, create_tables
from config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
CONFIG = {
    "chunks_file": PROJECT_ROOT / "data/processed/rag_chunks.json",
}


def generate_publication_id(title: str, doi: str = None) -> str:
    """生成 publication ID"""
    if doi:
        return doi
    # 无 DOI 时使用 title 的 hash
    return f"no-doi-{hashlib.md5(title.encode()).hexdigest()}"


def import_chunks_from_json(json_file: str, engine):
    """从 JSON 文件导入 chunks 到数据库"""
    logger.info("="*80)
    logger.info("Step 3: 导入 Chunks 到数据库")
    logger.info("="*80)

    # 读取 JSON
    logger.info(f"\n1. 读取 JSON 文件: {json_file}")
    with open(json_file, 'r') as f:
        chunks = json.load(f)

    logger.info(f"   ✓ 读取了 {len(chunks)} 个 chunks")

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

    logger.info(f"\n2. 开始导入...")

    try:
        for i, chunk in enumerate(chunks, 1):
            if i % 500 == 0:
                logger.info(f"   处理进度: {i}/{len(chunks)} ({i/len(chunks)*100:.1f}%)")

            chunk_type = chunk.get('chunk_type')
            chunk_id = chunk.get('chunk_id')
            content = chunk.get('content')
            metadata = chunk.get('metadata', {})

            # 提取 staff 信息 (使用 profile_url 作为主键)
            person_profile_url = metadata.get('person_profile_url') or metadata.get('profile_url')
            person_name = metadata.get('person_name')
            person_email = metadata.get('person_email')

            if not person_profile_url:
                stats['chunks_skipped'] += 1
                continue

            # 1. 处理 Staff
            if person_profile_url not in processed_staff:
                existing_staff = session.query(Staff).filter_by(profile_url=person_profile_url).first()

                if not existing_staff:
                    staff = Staff(
                        profile_url=person_profile_url,
                        email=person_email,
                        full_name=person_name or 'Unknown',
                        role=metadata.get('role'),
                        school=metadata.get('person_school') or metadata.get('school'),
                        faculty=metadata.get('faculty'),
                    )
                    session.add(staff)
                    stats['staff_added'] += 1
                else:
                    stats['staff_updated'] += 1

                processed_staff.add(person_profile_url)

            # 2. 处理 Publication
            publication_id = None
            if chunk_type in ['publication_title', 'publication_abstract', 'publication_keywords']:
                pub_title = metadata.get('pub_title')
                pub_doi = metadata.get('pub_doi')

                if pub_title:
                    publication_id = generate_publication_id(pub_title, pub_doi)

                    if publication_id not in processed_publications:
                        existing_pub = session.query(Publication).filter_by(id=publication_id).first()

                        if not existing_pub:
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
                                staff_profile_url=person_profile_url,
                                authors=[]
                            )
                            session.add(publication)
                            stats['publications_added'] += 1
                        else:
                            # 更新 abstract
                            if chunk_type == 'publication_abstract' and not existing_pub.abstract:
                                existing_pub.abstract = content
                                existing_pub.abstract_source = metadata.get('abstract_source', 'none')
                            stats['publications_updated'] += 1

                        processed_publications.add(publication_id)

            # 3. 创建 Chunk
            existing_chunk = session.query(Chunk).filter_by(chunk_id=chunk_id).first()

            if not existing_chunk:
                chunk_record = Chunk(
                    chunk_id=chunk_id,
                    chunk_type=chunk_type,
                    content=content,
                    chunk_metadata=metadata,
                    staff_profile_url=person_profile_url,
                    publication_id=publication_id
                )
                session.add(chunk_record)
                stats['chunks_added'] += 1
            else:
                stats['chunks_skipped'] += 1

            # 定期提交
            if i % 1000 == 0:
                session.commit()
                logger.info(f"   💾 已提交 {i} 条数据")

        # 最终提交
        session.commit()
        logger.info(f"\n   ✓ 最终提交完成")

    except Exception as e:
        logger.error(f"\n   ❌ 错误: {e}")
        session.rollback()
        raise
    finally:
        session.close()

    # 打印统计
    logger.info(f"\n3. 导入完成")
    logger.info("="*80)
    logger.info("统计:")
    logger.info(f"  Staff:")
    logger.info(f"    新增: {stats['staff_added']}")
    logger.info(f"    更新: {stats['staff_updated']}")
    logger.info(f"  Publications:")
    logger.info(f"    新增: {stats['publications_added']}")
    logger.info(f"    更新: {stats['publications_updated']}")
    logger.info(f"  Chunks:")
    logger.info(f"    新增: {stats['chunks_added']}")
    logger.info(f"    跳过: {stats['chunks_skipped']}")
    logger.info("="*80)

    return stats


def main():
    """主函数"""
    chunks_file = CONFIG["chunks_file"]

    if not chunks_file.exists():
        logger.error(f"❌ 错误: 文件不存在: {chunks_file}")
        logger.error(f"   请先运行 step2_parse_publications.py 生成 chunks")
        return

    # 创建数据库引擎
    logger.info(f"连接数据库: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)

    # 创建表
    logger.info("创建数据库表...")
    create_tables(engine)
    logger.info("✓ 表创建完成\n")

    # 导入数据
    import_chunks_from_json(str(chunks_file), engine)

    logger.info(f"\n✓ 数据导入完成!")


if __name__ == "__main__":
    main()
