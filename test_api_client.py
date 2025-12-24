"""
API Client for testing the RAG Q&A server

Usage:
    # Single query
    python3 test_api_client.py --query "What is digital twin?"

    # Custom context size
    python3 test_api_client.py --query "Industry 4.0 applications" --max-context 5

    # Multiple queries (benchmark)
    python3 test_api_client.py --benchmark
"""
import requests
import json
import argparse
import time
from typing import Dict


def ask_question(
    query: str,
    max_context: int = 10,
    include_sources: bool = True,
    model: str = None,
    base_url: str = "http://localhost:8000"
) -> Dict:
    """
    Send a question to the API server

    Args:
        query: Question to ask
        max_context: Maximum context chunks
        include_sources: Whether to include sources
        model: Optional model override
        base_url: API server base URL

    Returns:
        Response dictionary
    """
    url = f"{base_url}/ask"

    payload = {
        "query": query,
        "max_context": max_context,
        "include_sources": include_sources
    }

    if model:
        payload["model"] = model

    print(f"\n{'='*80}")
    print(f"Sending query: {query}")
    print(f"{'='*80}\n")

    start_time = time.time()

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        elapsed_time = time.time() - start_time

        result = response.json()

        # Print formatted response
        print(f"Question: {result['query']}")
        print(f"\n{'-'*80}")
        print("Answer:")
        print(f"{'-'*80}")
        print(result['answer'])
        print()

        if include_sources and result.get('sources'):
            print(f"{'-'*80}")
            print("Sources:")
            print(f"{'-'*80}")
            for i, source in enumerate(result['sources'], 1):
                if source.get('type') == 'publication':
                    print(f"[{i}] {source.get('title', 'N/A')}")
                    if source.get('year'):
                        print(f"    Year: {source['year']}")
                    if source.get('url'):
                        print(f"    URL: {source['url']}")
                elif source.get('type') == 'person':
                    print(f"[{i}] {source.get('name', 'N/A')}")
                    if source.get('school'):
                        print(f"    School: {source['school']}")
                print()

        print(f"{'-'*80}")
        print("Metadata:")
        print(f"{'-'*80}")
        print(f"Model: {result.get('model', 'N/A')}")
        print(f"Tokens used: {result.get('tokens_used', 0):,}")
        print(f"Search results: {result.get('search_results_count', 0)}")
        print(f"Response time: {elapsed_time:.2f}s")
        print()

        return result

    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to API server.")
        print("Make sure the server is running: python3 api_server.py")
        return None
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out (>60s)")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP {e.response.status_code}")
        print(e.response.text)
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def check_health(base_url: str = "http://localhost:8000") -> bool:
    """Check if the API server is healthy"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        health = response.json()

        print(f"\n{'='*80}")
        print("Server Health Check")
        print(f"{'='*80}")
        print(f"Status: {health['status']}")
        print(f"Models loaded: {health['models_loaded']}")
        print(f"Database connected: {health['database_connected']}")
        print(f"{'='*80}\n")

        return health['status'] == 'healthy'

    except:
        print("\n❌ Server is not running or not healthy")
        print("Start the server with: python3 api_server.py\n")
        return False


def run_benchmark(base_url: str = "http://localhost:8000"):
    """Run benchmark with multiple queries"""
    print(f"\n{'='*80}")
    print("Running Benchmark - Multiple Queries")
    print(f"{'='*80}\n")

    queries = [
        "What is digital twin?",
        "Industry 4.0 applications in manufacturing",
        "Machine learning in engineering",
        "Sustainable energy systems",
        "Robotics and automation"
    ]

    results = []
    total_time = 0

    for i, query in enumerate(queries, 1):
        print(f"\n[Query {i}/{len(queries)}]")
        start = time.time()
        result = ask_question(query, max_context=5, include_sources=False, base_url=base_url)
        elapsed = time.time() - start

        if result:
            results.append({
                "query": query,
                "tokens": result.get("tokens_used", 0),
                "time": elapsed
            })
            total_time += elapsed

        # Small delay between requests
        if i < len(queries):
            time.sleep(0.5)

    # Print summary
    print(f"\n{'='*80}")
    print("Benchmark Summary")
    print(f"{'='*80}")
    print(f"Total queries: {len(results)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per query: {total_time/len(results):.2f}s")
    print(f"Total tokens: {sum(r['tokens'] for r in results):,}")
    print(f"Average tokens per query: {sum(r['tokens'] for r in results)//len(results):,}")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="Test RAG Q&A API Client")
    parser.add_argument(
        "--query",
        help="Question to ask"
    )
    parser.add_argument(
        "--max-context",
        type=int,
        default=10,
        help="Maximum context chunks (default: 10)"
    )
    parser.add_argument(
        "--no-sources",
        action="store_true",
        help="Don't include sources in response"
    )
    parser.add_argument(
        "--model",
        help="Override default model (e.g., gpt-4o, gpt-3.5-turbo)"
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Check server health"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run benchmark with multiple queries"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    if args.health:
        check_health(args.url)
    elif args.benchmark:
        # Check health first
        if check_health(args.url):
            run_benchmark(args.url)
    elif args.query:
        # Check health first
        if check_health(args.url):
            ask_question(
                query=args.query,
                max_context=args.max_context,
                include_sources=not args.no_sources,
                model=args.model,
                base_url=args.url
            )
    else:
        print("\nPlease provide --query, --health, or --benchmark")
        print("\nExamples:")
        print('  python3 test_api_client.py --query "What is digital twin?"')
        print("  python3 test_api_client.py --health")
        print("  python3 test_api_client.py --benchmark")
        parser.print_help()


if __name__ == "__main__":
    main()
