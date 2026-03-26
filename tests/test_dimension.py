"""
UNSW Engineering AI Capability Mapping - Dimensions Data Fetcher
================================================================
这个脚本从 Postgres 读取 Engineering 学院的 staff 列表，
然后通过 Dimensions API 获取每个人的 publications, grants, patents，
最终输出两个 CSV 文件供 Copilot Studio 使用。

使用前请安装依赖：
    pip install dimcli pandas

使用方法：
    1. 把从 DBeaver 导出的 staff CSV 文件放到同目录下
    2. 填写下方的配置信息
    3. python fetch_dimensions_data.py
"""

import dimcli
import pandas as pd
import json
import time
import os
import logging
from datetime import datetime

# ============================================================
# 配置区 - 请填写你的信息
# ============================================================

# Dimensions API
DIMENSIONS_API_KEY = "5FB096C4B5FE415BA55B3949B9757997"
DIMENSIONS_ENDPOINT = "https://app.dimensions.ai"

# Staff CSV 文件路径（从 DBeaver 导出的）
STAFF_CSV_PATH = "/Users/z5241339/Documents/unsw_ai_rag/tests/staff_profiles_202603061106.csv"

# UNSW GRID ID
UNSW_GRID_ID = "grid.1005.4"

# 输出目录
OUTPUT_DIR = "output"

# 每个 staff 最多拉多少篇 publication
MAX_PUBS_PER_STAFF = 50

