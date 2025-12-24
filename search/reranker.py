"""
Reranker 重排序模块

使用 Cross-Encoder 对检索结果进行精细重排序
"""
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading
_MODEL_CACHE = {}


class Reranker:
    """重排序器 with model caching"""

    def __init__(self, model_type="local", model_name=None):
        """
        Args:
            model_type: 模型类型
                - "local": 本地 Cross-Encoder 模型（推荐）
                - "cohere": Cohere Rerank API
                - "openai": 使用 OpenAI embeddings 重排（简单方案）
            model_name: 模型名称
        """
        self.model_type = model_type
        self.model_name = model_name

        if model_type == "local":
            self._init_local_model()
        elif model_type == "cohere":
            self._init_cohere()
        elif model_type == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _init_local_model(self):
        """初始化本地 Cross-Encoder 模型 with caching"""
        global _MODEL_CACHE

        try:
            from sentence_transformers import CrossEncoder

            # 使用专门的 reranker 模型
            model_name = self.model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"

            # Check cache first
            cache_key = f"local_{model_name}"
            if cache_key in _MODEL_CACHE:
                logger.info(f"✓ Using cached reranker model: {model_name}")
                self.model = _MODEL_CACHE[cache_key]
                return

            logger.info(f"Loading reranker model: {model_name}")
            self.model = CrossEncoder(model_name)

            # Cache the model
            _MODEL_CACHE[cache_key] = self.model
            logger.info("✓ Reranker model loaded and cached")

        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            raise

    def _init_cohere(self):
        """初始化 Cohere Rerank API"""
        try:
            import cohere
            import os

            api_key = os.getenv("COHERE_API_KEY")
            if not api_key:
                raise ValueError("COHERE_API_KEY not found in environment")

            self.client = cohere.Client(api_key)
            logger.info("✓ Cohere reranker initialized")

        except ImportError:
            logger.error("cohere not installed. Run: pip install cohere")
            raise

    def _init_openai(self):
        """初始化 OpenAI（简单方案，不如专门的 reranker）"""
        logger.info("Using OpenAI embeddings for reranking (simple method)")
        # 实际使用时需要传入 embedding generator
        pass

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """
        重排序

        Args:
            query: 用户查询
            documents: 待重排序的文档列表
            top_k: 返回前 k 个结果

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        if self.model_type == "local":
            return self._rerank_local(query, documents, top_k)
        elif self.model_type == "cohere":
            return self._rerank_cohere(query, documents, top_k)
        elif self.model_type == "openai":
            return self._rerank_openai(query, documents, top_k)

    def _rerank_local(
        self,
        query: str,
        documents: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """使用本地 Cross-Encoder 重排序"""

        # 准备输入：(query, document) 对
        pairs = [(query, doc["content"]) for doc in documents]

        # 预测相关性分数
        scores = self.model.predict(pairs)

        # 将分数添加到文档中
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        # 按 rerank_score 排序
        reranked = sorted(
            documents,
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        # 返回 top_k
        top_results = reranked[:top_k]

        logger.info(f"Reranked {len(documents)} → {len(top_results)} documents")
        return top_results

    def _rerank_cohere(
        self,
        query: str,
        documents: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """使用 Cohere Rerank API 重排序"""

        # 提取文本
        texts = [doc["content"] for doc in documents]

        # 调用 Cohere Rerank API
        response = self.client.rerank(
            model="rerank-english-v2.0",
            query=query,
            documents=texts,
            top_n=top_k
        )

        # 重新组织结果
        reranked = []
        for result in response.results:
            idx = result.index
            doc = documents[idx].copy()
            doc["rerank_score"] = float(result.relevance_score)
            reranked.append(doc)

        logger.info(f"Cohere reranked {len(documents)} → {len(reranked)} documents")
        return reranked

    def _rerank_openai(
        self,
        query: str,
        documents: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """
        使用 OpenAI embeddings 简单重排序

        注意：这不如专门的 reranker，但如果已经有 embedding 可以使用
        """
        # 这里需要 embedding generator
        # 实际实现可以计算 query 和每个 doc 的 embedding 相似度
        logger.warning("OpenAI reranking not fully implemented")
        return documents[:top_k]

    def rerank_with_metadata(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 10,
        boost_fields: Dict[str, float] = None
    ) -> List[Dict]:
        """
        带元数据增强的重排序

        可以根据元数据（如引用数、年份等）调整排序

        Args:
            query: 用户查询
            documents: 待重排序的文档列表
            top_k: 返回前 k 个结果
            boost_fields: 元数据增强权重
                例如: {"citations_count": 0.1, "is_open_access": 0.05}

        Returns:
            重排序后的文档列表
        """
        # 先用 reranker 重排
        reranked = self.rerank(query, documents, top_k * 2)  # 取2倍，留余地

        if not boost_fields:
            return reranked[:top_k]

        # 应用元数据增强
        for doc in reranked:
            metadata = doc.get("metadata", {})
            boost_score = 0.0

            # 引用数增强
            if "citations_count" in boost_fields:
                citations = metadata.get("citations_count", 0)
                # 对数归一化
                import math
                boost_score += boost_fields["citations_count"] * math.log1p(citations) / 10

            # 开放获取增强
            if "is_open_access" in boost_fields:
                is_oa = metadata.get("is_open_access", False)
                if is_oa:
                    boost_score += boost_fields["is_open_access"]

            # 年份增强（越新越好）
            if "publication_year" in boost_fields:
                year = metadata.get("pub_year", 2000)
                # 归一化到 0-1（假设范围 2000-2025）
                year_score = (year - 2000) / 25
                boost_score += boost_fields["publication_year"] * year_score

            # 应用增强
            doc["final_score"] = doc.get("rerank_score", 0) + boost_score

        # 按最终分数重新排序
        reranked.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        return reranked[:top_k]
