import json
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scrape_profile_page(url: str) -> Dict[str, Any]:
    """
    爬取单个教职员工的详细profile页面信息

    Args:
        url: profile页面的URL

    Returns:
        包含所有详细信息的字典
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        profile_data = {
            'profile_url': url,
            'detailed_info': {}
        }

        # 1. 提取标题和职位信息
        title_elem = soup.find('h1')
        if title_elem:
            profile_data['detailed_info']['page_title'] = title_elem.get_text(strip=True)

        # 2. 提取职位和部门信息
        position_elem = soup.find('div', class_='field--name-field-job-title')
        if position_elem:
            profile_data['detailed_info']['position'] = position_elem.get_text(strip=True)

        org_elem = soup.find('div', class_='field--name-field-organisation')
        if org_elem:
            profile_data['detailed_info']['organisation'] = org_elem.get_text(strip=True)

        # 3. 提取联系信息
        email_elem = soup.find('a', href=lambda x: x and x.startswith('mailto:'))
        if email_elem:
            profile_data['detailed_info']['email'] = email_elem.get_text(strip=True)

        phone_elem = soup.find('div', class_='field--name-field-phone')
        if phone_elem:
            profile_data['detailed_info']['phone'] = phone_elem.get_text(strip=True)

        location_elem = soup.find('div', class_='field--name-field-location')
        if location_elem:
            profile_data['detailed_info']['location'] = location_elem.get_text(strip=True)

        # 4. 提取个人简介/传记
        biography_elem = soup.find('div', class_='field--name-field-biography')
        if biography_elem:
            profile_data['detailed_info']['biography'] = biography_elem.get_text(strip=True)

        # 5. 提取研究兴趣
        research_elem = soup.find('div', class_='field--name-field-research-interests')
        if research_elem:
            profile_data['detailed_info']['research_interests'] = research_elem.get_text(strip=True)

        # 6. 提取教育背景
        education_elem = soup.find('div', class_='field--name-field-education')
        if education_elem:
            profile_data['detailed_info']['education'] = education_elem.get_text(strip=True)

        # 7. 提取奖项和荣誉
        awards_elem = soup.find('div', class_='field--name-field-awards')
        if awards_elem:
            profile_data['detailed_info']['awards'] = awards_elem.get_text(strip=True)

        # 8. 提取出版物/文章
        publications_section = soup.find('div', id='publications') or soup.find('section', class_='publications')
        if publications_section:
            publications = []
            # 查找所有出版物条目
            pub_items = publications_section.find_all(['div', 'li'], class_=lambda x: x and 'publication' in str(x).lower())
            for item in pub_items:
                pub_text = item.get_text(strip=True)
                if pub_text:
                    publications.append(pub_text)

            if publications:
                profile_data['detailed_info']['publications'] = publications
            else:
                # 如果没有找到具体条目,保存整个section的文本
                pub_text = publications_section.get_text(strip=True)
                if pub_text:
                    profile_data['detailed_info']['publications_text'] = pub_text

        # 9. 提取研究项目
        projects_elem = soup.find('div', class_='field--name-field-research-projects')
        if projects_elem:
            profile_data['detailed_info']['research_projects'] = projects_elem.get_text(strip=True)

        # 10. 提取教学信息
        teaching_elem = soup.find('div', class_='field--name-field-teaching')
        if teaching_elem:
            profile_data['detailed_info']['teaching'] = teaching_elem.get_text(strip=True)

        # 11. 提取专业领域
        expertise_elem = soup.find('div', class_='field--name-field-expertise')
        if expertise_elem:
            profile_data['detailed_info']['expertise'] = expertise_elem.get_text(strip=True)

        # 12. 提取所有的字段(field)类元素,捕获可能遗漏的信息
        all_fields = soup.find_all('div', class_=lambda x: x and 'field--name-' in str(x))
        for field in all_fields:
            field_classes = field.get('class', [])
            for cls in field_classes:
                if cls.startswith('field--name-'):
                    field_name = cls.replace('field--name-', '').replace('-', '_')
                    if field_name not in profile_data['detailed_info']:
                        field_text = field.get_text(strip=True)
                        if field_text:
                            profile_data['detailed_info'][field_name] = field_text

        # 13. 提取所有section内容
        sections = soup.find_all('section')
        for section in sections:
            section_id = section.get('id', '')
            section_class = ' '.join(section.get('class', []))

            if section_id or section_class:
                key = section_id if section_id else section_class.replace(' ', '_')
                if key and key not in profile_data['detailed_info']:
                    section_text = section.get_text(strip=True)
                    if section_text and len(section_text) > 10:
                        profile_data['detailed_info'][f'section_{key}'] = section_text

        # 14. 提取所有链接(可能包含论文、项目等)
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            if text and len(text) > 3:  # 忽略很短的链接文本
                # 过滤掉一些常见的导航链接
                if not any(skip in href.lower() for skip in ['#', 'javascript:', 'mailto:', '/staff/', '/news/']):
                    links.append({
                        'text': text,
                        'url': href
                    })

        if links:
            profile_data['detailed_info']['related_links'] = links[:50]  # 限制链接数量

        logger.info(f"成功爬取: {url}")
        return profile_data

    except Exception as e:
        logger.error(f"爬取失败 {url}: {str(e)}")
        return {
            'profile_url': url,
            'error': str(e),
            'detailed_info': {}
        }


def main():
    """主函数:读取staff数据,爬取每个profile,保存结果"""

    # 读取原始数据
    input_file = 'engineering_staff_full.json'
    output_file = 'engineering_staff_with_profiles.json'

    logger.info(f"读取数据文件: {input_file}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            staff_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"找不到文件: {input_file}")
        return

    logger.info(f"共有 {len(staff_data)} 位教职员工")

    # 爬取每个profile
    results = []
    for i, staff in enumerate(staff_data, 1):
        profile_url = staff.get('profile_url')

        if not profile_url:
            logger.warning(f"[{i}/{len(staff_data)}] 跳过(无URL): {staff.get('full_name', 'Unknown')}")
            # 保留原始数据
            staff['profile_details'] = {'error': 'No profile URL'}
            results.append(staff)
            continue

        logger.info(f"[{i}/{len(staff_data)}] 爬取: {staff.get('full_name', 'Unknown')}")

        # 爬取详细信息
        profile_details = scrape_profile_page(profile_url)

        # 合并原始数据和详细信息
        combined_data = staff.copy()
        combined_data['profile_details'] = profile_details['detailed_info']
        if 'error' in profile_details:
            combined_data['scrape_error'] = profile_details['error']

        results.append(combined_data)

        # 每爬取10个保存一次,防止数据丢失
        if i % 10 == 0:
            logger.info(f"中间保存进度: {i}/{len(staff_data)}")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        # 礼貌延迟,避免过于频繁请求
        time.sleep(2)

    # 保存最终结果
    logger.info(f"保存结果到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"完成! 共爬取 {len(results)} 位教职员工的详细信息")

    # 统计
    success_count = sum(1 for r in results if 'scrape_error' not in r and r.get('profile_details'))
    error_count = sum(1 for r in results if 'scrape_error' in r)

    logger.info(f"成功: {success_count}, 失败: {error_count}")


if __name__ == '__main__':
    main()
