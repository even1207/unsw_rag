"""
测试从不同API获取论文信息
"""
import requests
import json
from time import sleep

# 测试的DOI列表
test_dois = [
    "10.1038/s41467-022-29711-9",  # Nature Communications - 应该是OA
    "10.1016/j.watres.2020.116422",  # Water Research
    "10.1016/j.tbs.2024.100919",  # Travel Behaviour and Society
]

def fetch_openalex(doi):
    """OpenAlex API - 免费、无需API key、数据丰富"""
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = {"User-Agent": "mailto:research@unsw.edu.au"}  # 礼貌性标识

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "source": "OpenAlex",
                "title": data.get("title"),
                "abstract": data.get("abstract_inverted_index"),  # 需要反转
                "publication_year": data.get("publication_year"),
                "authors": [{"name": a.get("author", {}).get("display_name")}
                           for a in data.get("authorships", [])],
                "venue": data.get("primary_location", {}).get("source", {}).get("display_name"),
                "citations_count": data.get("cited_by_count"),
                "open_access": data.get("open_access", {}).get("is_oa"),
                "pdf_url": data.get("open_access", {}).get("oa_url"),
                "keywords": [c.get("display_name") for c in data.get("concepts", [])[:10]],
                "referenced_works_count": len(data.get("referenced_works", [])),
            }
    except Exception as e:
        return {"source": "OpenAlex", "error": str(e)}

def fetch_semantic_scholar(doi):
    """Semantic Scholar API - 免费、无需API key、有abstract"""
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {
        "fields": "title,abstract,year,authors,citationCount,influentialCitationCount,venue,publicationTypes,tldr,embedding"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "source": "Semantic Scholar",
                "title": data.get("title"),
                "abstract": data.get("abstract"),  # 直接是文本
                "tldr": data.get("tldr", {}).get("text"),  # AI生成的摘要
                "year": data.get("year"),
                "authors": [a.get("name") for a in data.get("authors", [])],
                "venue": data.get("venue"),
                "citation_count": data.get("citationCount"),
                "influential_citations": data.get("influentialCitationCount"),
            }
    except Exception as e:
        return {"source": "Semantic Scholar", "error": str(e)}

def fetch_crossref(doi):
    """Crossref API - 最权威的metadata"""
    url = f"https://api.crossref.org/works/{doi}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()["message"]
            return {
                "source": "Crossref",
                "title": data.get("title", [""])[0],
                "abstract": data.get("abstract"),  # 很多论文没有
                "authors": [{"given": a.get("given"), "family": a.get("family")}
                           for a in data.get("author", [])],
                "published": data.get("published", {}).get("date-parts", [[]])[0],
                "publisher": data.get("publisher"),
                "type": data.get("type"),
            }
    except Exception as e:
        return {"source": "Crossref", "error": str(e)}

def invert_abstract(inverted_index):
    """将OpenAlex的倒排索引转换为正常文本"""
    if not inverted_index:
        return None

    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word

    return " ".join([words[i] for i in sorted(words.keys())])

print("="*80)
print("测试论文信息获取")
print("="*80)

for doi in test_dois:
    print(f"\n{'='*80}")
    print(f"DOI: {doi}")
    print(f"{'='*80}\n")

    # 测试 OpenAlex
    print("--- OpenAlex ---")
    oa_data = fetch_openalex(doi)
    if "error" not in oa_data:
        print(f"✓ Title: {oa_data['title'][:80]}...")
        abstract = invert_abstract(oa_data.get('abstract'))
        if abstract:
            print(f"✓ Abstract: {abstract[:200]}...")
        else:
            print("✗ No abstract")
        print(f"✓ Authors: {len(oa_data['authors'])} authors")
        print(f"✓ Citations: {oa_data['citations_count']}")
        print(f"✓ Open Access: {oa_data['open_access']}")
        if oa_data['pdf_url']:
            print(f"✓ PDF URL: {oa_data['pdf_url']}")
        print(f"✓ Keywords: {', '.join(oa_data['keywords'][:5])}")
    else:
        print(f"✗ Error: {oa_data['error']}")

    sleep(0.5)  # 礼貌性延迟

    # 测试 Semantic Scholar
    print("\n--- Semantic Scholar ---")
    ss_data = fetch_semantic_scholar(doi)
    if "error" not in ss_data:
        print(f"✓ Title: {ss_data['title'][:80]}..." if ss_data['title'] else "✗ No title")
        if ss_data['abstract']:
            print(f"✓ Abstract: {ss_data['abstract'][:200]}...")
        else:
            print("✗ No abstract")
        if ss_data.get('tldr'):
            print(f"✓ TLDR: {ss_data['tldr']}")
        print(f"✓ Citations: {ss_data['citation_count']} (influential: {ss_data['influential_citations']})")
    else:
        print(f"✗ Error: {ss_data['error']}")

    sleep(0.5)

    # 测试 Crossref
    print("\n--- Crossref ---")
    cr_data = fetch_crossref(doi)
    if "error" not in cr_data:
        print(f"✓ Title: {cr_data['title'][:80]}..." if cr_data['title'] else "✗ No title")
        if cr_data['abstract']:
            print(f"✓ Abstract: {cr_data['abstract'][:200]}...")
        else:
            print("✗ No abstract")
        print(f"✓ Publisher: {cr_data['publisher']}")
    else:
        print(f"✗ Error: {cr_data['error']}")

    print("\n" + "="*80)

print("\n\n总结:")
print("="*80)
print("OpenAlex: 最丰富的数据,包括abstract、keywords、OA状态、PDF链接")
print("Semantic Scholar: 高质量abstract + TLDR,citation分析")
print("Crossref: 权威metadata,但abstract覆盖率低")
print("\n推荐: OpenAlex为主 + Semantic Scholar补充")
