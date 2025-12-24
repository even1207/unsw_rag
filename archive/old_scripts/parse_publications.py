"""
解析UNSW工程学院staff数据,提取publications并从OpenAlex获取详细信息
生成适合RAG的分块文档
"""
import json
import re
import requests
from time import sleep
from typing import List, Dict, Optional
from datetime import datetime
from tqdm import tqdm
import hashlib

def parse_publication_text(pub_text: str, pub_type: str) -> List[Dict]:
    """
    解析publication文本字符串,提取individual publications

    格式示例:
    "Journal articles | 2025 Abdoli S; Djukic L, 2025, 'Title', Journal Name, 136, pp. 201 - 206, DOI"
    """
    publications = []

    # 按照 "类型 | 年份" 分割
    pattern = rf'{re.escape(pub_type)} \| (\d{{4}})'
    entries = re.split(pattern, pub_text)

    # entries格式: ['', '2025', '内容1', '2025', '内容2', ...]
    for i in range(1, len(entries), 2):
        year = entries[i]
        content = entries[i + 1].strip()

        # 提取DOI
        doi_match = re.search(r'http://dx\.doi\.org/([^\s]+)', content)
        doi = doi_match.group(1) if doi_match else None

        # 提取标题 (在单引号之间)
        title_match = re.search(r"'([^']+)'", content)
        title = title_match.group(1) if title_match else None

        # 提取作者 (逗号之前的部分)
        authors_text = content.split(',')[0].strip() if ',' in content else ""

        if title or doi:  # 至少要有title或DOI
            publications.append({
                'year': year,
                'title': title,
                'doi': doi,
                'authors_text': authors_text,
                'raw_text': content,
                'pub_type': pub_type
            })

    return publications

def invert_abstract_index(inverted_index: Dict) -> str:
    """将OpenAlex的倒排索引转换为正常文本"""
    if not inverted_index:
        return ""

    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word

    return " ".join([words[i] for i in sorted(words.keys())])

