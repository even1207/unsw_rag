"""
BM25 全文搜索模块

使用 PostgreSQL 全文搜索功能实现 BM25 算法
"""
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import logging

logger = logging.getLogger(__name__)


class BM25Searcher:
    """BM25 搜索器（使用 PostgreSQL 全文搜索）"""

    def __init__(self, session: Session):
        self.session = session

    def setup_full_text_search(self):
        """
        设置 PostgreSQL 全文搜索
        创建 tsvector 列和 GIN 索引
        """
        logger.info("Setting up full-text search...")

        try:
            # 1. 添加 tsvector 列（如果不存在）
            self.session.execute(text("""
                ALTER TABLE chunks
                ADD COLUMN IF NOT EXISTS content_tsv tsvector;
            """))

            # 2. 更新 tsvector 列
            self.session.execute(text("""
                UPDATE chunks
                SET content_tsv = to_tsvector('english', content)
                WHERE content_tsv IS NULL;
            """))

            # 3. 创建 GIN 索引（加速搜索）
            self.session.execute(text("""
                CREATE INDEX IF NOT EXISTS chunks_content_tsv_idx
                ON chunks
                USING GIN (content_tsv);
            """))

            # 4. 创建触发器（自动更新 tsvector）
            self.session.execute(text("""
                CREATE OR REPLACE FUNCTION chunks_tsv_trigger() RETURNS trigger AS $$
                BEGIN
                    NEW.content_tsv := to_tsvector('english', NEW.content);
                    RETURN NEW;
                END
                $$ LANGUAGE plpgsql;
            """))

            self.session.execute(text("""
                DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks;
                CREATE TRIGGER chunks_tsv_update
                BEFORE INSERT OR UPDATE ON chunks
                FOR EACH ROW EXECUTE FUNCTION chunks_tsv_trigger();
            """))

            self.session.commit()
            logger.info("✓ Full-text search setup complete")

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error setting up full-text search: {e}")
            raise

    def search(
        self,
        query: str,
        limit: int = 50,
        chunk_types: List[str] = None
    ) -> List[Dict]:
        """
        BM25 搜索

        Args:
            query: 搜索查询
            limit: 返回结果数量
            chunk_types: 限制的 chunk 类型列表

        Returns:
            搜索结果列表，包含 chunk_id, score, content 等
        """
        # 转换查询为 tsquery
        tsquery = self._build_tsquery(query)

        # 构建 SQL 查询
        sql = """
            SELECT
                chunk_id,
                chunk_type,
                content,
                chunk_metadata,
                staff_profile_url,
                publication_id,
                ts_rank_cd(content_tsv, query) AS bm25_score
            FROM
                chunks,
                to_tsquery('english', :tsquery) query
            WHERE
                content_tsv @@ query
        """

        # 添加类型过滤
        if chunk_types:
            placeholders = ','.join([f":type{i}" for i in range(len(chunk_types))])
            sql += f" AND chunk_type IN ({placeholders})"

        sql += """
            ORDER BY bm25_score DESC
            LIMIT :limit
        """

        # 执行查询
        params = {"tsquery": tsquery, "limit": limit}
        if chunk_types:
            for i, ct in enumerate(chunk_types):
                params[f"type{i}"] = ct

        result = self.session.execute(text(sql), params)

        # 格式化结果
        results = []
        for row in result:
            results.append({
                "chunk_id": row.chunk_id,
                "chunk_type": row.chunk_type,
                "content": row.content,
                "metadata": row.chunk_metadata,
                "staff_profile_url": row.staff_profile_url,
                "publication_id": row.publication_id,
                "bm25_score": float(row.bm25_score),
                "source": "bm25"
            })

        logger.info(f"BM25 search found {len(results)} results for query: '{query}'")
        return results

    def _build_tsquery(self, query: str) -> str:
        """
        构建 PostgreSQL tsquery

        将用户查询转换为 PostgreSQL 全文搜索查询格式
        """
        # 简单处理：将空格替换为 & (AND)
        # 可以扩展支持更复杂的查询语法
        terms = query.strip().split()

        # 处理特殊字符
        cleaned_terms = []
        for term in terms:
            # 移除特殊字符
            term = ''.join(c for c in term if c.isalnum() or c in ['-', '_'])
            if term:
                cleaned_terms.append(term)

        if not cleaned_terms:
            return ""

        # 使用 & 连接（AND 语义）
        tsquery = ' & '.join(cleaned_terms)

        return tsquery

    def search_with_filter(
        self,
        query: str,
        limit: int = 50,
        school: str = None,
        year_from: int = None,
        year_to: int = None,
        has_abstract: bool = None
    ) -> List[Dict]:
        """
        带过滤条件的搜索

        Args:
            query: 搜索查询
            limit: 返回结果数量
            school: 学院过滤
            year_from: 年份起始
            year_to: 年份结束
            has_abstract: 是否有摘要

        Returns:
            搜索结果列表
        """
        tsquery = self._build_tsquery(query)

        sql = """
            SELECT
                c.chunk_id,
                c.chunk_type,
                c.content,
                c.chunk_metadata,
                c.staff_profile_url,
                c.publication_id,
                ts_rank_cd(c.content_tsv, query) AS bm25_score
            FROM
                chunks c
                LEFT JOIN staff s ON c.staff_profile_url = s.profile_url
                LEFT JOIN publications p ON c.publication_id = p.id,
                to_tsquery('english', :tsquery) query
            WHERE
                c.content_tsv @@ query
        """

        params = {"tsquery": tsquery, "limit": limit}

        # 添加过滤条件
        if school:
            sql += " AND s.school = :school"
            params["school"] = school

        if year_from:
            sql += " AND p.publication_year >= :year_from"
            params["year_from"] = year_from

        if year_to:
            sql += " AND p.publication_year <= :year_to"
            params["year_to"] = year_to

        if has_abstract is not None:
            sql += " AND p.abstract IS NOT NULL" if has_abstract else " AND p.abstract IS NULL"

        sql += """
            ORDER BY bm25_score DESC
            LIMIT :limit
        """

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
                "bm25_score": float(row.bm25_score),
                "source": "bm25"
            })

        return results
