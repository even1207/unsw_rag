import json
import random
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any
import time


def clean_text(text: str) -> str:
    """清理文本"""
    if not text:
        return ""
    return ' '.join(text.split())


def fetch_live_data(url: str) -> Dict[str, Any]:
    """从网站实时获取教职员工数据"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        live_data = {}

        # 提取姓名
        title_elem = soup.find('h1', class_='profile-heading')
        if title_elem:
            live_data['full_name'] = clean_text(title_elem.get_text())

        # 提取职位
        position_elem = soup.find('div', class_='profile-title')
        if position_elem:
            live_data['position'] = clean_text(position_elem.get_text())

        # 提取学院
        faculty_elem = soup.find('div', class_='faculty-title')
        if faculty_elem:
            live_data['faculty'] = clean_text(faculty_elem.get_text())

        # 提取部门/中心
        all_profile_titles = soup.find_all('div', class_='profile-title')
        if len(all_profile_titles) > 1:
            live_data['school_or_centre'] = clean_text(all_profile_titles[1].get_text())

        # 提取邮箱
        email_link = soup.find('a', href=lambda x: x and 'mailto:' in x)
        if email_link:
            email = email_link.get('href', '').replace('mailto:', '')
            live_data['email'] = email

        # 提取传记
        bio_elem = soup.find('div', class_='cmp-text')
        if bio_elem:
            paragraphs = bio_elem.find_all('p')
            if paragraphs:
                biography = ' '.join([clean_text(p.get_text()) for p in paragraphs])
                live_data['biography'] = biography

        # 提取出版物类别
        publications = {}
        accordion_items = soup.find_all('li', class_='accordion-list-item')
        for item in accordion_items:
            heading_btn = item.find('button', class_='accordion-item')
            if heading_btn:
                heading_div = heading_btn.find('div', class_='accordion-item-heading')
                if heading_div:
                    category = clean_text(heading_div.get_text())
                    content_div = item.find('div', class_='accordion-content')
                    if content_div:
                        content_text = clean_text(content_div.get_text())
                        if content_text:
                            publications[category] = content_text

        if publications:
            live_data['publications'] = publications

        return live_data

    except Exception as e:
        return {'error': str(e)}


def compare_fields(field_name: str, stored_value: Any, live_value: Any) -> Dict[str, Any]:
    """比较单个字段的值"""
    result = {
        'field': field_name,
        'match': False,
        'stored': stored_value,
        'live': live_value,
        'notes': []
    }

    if stored_value is None and live_value is None:
        result['match'] = True
        result['notes'].append('都为空')
    elif stored_value is None:
        result['notes'].append('存储数据缺失')
    elif live_value is None:
        result['notes'].append('网站数据缺失')
    elif isinstance(stored_value, str) and isinstance(live_value, str):
        # 字符串比较(忽略空白差异)
        stored_clean = ' '.join(stored_value.split())
        live_clean = ' '.join(live_value.split())

        if stored_clean == live_clean:
            result['match'] = True
        elif stored_clean in live_clean or live_clean in stored_clean:
            result['match'] = True
            result['notes'].append('部分匹配')
        else:
            result['notes'].append('内容不匹配')
    elif isinstance(stored_value, dict) and isinstance(live_value, dict):
        # 字典比较(如publications)
        stored_keys = set(stored_value.keys())
        live_keys = set(live_value.keys())

        if stored_keys == live_keys:
            result['match'] = True
            result['notes'].append(f'类别数量: {len(stored_keys)}')
        else:
            missing_in_stored = live_keys - stored_keys
            missing_in_live = stored_keys - live_keys
            if missing_in_stored:
                result['notes'].append(f'存储缺失类别: {missing_in_stored}')
            if missing_in_live:
                result['notes'].append(f'网站缺失类别: {missing_in_live}')
    else:
        result['notes'].append('类型不同')

    return result


def verify_staff_data(staff_stored: Dict[str, Any], staff_live: Dict[str, Any]) -> Dict[str, Any]:
    """验证单个教职员工的数据"""

    profile_details = staff_stored.get('profile_details', {})

    # 需要验证的字段
    fields_to_check = [
        'full_name',
        'position',
        'faculty',
        'school_or_centre',
        'email',
        'biography',
        'publications'
    ]

    verification_results = []
    match_count = 0
    total_count = 0

    for field in fields_to_check:
        stored_value = profile_details.get(field)
        live_value = staff_live.get(field)

        comparison = compare_fields(field, stored_value, live_value)
        verification_results.append(comparison)

        total_count += 1
        if comparison['match']:
            match_count += 1

    return {
        'staff_name': staff_stored.get('full_name', 'Unknown'),
        'profile_url': staff_stored.get('profile_url', ''),
        'match_rate': match_count / total_count if total_count > 0 else 0,
        'match_count': match_count,
        'total_count': total_count,
        'field_results': verification_results
    }


def main():
    """主验证函数"""
    print("=" * 80)
    print("数据准确性验证 - 随机抽取10位教职员工对比")
    print("=" * 80)

    # 读取存储的数据
    print("\n读取本地数据...")
    with open('engineering_staff_with_profiles_cleaned.json', 'r', encoding='utf-8') as f:
        all_staff = json.load(f)

    print(f"总教职员工数: {len(all_staff)}")

    # 随机选择10个
    sample_staff = random.sample(all_staff, min(10, len(all_staff)))

    print(f"随机抽取: {len(sample_staff)} 人\n")

    # 验证每个教职员工
    all_results = []

    for i, staff in enumerate(sample_staff, 1):
        name = staff.get('full_name', 'Unknown')
        url = staff.get('profile_url', '')

        print(f"\n[{i}/{len(sample_staff)}] 验证: {name}")
        print(f"URL: {url}")
        print("-" * 80)

        # 获取实时数据
        print("  → 获取网站实时数据...")
        live_data = fetch_live_data(url)

        if 'error' in live_data:
            print(f"  ✗ 获取失败: {live_data['error']}")
            continue

        # 比较数据
        verification = verify_staff_data(staff, live_data)
        all_results.append(verification)

        # 显示结果
        match_rate = verification['match_rate'] * 100
        print(f"  → 匹配率: {match_rate:.1f}% ({verification['match_count']}/{verification['total_count']})")

        # 显示字段详情
        for field_result in verification['field_results']:
            field = field_result['field']
            match = field_result['match']
            notes = ', '.join(field_result['notes']) if field_result['notes'] else ''

            status = "✓" if match else "✗"
            print(f"    {status} {field:20s} {notes}")

        # 礼貌延迟
        if i < len(sample_staff):
            time.sleep(2)

    # 总结
    print("\n" + "=" * 80)
    print("验证总结")
    print("=" * 80)

    if all_results:
        avg_match_rate = sum(r['match_rate'] for r in all_results) / len(all_results) * 100
        print(f"平均匹配率: {avg_match_rate:.1f}%")
        print(f"验证样本数: {len(all_results)}")

        # 按匹配率排序
        all_results.sort(key=lambda x: x['match_rate'])

        print(f"\n最低匹配率:")
        for i, result in enumerate(all_results[:3], 1):
            print(f"  {i}. {result['staff_name']}: {result['match_rate']*100:.1f}%")

        print(f"\n最高匹配率:")
        for i, result in enumerate(reversed(all_results[-3:]), 1):
            print(f"  {i}. {result['staff_name']}: {result['match_rate']*100:.1f}%")

        # 字段级别统计
        field_match_counts = {}
        for result in all_results:
            for field_result in result['field_results']:
                field = field_result['field']
                if field not in field_match_counts:
                    field_match_counts[field] = {'match': 0, 'total': 0}
                field_match_counts[field]['total'] += 1
                if field_result['match']:
                    field_match_counts[field]['match'] += 1

        print(f"\n字段匹配率统计:")
        for field, counts in sorted(field_match_counts.items()):
            rate = counts['match'] / counts['total'] * 100 if counts['total'] > 0 else 0
            print(f"  {field:20s}: {rate:5.1f}% ({counts['match']}/{counts['total']})")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