def fetch_openalex_batch(dois: List[str], email: str = "research@unsw.edu.au") -> Dict[str, Dict]:
    """
    批量从OpenAlex获取论文信息
    OpenAlex支持批量查询,更高效
    """
    results = {}

    # OpenAlex单次API调用
    for doi in dois:
        if not doi:
            continue

        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        headers = {"User-Agent": f"mailto:{email}"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                # 提取关键信息
                abstract = invert_abstract_index(data.get("abstract_inverted_index"))

                results[doi] = {
                    "title": data.get("title"),
                    "abstract": abstract,
                    "publication_year": data.get("publication_year"),
                    "authors": [
                        {
                            "name": a.get("author", {}).get("display_name"),
                            "orcid": a.get("author", {}).get("orcid"),
                        }
                        for a in data.get("authorships", [])
                    ],
                    "venue": data.get("primary_location", {}).get("source", {}).get("display_name"),
                    "citations_count": data.get("cited_by_count", 0),
                    "is_open_access": data.get("open_access", {}).get("is_oa", False),
                    "pdf_url": data.get("open_access", {}).get("oa_url"),
                    "concepts": [
                        {
                            "name": c.get("display_name"),
                            "score": c.get("score", 0),
                            "level": c.get("level", 0)
                        }
                        for c in data.get("concepts", [])[:15]
                    ],
                    "referenced_works_count": len(data.get("referenced_works", [])),
                    "type": data.get("type"),
                    "language": data.get("language"),
                }
            elif response.status_code == 404:
                results[doi] = {"error": "not_found"}
            else:
                results[doi] = {"error": f"status_{response.status_code}"}

        except Exception as e:
            results[doi] = {"error": str(e)}

        sleep(0.1)  # 礼貌性延迟,避免rate limit

    return results

def create_rag_chunks(staff_entry: Dict, publication_data: Dict) -> List[Dict]:
    """
    为每个研究人员创建多个RAG chunks:
    1. 人员概览chunk (biography + research areas)
    2. 每篇论文一个chunk (title + abstract + metadata)
    """
    chunks = []

    # Chunk 1: 研究人员概览
    person_chunk = {
        "chunk_id": f"person_{staff_entry['email']}",
        "chunk_type": "person_profile",
        "content": f"{staff_entry['full_name']} is a {staff_entry['role']} in {staff_entry['school']}, {staff_entry['faculty']} at UNSW Sydney.\n\n"
                   f"Biography: {staff_entry.get('biography', '')}\n\n"
                   f"Research Areas: {staff_entry.get('research_text', '')}",
        "metadata": {
            "person_name": staff_entry['full_name'],
            "first_name": staff_entry['first_name'],
            "last_name": staff_entry['last_name'],
            "role": staff_entry['role'],
            "school": staff_entry['school'],
            "faculty": staff_entry['faculty'],
            "email": staff_entry['email'],
            "profile_url": staff_entry['profile_url'],
            "photo_url": staff_entry.get('photo_url'),
        }
    }
    chunks.append(person_chunk)

    # Chunk 2-N: 每篇论文
    for pub in publication_data:
        if 'error' in pub.get('openalex_data', {}):
            continue  # 跳过无法获取数据的论文

        oa_data = pub.get('openalex_data', {})

        # 构建论文内容
        content_parts = []

        # 标题和基本信息
        title = oa_data.get('title') or pub.get('title', 'Unknown Title')
        content_parts.append(f"Title: {title}")

        # 作者
        authors = oa_data.get('authors', [])
        if authors:
            author_names = [a['name'] for a in authors if a.get('name')]
            content_parts.append(f"Authors: {', '.join(author_names)}")

        # 发表信息
        year = oa_data.get('publication_year') or pub.get('year')
        venue = oa_data.get('venue')
        if venue:
            content_parts.append(f"Published in: {venue} ({year})")
        else:
            content_parts.append(f"Publication Year: {year}")

        # Abstract (最重要的内容)
        abstract = oa_data.get('abstract', '')
        if abstract:
            content_parts.append(f"\nAbstract:\n{abstract}")

        # Keywords/Concepts
        concepts = oa_data.get('concepts', [])
        if concepts:
            # 只保留高分的concepts
            high_score_concepts = [c['name'] for c in concepts if c.get('score', 0) > 0.3]
            if high_score_concepts:
                content_parts.append(f"\nKeywords: {', '.join(high_score_concepts)}")

        # 生成唯一ID
        pub_id = pub.get('doi') or hashlib.md5(title.encode()).hexdigest()

        pub_chunk = {
            "chunk_id": f"pub_{pub_id}",
            "chunk_type": "publication",
            "content": "\n".join(content_parts),
            "metadata": {
                "person_name": staff_entry['full_name'],
                "person_email": staff_entry['email'],
                "person_profile_url": staff_entry['profile_url'],
                "person_school": staff_entry['school'],
                "person_faculty": staff_entry['faculty'],
                "pub_title": title,
                "pub_year": year,
                "pub_type": pub.get('pub_type'),
                "pub_doi": pub.get('doi'),
                "pub_venue": venue,
                "citations_count": oa_data.get('citations_count', 0),
                "is_open_access": oa_data.get('is_open_access', False),
                "pdf_url": oa_data.get('pdf_url'),
                "has_abstract": bool(abstract),
                "concepts": [c['name'] for c in concepts[:10]],
            }
        }
        chunks.append(pub_chunk)

    return chunks

def main():
    """主处理流程"""
    print("="*80)
    print("UNSW Engineering Staff Publications Parser")
    print("="*80)

    # 1. 读取原始数据
    print("\n[1/5] Loading data...")
    with open('/Users/z5241339/Documents/unsw_ai_rag/engineering_staff_with_profiles_cleaned.json', 'r') as f:
        staff_data = json.load(f)
    print(f"✓ Loaded {len(staff_data)} staff members")

    # 2. 解析所有publications
    print("\n[2/5] Parsing publications from raw text...")
    all_publications = []
    staff_with_pubs = []

    for staff in tqdm(staff_data):
        if not staff.get('profile_details') or not staff['profile_details'].get('publications'):
            continue

        pubs = staff['profile_details']['publications']
        staff_pubs = []

        for pub_type, pub_text in pubs.items():
            parsed = parse_publication_text(pub_text, pub_type)
            for pub in parsed:
                pub['person_email'] = staff['email']
                pub['person_name'] = staff['full_name']
                staff_pubs.extend(parsed)

        if staff_pubs:
            staff_with_pubs.append({
                'staff': staff,
                'publications': staff_pubs
            })
            all_publications.extend(staff_pubs)

    print(f"✓ Found {len(all_publications)} publications from {len(staff_with_pubs)} staff members")

    # 3. 收集所有DOI
    print("\n[3/5] Collecting DOIs...")
    dois = [pub['doi'] for pub in all_publications if pub.get('doi')]
    print(f"✓ Found {len(dois)} publications with DOI")

    # 4. 从OpenAlex获取详细信息
    print("\n[4/5] Fetching publication details from OpenAlex...")
    print("(This may take a while... ~10 papers/second)")

    openalex_data = {}
    batch_size = 1  # 逐个处理,可以看到进度

    for i in tqdm(range(0, len(dois), batch_size)):
        batch = dois[i:i+batch_size]
        batch_results = fetch_openalex_batch(batch)
        openalex_data.update(batch_results)

    # 统计
    success = sum(1 for v in openalex_data.values() if 'error' not in v)
    with_abstract = sum(1 for v in openalex_data.values() if v.get('abstract'))

    print(f"✓ Successfully fetched {success}/{len(dois)} publications")
    print(f"✓ {with_abstract} publications have abstracts")

    # 5. 生成RAG chunks
    print("\n[5/5] Creating RAG chunks...")
    all_chunks = []

    for item in tqdm(staff_with_pubs):
        staff = item['staff']
        pubs = item['publications']

        # 添加OpenAlex数据到publications
        for pub in pubs:
            if pub.get('doi'):
                pub['openalex_data'] = openalex_data.get(pub['doi'], {})

        chunks = create_rag_chunks(staff, pubs)
        all_chunks.extend(chunks)

    print(f"✓ Created {len(all_chunks)} chunks")

    # 6. 保存结果
    output_file = '/Users/z5241339/Documents/unsw_ai_rag/rag_chunks.json'
    print(f"\n[6/6] Saving to {output_file}...")

    with open(output_file, 'w') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(all_chunks)} chunks")

    # 统计信息
    print("\n" + "="*80)
    print("STATISTICS")
    print("="*80)
    person_chunks = [c for c in all_chunks if c['chunk_type'] == 'person_profile']
    pub_chunks = [c for c in all_chunks if c['chunk_type'] == 'publication']
    pubs_with_abstract = [c for c in pub_chunks if c['metadata']['has_abstract']]

    print(f"Person profile chunks: {len(person_chunks)}")
    print(f"Publication chunks: {len(pub_chunks)}")
    print(f"  - With abstract: {len(pubs_with_abstract)} ({len(pubs_with_abstract)/len(pub_chunks)*100:.1f}%)")
    print(f"  - Open Access: {sum(1 for c in pub_chunks if c['metadata']['is_open_access'])}")
    print(f"  - With PDF URL: {sum(1 for c in pub_chunks if c['metadata']['pdf_url'])}")

    print("\n✓ Done!")

if __name__ == "__main__":
    main()
