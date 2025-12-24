"""
混合检索融合算法

实现 RRF (Reciprocal Rank Fusion) 和其他融合方法
"""
from typing import List, Dict
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class HybridFusion:
    """混合检索结果融合器"""

    @staticmethod
    def reciprocal_rank_fusion(
        results_lists: List[List[Dict]],
        k: int = 60
    ) -> List[Dict]:
        """
        RRF (Reciprocal Rank Fusion) 算法

        论文: Cormack, G. V., Clarke, C. L., & Buettcher, S. (2009).
        Reciprocal rank fusion outperforms condorcet and individual
        rank learning methods.

        公式: RRF(d) = Σ 1/(k + rank(d))

        Args:
            results_lists: 多个检索结果列表
            k: RRF 参数（默认60）

        Returns:
            融合后的结果列表
        """
        # 累积每个文档的 RRF 分数
        rrf_scores = defaultdict(float)
        doc_info = {}  # 存储文档完整信息

        for results in results_lists:
            for rank, doc in enumerate(results, start=1):
                chunk_id = doc["chunk_id"]

                # 计算 RRF 分数
                rrf_score = 1.0 / (k + rank)
                rrf_scores[chunk_id] += rrf_score

                # 保存文档信息（如果还没有）
                if chunk_id not in doc_info:
                    doc_info[chunk_id] = doc

        # 转换为列表并排序
        fused_results = []
        for chunk_id, rrf_score in rrf_scores.items():
            doc = doc_info[chunk_id].copy()
            doc["rrf_score"] = rrf_score

            # 保留原始分数
            if "bm25_score" not in doc:
                doc["bm25_score"] = 0.0
            if "vector_score" not in doc:
                doc["vector_score"] = 0.0

            fused_results.append(doc)

        # 按 RRF 分数排序
        fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)

        logger.info(f"RRF fusion: {len(fused_results)} unique documents")
        return fused_results

    @staticmethod
    def weighted_fusion(
        bm25_results: List[Dict],
        vector_results: List[Dict],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        normalize: bool = True
    ) -> List[Dict]:
        """
        加权融合算法

        Score = α * BM25_score + β * Vector_score

        Args:
            bm25_results: BM25 搜索结果
            vector_results: Vector 搜索结果
            bm25_weight: BM25 权重
            vector_weight: Vector 权重
            normalize: 是否归一化分数

        Returns:
            融合后的结果列表
        """
        # 归一化分数
        if normalize:
            bm25_results = HybridFusion._normalize_scores(
                bm25_results, "bm25_score"
            )
            vector_results = HybridFusion._normalize_scores(
                vector_results, "vector_score"
            )

        # 合并结果
        combined = {}

        for doc in bm25_results:
            chunk_id = doc["chunk_id"]
            combined[chunk_id] = doc.copy()
            combined[chunk_id]["bm25_score"] = doc.get("bm25_score", 0.0)
            combined[chunk_id]["vector_score"] = 0.0
            combined[chunk_id]["weighted_score"] = (
                bm25_weight * doc.get("bm25_score", 0.0)
            )

        for doc in vector_results:
            chunk_id = doc["chunk_id"]
            vector_score = doc.get("vector_score", 0.0)

            if chunk_id in combined:
                # 已存在，更新 vector 分数
                combined[chunk_id]["vector_score"] = vector_score
                combined[chunk_id]["weighted_score"] += vector_weight * vector_score
            else:
                # 新文档
                combined[chunk_id] = doc.copy()
                combined[chunk_id]["bm25_score"] = 0.0
                combined[chunk_id]["vector_score"] = vector_score
                combined[chunk_id]["weighted_score"] = vector_weight * vector_score

        # 转换为列表并排序
        fused_results = list(combined.values())
        fused_results.sort(key=lambda x: x["weighted_score"], reverse=True)

        logger.info(f"Weighted fusion: {len(fused_results)} documents")
        return fused_results

    @staticmethod
    def _normalize_scores(
        results: List[Dict],
        score_field: str
    ) -> List[Dict]:
        """
        归一化分数到 [0, 1]

        Args:
            results: 结果列表
            score_field: 分数字段名

        Returns:
            归一化后的结果列表
        """
        if not results:
            return results

        scores = [doc.get(score_field, 0.0) for doc in results]
        min_score = min(scores)
        max_score = max(scores)

        # 避免除零
        if max_score == min_score:
            for doc in results:
                doc[score_field] = 1.0
            return results

        # Min-Max 归一化
        for doc in results:
            original_score = doc.get(score_field, 0.0)
            normalized = (original_score - min_score) / (max_score - min_score)
            doc[score_field] = normalized

        return results

    @staticmethod
    def deduplicate(
        results: List[Dict],
        score_field: str = "rrf_score"
    ) -> List[Dict]:
        """
        去重（保留高分的）

        Args:
            results: 结果列表
            score_field: 用于比较的分数字段

        Returns:
            去重后的结果列表
        """
        seen = {}

        for doc in results:
            chunk_id = doc["chunk_id"]

            if chunk_id not in seen:
                seen[chunk_id] = doc
            else:
                # 保留分数更高的
                if doc.get(score_field, 0) > seen[chunk_id].get(score_field, 0):
                    seen[chunk_id] = doc

        return list(seen.values())
