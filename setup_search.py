"""
设置搜索引擎 - 一次性运行

功能:
1. 设置 BM25 全文搜索（创建 tsvector 列和索引）
2. 检查 embeddings 是否已生成

使用方法:
    python3 setup_search.py
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from search.bm25_search import BM25Searcher
from database.rag_schema import Embedding

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("="*80)
    logger.info("设置搜索引擎")
    logger.info("="*80)

    # 连接数据库
    logger.info(f"\n连接数据库: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 设置 BM25 全文搜索
        logger.info("\n[1/2] 设置 BM25 全文搜索...")
        logger.info("这会创建 tsvector 列和 GIN 索引（可能需要几分钟）")

        bm25 = BM25Searcher(session)
        bm25.setup_full_text_search()

        logger.info("✓ BM25 全文搜索设置完成")

        # 2. 检查 embeddings
        logger.info("\n[2/2] 检查 embeddings...")
        embedding_count = session.query(Embedding).count()

        if embedding_count == 0:
            logger.warning("⚠️  Embeddings 未生成!")
            logger.info("\n请运行以下命令生成 embeddings:")
            logger.info("  export OPENAI_API_KEY='your-key'")
            logger.info("  python3 pipeline/step4_generate_embeddings.py")
            logger.info("\n或使用本地模型（免费）:")
            logger.info("  python3 pipeline/step4_generate_embeddings.py --model local")
        else:
            logger.info(f"✓ 已有 {embedding_count:,} 个 embeddings")

        logger.info("\n" + "="*80)
        logger.info("✓ 搜索引擎设置完成!")
        logger.info("="*80)

        logger.info("\n现在可以运行搜索:")
        logger.info("  python3 test_search.py --query 'Industry 4.0'")

    except Exception as e:
        logger.error(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
