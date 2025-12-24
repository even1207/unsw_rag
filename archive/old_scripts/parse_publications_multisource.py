"""
多源版本 - 按优先级从多个API获取abstract
优先级: OpenAlex > Semantic Scholar > Crossref > PubMed
"""
import json
import re
import requests
from time import sleep
from typing import List, Dict, Optional
import hashlib
import os
from datetime import datetime

# 配置
CONFIG = {
    "input_file": "/Users/z5241339/Documents/unsw_ai_rag/engineering_staff_with_profiles_cleaned.json",
    "output_file": "/Users/z5241339/Documents/unsw_ai_rag/rag_chunks_multisource.json",
    "progress_file": "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource.json",
    "stats_file": "/Users/z5241339/Documents/unsw_ai_rag/parsing_statistics_multisource.json",
    "max_retries": 3,
    "retry_delay": 1.0,
    "api_delay": 0.15,
    "email": "research@unsw.edu.au",
}

class MultiSourceFetcher:
    """多源Abstract获取器"""

    def __init__(self, stats_tracker):
        self.stats = stats_tracker

    def fetch_abstract(self, doi: str) -> Dict:
        """
        按优先级尝试多个源获取abstract
        返回: {abstract, source, ...其他metadata}
        """
        if not doi:
            return {"error": "no_doi"}

        # 1. OpenAlex (优先,数据最全)
        result = self._fetch_openalex(doi)
        if result and result.get('abstract'):
            result['abstract_source'] = 'OpenAlex'
            self.stats['abstract_sources']['openalex'] += 1
            return result

        # 保存OpenAlex的metadata (即使没有abstract)
        base_data = result if result and 'error' not in result else {}

        # 2. Semantic Scholar (高质量abstract + TLDR)
        abstract = self._fetch_semantic_scholar(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'Semantic Scholar'
            self.stats['abstract_sources']['semantic_scholar'] += 1
            return base_data

        # 3. Crossref
        abstract = self._fetch_crossref(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'Crossref'
            self.stats['abstract_sources']['crossref'] += 1
            return base_data

        # 4. PubMed (主要用于生物医学论文)
        abstract = self._fetch_pubmed(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'PubMed'
            self.stats['abstract_sources']['pubmed'] += 1
            return base_data

        # 如果都没有abstract,返回OpenAlex的数据
        if base_data:
            base_data['abstract_source'] = 'none'
        return base_data if base_data else {"error": "not_found"}

    def _fetch_openalex(self, doi: str) -> Optional[Dict]:
        """从OpenAlex获取"""
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        headers = {"User-Agent": f"mailto:{CONFIG['email']}"}

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                abstract = self._invert_abstract_index(data.get("abstract_inverted_index"))

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
                        for c in data.get("concepts", [])[:20]
                    ],
                    "type": data.get("type"),
                }
            return None
        except Exception as e:
            self.stats['errors'].append(f"OpenAlex error for {doi}: {str(e)}")
            return None

    def _fetch_semantic_scholar(self, doi: str) -> Optional[str]:
        """从Semantic Scholar获取abstract"""
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        params = {"fields": "abstract,tldr"}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # 优先用abstract,其次用TLDR
                abstract = data.get('abstract')
                if abstract:
                    return abstract
                # TLDR是AI生成的摘要,也很有价值
                tldr = data.get('tldr', {}).get('text') if data.get('tldr') else None
                if tldr:
                    return f"[TLDR] {tldr}"
            return None
        except:
            return None

    def _fetch_crossref(self, doi: str) -> Optional[str]:
        """从Crossref获取abstract"""
        url = f"https://api.crossref.org/works/{doi}"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()['message']
                abstract = data.get('abstract', '')
                if abstract:
                    # 清理HTML标签
                    abstract = re.sub(r'<[^>]+>', '', abstract)
                    abstract = abstract.strip()
                    return abstract if abstract else None
            return None
        except:
            return None

    def _fetch_pubmed(self, doi: str) -> Optional[str]:
        """从PubMed获取abstract"""
        # 先通过DOI搜索PMID
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": f"{doi}[DOI]",
            "retmode": "json"
        }

        try:
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                id_list = data.get('esearchresult', {}).get('idlist', [])
                if id_list:
                    pmid = id_list[0]
                    # 获取abstract
                    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                    params = {
                        "db": "pubmed",
                        "id": pmid,
                        "retmode": "xml"
                    }
                    sleep(0.2)  # PubMed要求延迟
                    response = requests.get(fetch_url, params=params, timeout=10)
                    if response.status_code == 200:
                        # 提取abstract文本
                        match = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>',
                                        response.text, re.DOTALL)
                        if match:
                            abstract = match.group(1).strip()
                            # 清理XML实体
                            abstract = re.sub(r'&lt;', '<', abstract)
                            abstract = re.sub(r'&gt;', '>', abstract)
                            abstract = re.sub(r'&amp;', '&', abstract)
                            return abstract
            return None
        except:
            return None

    def _invert_abstract_index(self, inverted_index: Dict) -> str:
        """将OpenAlex的倒排索引转换为正常文本"""
        if not inverted_index:
            return ""
        try:
            words = {}
            for word, positions in inverted_index.items():
                for pos in positions:
                    words[pos] = word
            return " ".join([words[i] for i in sorted(words.keys())])
        except:
            return ""

