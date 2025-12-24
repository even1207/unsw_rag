import json
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

def scrape_profile_page(url: str) -> Dict[str, Any]:
    """爬取单个教职员工的详细profile页面信息"""
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
            pub_items = publications_section.find_all(['div', 'li'], class_=lambda x: x and 'publication' in str(x).lower())
            for item in pub_items:
                pub_text = item.get_text(strip=True)
                if pub_text:
                    publications.append(pub_text)

            if publications:
                profile_data['detailed_info']['publications'] = publications
            else:
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

        # 12. 提取所有的字段(field)类元素
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

        print(f"✓ 成功爬取: {url}")
        return profile_data

    except Exception as e:
        print(f"✗ 爬取失败 {url}: {str(e)}")
        return {
            'profile_url': url,
            'error': str(e),
            'detailed_info': {}
        }


# 测试
if __name__ == '__main__':
    test_url = "https://www.unsw.edu.au/staff/mr-ademir-abdala-prata-junior"
    print(f"测试URL: {test_url}\n")

    result = scrape_profile_page(test_url)

    print("\n提取的信息:")
    print("="*60)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n"+"="*60)
    print(f"字段数量: {len(result['detailed_info'])}")
    print(f"字段列表: {list(result['detailed_info'].keys())}")
