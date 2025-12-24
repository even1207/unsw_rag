"""
清理旧数据中错误的 PubMed abstract
"""
import json
import shutil
from datetime import datetime

# 文件路径
OLD_PROGRESS_FILE = "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource.json"
BACKUP_FILE = f"/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
CLEANED_FILE = "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource_cleaned.json"

def clean_pubmed_data():
    """清理错误的 PubMed abstract"""

    print("="*80)
    print("清理错误的 PubMed Abstract 数据")
    print("="*80)

    # 1. 备份原文件
    print(f"\n1. 备份原文件...")
    shutil.copy(OLD_PROGRESS_FILE, BACKUP_FILE)
    print(f"   ✓ 备份到: {BACKUP_FILE}")

    # 2. 读取数据
    print(f"\n2. 读取数据...")
    with open(OLD_PROGRESS_FILE, 'r') as f:
        data = json.load(f)

    publications = data.get('publication_cache', {})
    total = len(publications)
    print(f"   总出版物: {total}")

    # 3. 统计需要清理的数据
    print(f"\n3. 分析数据...")
    pubmed_entries = []
    for doi, pub in publications.items():
        if pub.get('abstract_source') == 'PubMed':
            pubmed_entries.append(doi)

    print(f"   找到 {len(pubmed_entries)} 个 PubMed 来源的 abstract")

    # 4. 清理 PubMed abstract
    print(f"\n4. 清理 PubMed abstract...")
    cleaned_count = 0
    for doi in pubmed_entries:
        pub = publications[doi]
        # 保留其他数据，只删除 abstract 和修改 source
        if pub.get('abstract'):
            pub['abstract'] = ""
            pub['abstract_source'] = 'none'
            cleaned_count += 1

    print(f"   ✓ 清理了 {cleaned_count} 个错误的 abstract")

    # 5. 保存清理后的数据
    print(f"\n5. 保存清理后的数据...")
    with open(CLEANED_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"   ✓ 保存到: {CLEANED_FILE}")

    # 6. 统计清理后的状态
    print(f"\n6. 清理后统计:")
    stats = {
        'total': len(publications),
        'with_abstract': 0,
        'without_abstract': 0,
        'sources': {}
    }

    for doi, pub in publications.items():
        source = pub.get('abstract_source', 'unknown')
        stats['sources'][source] = stats['sources'].get(source, 0) + 1

        if pub.get('abstract') and pub.get('abstract').strip():
            stats['with_abstract'] += 1
        else:
            stats['without_abstract'] += 1

    print(f"   总出版物: {stats['total']}")
    print(f"   有 abstract: {stats['with_abstract']} ({stats['with_abstract']/stats['total']*100:.1f}%)")
    print(f"   缺失 abstract: {stats['without_abstract']} ({stats['without_abstract']/stats['total']*100:.1f}%)")
    print(f"\n   Abstract 来源分布:")
    for source, count in sorted(stats['sources'].items(), key=lambda x: x[1], reverse=True):
        print(f"     {source}: {count} ({count/stats['total']*100:.1f}%)")

    print(f"\n{'='*80}")
    print("清理完成！")
    print("="*80)
    print(f"\n下一步:")
    print(f"1. 检查清理后的文件: {CLEANED_FILE}")
    print(f"2. 如果确认无误，可以替换原文件:")
    print(f"   mv {CLEANED_FILE} {OLD_PROGRESS_FILE}")
    print(f"3. 或者直接使用新的 V2 脚本重新获取数据")

if __name__ == "__main__":
    clean_pubmed_data()
