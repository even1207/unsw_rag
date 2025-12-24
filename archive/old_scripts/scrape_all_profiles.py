import json
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any
import logging
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """清理文本,去除多余空白"""
    if not text:
        return ""
    return ' '.join(text.split())


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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        profile_data = {
            'profile_url': url,
            'detailed_info': {}
        }

        # 1. 提取标题
        title_elem = soup.find('h1', class_='profile-heading')
        if title_elem:
            profile_data['detailed_info']['full_name'] = clean_text(title_elem.get_text())

        # 2. 提取职位
        position_elem = soup.find('div', class_='profile-title')
        if position_elem:
            profile_data['detailed_info']['position'] = clean_text(position_elem.get_text())

        # 3. 提取学院
        faculty_elem = soup.find('div', class_='faculty-title')
        if faculty_elem:
            profile_data['detailed_info']['faculty'] = clean_text(faculty_elem.get_text())

        # 4. 提取研究中心/部门 (第二个profile-title)
        all_profile_titles = soup.find_all('div', class_='profile-title')
        if len(all_profile_titles) > 1:
            profile_data['detailed_info']['school_or_centre'] = clean_text(all_profile_titles[1].get_text())

        # 5. 提取邮箱
        email_link = soup.find('a', href=lambda x: x and 'mailto:' in x)
        if email_link:
            email = email_link.get('href', '').replace('mailto:', '')
            profile_data['detailed_info']['email'] = email

        # 6. 提取个人简介 (biography)
        bio_elem = soup.find('div', class_='cmp-text')
        if bio_elem:
            paragraphs = bio_elem.find_all('p')
            if paragraphs:
                biography = ' '.join([clean_text(p.get_text()) for p in paragraphs])
                profile_data['detailed_info']['biography'] = biography

        # 7. 从meta标签提取额外信息
        meta_keywords = soup.find('meta', {'name': 'keywords'})
        if meta_keywords:
            keywords = meta_keywords.get('content', '')
            if keywords:
                profile_data['detailed_info']['keywords'] = keywords

        meta_school = soup.find('meta', {'name': 'profile-school'})
        if meta_school:
            profile_data['detailed_info']['profile_school'] = meta_school.get('content', '')

        meta_faculty = soup.find('meta', {'name': 'profile-faculty'})
        if meta_faculty:
            profile_data['detailed_info']['profile_faculty'] = meta_faculty.get('content', '')

        # 8. 提取出版物信息
        publications_data = {}

        # 查找所有的accordion项目(Books, Book Chapters, Journal Articles等)
        accordion_items = soup.find_all('li', class_='accordion-list-item')
        for item in accordion_items:
            # 获取标题(如 "Books", "Journal Articles"等)
            heading_btn = item.find('button', class_='accordion-item')
            if heading_btn:
                heading_div = heading_btn.find('div', class_='accordion-item-heading')
                if heading_div:
                    category = clean_text(heading_div.get_text())

                    # 获取内容
                    content_div = item.find('div', class_='accordion-content')
                    if content_div:
                        # 提取所有文本内容
                        content_text = clean_text(content_div.get_text())

                        # 尝试提取所有文本元素
                        text_elements = content_div.find_all('div', class_='cmp-text')
                        if text_elements:
                            items = []
                            for elem in text_elements:
                                text = clean_text(elem.get_text())
                                if text:
                                    items.append(text)
                            if items:
                                publications_data[category] = items
                            elif content_text:  # 如果没有找到具体项目,但有文本内容
                                publications_data[category] = content_text
                        elif content_text:
                            publications_data[category] = content_text

        if publications_data:
            profile_data['detailed_info']['publications'] = publications_data

        # 9. 提取所有链接(可能包含研究项目、外部链接等)
        main_content = soup.find('main', class_='root')
        if main_content:
            links = []
            for link in main_content.find_all('a', href=True):
                href = link['href']
                text = clean_text(link.get_text())

                # 过滤掉导航链接和无用链接
                if text and len(text) > 5:
                    # 排除导航、页脚等链接
                    skip_keywords = [
                        '/study', '/research/', '/engage', '/about',
                        'facebook.com', 'twitter.com', 'linkedin.com',
                        'Send an email', 'Home', 'Staff', 'UNSW'
                    ]

                    # 检查是否应该跳过这个链接
                    should_skip = False
                    for keyword in skip_keywords:
                        if keyword.lower() in href.lower() or keyword.lower() in text.lower():
                            should_skip = True
                            break

                    if not should_skip:
                        # 转换相对链接为绝对链接
                        if href.startswith('/'):
                            href = 'https://www.unsw.edu.au' + href

                        links.append({
                            'text': text,
                            'url': href
                        })

            # 去重并限制数量
            unique_links = []
            seen_urls = set()
            for link in links:
                if link['url'] not in seen_urls:
                    seen_urls.add(link['url'])
                    unique_links.append(link)
                    if len(unique_links) >= 30:  # 限制数量
                        break

            if unique_links:
                profile_data['detailed_info']['related_links'] = unique_links

        # 10. 提取所有可见的文本段落(可能包含研究兴趣、项目等)
        all_text_components = soup.find_all('div', class_='cmp-text')
        additional_text = []
        for comp in all_text_components:
            text = clean_text(comp.get_text())
            if text and len(text) > 50 and text not in str(profile_data):  # 避免重复
                additional_text.append(text)

        if additional_text:
            profile_data['detailed_info']['additional_content'] = additional_text[:5]  # 限制数量

        return profile_data

    except Exception as e:
        logger.error(f"✗ 爬取失败 {url}: {str(e)}")
        return {
            'profile_url': url,
            'error': str(e),
            'detailed_info': {}
        }


def scrape_all_profiles(input_file: str, output_file: str, limit: int = None):
    """
    爬取所有教职员工的profile详细信息

    Args:
        input_file: 输入的JSON文件
        output_file: 输出的JSON文件
        limit: 限制爬取数量(用于测试),None表示全部爬取
    """
    logger.info(f"读取数据文件: {input_file}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            staff_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"找不到文件: {input_file}")
        return

    total_count = len(staff_data)
    if limit:
        staff_data = staff_data[:limit]
        logger.info(f"限制爬取前 {limit} 位教职员工(总共 {total_count} 位)")
    else:
        logger.info(f"共有 {total_count} 位教职员工")

    # 爬取每个profile
    results = []
    success_count = 0
    error_count = 0

    for i, staff in enumerate(staff_data, 1):
        profile_url = staff.get('profile_url')

        if not profile_url:
            logger.warning(f"[{i}/{len(staff_data)}] 跳过(无URL): {staff.get('full_name', 'Unknown')}")
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
            error_count += 1
        else:
            success_count += 1
            logger.info(f"✓ 成功爬取: {profile_url}")

        results.append(combined_data)

        # 每爬取10个保存一次
        if i % 10 == 0:
            logger.info(f"中间保存进度: {i}/{len(staff_data)} | 成功: {success_count}, 失败: {error_count}")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        # 礼貌延迟
        time.sleep(2)

    # 保存最终结果
    logger.info(f"保存结果到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"="*60)
    logger.info(f"完成! 总数: {len(results)} | 成功: {success_count}, 失败: {error_count}")
    logger.info(f"="*60)


if __name__ == '__main__':
    # 爬取所有教职员工
    scrape_all_profiles(
        input_file='engineering_staff_full.json',
        output_file='engineering_staff_with_profiles.json',
        limit=None  # None = 爬取全部
    )
