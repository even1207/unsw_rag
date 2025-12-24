"""
RAG 回答生成器 - 使用 LLM 基于检索内容生成自然语言回答

使用 OpenAI API 生成流畅、用户友好的回答
"""
import logging
from typing import List, Dict, Optional
from openai import OpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


class RAGAnswerGenerator:
    """RAG 回答生成器"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",  # 使用更便宜的模型
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """
        初始化回答生成器

        Args:
            model: OpenAI 模型名称
            temperature: 生成温度 (0-2)，越高越有创意
            max_tokens: 最大生成长度
        """
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        logger.info(f"✓ RAG Answer Generator initialized with model: {model}")

    def generate_answer(
        self,
        query: str,
        search_results: List[Dict],
        max_context_chunks: int = 10
    ) -> Dict:
        """
        Generate answer based on search results

        Args:
            query: User question
            search_results: Retrieved relevant documents
            max_context_chunks: Maximum number of chunks to use as context

        Returns:
            {
                "answer": "Generated answer",
                "sources": [Citation sources],
                "model": "Model used",
                "tokens_used": Number of tokens consumed
            }
        """

        # 1. Build context
        context = self._build_context(search_results[:max_context_chunks])

        if not context:
            return {
                "answer": "Sorry, I couldn't find relevant information to answer your question.",
                "sources": [],
                "model": self.model,
                "tokens_used": 0
            }

        # 2. Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(query, context)

        # 3. 调用 LLM 生成回答
        try:
            logger.info(f"Generating answer for query: {query}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            answer = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens

            logger.info(f"✓ Answer generated ({tokens_used} tokens)")

            # 4. 提取引用的来源
            sources = self._extract_sources(search_results[:max_context_chunks])

            return {
                "answer": answer,
                "sources": sources,
                "model": self.model,
                "tokens_used": tokens_used
            }

        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            return {
                "answer": f"Error generating answer: {str(e)}",
                "sources": [],
                "model": self.model,
                "tokens_used": 0
            }

    def _build_context(self, search_results: List[Dict]) -> str:
        """Build context string from search results"""

        context_parts = []

        for i, result in enumerate(search_results, 1):
            # Get content - may be in content_preview or content field
            content = result.get("content_preview", "") or result.get("content", "")
            content = content.strip()

            if not content:
                continue

            # Get metadata
            chunk_type = result.get("chunk_type", "")
            citation = result.get("citation", {})

            # Format context
            context_part = f"[Document {i}]\n"
            context_part += f"Type: {chunk_type}\n"

            # Add source information
            if citation.get("type") == "publication":
                title = citation.get("title", "")
                authors = citation.get("authors", [])
                year = citation.get("year", "")
                context_part += f"Source: Academic Publication\n"
                if title:
                    context_part += f"Title: {title}\n"
                if authors:
                    context_part += f"Authors: {', '.join(authors[:3])}\n"
                if year:
                    context_part += f"Year: {year}\n"

            elif citation.get("type") == "person":
                name = citation.get("name", "")
                school = citation.get("school", "")
                context_part += f"Source: Researcher Profile\n"
                if name:
                    context_part += f"Name: {name}\n"
                if school:
                    context_part += f"School: {school}\n"

            # Add content
            context_part += f"\nContent:\n{content}\n"

            context_parts.append(context_part)

        return "\n---\n\n".join(context_parts)

    def _build_system_prompt(self) -> str:
        """Build system prompt - always in English"""

        return """You are a professional academic research assistant specializing in UNSW (University of New South Wales) research information.

Your tasks:
1. **Answer STRICTLY based on the provided documents** - every point must be supported by document evidence
2. Directly cite specific content, data, methods, and conclusions from the documents
3. When synthesizing multiple documents, clearly indicate which points come from which research
4. Use professional and precise academic language
5. If documents don't contain relevant information, explicitly state this
6. **Never fabricate, speculate, or add information not present in the documents**

Answer format:
- Use 2-4 concise paragraphs in English
- Every point must have document evidence
- Use bullet points to organize information when appropriate
- Focus on substantive content: research findings, methods, data, etc.
- Don't list references in the answer (system will display them automatically)

IMPORTANT: Always answer in English."""

    def _build_user_prompt(self, query: str, context: str) -> str:
        """Build user prompt - always in English"""

        return f"""Answer the question based on the following documents.

Question: {query}

Documents:
{context}

Important instructions:
- Use ONLY information explicitly mentioned in the documents above
- Cite specific research findings, data, and methods
- Do not add information not present in the documents
- If documents are insufficient to answer the question, state this clearly
- Answer in English"""

    def _extract_sources(self, search_results: List[Dict]) -> List[Dict]:
        """Extract citation sources from search results"""

        sources = []

        for result in search_results:
            citation = result.get("citation", {})

            if citation.get("type") == "publication":
                source = {
                    "type": "publication",
                    "title": citation.get("title"),
                    "authors": citation.get("authors", [])[:3],  # 只显示前3个作者
                    "year": citation.get("year"),
                    "venue": citation.get("venue"),
                    "doi": citation.get("doi"),
                    "url": f"https://doi.org/{citation['doi']}" if citation.get("doi") else None
                }
                sources.append(source)

            elif citation.get("type") == "person":
                source = {
                    "type": "person",
                    "name": citation.get("name"),
                    "school": citation.get("school"),
                    "profile_url": citation.get("profile_url")
                }
                sources.append(source)

        return sources


def format_rag_response(
    answer_data: Dict,
    query: str,
    include_scores: bool = False
) -> str:
    """
    Format RAG answer as user-friendly text

    Args:
        answer_data: Result from generate_answer
        query: Original question
        include_scores: Whether to show relevance scores

    Returns:
        Formatted text
    """

    output = []

    # Title
    output.append("=" * 80)
    output.append("RAG Q&A SYSTEM")
    output.append("=" * 80)
    output.append("")

    # Question
    output.append(f"Question: {query}")
    output.append("")

    # Answer
    output.append("-" * 80)
    output.append("Answer:")
    output.append("-" * 80)
    output.append("")
    output.append(answer_data.get("answer", ""))
    output.append("")

    # Sources
    sources = answer_data.get("sources", [])
    if sources:
        output.append("-" * 80)
        output.append("Sources:")
        output.append("-" * 80)
        output.append("")

        for i, source in enumerate(sources, 1):
            if source.get("type") == "publication":
                output.append(f"[{i}] {source.get('title', 'N/A')}")
                authors = source.get("authors", [])
                if authors:
                    output.append(f"    Authors: {', '.join(authors)}")
                if source.get("year"):
                    output.append(f"    Year: {source['year']}")
                if source.get("venue"):
                    output.append(f"    Venue: {source['venue']}")
                if source.get("url"):
                    output.append(f"    URL: {source['url']}")

            elif source.get("type") == "person":
                output.append(f"[{i}] {source.get('name', 'N/A')}")
                if source.get("school"):
                    output.append(f"    School: {source['school']}")
                if source.get("profile_url"):
                    output.append(f"    Profile: {source['profile_url']}")

            output.append("")

    # Metadata
    output.append("-" * 80)
    output.append("Generation Info:")
    output.append("-" * 80)
    output.append(f"Model: {answer_data.get('model', 'N/A')}")
    output.append(f"Tokens used: {answer_data.get('tokens_used', 0):,}")
    output.append("")

    output.append("=" * 80)

    return "\n".join(output)
