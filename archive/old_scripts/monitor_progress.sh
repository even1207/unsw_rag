#!/bin/bash
# 实时监控多源解析进度

python3 << 'EOF'
import json
import os
from datetime import datetime

progress_file = "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource.json"

if not os.path.exists(progress_file):
    print("⏳ 解析还未开始或进度文件未创建")
    exit()

with open(progress_file) as f:
    progress = json.load(f)

processed = len(progress['processed_staff_emails'])
cache_size = len(progress['publication_cache'])

# 统计
sources = {}
with_abstract = 0
total_citations = 0

for doi, data in progress['publication_cache'].items():
    if 'error' in data:
        continue
    source = data.get('abstract_source', 'unknown')
    sources[source] = sources.get(source, 0) + 1
    if data.get('abstract'):
        with_abstract += 1
    total_citations += data.get('citations_count', 0)

print("="*80)
print(f"📊 解析进度监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)
print(f"\n进度: {processed}/649 staff ({processed/649*100:.1f}%)")
print(f"论文: {cache_size} 篇")

if cache_size > 0:
    print(f"\nAbstract: {with_abstract}/{cache_size} ({with_abstract/cache_size*100:.1f}%)")
    print(f"总引用数: {total_citations}")
    print(f"平均引用: {total_citations/cache_size:.1f}")

    print(f"\n📚 Abstract来源:")
    for source in ['OpenAlex', 'Semantic Scholar', 'Crossref', 'PubMed', 'none']:
        count = sources.get(source, 0)
        if count > 0:
            pct = count/cache_size*100
            bar = '█' * int(pct/2)
            print(f"  {source:20} {count:4} ({pct:5.1f}%) {bar}")

    # 预估
    if processed > 0:
        avg_pubs = cache_size / processed
        remaining = 649 - processed
        est_total = avg_pubs * 649
        est_abstracts = est_total * (with_abstract/cache_size)

        print(f"\n📈 预估最终:")
        print(f"  总论文: ~{est_total:.0f}")
        print(f"  有abstract: ~{est_abstracts:.0f} ({est_abstracts/est_total*100:.1f}%)")

        # 时间估算
        import time
        est_seconds = remaining * avg_pubs * 0.2  # 每篇0.2秒
        est_minutes = est_seconds / 60
        print(f"  预计剩余时间: ~{est_minutes:.0f}分钟")

print("\n" + "="*80)
EOF
