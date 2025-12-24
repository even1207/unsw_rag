"""
测试 RAG 问答系统 - 生成自然语言回答

使用方法:
    # 单个问题
    python3 test_rag_qa.py --query "Industry 4.0 在制造业的应用有哪些？"

    # 运行示例问题
    python3 test_rag_qa.py --examples

    # 英文回答
    python3 test_rag_qa.py --query "What are the applications of Industry 4.0?" --language english

    # 调整上下文数量
    python3 test_rag_qa.py --query "数字孪生技术" --max-context 15
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
from search.rag_generator import RAGAnswerGenerator, format_rag_response
from pipeline.step4_generate_embeddings import EmbeddingGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ask_question(
    search_engine: HybridSearchEngine,
    rag_generator: RAGAnswerGenerator,
    query: str,
    max_context: int = 10
):
    """
    Ask question and get answer

    Args:
        search_engine: Hybrid search engine
        rag_generator: RAG answer generator
        query: User question
        max_context: Number of search results to use as context
    """

    logger.info(f"Processing query: {query}")

    # 1. Search for relevant documents
    logger.info("Searching for relevant documents...")
    search_response = search_engine.search(
        query=query,
        top_k=max_context,
        include_scores=True
    )

    logger.info(f"Found {search_response['total_results']} relevant documents")

    # 2. Generate answer
    logger.info("Generating answer with LLM...")
    answer_data = rag_generator.generate_answer(
        query=query,
        search_results=search_response['citations'],
        max_context_chunks=max_context
    )

    # 3. 格式化输出
    formatted_output = format_rag_response(
        answer_data=answer_data,
        query=query
    )

    print("\n" + formatted_output)

    return answer_data


def run_example_questions(
    search_engine: HybridSearchEngine,
    rag_generator: RAGAnswerGenerator
):
    """运行示例问题"""

    example_questions = [
        "Industry 4.0 在制造业中有哪些应用？",
        "数字孪生技术的主要优势是什么？",
        "UNSW 有哪些研究人员在做机器学习相关的研究？",
        "可持续能源系统的最新进展有哪些？",
        "机器人和自动化技术在工业中的应用场景？"
    ]

    print("\n" + "=" * 80)
    print("运行示例问题")
    print("=" * 80 + "\n")

    results = []

    for i, question in enumerate(example_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"示例问题 {i}/{len(example_questions)}")
        print("=" * 80)

        answer_data = ask_question(
            search_engine=search_engine,
            rag_generator=rag_generator,
            query=question,
            max_context=8
        )

        results.append({
            "question": question,
            "answer": answer_data["answer"],
            "sources_count": len(answer_data["sources"]),
            "tokens": answer_data["tokens_used"]
        })

        # 暂停一下，避免 API 限流
        import time
        time.sleep(1)

    # 总结
    print("\n" + "=" * 80)
    print("示例问题总结")
    print("=" * 80)
    total_tokens = sum(r["tokens"] for r in results)
    print(f"总问题数: {len(results)}")
    print(f"总消耗 tokens: {total_tokens:,}")
    print(f"平均每个问题: {total_tokens // len(results):,} tokens")
    print("")


def main():
    """主函数"""

    parser = argparse.ArgumentParser(description="Test RAG Q&A System")
    parser.add_argument(
        "--query",
        help="Your question",
        default=None
    )
    parser.add_argument(
        "--max-context",
        type=int,
        default=10,
        help="Maximum context chunks to use (default: 10)"
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Run example questions"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Generation temperature (default: 0.7)"
    )
    parser.add_argument(
        "--no-reranker",
        action="store_true",
        help="Disable reranker in search"
    )

    args = parser.parse_args()

    # 连接数据库
    logger.info(f"Connecting to database: {settings.postgres_dsn}")
    engine = create_engine(settings.postgres_dsn, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 初始化组件
    logger.info("Initializing embedding generator...")
    embedding_gen = EmbeddingGenerator(model_type="openai")

    logger.info("Initializing search engine...")
    search_engine = HybridSearchEngine(
        session=session,
        embedding_generator=embedding_gen,
        use_reranker=not args.no_reranker,
        reranker_model="local"
    )

    logger.info(f"Initializing RAG answer generator with model: {args.model}")
    rag_generator = RAGAnswerGenerator(
        model=args.model,
        temperature=args.temperature
    )

    try:
        if args.examples:
            # 运行示例问题
            run_example_questions(search_engine, rag_generator)

        elif args.query:
            # 回答单个问题
            answer_data = ask_question(
                search_engine=search_engine,
                rag_generator=rag_generator,
                query=args.query,
                max_context=args.max_context
            )

            # 保存结果
            output_file = PROJECT_ROOT / "rag_answer.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": args.query,
                    "answer": answer_data["answer"],
                    "sources": answer_data["sources"],
                    "model": answer_data["model"],
                    "tokens_used": answer_data["tokens_used"]
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"\n✓ Result saved to: {output_file}")

        else:
            print("\nPlease provide --query or use --examples")
            print("Example: python3 test_rag_qa.py --query '你的问题'")
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
