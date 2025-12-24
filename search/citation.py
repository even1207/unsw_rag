"""
Citation 格式化模块

将搜索结果转换为带引用的格式
"""
from typing import List, Dict
from sqlalchemy.orm import Session
from database.rag_schema import Staff, Publication, Author, PublicationAuthor
import logging

logger = logging.getLogger(__name__)


class CitationFormatter:
    """Citation 格式化器"""

    def __init__(self, session: Session):
        self.session = session

    def format_results(
        self,
        results: List[Dict],
        include_content: bool = True,
        citation_style: str = "apa"
    ) -> Dict:
        """
        格式化搜索结果为带 citation 的格式

        Args:
            results: 搜索结果列表
            include_content: 是否包含完整内容
            citation_style: 引用格式（apa, ieee, mla）

        Returns:
            格式化后的结果
        """
        formatted_results = []

        for idx, result in enumerate(results, start=1):
            formatted = self._format_single_result(
                result,
                citation_id=idx,
                include_content=include_content,
                citation_style=citation_style
            )
            formatted_results.append(formatted)

        return {
            "total": len(formatted_results),
            "results": formatted_results
        }

    def _format_single_result(
        self,
        result: Dict,
        citation_id: int,
        include_content: bool,
        citation_style: str
    ) -> Dict:
        """格式化单个结果"""

        chunk_type = result.get("chunk_type")
        metadata = result.get("metadata", {})

        formatted = {
            "citation_id": citation_id,
            "chunk_id": result.get("chunk_id"),
            "chunk_type": chunk_type,
            "relevance_scores": {
                "bm25": result.get("bm25_score", 0.0),
                "vector": result.get("vector_score", 0.0),
                "rrf": result.get("rrf_score", 0.0),
                "rerank": result.get("rerank_score", 0.0),
                "final": result.get("final_score", result.get("rerank_score", result.get("rrf_score", 0.0)))
            }
        }

        # 添加内容预览
        if include_content:
            content = result.get("content", "")
            # 限制长度
            formatted["content_preview"] = content[:500] + "..." if len(content) > 500 else content
            formatted["content_full"] = content

        # 根据 chunk 类型添加 citation
        if chunk_type in ["publication_title", "publication_abstract", "publication_keywords"]:
            formatted["citation"] = self._create_publication_citation(
                result,
                metadata,
                citation_style
            )
        elif chunk_type in ["person_basic", "person_biography"]:
            formatted["citation"] = self._create_person_citation(
                result,
                metadata
            )

        return formatted

    def _create_publication_citation(
        self,
        result: Dict,
        metadata: Dict,
        style: str
    ) -> Dict:
        """创建论文引用"""

        pub_id = result.get("publication_id")
        citation = {
            "type": "publication",
            "title": metadata.get("pub_title", "Unknown Title"),
            "year": metadata.get("pub_year"),
            "doi": metadata.get("pub_doi"),
            "url": f"https://doi.org/{metadata.get('pub_doi')}" if metadata.get("pub_doi") else None,
            "venue": metadata.get("pub_venue"),
            "citations_count": metadata.get("citations_count", 0),
            "is_open_access": metadata.get("is_open_access", False),
            "abstract_source": metadata.get("abstract_source"),
        }

        # 获取详细信息（如果有 publication_id）
        if pub_id:
            pub = self.session.query(Publication).filter_by(id=pub_id).first()
            if pub:
                # 作者列表 - 使用新的Author关系
                # 按author_position排序获取作者
                pub_authors = (
                    self.session.query(Author, PublicationAuthor)
                    .join(PublicationAuthor, Author.id == PublicationAuthor.author_id)
                    .filter(PublicationAuthor.publication_id == pub_id)
                    .order_by(PublicationAuthor.author_position)
                    .all()
                )

                if pub_authors:
                    citation["authors"] = [author.name for author, _ in pub_authors]
                    citation["author_details"] = [
                        {
                            "name": author.name,
                            "position": pub_author.author_position,
                            "is_corresponding": pub_author.is_corresponding,
                            "is_unsw_staff": author.is_unsw_staff,
                            "openalex_id": author.openalex_id,
                            "orcid": author.orcid,
                            "institutions": pub_author.institutions
                        }
                        for author, pub_author in pub_authors
                    ]
                else:
                    # 如果没有Author关系数据,回退到旧的JSON字段
                    authors = pub.authors or []
                    citation["authors"] = [a.get("name") for a in authors if a.get("name")]

                # PDF URL
                if pub.pdf_url:
                    citation["pdf_url"] = pub.pdf_url

                # 关键词
                concepts = pub.concepts or []
                citation["keywords"] = [
                    c.get("name") for c in concepts
                    if c.get("score", 0) > 0.3
                ][:10]

        # 格式化引用字符串
        citation["formatted"] = self._format_citation_string(citation, style)

        # 添加 staff 信息
        citation["staff"] = {
            "name": metadata.get("person_name"),
            "email": metadata.get("person_email"),
            "school": metadata.get("person_school"),
            "profile_url": metadata.get("person_profile_url")
        }

        return citation

    def _create_person_citation(
        self,
        result: Dict,
        metadata: Dict
    ) -> Dict:
        """创建人员引用"""

        staff_profile_url = result.get("staff_profile_url")
        citation = {
            "type": "person",
            "name": metadata.get("person_name"),
            "email": metadata.get("person_email"),
            "role": metadata.get("role"),
            "school": metadata.get("school") or metadata.get("person_school"),
            "faculty": metadata.get("faculty"),
            "profile_url": metadata.get("profile_url") or metadata.get("person_profile_url")
        }

        # 获取详细信息
        if staff_profile_url:
            staff = self.session.query(Staff).filter_by(profile_url=staff_profile_url).first()
            if staff:
                citation["email"] = staff.email
                citation["phone"] = staff.phone
                citation["photo_url"] = staff.photo_url

                # 统计信息
                pub_count = self.session.query(Publication).filter_by(
                    staff_profile_url=staff_profile_url
                ).count()
                citation["publication_count"] = pub_count

        # 格式化引用字符串
        citation["formatted"] = (
            f"{citation['name']}, {citation.get('role', 'Staff')}, "
            f"{citation.get('school', 'UNSW Engineering')}"
        )

        return citation

    def _format_citation_string(
        self,
        citation: Dict,
        style: str
    ) -> str:
        """
        格式化引用字符串

        Args:
            citation: 引用信息字典
            style: 引用格式（apa, ieee, mla）

        Returns:
            格式化的引用字符串
        """
        authors = citation.get("authors", [])
        title = citation.get("title", "")
        year = citation.get("year", "n.d.")
        venue = citation.get("venue", "")
        doi = citation.get("doi", "")

        if style == "apa":
            # APA 格式
            if authors:
                if len(authors) == 1:
                    author_str = authors[0]
                elif len(authors) == 2:
                    author_str = f"{authors[0]} & {authors[1]}"
                else:
                    author_str = f"{authors[0]} et al."
            else:
                author_str = "Unknown Author"

            citation_str = f"{author_str} ({year}). {title}. {venue}."
            if doi:
                citation_str += f" https://doi.org/{doi}"

        elif style == "ieee":
            # IEEE 格式
            if authors:
                if len(authors) == 1:
                    author_str = authors[0]
                else:
                    author_str = f"{authors[0]} et al."
            else:
                author_str = "Unknown Author"

            citation_str = f'{author_str}, "{title}," {venue}, {year}.'
            if doi:
                citation_str += f" doi: {doi}"

        elif style == "mla":
            # MLA 格式
            if authors:
                author_str = authors[0]
            else:
                author_str = "Unknown Author"

            citation_str = f'{author_str}. "{title}." {venue}, {year}.'

        else:
            # 默认简单格式
            citation_str = f"{title} ({year})"

        return citation_str

    def create_answer_with_citations(
        self,
        query: str,
        results: List[Dict],
        max_citations: int = 5
    ) -> Dict:
        """
        创建带引用的答案格式

        Args:
            query: 用户查询
            results: 搜索结果
            max_citations: 最大引用数量

        Returns:
            包含答案和引用的字典
        """
        # 取前 N 个结果作为引用
        top_results = results[:max_citations]

        # 格式化引用
        formatted = self.format_results(
            top_results,
            include_content=True,
            citation_style="apa"
        )

        # 构建回答结构
        response = {
            "query": query,
            "summary": self._generate_summary(top_results),
            "citations": formatted["results"],
            "total_results": len(results),
            "shown_citations": len(top_results)
        }

        return response

    def _generate_summary(self, results: List[Dict]) -> str:
        """
        生成简单摘要

        注意：这是简单版本，可以用 LLM 生成更好的摘要
        """
        if not results:
            return "No relevant results found."

        # 统计不同类型的结果
        pub_count = sum(1 for r in results if r.get("chunk_type", "").startswith("publication"))
        person_count = sum(1 for r in results if r.get("chunk_type", "").startswith("person"))

        summary_parts = []

        if pub_count > 0:
            summary_parts.append(f"Found {pub_count} relevant publication(s)")

        if person_count > 0:
            summary_parts.append(f"{person_count} researcher profile(s)")

        summary = ". ".join(summary_parts) + "."

        return summary
