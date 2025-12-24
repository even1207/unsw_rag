import json
import random
import requests
from bs4 import BeautifulSoup
import time
import re


def clean_text(text: str) -> str:
    """清理文本"""
    if not text:
        return ""
    return ' '.join(text.split())


def fetch_publications_from_web(url: str) -> dict:
    """从网站获取出版物信息"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        publications = {}

        # 查找所有accordion项目
        accordion_items = soup.find_all('li', class_='accordion-list-item')

        for item in accordion_items:
            heading_btn = item.find('button', class_='accordion-item')
            if heading_btn:
                heading_div = heading_btn.find('div', class_='accordion-item-heading')
                if heading_div:
                    category = clean_text(heading_div.get_text())

                    # 获取内容
                    content_div = item.find('div', class_='accordion-content')
                    if content_div:
                        # 方法1: 尝试提取所有文本元素
                        text_elements = content_div.find_all('div', class_='cmp-text')

                        if text_elements:
                            items = []
                            for elem in text_elements:
                                text = clean_text(elem.get_text())
                                if text:
                                    items.append(text)
                            if items:
                                publications[category] = items
                        else:
                            # 方法2: 提取整体文本
                            content_text = clean_text(content_div.get_text())
                            if content_text:
                                publications[category] = content_text

        return publications

    except Exception as e:
        return {'error': str(e)}


def count_publications(pub_data) -> int:
    """统计出版物数量"""
    if not pub_data:
        return 0

    total = 0
    if isinstance(pub_data, dict):
        for category, content in pub_data.items():
            if isinstance(content, list):
                total += len(content)
            elif isinstance(content, str):
                # 通过 | 分隔符估算数量
                items = [x.strip() for x in content.split('|') if x.strip()]
                # 过滤掉类别名称本身
                items = [x for x in items if category not in x]
                total += len(items)

    return total


def extract_publication_items(pub_text: str) -> list:
    """从出版物文本中提取单个条目"""
    if not pub_text:
        return []

    # 按 | 分割
    items = pub_text.split('|')

    # 清理和过滤
    cleaned_items = []
    for item in items:
        item = item.strip()
        # 跳过类别标题
        if item and not re.match(r'^(Books|Book Chapters|Journal [Aa]rticles|Conference Papers|Working Papers|Edited Books|Other|Media)$', item):
            cleaned_items.append(item)

    return cleaned_items


def verify_publications(staff_name: str, staff_url: str, stored_pubs: dict, live_pubs: dict) -> dict:
    """验证出版物数据"""

    result = {
        'staff_name': staff_name,
        'url': staff_url,
        'stored_categories': set(stored_pubs.keys()) if stored_pubs else set(),
        'live_categories': set(live_pubs.keys()) if live_pubs else set(),
        'stored_count': count_publications(stored_pubs),
        'live_count': count_publications(live_pubs),
        'match': False,
        'issues': []
    }

    # 比较类别
    if result['stored_categories'] != result['live_categories']:
        missing_in_stored = result['live_categories'] - result['stored_categories']
        missing_in_live = result['stored_categories'] - result['live_categories']

        if missing_in_stored:
            result['issues'].append(f"存储数据缺失类别: {missing_in_stored}")
        if missing_in_live:
            result['issues'].append(f"网站数据缺失类别: {missing_in_live}")

    # 比较数量
    if result['stored_count'] != result['live_count']:
        diff = result['stored_count'] - result['live_count']
        result['issues'].append(f"数量差异: {diff:+d}")

    # 详细比较每个类别
    for category in result['stored_categories'] | result['live_categories']:
        stored_content = stored_pubs.get(category, '')
        live_content = live_pubs.get(category, '')

        # 提取条目
        stored_items = extract_publication_items(stored_content) if isinstance(stored_content, str) else stored_content
        live_items = extract_publication_items(live_content) if isinstance(live_content, str) else live_content

        if isinstance(stored_items, list) and isinstance(live_items, list):
            if len(stored_items) != len(live_items):
                result['issues'].append(
                    f"{category}: 存储{len(stored_items)}条 vs 网站{len(live_items)}条"
                )

    # 判断是否匹配
    if not result['issues']:
        result['match'] = True

    return result


def main():
    """主函数"""
    print("=" * 80)
    print("出版物数据完整性验证")
    print("=" * 80)

    # 读取数据
    print("\n读取本地数据...")
    with open('engineering_staff_with_profiles_cleaned.json', 'r', encoding='utf-8') as f:
        all_staff = json.load(f)

    print(f"总教职员工数: {len(all_staff)}")

    # 统计有出版物的教职员工
    staff_with_pubs = [s for s in all_staff if s.get('profile_details', {}).get('publications')]
    print(f"有出版物的教职员工: {len(staff_with_pubs)} ({len(staff_with_pubs)/len(all_staff)*100:.1f}%)")

    # 随机选择10个有出版物的教职员工
    sample_size = min(10, len(staff_with_pubs))
    sample_staff = random.sample(staff_with_pubs, sample_size)

    print(f"\n随机抽取{sample_size}位有出版物的教职员工进行验证...\n")

    verification_results = []

    for i, staff in enumerate(sample_staff, 1):
        name = staff.get('full_name', 'Unknown')
        url = staff.get('profile_url', '')
        stored_pubs = staff.get('profile_details', {}).get('publications', {})

        print(f"[{i}/{sample_size}] {name}")
        print(f"URL: {url}")
        print("-" * 80)

        # 获取网站数据
        print("  → 获取网站出版物数据...")
        live_pubs = fetch_publications_from_web(url)

        if 'error' in live_pubs:
            print(f"  ✗ 获取失败: {live_pubs['error']}")
            continue

        # 验证
        verification = verify_publications(name, url, stored_pubs, live_pubs)
        verification_results.append(verification)

        # 显示结果
        status = "✓" if verification['match'] else "✗"
        print(f"  {status} 存储数据: {len(verification['stored_categories'])}个类别, {verification['stored_count']}篇")
        print(f"  {status} 网站数据: {len(verification['live_categories'])}个类别, {verification['live_count']}篇")

        if verification['match']:
            print(f"  ✓ 数据完全匹配!")
        else:
            print(f"  ✗ 发现问题:")
            for issue in verification['issues']:
                print(f"    - {issue}")

        # 显示类别详情
        print(f"  类别: {', '.join(sorted(verification['stored_categories']))}")

        # 显示几个样本
        if stored_pubs:
            first_category = list(stored_pubs.keys())[0]
            first_content = stored_pubs[first_category]
            items = extract_publication_items(first_content) if isinstance(first_content, str) else first_content
            if items and len(items) > 0:
                sample_item = items[0] if isinstance(items, list) else str(items)[:150]
                print(f"  样本 ({first_category}): {sample_item[:100]}...")

        print()

        # 延迟
        if i < sample_size:
            time.sleep(2)

    # 总结
    print("\n" + "=" * 80)
    print("验证总结")
    print("=" * 80)

    if verification_results:
        match_count = sum(1 for r in verification_results if r['match'])
        total_count = len(verification_results)

        print(f"完全匹配: {match_count}/{total_count} ({match_count/total_count*100:.1f}%)")

        # 统计总出版物数
        total_stored = sum(r['stored_count'] for r in verification_results)
        total_live = sum(r['live_count'] for r in verification_results)

        print(f"\n出版物总数:")
        print(f"  存储数据: {total_stored}篇")
        print(f"  网站数据: {total_live}篇")
        print(f"  差异: {total_stored - total_live:+d}篇")

        # 显示有问题的案例
        issues_cases = [r for r in verification_results if not r['match']]
        if issues_cases:
            print(f"\n发现问题的案例 ({len(issues_cases)}个):")
            for r in issues_cases:
                print(f"  - {r['staff_name']}")
                for issue in r['issues']:
                    print(f"    {issue}")
        else:
            print(f"\n✓ 所有抽样数据都完全匹配!")

        # 类别统计
        all_categories = set()
        for r in verification_results:
            all_categories.update(r['stored_categories'])

        print(f"\n发现的出版物类别 ({len(all_categories)}种):")
        for cat in sorted(all_categories):
            count = sum(1 for r in verification_results if cat in r['stored_categories'])
            print(f"  - {cat}: {count}/{total_count}人")

    print("\n" + "=" * 80)

    # 全局统计
    print("\n全局出版物统计 (所有649人):")
    print("=" * 80)

    all_pub_counts = []
    all_categories_global = {}

    for staff in all_staff:
        pubs = staff.get('profile_details', {}).get('publications', {})
        if pubs:
            count = count_publications(pubs)
            all_pub_counts.append(count)

            for category in pubs.keys():
                all_categories_global[category] = all_categories_global.get(category, 0) + 1

    if all_pub_counts:
        print(f"总出版物数: {sum(all_pub_counts)}")
        print(f"平均每人: {sum(all_pub_counts)/len(all_pub_counts):.1f}篇")
        print(f"最多: {max(all_pub_counts)}篇")
        print(f"最少: {min(all_pub_counts)}篇")

        print(f"\n各类别分布:")
        for cat, count in sorted(all_categories_global.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cat:25s}: {count:3d}人 ({count/len(all_staff)*100:.1f}%)")

    print("=" * 80)


if __name__ == '__main__':
    main()
