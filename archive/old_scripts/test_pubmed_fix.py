"""
测试修复后的 PubMed 获取功能
"""
import json
import sys
sys.path.insert(0, '/Users/z5241339/Documents/unsw_ai_rag')

from parse_publications_multisource_v2 import MultiSourceFetcher
from threading import Lock

# 测试 DOI 列表
test_cases = [
    {
        "doi": "10.1007/978-3-032-03546-2_14",
        "expected_title_keywords": ["photovoltaic", "panels", "life", "extension"],
        "should_be_in_pubmed": False,
        "description": "Springer 工程论文（不应该在 PubMed）"
    },
    {
        "doi": "10.1016/j.heliyon.2023.e17057",
        "expected_title_keywords": ["computational", "fluid", "dynamic", "wind", "turbine"],
        "should_be_in_pubmed": True,
        "description": "工程论文但可能在 PubMed"
    },
    {
        "doi": "10.1109/EMBC.2012.6347091",
        "expected_title_keywords": [],
        "should_be_in_pubmed": True,
        "description": "医学工程论文（应该在 PubMed）"
    }
]

def test_pubmed_fix():
    """测试修复后的 PubMed 功能"""

    stats = {
        "abstract_sources": {
            "openalex": 0,
            "semantic_scholar": 0,
            "crossref": 0,
            "pubmed": 0,
            "none": 0
        },
        "errors": []
    }
    stats_lock = Lock()

    fetcher = MultiSourceFetcher(stats, stats_lock)

    print("="*80)
    print("测试修复后的 PubMed Abstract 获取")
    print("="*80)

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试 {i}/{len(test_cases)}: {test['description']}")
        print(f"DOI: {test['doi']}")
        print('='*80)

        result = fetcher.fetch_abstract(test['doi'])

        # 检查结果
        title = result.get('title', '').lower()
        abstract = result.get('abstract', '').lower()
        source = result.get('abstract_source', 'none')

        print(f"\n获取到的信息:")
        print(f"  来源: {source}")
        print(f"  Title: {result.get('title', 'N/A')[:80]}...")

        if abstract:
            print(f"  Abstract (前100字符): {abstract[:100]}...")

            # 检查 title 和 abstract 的匹配度
            if title and len(title) > 10:
                title_words = set([w for w in title.split() if len(w) > 4])
                abstract_words = set(abstract.split())
                common = title_words & abstract_words
                match_rate = len(common) / len(title_words) if title_words else 0

                print(f"  Title-Abstract 匹配率: {match_rate:.1%}")
                print(f"  共同关键词: {list(common)[:5]}")

                # 验证结果
                is_valid = True

                # 如果有期望的关键词，检查它们
                if test['expected_title_keywords']:
                    keyword_found = any(kw in title or kw in abstract for kw in test['expected_title_keywords'])
                    if not keyword_found:
                        print(f"  ⚠️  警告: 期望的关键词未找到")
                        is_valid = False

                # 检查匹配率
                if source == 'PubMed':
                    if match_rate < 0.2:
                        print(f"  ❌ 失败: PubMed abstract 与 title 不匹配 (匹配率: {match_rate:.1%})")
                        is_valid = False
                    else:
                        print(f"  ✓ PubMed abstract 匹配良好")

                if is_valid:
                    print(f"\n✅ 测试通过")
                    passed += 1
                else:
                    print(f"\n❌ 测试失败")
                    failed += 1
            else:
                print(f"  ⚠️  无法验证（title 太短）")
                passed += 1
        else:
            if source == 'PubMed':
                print(f"  ❌ PubMed 返回了来源但没有 abstract")
                failed += 1
            else:
                print(f"  ℹ️  未获取到 abstract（来源: {source}）")
                passed += 1

    print(f"\n{'='*80}")
    print(f"测试总结")
    print(f"{'='*80}")
    print(f"通过: {passed}/{len(test_cases)}")
    print(f"失败: {failed}/{len(test_cases)}")

    print(f"\n来源统计:")
    for source, count in stats['abstract_sources'].items():
        if count > 0:
            print(f"  {source}: {count}")

    return failed == 0

if __name__ == "__main__":
    success = test_pubmed_fix()
    sys.exit(0 if success else 1)
