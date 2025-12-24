"""
将 embeddings 表的 vector (JSON) 迁移到 vector_pgvector (pgvector类型)

使用方法:
    python3 scripts/migrate_to_pgvector.py
"""
import sys
from pathlib import Path
import logging
from tqdm import tqdm

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_vectors(session, batch_size=1000):
    """迁移 vector 到 vector_pgvector"""

    # 1. 统计需要迁移的数量
    result = session.execute(text("""
        SELECT COUNT(*) as total,
               COUNT(vector_pgvector) as already_migrated
        FROM embeddings
    """))
    row = result.fetchone()
    total = row.total
    already_migrated = row.already_migrated

    logger.info(f"Total embeddings: {total:,}")
    logger.info(f"Already migrated: {already_migrated:,}")
    logger.info(f"Need to migrate: {(total - already_migrated):,}")

    if already_migrated == total:
        logger.info("✓ All embeddings already migrated!")
        return

    # 2. 批量迁移
    logger.info(f"\nStarting migration with batch_size={batch_size}...")

    # 使用 UPDATE 语句将 JSON 数组转换为 pgvector 类型
    # PostgreSQL 可以直接将 JSON 数组转换为 vector 类型
    sql = text("""
        UPDATE embeddings
        SET vector_pgvector = vector::text::vector
        WHERE vector_pgvector IS NULL
    """)

    # 执行更新
    logger.info("Converting JSON vectors to pgvector format...")
    result = session.execute(sql)
    session.commit()

    updated_count = result.rowcount
    logger.info(f"✓ Migrated {updated_count:,} embeddings")

    # 3. 验证迁移结果
    result = session.execute(text("""
        SELECT COUNT(*) as migrated
        FROM embeddings
        WHERE vector_pgvector IS NOT NULL
    """))
    migrated = result.fetchone().migrated

    logger.info(f"\nMigration complete!")
    logger.info(f"Total migrated: {migrated:,} / {total:,}")

    if migrated == total:
        logger.info("✓ All embeddings successfully migrated!")
    else:
        logger.warning(f"⚠ Missing {total - migrated:,} embeddings")


def create_hnsw_index(session):
    """创建 HNSW 索引以加速向量搜索"""

    logger.info("\nCreating HNSW index for fast vector search...")
    logger.info("This may take a few minutes for 120k+ vectors...")

    try:
        # 先删除旧索引（如果存在）
        session.execute(text("DROP INDEX IF EXISTS embeddings_vector_pgvector_idx"))
        session.commit()

        # 创建 HNSW 索引（使用余弦距离）
        session.execute(text("""
            CREATE INDEX embeddings_vector_pgvector_idx
            ON embeddings
            USING hnsw (vector_pgvector vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
        session.commit()

        logger.info("✓ HNSW index created successfully!")
        logger.info("  - Index type: HNSW")
        logger.info("  - Distance: Cosine")
        logger.info("  - Parameters: m=16, ef_construction=64")

    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        session.rollback()
        raise


def main():
    """主函数"""

    print("\n" + "="*80)
    print("MIGRATE VECTORS TO PGVECTOR")
    print("="*80 + "\n")

    # 连接数据库
    logger.info(f"Connecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 检查 pgvector 扩展
        result = session.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        if not result.fetchone():
            logger.error("pgvector extension not installed!")
            logger.error("Run: CREATE EXTENSION vector;")
            return

        logger.info("✓ pgvector extension is installed")

        # 2. 检查 vector_pgvector 列是否存在
        result = session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'embeddings'
            AND column_name = 'vector_pgvector'
        """))

        if not result.fetchone():
            logger.error("vector_pgvector column does not exist!")
            logger.error("Run: ALTER TABLE embeddings ADD COLUMN vector_pgvector vector(1536);")
            return

        logger.info("✓ vector_pgvector column exists")

        # 3. 执行迁移
        migrate_vectors(session)

        # 4. 创建索引
        create_hnsw_index(session)

        print("\n" + "="*80)
        print("MIGRATION COMPLETE!")
        print("="*80)
        print("\nYou can now use fast pgvector search!")
        print("The warning about pgvector should disappear.\n")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
