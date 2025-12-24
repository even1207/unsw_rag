"""
分析 Publication 数据质量
"""
import json
import sys

def analyze_quality(progress_file):
    """分析数据质量"""

    print("="*80)
    print("Publication 数据质量分析")
    print("="*80)

    with open(progress_file, 'r') as f:
        data = json.load(f)

    publications = data.get('publication_cache', {})
    total = len(publications)

    print(f"\n总出版物: {total}")

    # 1. Abstract 覆盖率
    print(f"\n{'='*80}")
    print("1. Abstract 覆盖率")
    print('='*80)

    has_abstract = 0
    no_abstract = 0
    abstract_lengths = []
    sources = {}

    for doi, pub in publications.items():
        abstract = pub.get('abstract', '').strip()
        source = pub.get('abstract_source', 'unknown')

        sources[source] = sources.get(source, 0) + 1

        if abstract:
            has_abstract += 1
            abstract_lengths.append(len(abstract))
        else:
            no_abstract += 1

    print(f"有 abstract: {has_abstract} ({has_abstract/total*100:.1f}%)")
    print(f"缺失 abstract: {no_abstract} ({no_abstract/total*100:.1f}%)")

    if abstract_lengths:
        avg_length = sum(abstract_lengths) / len(abstract_lengths)
        print(f"\nAbstract 平均长度: {avg_length:.0f} 字符")
        print(f"最短: {min(abstract_lengths)} 字符")
        print(f"最长: {max(abstract_lengths)} 字符")

    # 2. 来源分布
    print(f"\n{'='*80}")
    print("2. Abstract 来源分布")
    print('='*80)

    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"{source:20s}: {count:4d} ({count/total*100:5.1f}%)")

    # 3. Title-Abstract 匹配度分析
    print(f"\n{'='*80}")
    print("3. Title-Abstract 匹配度分析")
    print('='*80)

    match_rates = []
    suspicious = []

    for doi, pub in publications.items():
        title = pub.get('title', '').lower()
        abstract = pub.get('abstract', '').lower()

        if title and abstract and len(title) > 10:
            title_words = set([w for w in title.split() if len(w) > 4])
            abstract_words = set(abstract.split())
            common = title_words & abstract_words

            if title_words:
                match_rate = len(common) / len(title_words)
                match_rates.append(match_rate)

                if match_rate < 0.2:  # 可疑的低匹配率
                    suspicious.append({
                        'doi': doi,
                        'title': pub.get('title', '')[:60],
                        'source': pub.get('abstract_source', 'unknown'),
                        'match_rate': match_rate
                    })

    if match_rates:
        avg_match = sum(match_rates) / len(match_rates)
        print(f"平均匹配率: {avg_match*100:.1f}%")
        print(f"检查的论文数: {len(match_rates)}")

    if suspicious:
        print(f"\n⚠️  发现 {len(suspicious)} 篇可疑的低匹配论文 (<20% 匹配率):")
        for i, item in enumerate(suspicious[:5], 1):
            print(f"\n{i}. {item['title']}...")
            print(f"   DOI: {item['doi']}")
            print(f"   来源: {item['source']}")
            print(f"   匹配率: {item['match_rate']*100:.1f}%")

        if len(suspicious) > 5:
            print(f"\n... 还有 {len(suspicious)-5} 篇可疑论文")

    # 4. 出版年份分布
    print(f"\n{'='*80}")
    print("4. 出版年份分布")
    print('='*80)

    years = {}
    for doi, pub in publications.items():
        year = pub.get('publication_year')
        if year:
            years[year] = years.get(year, 0) + 1

    recent_years = sorted([y for y in years.keys() if y >= 2020], reverse=True)
    print("最近年份分布:")
    for year in recent_years[:5]:
        count = years[year]
        print(f"  {year}: {count:4d} ({count/total*100:5.1f}%)")

    # 5. 引用统计
    print(f"\n{'='*80}")
    print("5. 引用统计")
    print('='*80)

    citations = [pub.get('citations_count', 0) for pub in publications.values() if pub.get('citations_count')]

    if citations:
        print(f"总引用数: {sum(citations)}")
        print(f"平均引用: {sum(citations)/len(citations):.1f}")
        print(f"中位数: {sorted(citations)[len(citations)//2]}")
        print(f"最高引用: {max(citations)}")

        # Top 5 高引论文
        top_cited = sorted(
            [(doi, pub.get('title', 'N/A')[:60], pub.get('citations_count', 0))
             for doi, pub in publications.items()],
            key=lambda x: x[2],
            reverse=True
        )[:5]

        print(f"\nTop 5 高引论文:")
        for i, (doi, title, count) in enumerate(top_cited, 1):
            print(f"{i}. ({count} 次引用) {title}...")

    # 6. 开放获取统计
    print(f"\n{'='*80}")
    print("6. 开放获取统计")
    print('='*80)

    oa_count = sum(1 for pub in publications.values() if pub.get('is_open_access'))
    print(f"开放获取论文: {oa_count} ({oa_count/total*100:.1f}%)")

    # 7. RAG 就绪度评估
    print(f"\n{'='*80}")
    print("7. RAG 就绪度评估")
    print('='*80)

    # 好的 abstract (长度 > 100 字符)
    good_abstracts = sum(1 for pub in publications.values()
                        if pub.get('abstract') and len(pub.get('abstract', '')) > 100)

    # 有 title 的
    has_title = sum(1 for pub in publications.values() if pub.get('title'))

    # 有 keywords/concepts 的
    has_keywords = sum(1 for pub in publications.values()
                      if pub.get('concepts') and len(pub.get('concepts', [])) > 0)

    rag_ready_score = (
        (good_abstracts / total * 0.6) +  # abstract 占 60%
        (has_title / total * 0.2) +       # title 占 20%
        (has_keywords / total * 0.2)      # keywords 占 20%
    ) * 100

    print(f"高质量 abstract (>100字符): {good_abstracts} ({good_abstracts/total*100:.1f}%)")
    print(f"有 title: {has_title} ({has_title/total*100:.1f}%)")
    print(f"有 keywords: {has_keywords} ({has_keywords/total*100:.1f}%)")
    print(f"\nRAG 就绪度评分: {rag_ready_score:.1f}/100")

    if rag_ready_score >= 70:
        print("✅ 数据质量良好，可以用于 RAG")
    elif rag_ready_score >= 50:
        print("⚠️  数据质量一般，建议继续改进")
    else:
        print("❌ 数据质量不足，需要获取更多 abstract")

    print("\n" + "="*80)

if __name__ == "__main__":
    # 默认使用清理后的文件
    if len(sys.argv) > 1:
        progress_file = sys.argv[1]
    else:
        progress_file = "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource_cleaned.json"

    print(f"分析文件: {progress_file}\n")
    analyze_quality(progress_file)