class PublicationParser:
    def __init__(self):
        self.stats = {
            "start_time": datetime.now().isoformat(),
            "total_staff": 0,
            "staff_with_publications": 0,
            "total_publications_parsed": 0,
            "publications_with_doi": 0,
            "publications_with_abstract": 0,
            "publications_open_access": 0,
            "total_citations": 0,
            "chunks_created": 0,
            "abstract_sources": {
                "openalex": 0,
                "semantic_scholar": 0,
                "crossref": 0,
                "pubmed": 0,
                "none": 0
            },
            "errors": []
        }
        self.progress = self.load_progress()
        self.fetcher = MultiSourceFetcher(self.stats)

    def load_progress(self) -> Dict:
        if os.path.exists(CONFIG["progress_file"]):
            with open(CONFIG["progress_file"], 'r') as f:
                return json.load(f)
        return {
            "processed_staff_emails": [],
            "publication_cache": {}
        }

    def save_progress(self):
        with open(CONFIG["progress_file"], 'w') as f:
            json.dump(self.progress, f, indent=2)

    def save_stats(self):
        self.stats["end_time"] = datetime.now().isoformat()
        with open(CONFIG["stats_file"], 'w') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def parse_publication_text(self, pub_text: str, pub_type: str) -> List[Dict]:
        """解析publication文本"""
        publications = []
        # Many "Other" sections actually contain entries like "Conference Papers | 2025".
        # Instead of relying on the dict key, detect the actual label inside the text.
        split_pattern = re.compile(r'([A-Za-z][A-Za-z\s/&()\-\']+?)\s\|\s(\d{4})', re.IGNORECASE)

        try:
            matches = list(split_pattern.finditer(pub_text))
            for idx, match in enumerate(matches):
                entry_label = match.group(1).strip()
                year = match.group(2)

                start = match.end()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(pub_text)
                content = pub_text[start:end].strip()
                if not content:
                    continue

                doi_match = re.search(r'https?://(?:dx\.)?doi\.org/([^\s,]+)', content, re.IGNORECASE)
                doi = doi_match.group(1) if doi_match else None

                title_match = re.search(r"'([^']+)'", content)
                title = title_match.group(1) if title_match else None

                if title or doi:
                    publications.append({
                        'year': int(year) if year.isdigit() else year,
                        'title': title,
                        'doi': doi,
                        'raw_text': content,
                        'pub_type': entry_label or pub_type
                    })
        except Exception as e:
            self.stats["errors"].append(f"Parse error: {str(e)}")

        return publications

    def create_rag_chunks(self, staff_entry: Dict, publication_data: List[Dict]) -> List[Dict]:
        """创建RAG chunks"""
        chunks = []

        # Person basic chunk
        person_basic = {
            "chunk_id": f"person_basic_{staff_entry['email']}",
            "chunk_type": "person_basic",
            "content": f"{staff_entry['full_name']}\n"
                       f"Position: {staff_entry['role']}\n"
                       f"School: {staff_entry['school']}\n"
                       f"Faculty: {staff_entry['faculty']}",
            "metadata": {
                "person_name": staff_entry['full_name'],
                "person_email": staff_entry['email'],
                "role": staff_entry['role'],
                "school": staff_entry['school'],
                "faculty": staff_entry['faculty'],
                "profile_url": staff_entry['profile_url'],
            }
        }
        chunks.append(person_basic)

        # Person biography chunk
        if staff_entry.get('biography'):
            person_bio = {
                "chunk_id": f"person_bio_{staff_entry['email']}",
                "chunk_type": "person_biography",
                "content": f"{staff_entry['full_name']} - Research Profile\n\n"
                           f"{staff_entry['biography']}\n\n"
                           f"Research Areas: {staff_entry.get('research_text', '')}",
                "metadata": {
                    "person_name": staff_entry['full_name'],
                    "person_email": staff_entry['email'],
                    "school": staff_entry['school'],
                    "profile_url": staff_entry['profile_url'],
                }
            }
            chunks.append(person_bio)

        # Publication chunks
        for pub in publication_data:
            pub_data = pub.get('publication_data', {})
            if 'error' in pub_data:
                continue

            pub_chunks = self._create_publication_chunks(staff_entry, pub, pub_data)
            chunks.extend(pub_chunks)

        self.stats["chunks_created"] += len(chunks)
        return chunks

    def _create_publication_chunks(self, staff: Dict, pub: Dict, pub_data: Dict) -> List[Dict]:
        """创建论文chunks"""
        chunks = []

        title = pub_data.get('title') or pub.get('title', 'Unknown')
        pub_id = pub.get('doi') or hashlib.md5(title.encode()).hexdigest()
        year = pub_data.get('publication_year') or pub.get('year')
        abstract = pub_data.get('abstract', '')
        abstract_source = pub_data.get('abstract_source', 'none')

        base_metadata = {
            "person_name": staff['full_name'],
            "person_email": staff['email'],
            "person_profile_url": staff['profile_url'],
            "person_school": staff['school'],
            "pub_title": title,
            "pub_year": year,
            "pub_doi": pub.get('doi'),
            "pub_venue": pub_data.get('venue'),
            "citations_count": pub_data.get('citations_count', 0),
            "is_open_access": pub_data.get('is_open_access', False),
            "has_abstract": bool(abstract),
            "abstract_source": abstract_source,
        }

        # Title chunk
        authors = pub_data.get('authors', [])
        author_names = [a['name'] for a in authors if a.get('name')]

        title_chunk = {
            "chunk_id": f"pub_title_{pub_id}",
            "chunk_type": "publication_title",
            "content": f"Title: {title}\n"
                       f"Authors: {', '.join(author_names[:10])}\n"
                       f"Published: {pub_data.get('venue')} ({year})\n"
                       f"Citations: {pub_data.get('citations_count', 0)}",
            "metadata": base_metadata
        }
        chunks.append(title_chunk)

        # Abstract chunk (如果有)
        if abstract:
            abstract_chunk = {
                "chunk_id": f"pub_abstract_{pub_id}",
                "chunk_type": "publication_abstract",
                "content": f"Paper: {title}\n"
                           f"Author: {staff['full_name']} ({staff['school']})\n"
                           f"Year: {year}\n\n"
                           f"Abstract:\n{abstract}\n\n"
                           f"[Source: {abstract_source}]",
                "metadata": base_metadata
            }
            chunks.append(abstract_chunk)

        # Keywords chunk
        concepts = pub_data.get('concepts', [])
        if concepts:
            keywords = [c['name'] for c in concepts if c.get('score', 0) > 0.3]
            if keywords:
                keywords_chunk = {
                    "chunk_id": f"pub_keywords_{pub_id}",
                    "chunk_type": "publication_keywords",
                    "content": f"Paper: {title}\n"
                               f"Author: {staff['full_name']}\n"
                               f"Keywords: {', '.join(keywords)}",
                    "metadata": {**base_metadata, "keywords": keywords}
                }
                chunks.append(keywords_chunk)

        return chunks

    def process_staff(self, staff: Dict) -> List[Dict]:
        """处理单个staff"""
        email = staff['email']

        if email in self.progress["processed_staff_emails"]:
            return []

        if not staff.get('profile_details') or not staff['profile_details'].get('publications'):
            self.progress["processed_staff_emails"].append(email)
            return []

        pubs = staff['profile_details']['publications']
        staff_pubs = []

        for pub_type, pub_text in pubs.items():
            parsed = self.parse_publication_text(pub_text, pub_type)
            staff_pubs.extend(parsed)

        if not staff_pubs:
            self.progress["processed_staff_emails"].append(email)
            return []

        self.stats["staff_with_publications"] += 1
        self.stats["total_publications_parsed"] += len(staff_pubs)

        # 获取publication数据 (多源)
        for pub in staff_pubs:
            if pub.get('doi'):
                self.stats["publications_with_doi"] += 1

                # 检查缓存
                if pub['doi'] in self.progress["publication_cache"]:
                    pub['publication_data'] = self.progress["publication_cache"][pub['doi']]
                else:
                    # 多源获取
                    pub_data = self.fetcher.fetch_abstract(pub['doi'])
                    pub['publication_data'] = pub_data
                    self.progress["publication_cache"][pub['doi']] = pub_data

                    if pub_data.get('abstract'):
                        self.stats["publications_with_abstract"] += 1

                    sleep(CONFIG["api_delay"])
            else:
                pub['publication_data'] = {"error": "no_doi"}

        chunks = self.create_rag_chunks(staff, staff_pubs)
        self.progress["processed_staff_emails"].append(email)

        return chunks

    def run(self):
        """运行完整流程"""
        print("="*80)
        print("Multi-Source Publication Parser")
        print("="*80)

        with open(CONFIG["input_file"], 'r') as f:
            staff_data = json.load(f)

        self.stats["total_staff"] = len(staff_data)
        print(f"\\nTotal staff: {len(staff_data)}")
        print(f"Already processed: {len(self.progress['processed_staff_emails'])}")

        all_chunks = []

        try:
            for i, staff in enumerate(staff_data, 1):
                if staff['email'] in self.progress["processed_staff_emails"]:
                    continue

                print(f"\\n[{i}/{len(staff_data)}] {staff['full_name']}")

                chunks = self.process_staff(staff)
                all_chunks.extend(chunks)

                if chunks:
                    print(f"  ✓ {len(chunks)} chunks")

                if i % 10 == 0:
                    self.save_progress()
                    print(f"  💾 Progress saved")

        except KeyboardInterrupt:
            print("\\n\\n⚠️  Interrupted. Saving...")
            self.save_progress()
            self.save_stats()
            return

        with open(CONFIG["output_file"], 'w') as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False)

        self.save_progress()
        self.save_stats()
        self._print_statistics()

    def _print_statistics(self):
        print("\\n" + "="*80)
        print("STATISTICS")
        print("="*80)
        print(f"\\nPublications with abstract: {self.stats['publications_with_abstract']}")
        print(f"\\nAbstract sources:")
        for source, count in self.stats['abstract_sources'].items():
            if count > 0:
                print(f"  {source}: {count}")

if __name__ == "__main__":
    parser = PublicationParser()
    parser.run()
