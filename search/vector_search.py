"""
向量相似度搜索模块

使用余弦相似度进行语义搜索
"""
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import numpy as np

logger = logging.getLogger(__name__)


class VectorSearcher:
    """向量搜索器"""

    def __init__(self, session: Session, embedding_generator=None):
        """
        Args:
            session: 数据库 session
            embedding_generator: 向量生成器（与 step4 使用相同的）
        """
        self.session = session
        self.embedding_generator = embedding_generator

    def search(
        self,
        query: str,
        limit: int = 50,
        chunk_types: List[str] = None,
        similarity_threshold: float = 0.0
    ) -> List[Dict]:
        """
        向量相似度搜索 - pgvector 优化版

        Args:
            query: 搜索查询
            limit: 返回结果数量
            chunk_types: 限制的 chunk 类型列表
            similarity_threshold: 相似度阈值（0-1）

        Returns:
            搜索结果列表
        """
        # 尝试使用 pgvector，如果失败则回退到 NumPy 方法
        try:
            return self.search_with_pgvector(query, limit, chunk_types, similarity_threshold)
        except Exception as e:
            logger.warning(f"pgvector search failed, falling back to NumPy: {e}")
            # 回滚失败的事务
            try:
                self.session.rollback()
            except:
                pass
            return self._search_with_numpy(query, limit, chunk_types, similarity_threshold)

    def _search_with_numpy(
        self,
        query: str,
        limit: int = 50,
        chunk_types: List[str] = None,
        similarity_threshold: float = 0.0
    ) -> List[Dict]:
        """
        NumPy 版本的向量搜索（备用方案）
        """
        # 1. 生成查询向量
        if not self.embedding_generator:
            raise ValueError("Embedding generator not initialized")

        query_embedding = self.embedding_generator.generate_embeddings([query])[0]

        # 2. 获取所有向量
        sql = """
            SELECT
                c.chunk_id,
                c.chunk_type,
                c.content,
                c.chunk_metadata,
                c.staff_profile_url,
                c.publication_id,
                e.vector
            FROM
                chunks c
                JOIN embeddings e ON c.chunk_id = e.chunk_id
        """

        # 添加类型过滤
        where_clauses = []
        params = {}

        if chunk_types:
            placeholders = ','.join([f":type{i}" for i in range(len(chunk_types))])
            where_clauses.append(f"c.chunk_type IN ({placeholders})")
            for i, ct in enumerate(chunk_types):
                params[f"type{i}"] = ct

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        result = self.session.execute(text(sql), params)

        # 3. 使用 NumPy 批量计算相似度
        query_vec = np.array(query_embedding)
        candidates = []

        for row in result:
            doc_vec = np.array(row.vector)
            similarity = self._fast_cosine_similarity(query_vec, doc_vec)

            if similarity >= similarity_threshold:
                candidates.append({
                    "chunk_id": row.chunk_id,
                    "chunk_type": row.chunk_type,
                    "content": row.content,
                    "metadata": row.chunk_metadata,
                    "staff_profile_url": row.staff_profile_url,
                    "publication_id": row.publication_id,
                    "vector_score": float(similarity),
                    "source": "vector"
                })

        # 4. 排序并限制结果
        candidates.sort(key=lambda x: x["vector_score"], reverse=True)
        results = candidates[:limit]

        logger.info(f"Vector search (NumPy) found {len(results)} results for query: '{query}'")
        return results

    def _fast_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        快速计算余弦相似度（使用 NumPy 向量化运算）

        Args:
            vec1: 向量1（NumPy 数组）
            vec2: 向量2（NumPy 数组）

        Returns:
            相似度分数（0-1）
        """
        # 使用 NumPy 向量化运算
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            相似度分数（0-1）
        """
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        # 计算点积
        dot_product = np.dot(vec1, vec2)

        # 计算模
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        # 避免除零
        if norm1 == 0 or norm2 == 0:
            return 0.0

        # 余弦相似度
        similarity = dot_product / (norm1 * norm2)

        return float(similarity)

    def search_with_pgvector(
        self,
        query: str,
        limit: int = 50,
        chunk_types: List[str] = None,
        similarity_threshold: float = 0.0
    ) -> List[Dict]:
        """
        使用 pgvector 扩展进行高效向量搜索（使用 HNSW 索引）

        性能提升：从 30+ 秒降到 < 1 秒！

        Args:
            query: 搜索查询
            limit: 返回结果数量
            chunk_types: 限制的 chunk 类型列表
            similarity_threshold: 相似度阈值（0-1）

        Returns:
            搜索结果列表
        """
        from sqlalchemy import bindparam

        # 1. 生成查询向量
        query_embedding = self.embedding_generator.generate_embeddings([query])[0]

        # 将向量转换为字符串格式：'[0.1, 0.2, ...]'
        vector_str = '[' + ','.join(map(str, query_embedding)) + ']'

        # 2. 构建 SQL（使用字符串格式化避免参数绑定问题）
        # 注意：使用 vector_pgvector 列（不是 vector）

        # 构建基础查询
        sql_parts = []
        sql_parts.append(f"""
            SELECT
                c.chunk_id,
                c.chunk_type,
                c.content,
                c.chunk_metadata,
                c.staff_profile_url,
                c.publication_id,
                1 - (e.vector_pgvector <=> '{vector_str}'::vector) AS similarity
            FROM
                chunks c
                JOIN embeddings e ON c.chunk_id = e.chunk_id
        """)

        # 添加 WHERE 子句
        where_clauses = []
        params = {}

        if chunk_types:
            placeholders = ','.join([f":type{i}" for i in range(len(chunk_types))])
            where_clauses.append(f"c.chunk_type IN ({placeholders})")
            for i, ct in enumerate(chunk_types):
                params[f"type{i}"] = ct

        # 添加相似度阈值过滤
        if similarity_threshold > 0:
            where_clauses.append(f"(1 - (e.vector_pgvector <=> '{vector_str}'::vector)) >= {similarity_threshold}")

        if where_clauses:
            sql_parts.append(" WHERE " + " AND ".join(where_clauses))

        # 添加排序和限制
        sql_parts.append(f"""
            ORDER BY e.vector_pgvector <=> '{vector_str}'::vector
            LIMIT {limit}
        """)

        sql = " ".join(sql_parts)

        # 执行查询
        result = self.session.execute(text(sql), params)

        results = []
        for row in result:
            results.append({
                "chunk_id": row.chunk_id,
                "chunk_type": row.chunk_type,
                "content": row.content,
                "metadata": row.chunk_metadata,
                "staff_profile_url": row.staff_profile_url,
                "publication_id": row.publication_id,
                "vector_score": float(row.similarity),
                "source": "vector_pgvector"
            })

        logger.info(f"pgvector search found {len(results)} results (HNSW accelerated)")
        return results
