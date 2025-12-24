import json
import re

def should_keep_link(link_text: str, link_url: str) -> bool:
    """
    判断链接是否应该保留

    Args:
        link_text: 链接文本
        link_url: 链接URL

    Returns:
        True表示保留,False表示删除
    """

    # 移除的链接文本模式
    remove_texts = [
        'Arts, Design & Architecture',
        'Business School',
        'Engineering',
        'Law & Justice',
        'Medicine & Health',
        'Science',
        'Overview',
        'Areas to support',
        'Ways to give',
        'Impact stories',
        'Alumni essentials',
        'Professional hub',
        'Get involved',
        'Update your details',
        'Our strategy',
        'Human resources',
        'Back to',
        'The Uluru Statement',
        'UNSW',
        'Home',
        'Staff',
        'Study',
        'Research',
        'Engage',
        'About',
        'Giving',
        'Alumni'
    ]

    # 检查文本是否在移除列表中
    for remove_text in remove_texts:
        if remove_text.lower() in link_text.lower():
            return False

    # 移除的URL模式
    remove_url_patterns = [
        r'unsw\.edu\.au/(arts-design-architecture|business|engineering|law-justice|medicine-health|science)',
        r'unsw\.edu\.au/(giving|alumni|strategy|human-resources)',
        r'unsw\.edu\.au/(study|research|engage|about)',
        r'ulurustatement\.org',
        r'^#$',
        r'facebook\.com',
        r'twitter\.com',
        r'linkedin\.com',
        r'instagram\.com',
    ]

    for pattern in remove_url_patterns:
        if re.search(pattern, link_url.lower()):
            return False

    # 保留的URL模式
    keep_url_patterns = [
        r'doi\.org',  # DOI链接
        r'dx\.doi\.org',  # DOI链接
        r'github\.com',  # GitHub
        r'gitlab\.com',  # GitLab
        r'scholar\.google',  # Google Scholar
        r'researchgate\.net',  # ResearchGate
        r'orcid\.org',  # ORCID
        r'arxiv\.org',  # arXiv
        r'\.edu(?!/)',  # 教育机构(但不是unsw.edu.au的内部页面)
        r'\.gov',  # 政府网站
        r'\.org(?!$)',  # 组织网站(但不是简单的.org)
    ]

    for pattern in keep_url_patterns:
        if re.search(pattern, link_url.lower()):
            return True

    # 如果链接文本很短(少于5个字符),可能是无意义的
    if len(link_text.strip()) < 5:
        return False

    # 默认:如果是外部链接且文本合理,保留
    if not link_url.startswith('https://www.unsw.edu.au'):
        return True

    # 其他UNSW内部链接,默认移除
    return False


def clean_staff_data(input_file: str, output_file: str):
    """
    清理教职员工数据中的无关链接

    Args:
        input_file: 输入的JSON文件
        output_file: 输出的清理后JSON文件
    """
    print("=" * 70)
    print("清理教职员工数据中的无关链接")
    print("=" * 70)

    # 读取数据
    print(f"\n读取文件: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_staff = len(data)
    total_links_before = 0
    total_links_after = 0

    # 清理每个教职员工的链接
    for i, staff in enumerate(data, 1):
        profile_details = staff.get('profile_details', {})
        links = profile_details.get('related_links', [])

        if not links:
            continue

        links_before = len(links)
        total_links_before += links_before

        # 过滤链接
        cleaned_links = []
        for link in links:
            text = link.get('text', '')
            url = link.get('url', '')

            if should_keep_link(text, url):
                cleaned_links.append(link)

        # 更新链接
        if cleaned_links:
            profile_details['related_links'] = cleaned_links
        else:
            # 如果没有有效链接,移除整个字段
            if 'related_links' in profile_details:
                del profile_details['related_links']

        links_after = len(cleaned_links)
        total_links_after += links_after

        if (i % 100 == 0) or (links_before != links_after):
            removed = links_before - links_after
            if removed > 0:
                print(f"[{i}/{total_staff}] {staff.get('full_name', 'Unknown')}: "
                      f"{links_before} → {links_after} (移除{removed}个)")

    # 保存清理后的数据
    print(f"\n保存清理后的数据到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 统计
    print("\n" + "=" * 70)
    print("清理完成!")
    print("=" * 70)
    print(f"总教职员工数: {total_staff}")
    print(f"清理前总链接数: {total_links_before}")
    print(f"清理后总链接数: {total_links_after}")
    print(f"移除链接数: {total_links_before - total_links_after}")
    print(f"保留率: {total_links_after/total_links_before*100:.1f}%")
    print("=" * 70)


if __name__ == '__main__':
    clean_staff_data(
        input_file='engineering_staff_with_profiles.json',
        output_file='engineering_staff_with_profiles_cleaned.json'
    )
