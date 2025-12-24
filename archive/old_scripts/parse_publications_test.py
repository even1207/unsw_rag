"""
测试版本 - 只处理前5个staff
"""
import json
import re
import requests
from time import sleep
from typing import List, Dict
import hashlib

def parse_publication_text(pub_text: str, pub_type: str) -> List[Dict]:
    """解析publication文本字符串"""
    publications = []
    pattern = rf'{re.escape(pub_type)} \| (\d{{4}})'
    entries = re.split(pattern, pub_text)

    for i in range(1, len(entries), 2):
        year = entries[i]
        content = entries[i + 1].strip()

        doi_match = re.search(r'http://dx\.doi\.org/([^\s]+)', content)
        doi = doi_match.group(1) if doi_match else None

        title_match = re.search(r"'([^']+)'", content)
        title = title_match.group(1) if title_match else None

        authors_text = content.split(',')[0].strip() if ',' in content else ""

        if title or doi:
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

def fetch_openalex(doi: str) -> Dict:
    """从OpenAlex获取单篇论文信息"""
    if not doi:
        return {"error": "no_doi"}

    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = {"User-Agent": "mailto:research@unsw.edu.au"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            abstract = invert_abstract_index(data.get("abstract_inverted_index"))

            return {
                "title": data.get("title"),
                "abstract": abstract,
                "publication_year": data.get("publication_year"),
                "authors": [
                    {"name": a.get("author", {}).get("display_name")}
                    for a in data.get("authorships", [])
                ],
                "venue": data.get("primary_location", {}).get("source", {}).get("display_name"),
                "citations_count": data.get("cited_by_count", 0),
                "is_open_access": data.get("open_access", {}).get("is_oa", False),
                "pdf_url": data.get("open_access", {}).get("oa_url"),
                "concepts": [
                    {"name": c.get("display_name"), "score": c.get("score", 0)}
                    for c in data.get("concepts", [])[:15]
                ],
            }
        else:
            return {"error": f"status_{response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def create_rag_chunks(staff_entry: Dict, publication_data: List[Dict]) -> List[Dict]:
    """创建RAG chunks"""
    chunks = []

    # Chunk 1: 人员概览
    person_chunk = {
        "chunk_id": f"person_{staff_entry['email']}",
        "chunk_type": "person_profile",
        "content": f"{staff_entry['full_name']} is a {staff_entry['role']} in {staff_entry['school']}, {staff_entry['faculty']} at UNSW Sydney.\n\n"
                   f"Biography: {staff_entry.get('biography', '')}\n\n"
                   f"Research Areas: {staff_entry.get('research_text', '')}",
        "metadata": {
            "person_name": staff_entry['full_name'],
            "role": staff_entry['role'],
            "school": staff_entry['school'],
            "faculty": staff_entry['faculty'],
            "email": staff_entry['email'],
            "profile_url": staff_entry['profile_url'],
        }
    }
    chunks.append(person_chunk)

    # Chunk 2-N: 每篇论文
    for pub in publication_data:
        oa_data = pub.get('openalex_data', {})
        if 'error' in oa_data:
            continue

        content_parts = []
        title = oa_data.get('title') or pub.get('title', 'Unknown Title')
        content_parts.append(f"Title: {title}")

        authors = oa_data.get('authors', [])
        if authors:
            author_names = [a['name'] for a in authors if a.get('name')]
            content_parts.append(f"Authors: {', '.join(author_names)}")

        year = oa_data.get('publication_year') or pub.get('year')
        venue = oa_data.get('venue')
        if venue:
            content_parts.append(f"Published in: {venue} ({year})")

        abstract = oa_data.get('abstract', '')
        if abstract:
            content_parts.append(f"\nAbstract:\n{abstract}")

        concepts = oa_data.get('concepts', [])
        high_score_concepts = [c['name'] for c in concepts if c.get('score', 0) > 0.3]
        if high_score_concepts:
            content_parts.append(f"\nKeywords: {', '.join(high_score_concepts)}")

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
                "pub_title": title,
                "pub_year": year,
                "pub_type": pub.get('pub_type'),
                "pub_doi": pub.get('doi'),
                "citations_count": oa_data.get('citations_count', 0),
                "is_open_access": oa_data.get('is_open_access', False),
                "has_abstract": bool(abstract),
            }
        }
        chunks.append(pub_chunk)

    return chunks

print("="*80)
print("Testing with first 3 staff members")
print("="*80)

# 读取数据
with open('/Users/z5241339/Documents/unsw_ai_rag/engineering_staff_with_profiles_cleaned.json', 'r') as f:
    staff_data = json.load(f)

# 只处理前3个有publications的staff
processed = 0
all_chunks = []

for staff in staff_data:
    if processed >= 3:
        break

    if not staff.get('profile_details') or not staff['profile_details'].get('publications'):
        continue

    print(f"\n{'='*80}")
    print(f"Processing: {staff['full_name']}")
    print(f"{'='*80}")

    pubs = staff['profile_details']['publications']
    staff_pubs = []

    # 解析publications
    for pub_type, pub_text in pubs.items():
        parsed = parse_publication_text(pub_text, pub_type)
        staff_pubs.extend(parsed)

    print(f"Found {len(staff_pubs)} publications")

    # 获取OpenAlex数据 (只取前3篇测试)
    print("Fetching from OpenAlex...")
    for i, pub in enumerate(staff_pubs[:3], 1):
        if pub.get('doi'):
            print(f"  [{i}/3] {pub['title'][:60]}...")
            oa_data = fetch_openalex(pub['doi'])
            pub['openalex_data'] = oa_data

            if 'error' not in oa_data:
                has_abstract = "✓" if oa_data.get('abstract') else "✗"
                print(f"         {has_abstract} Abstract, Citations: {oa_data.get('citations_count', 0)}")
            else:
                print(f"         ✗ Error: {oa_data.get('error')}")

            sleep(0.2)

    # 创建chunks
    chunks = create_rag_chunks(staff, staff_pubs[:3])
    all_chunks.extend(chunks)
    print(f"Created {len(chunks)} chunks")

    processed += 1

# 保存
output_file = '/Users/z5241339/Documents/unsw_ai_rag/rag_chunks_test.json'
with open(output_file, 'w') as f:
    json.dump(all_chunks, f, indent=2, ensure_ascii=False)

print(f"\n{'='*80}")
print("RESULTS")
print(f"{'='*80}")
print(f"Total chunks: {len(all_chunks)}")
print(f"Person chunks: {sum(1 for c in all_chunks if c['chunk_type'] == 'person_profile')}")
print(f"Publication chunks: {sum(1 for c in all_chunks if c['chunk_type'] == 'publication')}")
print(f"Saved to: {output_file}")

# 显示一个示例
print(f"\n{'='*80}")
print("SAMPLE PUBLICATION CHUNK")
print(f"{'='*80}")
pub_chunks = [c for c in all_chunks if c['chunk_type'] == 'publication']
if pub_chunks:
    sample = pub_chunks[0]
    print(f"Chunk ID: {sample['chunk_id']}")
    print(f"Person: {sample['metadata']['person_name']}")
    print(f"Title: {sample['metadata']['pub_title']}")
    print(f"\nContent Preview:")
    print(sample['content'][:500])
    print("...")
