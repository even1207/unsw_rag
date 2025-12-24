"""
测试搜索功能

使用方法:
    # 测试完整搜索
    python3 test_search.py

    # 测试特定查询
    python3 test_search.py --query "Industry 4.0"

    # 只搜索论文
    python3 test_search.py --query "Digital Twin" --publications-only

    # 只搜索研究人员
    python3 test_search.py --query "machine learning" --researchers-only
"""
import sys
from pathlib import Path
import argparse
import json
import logging

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from search.hybrid_search import HybridSearchEngine
from pipeline.step4_generate_embeddings import EmbeddingGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_results(response: dict):
    """打印搜索结果"""
    print("\n" + "="*80)
    print(f"SEARCH RESULTS")
    print("="*80)

    print(f"\nQuery: {response['query']}")
    print(f"Total matched: {response['total_results']}")
    print(f"Showing: {response['returned_results']} results")

    print("\n" + "-"*80)
    print("CITATIONS:")
    print("-"*80)

    for i, citation_data in enumerate(response['citations'], 1):
        print(f"\n[{i}] {citation_data.get('chunk_type', 'Unknown Type')}")

        citation = citation_data.get('citation', {})

        if citation.get('type') == 'publication':
            # 论文引用
            print(f"  Title: {citation.get('title', 'N/A')}")
            print(f"  Authors: {', '.join(citation.get('authors', ['N/A'])[:3])}")
            print(f"  Year: {citation.get('year', 'N/A')}")
            print(f"  Venue: {citation.get('venue', 'N/A')}")
            print(f"  Citations: {citation.get('citations_count', 0)}")

            if citation.get('doi'):
                print(f"  DOI: {citation['doi']}")
                print(f"  URL: https://doi.org/{citation['doi']}")

            # Staff info
            staff = citation.get('staff', {})
            print(f"  Author (UNSW): {staff.get('name')} ({staff.get('school')})")

        elif citation.get('type') == 'person':
            # 人员引用
            print(f"  Name: {citation.get('name')}")
            print(f"  Role: {citation.get('role', 'N/A')}")
            print(f"  School: {citation.get('school', 'N/A')}")
            print(f"  Publications: {citation.get('publication_count', 0)}")
            if citation.get('profile_url'):
                print(f"  Profile: {citation['profile_url']}")

        # 相关性分数
        scores = citation_data.get('relevance_scores', {})
        print(f"  Scores: BM25={scores.get('bm25', 0):.3f}, "
              f"Vector={scores.get('vector', 0):.3f}, "
              f"RRF={scores.get('rrf', 0):.3f}, "
              f"Rerank={scores.get('rerank', 0):.3f}")

        # 内容预览
        if 'content_preview' in citation_data:
            print(f"\n  Preview:")
            print(f"  {citation_data['content_preview'][:200]}...")

    # 搜索元数据
    print("\n" + "-"*80)
    print("SEARCH METADATA:")
    print("-"*80)
    metadata = response.get('search_metadata', {})
    print(f"  BM25 results: {metadata.get('bm25_results', 0)}")
    print(f"  Vector results: {metadata.get('vector_results', 0)}")
    print(f"  Fused results: {metadata.get('fused_results', 0)}")
    print(f"  Reranked: {metadata.get('reranked', False)}")

    print("\n" + "="*80 + "\n")


def run_example_queries(search_engine: HybridSearchEngine):
    """运行示例查询"""

    example_queries = [
        "Industry 4.0 and manufacturing",
        "Digital Twin applications",
        "machine learning in engineering",
        "sustainable energy systems",
        "robotics and automation"
    ]

    print("\n" + "="*80)
    print("RUNNING EXAMPLE QUERIES")
    print("="*80)

    for query in example_queries:
        print(f"\n\nQuery: '{query}'")
        print("-"*80)

        response = search_engine.search(
            query=query,
            top_k=3,
            include_scores=False
        )

        # 简化输出
        print(f"Total results: {response['total_results']}")
        print(f"Top 3 citations:")

        for i, cit in enumerate(response['citations'][:3], 1):
            citation = cit.get('citation', {})
            if citation.get('type') == 'publication':
                print(f"  {i}. {citation.get('title', 'N/A')[:60]}...")
            elif citation.get('type') == 'person':
                print(f"  {i}. {citation.get('name')} - {citation.get('school', 'N/A')}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Test hybrid search")
    parser.add_argument(
        "--query",
        help="Search query",
        default="Industry 4.0"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to return"
    )
    parser.add_argument(
        "--publications-only",
        action="store_true",
        help="Search publications only"
    )
    parser.add_argument(
        "--researchers-only",
        action="store_true",
        help="Search researchers only"
    )
    parser.add_argument(
        "--no-reranker",
        action="store_true",
        help="Disable reranker"
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Run example queries"
    )
    parser.add_argument(
        "--model",
        choices=["openai", "local"],
        default="openai",
        help="Embedding model type"
    )

    args = parser.parse_args()

    # 连接数据库
    logger.info(f"Connecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 初始化 embedding generator
    logger.info(f"Initializing {args.model} embedding generator...")
    embedding_gen = EmbeddingGenerator(model_type=args.model)

    # 初始化搜索引擎
    logger.info("Initializing search engine...")
    search_engine = HybridSearchEngine(
        session=session,
        embedding_generator=embedding_gen,
        use_reranker=not args.no_reranker,
        reranker_model="local"
    )

    try:
        if args.examples:
            # 运行示例查询
            run_example_queries(search_engine)
        else:
            # 执行搜索
            if args.publications_only:
                logger.info("Searching publications only...")
                response = search_engine.search_publications_only(
                    query=args.query,
                    top_k=args.top_k,
                    has_abstract=True
                )
            elif args.researchers_only:
                logger.info("Searching researchers only...")
                response = search_engine.search_researchers_only(
                    query=args.query,
                    top_k=args.top_k
                )
            else:
                logger.info("Searching all content...")
                response = search_engine.search(
                    query=args.query,
                    top_k=args.top_k
                )

            # 打印结果
            print_results(response)

            # 可选：保存到文件
            output_file = PROJECT_ROOT / "test_search_results.json"
            with open(output_file, 'w') as f:
                json.dump(response, f, indent=2, ensure_ascii=False)
            logger.info(f"\n✓ Results saved to: {output_file}")

    except Exception as e:
        logger.error(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
