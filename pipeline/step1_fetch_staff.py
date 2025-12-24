"""
Step 1: 爬取 UNSW Engineering Staff 数据

功能:
1. 从 Funnelback API 获取 staff 基本信息
2. 爬取每个 staff 的详细 profile 页面
3. 保存到 data/processed/staff_with_profiles.json

使用方法:
    python3 pipeline/step1_fetch_staff.py
"""
import json
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data/processed/staff_with_profiles.json"
TEMP_FILE = PROJECT_ROOT / "data/cache/staff_basic.json"


# ============================================================================
# Part 1: 从 Funnelback API 获取 staff 列表
# ============================================================================

def fetch_staff_from_api(page_size: int = 50, delay_seconds: float = 1.0) -> List[Dict[str, str]]:
    """从 Funnelback API 获取 Engineering staff 列表"""

    BASE_URL = "https://unsw-search.funnelback.squiz.cloud/s/search.html"

    params = {
        "form": "json",
        "collection": "unsw~unsw-search",
        "profile": "profiles",
        "query": "!padrenull",
        "sort": "metastaffLastName",
        "f.Faculty|staffFaculty": "Engineering",
        "gscope1": "engineeringStaff",
        "meta_staffRole_not": "casual adjunct visiting honorary",
    }

    all_staff: List[Dict[str, str]] = []
    start_rank = 1

    logger.info("开始从 Funnelback API 获取 staff 数据...")

    while True:
        params["start_rank"] = start_rank
        params["num_ranks"] = page_size

        try:
            resp = requests.get(
                BASE_URL,
                params=params,
                timeout=10,
                headers={"User-Agent": "UNSW-AI-RAG-Research-Bot/0.1"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"API 请求失败: {e}")
            break

        results = data.get("response", {}).get("resultPacket", {}).get("results", [])
        if not results:
            break

        for record in results:
            meta = record.get("metaData", {})
            all_staff.append({
                "full_name": record.get("title"),
                "profile_url": record.get("liveUrl"),
                "summary": record.get("summary"),
                "first_name": meta.get("staffFirstName"),
                "last_name": meta.get("staffLastName"),
                "role": meta.get("staffRole"),
                "faculty": meta.get("staffFaculty"),
                "school": meta.get("staffSchool"),
                "email": meta.get("emailAddress"),
                "phone": meta.get("staffPhone"),
                "photo_url": meta.get("image"),
            })

        logger.info(f"获取了 {len(results)} 位 staff (从 {start_rank} 到 {start_rank + page_size - 1})")
        start_rank += page_size
        time.sleep(delay_seconds)

    logger.info(f"✓ 总共获取了 {len(all_staff)} 位 Engineering staff")
    return all_staff


# ============================================================================
# Part 2: 爬取每个 staff 的详细 profile 页面
# ============================================================================

def scrape_profile_page(url: str) -> Dict[str, Any]:
    """爬取单个 staff 的详细 profile 页面"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        profile_data = {}

        # 提取职位信息
        position_elem = soup.find('div', class_='field--name-field-job-title')
        if position_elem:
            profile_data['position'] = position_elem.get_text(strip=True)

        org_elem = soup.find('div', class_='field--name-field-organisation')
        if org_elem:
            profile_data['organisation'] = org_elem.get_text(strip=True)

        # 提取联系信息
        email_elem = soup.find('a', href=lambda x: x and x.startswith('mailto:'))
        if email_elem:
            profile_data['email'] = email_elem.get_text(strip=True)

        phone_elem = soup.find('div', class_='field--name-field-phone')
        if phone_elem:
            profile_data['phone'] = phone_elem.get_text(strip=True)

        location_elem = soup.find('div', class_='field--name-field-location')
        if location_elem:
            profile_data['location'] = location_elem.get_text(strip=True)

        # 提取个人简介
        biography_elem = soup.find('div', class_='field--name-field-biography')
        if biography_elem:
            profile_data['biography'] = biography_elem.get_text(strip=True)

        # 提取研究兴趣
        research_elem = soup.find('div', class_='field--name-field-research-interests')
        if research_elem:
            profile_data['research_interests'] = research_elem.get_text(strip=True)

        # 提取教育背景
        education_elem = soup.find('div', class_='field--name-field-education')
        if education_elem:
            profile_data['education'] = education_elem.get_text(strip=True)

        # 提取 publications (重要!)
        # 查找所有包含 publication 的 div
        publications = {}
        for div in soup.find_all('div', class_=lambda x: x and 'field--name-field-publication' in str(x)):
            field_classes = div.get('class', [])
            for cls in field_classes:
                if cls.startswith('field--name-field-publication'):
                    # 提取类型名称，如 field-publication-journal-articles -> journal-articles
                    pub_type = cls.replace('field--name-field-publication-', '').replace('-', '_')
                    pub_text = div.get_text(strip=True)
                    if pub_text:
                        publications[pub_type] = pub_text

        if publications:
            profile_data['publications'] = publications

        return profile_data

    except Exception as e:
        logger.error(f"爬取失败 {url}: {str(e)}")
        return {'error': str(e)}


def scrape_all_profiles(staff_list: List[Dict]) -> List[Dict]:
    """爬取所有 staff 的 profile 页面"""

    logger.info(f"\n开始爬取 {len(staff_list)} 位 staff 的详细 profile...")

    results = []
    for i, staff in enumerate(staff_list, 1):
        profile_url = staff.get('profile_url')

        if not profile_url:
            logger.warning(f"[{i}/{len(staff_list)}] 跳过(无URL): {staff.get('full_name', 'Unknown')}")
            staff['profile_details'] = {'error': 'No profile URL'}
            results.append(staff)
            continue

        logger.info(f"[{i}/{len(staff_list)}] 爬取: {staff.get('full_name', 'Unknown')}")

        # 爬取详细信息
        profile_details = scrape_profile_page(profile_url)

        # 合并数据
        combined_data = staff.copy()
        combined_data['profile_details'] = profile_details
        if 'error' in profile_details:
            combined_data['scrape_error'] = profile_details['error']

        results.append(combined_data)

        # 每爬取 10 个保存一次
        if i % 10 == 0:
            logger.info(f"中间保存进度: {i}/{len(staff_list)}")
            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        # 礼貌延迟
        time.sleep(2)

    logger.info(f"✓ 完成! 共爬取 {len(results)} 位 staff 的详细信息")

    # 统计
    success_count = sum(1 for r in results if 'scrape_error' not in r and r.get('profile_details'))
    error_count = sum(1 for r in results if 'scrape_error' in r)
    logger.info(f"成功: {success_count}, 失败: {error_count}")

    return results


# ============================================================================
# Main
# ============================================================================

def main():
    """主函数"""
    logger.info("="*80)
    logger.info("Step 1: 爬取 UNSW Engineering Staff 数据")
    logger.info("="*80)

    # Step 1.1: 从 API 获取基本信息
    staff_list = fetch_staff_from_api()

    # 保存基本信息到临时文件
    TEMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TEMP_FILE, 'w', encoding='utf-8') as f:
        json.dump(staff_list, f, ensure_ascii=False, indent=2)
    logger.info(f"基本信息已保存到: {TEMP_FILE}")

    # Step 1.2: 爬取详细 profile
    staff_with_profiles = scrape_all_profiles(staff_list)

    # 保存最终结果
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(staff_with_profiles, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✓ 数据已保存到: {OUTPUT_FILE}")
    logger.info("="*80)


if __name__ == '__main__':
    main()
