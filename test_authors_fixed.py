"""
Quick test to verify authors are now showing in search results
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from search.hybrid_search import HybridSearchEngine
from search.rag_generator import RAGAnswerGenerator
from pipeline.step4_generate_embeddings import EmbeddingGenerator
import json

# Connect to database
engine = create_engine(settings.postgres_dsn, echo=False)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

try:
    # Initialize components
    print("Initializing search engine...")
    embedding_gen = EmbeddingGenerator(model_type="openai")
    search_engine = HybridSearchEngine(
        session=session,
        embedding_generator=embedding_gen,
        use_reranker=True,
        reranker_model="local"
    )

    # Initialize RAG generator
    rag_gen = RAGAnswerGenerator(model="gpt-4o-mini")

    # Search
    print("\nSearching for 'What is digital twin?'...")
    search_results = search_engine.search(
        query="What is digital twin?",
        top_k=5,
        include_scores=True
    )

    print(f"\nFound {search_results['total_results']} results")

    # Generate answer
    print("\nGenerating answer...")
    answer_data = rag_gen.generate_answer(
        query="What is digital twin?",
        search_results=search_results['citations'],
        max_context_chunks=5
    )

    # Format output
    output = {
        "query": "What is digital twin?",
        "answer": answer_data["answer"],
        "sources": answer_data["sources"],
        "model": answer_data["model"],
        "tokens_used": answer_data["tokens_used"],
        "search_results_count": search_results["total_results"]
    }

    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(json.dumps(output, indent=2))

    # Check if authors are present
    print("\n" + "="*80)
    print("AUTHORS CHECK:")
    print("="*80)
    for i, source in enumerate(output["sources"], 1):
        title = source.get("title", "N/A")
        authors = source.get("authors", [])
        print(f"\n[{i}] {title}")
        print(f"    Authors: {authors if authors else 'MISSING'}")
        if not authors:
            print("    ⚠️  WARNING: No authors!")

finally:
    session.close()
    engine.dispose()
