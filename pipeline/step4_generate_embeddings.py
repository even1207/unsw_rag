"""
Step 4: 生成 Embeddings (向量嵌入)

功能:
1. 读取 data/processed/rag_chunks.json
2. 为每个 chunk 生成向量嵌入
3. 存储到数据库 embeddings 表

支持的 Embedding 模型:
- OpenAI: text-embedding-3-small (推荐, 1536维)
- OpenAI: text-embedding-ada-002 (旧版, 1536维)
- 本地模型: sentence-transformers (可选)

使用方法:
    # 使用 OpenAI API
    export OPENAI_API_KEY="your-api-key"
    python3 pipeline/step4_generate_embeddings.py

    # 使用本地模型 (不需要API key)
    python3 pipeline/step4_generate_embeddings.py --model local
"""
import json
import sys
import os
from pathlib import Path
from typing import List, Dict
import time
from tqdm import tqdm
import logging

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from database.rag_schema import Chunk, Embedding, create_tables

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
CONFIG = {
    "batch_size": 200,  # 每批处理的 chunk 数量（平衡速度和速率限制）
    "model": "text-embedding-3-small",  # OpenAI 模型
    "dimension": 1536,  # 向量维度
    "max_retries": 3,
    "retry_delay": 2.0,
}


class EmbeddingGenerator:
    """向量生成器"""

    def __init__(self, model_type="openai", model_name=None):
        self.model_type = model_type
        self.model_name = model_name or CONFIG["model"]

        if model_type == "openai":
            self._init_openai()
        elif model_type == "local" :
            self._init_local()
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _init_openai(self):
        """初始化 OpenAI"""
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY not found. "
                    "Set it in environment or config/settings.py"
                )

            self.client = OpenAI(api_key=api_key)
            logger.info(f"✓ OpenAI client initialized with model: {self.model_name}")
        except ImportError:
            logger.error("OpenAI library not installed. Run: pip install openai")
            sys.exit(1)

    def _init_local(self):
        """初始化本地 Sentence Transformers 模型"""
        try:
            from sentence_transformers import SentenceTransformer

            # 使用轻量级但效果好的模型
            self.model_name = "all-MiniLM-L6-v2"
            self.model = SentenceTransformer(self.model_name)
            CONFIG["dimension"] = self.model.get_sentence_embedding_dimension()

            logger.info(f"✓ Local model loaded: {self.model_name}")
            logger.info(f"  Dimension: {CONFIG['dimension']}")
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            sys.exit(1)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        生成向量嵌入

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if self.model_type == "openai":
            return self._generate_openai(texts)
        elif self.model_type == "local":
            return self._generate_local(texts)

    def _generate_openai(self, texts: List[str]) -> List[List[float]]:
        """使用 OpenAI API 生成"""
        retries = 0
        while retries < CONFIG["max_retries"]:
            try:
                response = self.client.embeddings.create(
                    input=texts,
                    model=self.model_name
                )

                embeddings = [item.embedding for item in response.data]
                return embeddings

            except Exception as e:
                retries += 1
                if retries >= CONFIG["max_retries"]:
                    logger.error(f"Failed after {CONFIG['max_retries']} retries: {e}")
                    raise

                logger.warning(f"Retry {retries}/{CONFIG['max_retries']}: {e}")
                time.sleep(CONFIG["retry_delay"])

    def _generate_local(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型生成"""
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()


def load_chunks_from_db(session) -> List[Dict]:
    """从数据库加载所有 chunks"""
    logger.info("Loading chunks from database...")

    chunks = session.query(Chunk).all()

    chunk_list = []
    for chunk in chunks:
        chunk_list.append({
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "chunk_type": chunk.chunk_type
        })

    logger.info(f"✓ Loaded {len(chunk_list)} chunks from database")
    return chunk_list


def check_existing_embeddings(session) -> set:
    """检查已存在的 embeddings"""
    logger.info("Checking existing embeddings...")

    existing = session.query(Embedding.chunk_id).all()
    existing_ids = {row[0] for row in existing}

    logger.info(f"✓ Found {len(existing_ids)} existing embeddings")
    return existing_ids


def process_chunks(chunks: List[Dict], generator: EmbeddingGenerator,
                   session, existing_ids: set):
    """
    处理所有 chunks 并生成 embeddings

    Args:
        chunks: chunk 列表
        generator: 向量生成器
        session: 数据库 session
        existing_ids: 已存在的 embedding IDs
    """
    # 过滤已存在的
    chunks_to_process = [
        c for c in chunks
        if c["chunk_id"] not in existing_ids
    ]

    if not chunks_to_process:
        logger.info("✓ All chunks already have embeddings!")
        return

    logger.info(f"Processing {len(chunks_to_process)} new chunks...")

    batch_size = CONFIG["batch_size"]
    total_batches = (len(chunks_to_process) + batch_size - 1) // batch_size

    # 进度条
    pbar = tqdm(total=len(chunks_to_process), desc="Generating embeddings")

    for i in range(0, len(chunks_to_process), batch_size):
        batch = chunks_to_process[i:i + batch_size]

        # 提取文本
        texts = [c["content"] for c in batch]
        chunk_ids = [c["chunk_id"] for c in batch]

        try:
            # 生成 embeddings
            embeddings = generator.generate_embeddings(texts)

            # 保存到数据库
            for chunk_id, embedding in zip(chunk_ids, embeddings):
                emb_record = Embedding(
                    chunk_id=chunk_id,
                    vector=embedding,  # 存储为 JSON
                    model=generator.model_name
                )
                session.add(emb_record)

            # 每批提交一次
            session.commit()

            pbar.update(len(batch))

            # API 限流延迟 - 避免触发速率限制
            if generator.model_type == "openai":
                time.sleep(0.2)

        except Exception as e:
            logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
            session.rollback()
            raise

    pbar.close()
    logger.info(f"✓ Successfully generated {len(chunks_to_process)} embeddings")


def verify_embeddings(session):
    """验证生成的 embeddings"""
    logger.info("\nVerifying embeddings...")

    total_chunks = session.query(Chunk).count()
    total_embeddings = session.query(Embedding).count()

    logger.info(f"  Total chunks: {total_chunks}")
    logger.info(f"  Total embeddings: {total_embeddings}")

    if total_chunks == total_embeddings:
        logger.info("  ✓ All chunks have embeddings!")
    else:
        logger.warning(f"  ⚠ Missing {total_chunks - total_embeddings} embeddings")

    # 检查向量维度
    sample = session.query(Embedding).first()
    if sample:
        vector_dim = len(sample.vector)
        logger.info(f"  Vector dimension: {vector_dim}")
        logger.info(f"  Model: {sample.model}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate embeddings for RAG chunks")
    parser.add_argument(
        "--model",
        choices=["openai", "local"],
        default="openai",
        help="Model type: openai (default) or local"
    )
    parser.add_argument(
        "--model-name",
        help="Specific model name (optional)"
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("Step 4: Generate Embeddings")
    logger.info("="*80)

    # 检查数据库连接
    logger.info(f"\nConnecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)

    # 确保表存在
    create_tables(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 加载 chunks
        chunks = load_chunks_from_db(session)

        if not chunks:
            logger.error("No chunks found in database!")
            logger.error("Please run step3_import_to_database.py first")
            return

        # 2. 检查已存在的 embeddings
        existing_ids = check_existing_embeddings(session)

        # 3. 初始化生成器
        logger.info(f"\nInitializing {args.model} embedding generator...")
        generator = EmbeddingGenerator(
            model_type=args.model,
            model_name=args.model_name
        )

        # 4. 生成 embeddings
        logger.info("\n" + "="*80)
        process_chunks(chunks, generator, session, existing_ids)

        # 5. 验证
        verify_embeddings(session)

        logger.info("\n" + "="*80)
        logger.info("✓ Step 4 Complete!")
        logger.info("="*80)
        logger.info("\nNext steps:")
        logger.info("  - Run search API to test hybrid search")
        logger.info("  - See: api/search.py")

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
