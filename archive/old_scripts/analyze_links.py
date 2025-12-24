import json
from collections import Counter

# 读取数据
with open('engineering_staff_with_profiles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("分析 related_links 内容")
print("=" * 70)

# 统计所有链接
all_link_texts = []
all_link_domains = []

for staff in data[:50]:  # 只看前50个样本
    links = staff.get('profile_details', {}).get('related_links', [])
    for link in links:
        text = link.get('text', '')
        url = link.get('url', '')
        all_link_texts.append(text)

        # 提取域名
        if 'unsw.edu.au' in url:
            all_link_domains.append('unsw.edu.au (internal)')
        elif 'doi.org' in url or 'dx.doi.org' in url:
            all_link_domains.append('DOI links')
        elif url.startswith('http'):
            all_link_domains.append('external')
        else:
            all_link_domains.append('other')

print("\n最常见的链接文本 (前30个):")
text_counter = Counter(all_link_texts)
for text, count in text_counter.most_common(30):
    print(f"  {count:3d}x  {text}")

print("\n\n链接类型分布:")
domain_counter = Counter(all_link_domains)
for domain, count in domain_counter.most_common():
    print(f"  {count:3d}x  {domain}")

# 查看一个完整样本
print("\n" + "=" * 70)
print("样本: Mr Zubair Abdullah-Vetter 的 related_links:")
print("=" * 70)

for staff in data:
    if staff.get('full_name') == 'Mr Zubair Abdullah-Vetter':
        links = staff.get('profile_details', {}).get('related_links', [])
        for i, link in enumerate(links, 1):
            text = link.get('text', '')
            url = link.get('url', '')
            print(f"{i:2d}. [{text}]")
            print(f"    URL: {url}")
        break

print("\n" + "=" * 70)
print("建议保留的链接类型:")
print("=" * 70)
print("✓ DOI链接 (dx.doi.org) - 学术文章")
print("✓ 外部学术链接 (scholar.google.com, researchgate.net等)")
print("✓ 个人网站/项目网站")
print("✓ GitHub/代码仓库")
print("\n建议移除的链接类型:")
print("=" * 70)
print("✗ UNSW内部导航 (Arts, Business School, Engineering等)")
print("✗ 通用footer链接 (Giving, Alumni, Human resources等)")
print("✗ Uluru Statement等通用链接")
print("✗ 社交媒体图标链接")