# 是否只跑 Engineering（设为 None 则跑全部）
FACULTY_FILTER = "Engineering"

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("fetch_dimensions.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_staff_from_csv():
    """从 CSV 文件读取 staff_profiles"""
    logger.info(f"正在从 {STAFF_CSV_PATH} 读取 staff 数据...")

    df = pd.read_csv(STAFF_CSV_PATH, encoding='utf-8-sig')
    
    if FACULTY_FILTER:
        df = df[df['faculty'] == FACULTY_FILTER]
    
    df = df.sort_values(['last_name', 'first_name']).reset_index(drop=True)

    logger.info(f"读取到 {len(df)} 条 staff 记录")
    return df


def init_dimensions():
    """初始化 Dimensions API 连接"""
    logger.info("正在连接 Dimensions API...")
    dimcli.login(key=DIMENSIONS_API_KEY, endpoint=DIMENSIONS_ENDPOINT)
    dsl = dimcli.Dsl()
    
    # 测试连接
    test = dsl.query('search publications where research_orgs = "grid.1005.4" return publications limit 1')
    if hasattr(test, 'publications') and len(test.publications) > 0:
        logger.info("Dimensions API 连接成功")
    else:
        logger.warning("Dimensions API 连接可能有问题，请检查 key")
    
    return dsl


def search_researcher_id(dsl, first_name, last_name):
    """
    通过姓名 + UNSW 在 Dimensions 中查找 researcher_id
    返回: (researcher_id, match_status)
    match_status: 'exact' / 'multiple' / 'not_found'
    """
    query = f'''
        search researchers 
        where first_name = "{first_name}" 
        and last_name = "{last_name}"
        and research_orgs = "{UNSW_GRID_ID}"
        return researchers[basics+extras] limit 5
    '''
    
    try:
        result = dsl.query(query)
        researchers = result.json.get('researchers', [])
        
        if len(researchers) == 1:
            return researchers[0].get('id'), 'exact'
        elif len(researchers) > 1:
            return researchers[0].get('id'), 'multiple'
        else:
            return None, 'not_found'
    except Exception as e:
        logger.error(f"查找 researcher_id 失败 ({first_name} {last_name}): {e}")
        return None, 'error'


def fetch_publications(dsl, researcher_id, first_name, last_name):
    """获取某个研究者的 publications"""
    if researcher_id:
        query = f'''
            search publications 
            where researchers.id = "{researcher_id}"
            return publications[
                id+title+doi+year+type+times_cited+
                journal+concepts+abstract+
                source_title+field_citation_ratio
            ] sort by times_cited limit {MAX_PUBS_PER_STAFF}
        '''
    else:
        # 没有 researcher_id，用姓名 + UNSW 匹配
        query = f'''
            search publications 
            where authors = "{first_name} {last_name}"
            and research_orgs = "{UNSW_GRID_ID}"
            return publications[
                id+title+doi+year+type+times_cited+
                journal+concepts+abstract+
                source_title+field_citation_ratio
            ] sort by times_cited limit {MAX_PUBS_PER_STAFF}
        '''
    
    try:
        result = dsl.query(query)
        return result.json.get('publications', [])
    except Exception as e:
        logger.error(f"获取 publications 失败 ({first_name} {last_name}): {e}")
        return []


def fetch_grants(dsl, researcher_id, first_name, last_name):
    """获取某个研究者的 grants"""
    if researcher_id:
        query = f'''
            search grants 
            where researchers.id = "{researcher_id}"
            return grants[
                id+title+start_date+end_date+
                funding_aud+funder_org_name+
                funder_countries+concepts
            ] limit 50
        '''
    else:
        query = f'''
            search grants 
            where investigators = "{first_name} {last_name}"
            and research_orgs = "{UNSW_GRID_ID}"
            return grants[
                id+title+start_date+end_date+
                funding_aud+funder_org_name+
                funder_countries+concepts
            ] limit 50
        '''
    
    try:
        result = dsl.query(query)
        return result.json.get('grants', [])
    except Exception as e:
        logger.error(f"获取 grants 失败 ({first_name} {last_name}): {e}")
        return []


def fetch_patents(dsl, researcher_id, first_name, last_name):
    """获取某个研究者的 patents"""
    if researcher_id:
        query = f'''
            search patents 
            where researchers.id = "{researcher_id}"
            return patents[id+title+year+times_cited] limit 20
        '''
    else:
        query = f'''
            search patents 
            where inventors = "{first_name} {last_name}"
            and assignees = "{UNSW_GRID_ID}"
            return patents[id+title+year+times_cited] limit 20
        '''
    
    try:
        result = dsl.query(query)
        return result.json.get('patents', [])
    except Exception as e:
        logger.error(f"获取 patents 失败 ({first_name} {last_name}): {e}")
        return []


def extract_concepts(items):
    """从 publications/grants 的 concepts 字段提取关键词"""
    all_concepts = []
    for item in items:
        concepts = item.get('concepts', [])
        if isinstance(concepts, list):
            for c in concepts:
                if isinstance(c, str):
                    all_concepts.append(c)
                elif isinstance(c, dict):
                    all_concepts.append(c.get('concept', ''))
    # 去重并取前 20 个
    seen = set()
    unique = []
    for c in all_concepts:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            unique.append(c)
    return unique[:20]


def process_staff(dsl, staff_row):
    """处理单个 staff，返回汇总数据和详细 publication 列表"""
    first_name = staff_row['first_name']
    last_name = staff_row['last_name']
    full_name = staff_row['full_name']
    
    logger.info(f"正在处理: {full_name}")
    
    # Step 1: 查找 Dimensions researcher_id
    researcher_id, match_status = search_researcher_id(dsl, first_name, last_name)
    time.sleep(2.1)  # Dimensions 限制 30 请求/分钟

    # Step 2: 获取 publications
    publications = fetch_publications(dsl, researcher_id, first_name, last_name)
    time.sleep(2.1)

    # Step 3: 获取 grants
    grants = fetch_grants(dsl, researcher_id, first_name, last_name)
    time.sleep(2.1)

    # Step 4: 获取 patents
    patents = fetch_patents(dsl, researcher_id, first_name, last_name)
    time.sleep(2.1)

    # ---- 汇总数据（用于 staff_capability.csv）----
    
    # Top 5 最高引用的 publication 标题
    sorted_pubs = sorted(publications, key=lambda x: x.get('times_cited', 0), reverse=True)
    top5_titles = "; ".join([p.get('title', '') for p in sorted_pubs[:5]])
    all_pub_titles = "; ".join([p.get('title', '') for p in sorted_pubs[:20]])
    
    # Grant 标题和资助机构
    grant_titles = "; ".join([g.get('title', '') for g in grants])
    grant_funders = "; ".join(set([
        g.get('funder_org_name', '') for g in grants if g.get('funder_org_name')
    ]))
    
    # Patent 标题
    patent_titles = "; ".join([p.get('title', '') for p in patents])
    
    # 研究关键词（从 publications + grants 的 concepts 合并）
    research_keywords = "; ".join(extract_concepts(publications + grants))
    
    # 总引用数
    total_citations = sum(p.get('times_cited', 0) for p in publications)
    
    # 最新发表年份
    pub_years = [p.get('year', 0) for p in publications if p.get('year')]
    latest_pub_year = max(pub_years) if pub_years else None
    
    # 总资助金额
    total_funding = sum(g.get('funding_aud', 0) or 0 for g in grants)

    capability_row = {
        'profile_url': staff_row['profile_url'],
        'first_name': first_name,
        'last_name': last_name,
        'full_name': full_name,
        'role': staff_row['role'],
        'faculty': staff_row['faculty'],
        'school': staff_row['school'],
        'email': staff_row['email'],
        'photo_url': staff_row.get('photo_url', ''),
        'summary': staff_row.get('summary', ''),
        'biography': staff_row.get('biography', ''),
        'research_text': staff_row.get('research_text', ''),
        'dimensions_researcher_id': researcher_id or '',
        'match_status': match_status,
        'total_publications': len(publications),
        'total_citations': total_citations,
        'total_grants': len(grants),
        'total_funding_aud': total_funding,
        'total_patents': len(patents),
        'latest_pub_year': latest_pub_year,
        'top5_publication_titles': top5_titles,
        'all_publication_titles': all_pub_titles,
        'grant_titles': grant_titles,
        'grant_funders': grant_funders,
        'patent_titles': patent_titles,
        'research_keywords': research_keywords,
    }

    # ---- 详细 publication 列表（用于 publications_detail.csv）----
    pub_details = []
    for p in publications:
        journal = p.get('journal', {})
        journal_title = journal.get('title', '') if isinstance(journal, dict) else str(journal)
        
        pub_details.append({
            'staff_full_name': full_name,
            'staff_profile_url': staff_row['profile_url'],
            'faculty': staff_row['faculty'],
            'school': staff_row['school'],
            'publication_id': p.get('id', ''),
            'title': p.get('title', ''),
            'doi': p.get('doi', ''),
            'year': p.get('year', ''),
            'type': p.get('type', ''),
            'journal': journal_title,
            'times_cited': p.get('times_cited', 0),
            'field_citation_ratio': p.get('field_citation_ratio', ''),
            'abstract': (p.get('abstract', '') or '')[:500],  # 截断 abstract 控制大小
            'concepts': "; ".join(extract_concepts([p])),
        })

    return capability_row, pub_details


def save_progress(capability_rows, pub_detail_rows, suffix=""):
    """保存中间结果，防止中断丢失数据"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if capability_rows:
        df1 = pd.DataFrame(capability_rows)
        path1 = os.path.join(OUTPUT_DIR, f"staff_capability{suffix}.csv")
        df1.to_csv(path1, index=False, encoding='utf-8-sig')
        logger.info(f"已保存 {len(df1)} 条 staff 记录到 {path1}")

    if pub_detail_rows:
        df2 = pd.DataFrame(pub_detail_rows)
        path2 = os.path.join(OUTPUT_DIR, f"publications_detail{suffix}.csv")
        df2.to_csv(path2, index=False, encoding='utf-8-sig')
        logger.info(f"已保存 {len(df2)} 条 publication 记录到 {path2}")


def main():
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("UNSW AI Capability Mapping - 开始数据获取")
    logger.info("=" * 60)

    # 1. 读取 staff 列表
    staff_df = get_staff_from_csv()

    # 2. 初始化 Dimensions API
    dsl = init_dimensions()

    # 3. 逐个处理 staff
    capability_rows = []
    pub_detail_rows = []
    
    total = len(staff_df)
    
    for idx, row in staff_df.iterrows():
        logger.info(f"进度: {idx + 1}/{total} ({(idx + 1) / total * 100:.1f}%)")
        
        try:
            cap_row, pub_rows = process_staff(dsl, row)
            capability_rows.append(cap_row)
            pub_detail_rows.extend(pub_rows)
        except Exception as e:
            logger.error(f"处理 {row['full_name']} 时出错: {e}")
            # 记录一条空数据，确保不丢失这个人
            capability_rows.append({
                'profile_url': row['profile_url'],
                'full_name': row['full_name'],
                'role': row['role'],
                'faculty': row['faculty'],
                'school': row['school'],
                'email': row['email'],
                'match_status': 'error',
            })
        
        # 每处理 50 人保存一次中间结果
        if (idx + 1) % 50 == 0:
            save_progress(capability_rows, pub_detail_rows, suffix="_checkpoint")
            logger.info(f"已保存 checkpoint ({idx + 1}/{total})")

    # 4. 保存最终结果
    save_progress(capability_rows, pub_detail_rows)
    
    # 5. 打印统计
    elapsed = datetime.now() - start_time
    df_cap = pd.DataFrame(capability_rows)
    
    logger.info("=" * 60)
    logger.info("完成！统计信息：")
    logger.info(f"  总 staff 数: {len(df_cap)}")
    logger.info(f"  精确匹配: {len(df_cap[df_cap.get('match_status', '') == 'exact'])} 人")
    logger.info(f"  多重匹配: {len(df_cap[df_cap.get('match_status', '') == 'multiple'])} 人")
    logger.info(f"  未找到: {len(df_cap[df_cap.get('match_status', '') == 'not_found'])} 人")
    logger.info(f"  总 publications: {len(pub_detail_rows)} 条")
    logger.info(f"  耗时: {elapsed}")
    logger.info("=" * 60)
    logger.info(f"输出文件:")
    logger.info(f"  1. {OUTPUT_DIR}/staff_capability.csv (上传到 Copilot Studio)")
    logger.info(f"  2. {OUTPUT_DIR}/publications_detail.csv (上传到 Copilot Studio)")


if __name__ == "__main__":
    main()