"""
混合搜索 API - 方案C 专业版

集成 BM25 + Vector + RRF + Reranker + Citation
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import logging

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from search.bm25_search import BM25Searcher
from search.vector_search import VectorSearcher
from search.fusion import HybridFusion
from search.reranker import Reranker
from search.citation import CitationFormatter

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    混合搜索引擎 - 专业版

    流程:
    1. BM25 + Vector 并行检索 → Top 50 each
    2. RRF 融合 → Top 80
    3. Reranker 重排 → Top 10-20
    4. Citation 格式化 → 返回结果
    """

    def __init__(
        self,
        session: Session,
        embedding_generator,
        use_reranker: bool = True,
        reranker_model: str = "local"
    ):
        """
        Args:
            session: 数据库 session
            embedding_generator: 向量生成器
            use_reranker: 是否使用 reranker
            reranker_model: reranker 模型类型
        """
        self.session = session
        self.embedding_generator = embedding_generator

        # 初始化各个组件
        logger.info("Initializing search components...")

        self.bm25_searcher = BM25Searcher(session)
        self.vector_searcher = VectorSearcher(session, embedding_generator)
        self.citation_formatter = CitationFormatter(session)

        # 可选：Reranker
        self.use_reranker = use_reranker
        if use_reranker:
            try:
                self.reranker = Reranker(model_type=reranker_model)
                logger.info("✓ Reranker initialized")
            except Exception as e:
                logger.warning(f"Reranker initialization failed: {e}")
                logger.info("  Continuing without reranker")
                self.use_reranker = False

        logger.info("✓ Search engine initialized")

    def search(
        self,
        query: str,
        top_k: int = 10,
        chunk_types: List[str] = None,
        filters: Dict = None,
        include_scores: bool = True,
        citation_style: str = "apa"
    ) -> Dict:
        """
        执行混合搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            chunk_types: 限制的 chunk 类型
            filters: 额外过滤条件
            include_scores: 是否包含分数详情
            citation_style: 引用格式

        Returns:
            搜索结果字典
        """
        logger.info(f"="*80)
        logger.info(f"Search query: '{query}'")
        logger.info(f"="*80)

        # ========== Step 1: 并行检索 ==========
        logger.info("\n[Step 1] Parallel Retrieval (BM25 + Vector)")

        # BM25 检索
        logger.info("  → BM25 search...")
        bm25_results = self.bm25_searcher.search(
            query=query,
            limit=50,
            chunk_types=chunk_types
        )
        logger.info(f"    ✓ BM25 found {len(bm25_results)} results")

        # Vector 检索
        logger.info("  → Vector search...")
        vector_results = self.vector_searcher.search(
            query=query,
            limit=50,
            chunk_types=chunk_types
        )
        logger.info(f"    ✓ Vector found {len(vector_results)} results")

        # ========== Step 2: RRF 融合 ==========
        logger.info("\n[Step 2] RRF Fusion")

        fused_results = HybridFusion.reciprocal_rank_fusion(
            results_lists=[bm25_results, vector_results],
            k=60
        )
        logger.info(f"  ✓ Fused to {len(fused_results)} unique documents")

        # 取前 80 个作为候选
        candidate_results = fused_results[:80]
        logger.info(f"  → Candidate set: {len(candidate_results)} documents")

        # ========== Step 3: Reranker 重排序 ==========
        if self.use_reranker:
            logger.info("\n[Step 3] Reranking")

            reranked_results = self.reranker.rerank_with_metadata(
                query=query,
                documents=candidate_results,
                top_k=top_k,
                boost_fields={
                    "citations_count": 0.1,
                    "is_open_access": 0.05,
                    "publication_year": 0.05
                }
            )
            logger.info(f"  ✓ Reranked to top {len(reranked_results)} results")

            final_results = reranked_results
        else:
            logger.info("\n[Step 3] Reranking (Skipped)")
            final_results = candidate_results[:top_k]

        # ========== Step 4: Citation 格式化 ==========
        logger.info("\n[Step 4] Citation Formatting")

        formatted_response = self.citation_formatter.create_answer_with_citations(
            query=query,
            results=final_results,
            max_citations=top_k
        )
        logger.info(f"  ✓ Formatted {len(formatted_response['citations'])} citations")

        # ========== 添加额外信息 ==========
        response = {
            "query": query,
            "total_results": len(fused_results),
            "returned_results": len(final_results),
            "citations": formatted_response["citations"],
            "search_metadata": {
                "bm25_results": len(bm25_results),
                "vector_results": len(vector_results),
                "fused_results": len(fused_results),
                "reranked": self.use_reranker,
                "filters_applied": filters or {}
            }
        }

        if include_scores:
            response["score_breakdown"] = self._get_score_breakdown(final_results)

        logger.info(f"\n{'='*80}")
        logger.info(f"✓ Search complete: {len(final_results)} results")
        logger.info(f"{'='*80}\n")

        return response

    def _get_score_breakdown(self, results: List[Dict]) -> Dict:
        """获取分数统计"""
        if not results:
            return {}

        breakdown = {
            "bm25_scores": [r.get("bm25_score", 0) for r in results],
            "vector_scores": [r.get("vector_score", 0) for r in results],
            "rrf_scores": [r.get("rrf_score", 0) for r in results],
        }

        if self.use_reranker:
            breakdown["rerank_scores"] = [r.get("rerank_score", 0) for r in results]

        # 统计 - 使用 list() 创建副本避免 RuntimeError
        for key in list(breakdown.keys()):
            scores = breakdown[key]
            breakdown[f"{key}_avg"] = sum(scores) / len(scores) if scores else 0
            breakdown[f"{key}_max"] = max(scores) if scores else 0
            breakdown[f"{key}_min"] = min(scores) if scores else 0

        return breakdown

    def setup(self):
        """设置搜索引擎（创建索引等）"""
        logger.info("Setting up search engine...")

        # 设置 BM25 全文搜索
        self.bm25_searcher.setup_full_text_search()

        logger.info("✓ Search engine setup complete")

    def search_publications_only(
        self,
        query: str,
        top_k: int = 10,
        year_from: int = None,
        year_to: int = None,
        has_abstract: bool = True
    ) -> Dict:
        """
        只搜索论文

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            year_from: 年份起始
            year_to: 年份结束
            has_abstract: 是否必须有摘要

        Returns:
            搜索结果
        """
        return self.search(
            query=query,
            top_k=top_k,
            chunk_types=["publication_abstract", "publication_title"],
            filters={
                "year_from": year_from,
                "year_to": year_to,
                "has_abstract": has_abstract
            }
        )

    def search_researchers_only(
        self,
        query: str,
        top_k: int = 10,
        school: str = None
    ) -> Dict:
        """
        只搜索研究人员

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            school: 学院过滤

        Returns:
            搜索结果
        """
        return self.search(
            query=query,
            top_k=top_k,
            chunk_types=["person_biography", "person_basic"],
            filters={"school": school}
        )
