"""
多源版本 V2 - 多线程优化版
改进:
1. 修复 PubMed DOI 搜索问题（使用 ID Converter API）
2. 添加多线程支持
3. 添加分批保存功能
4. 优化错误处理和重试机制

优先级: OpenAlex > Semantic Scholar > Crossref > PubMed (仅当确认在数据库中)
"""
import json
import re
import requests
from time import sleep
from typing import List, Dict, Optional
import hashlib
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/z5241339/Documents/unsw_ai_rag/parsing_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置
CONFIG = {
    "input_file": "/Users/z5241339/Documents/unsw_ai_rag/engineering_staff_with_profiles_cleaned.json",
    "output_file": "/Users/z5241339/Documents/unsw_ai_rag/rag_chunks_multisource_v2.json",
    "progress_file": "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress_multisource_v2.json",
    "stats_file": "/Users/z5241339/Documents/unsw_ai_rag/parsing_statistics_multisource_v2.json",
    "max_retries": 3,
    "retry_delay": 1.0,
    "api_delay": 0.1,  # 减少延迟，因为使用多线程
    "email": "research@unsw.edu.au",
    "max_workers": 5,  # 并发线程数
    "batch_save_interval": 5,  # 每处理5个staff保存一次
}

class MultiSourceFetcher:
    """多源Abstract获取器 - 线程安全版本"""

    def __init__(self, stats_tracker, stats_lock):
        self.stats = stats_tracker
        self.stats_lock = stats_lock

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
            with self.stats_lock:
                self.stats['abstract_sources']['openalex'] += 1
            return result

        # 保存OpenAlex的metadata (即使没有abstract)
        base_data = result if result and 'error' not in result else {}

        # 2. Semantic Scholar (高质量abstract + TLDR)
        abstract = self._fetch_semantic_scholar(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'Semantic Scholar'
            with self.stats_lock:
                self.stats['abstract_sources']['semantic_scholar'] += 1
            return base_data

        # 3. Crossref
        abstract = self._fetch_crossref(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'Crossref'
            with self.stats_lock:
                self.stats['abstract_sources']['crossref'] += 1
            return base_data

        # 4. PubMed (使用正确的 ID Converter API)
        abstract = self._fetch_pubmed_correct(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'PubMed'
            with self.stats_lock:
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
            with self.stats_lock:
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

    def _fetch_pubmed_correct(self, doi: str) -> Optional[str]:
        """
        从PubMed获取abstract - 使用正确的 ID Converter API

        改进:
        1. 先用 PMC ID Converter 验证 DOI 是否在 PubMed
        2. 只有找到有效 PMID 才获取 abstract
        3. 避免错误匹配问题
        """
        try:
            # 步骤1: 使用 ID Converter API 获取 PMID
            converter_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
            params = {
                "ids": doi,
                "format": "json"
            }

            response = requests.get(converter_url, params=params, timeout=10)
            if response.status_code != 200:
                return None

            data = response.json()
            records = data.get('records', [])

            # 检查是否找到有效的 PMID
            if not records or not records[0].get('pmid'):
                return None

            pmid = records[0].get('pmid')

            # 步骤2: 使用 PMID 获取 abstract
            sleep(0.2)  # PubMed 要求延迟

            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml"
            }

            response = requests.get(fetch_url, params=params, timeout=10)
            if response.status_code != 200:
                return None

            # 提取 abstract 文本
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

        except Exception as e:
            logger.debug(f"PubMed fetch failed for {doi}: {e}")
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
            "publications_without_doi": 0,  # 新增：无 DOI 的论文数
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
        self.stats_lock = Lock()
        self.progress_lock = Lock()
        self.progress = self.load_progress()
        self.fetcher = MultiSourceFetcher(self.stats, self.stats_lock)

    def load_progress(self) -> Dict:
        if os.path.exists(CONFIG["progress_file"]):
            with open(CONFIG["progress_file"], 'r') as f:
                return json.load(f)
        return {
            "processed_staff_emails": [],
            "publication_cache": {}
        }

    def save_progress(self):
        with self.progress_lock:
            with open(CONFIG["progress_file"], 'w') as f:
                json.dump(self.progress, f, indent=2)

    def save_stats(self):
        with self.stats_lock:
            self.stats["end_time"] = datetime.now().isoformat()
            with open(CONFIG["stats_file"], 'w') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def parse_publication_text(self, pub_text: str, pub_type: str) -> List[Dict]:
        """解析publication文本"""
        publications = []
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
            with self.stats_lock:
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
            # 移除了 error 检查 - 即使无 DOI 也保留基本信息
            # 现在 pub_data 总是包含至少 title 和 year

            pub_chunks = self._create_publication_chunks(staff_entry, pub, pub_data)
            chunks.extend(pub_chunks)

        with self.stats_lock:
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

    def process_single_publication(self, pub: Dict) -> Dict:
        """处理单个出版物 - 线程安全版本"""
        if pub.get('doi'):
            # 检查缓存
            with self.progress_lock:
                if pub['doi'] in self.progress["publication_cache"]:
                    return self.progress["publication_cache"][pub['doi']]

            # 多源获取
            pub_data = self.fetcher.fetch_abstract(pub['doi'])

            # 更新缓存
            with self.progress_lock:
                self.progress["publication_cache"][pub['doi']] = pub_data

            sleep(CONFIG["api_delay"])
            return pub_data
        else:
            # 无 DOI：保留基本信息，至少创建 title chunk
            pub_data = {
                "title": pub.get('title'),
                "publication_year": pub.get('year'),
                "authors": [],  # 无法从 API 获取，使用空列表
                "abstract": "",
                "abstract_source": "none",
                "type": pub.get('pub_type'),
                "venue": None,
                "citations_count": 0,
                "is_open_access": False,
                "concepts": [],
                "has_doi": False  # 标记为无 DOI
            }
            return pub_data

    def process_staff(self, staff: Dict) -> List[Dict]:
        """处理单个staff"""
        email = staff['email']

        with self.progress_lock:
            if email in self.progress["processed_staff_emails"]:
                return []

        if not staff.get('profile_details') or not staff['profile_details'].get('publications'):
            with self.progress_lock:
                self.progress["processed_staff_emails"].append(email)
            return []

        pubs = staff['profile_details']['publications']
        staff_pubs = []

        for pub_type, pub_text in pubs.items():
            parsed = self.parse_publication_text(pub_text, pub_type)
            staff_pubs.extend(parsed)

        if not staff_pubs:
            with self.progress_lock:
                self.progress["processed_staff_emails"].append(email)
            return []

        with self.stats_lock:
            self.stats["staff_with_publications"] += 1
            self.stats["total_publications_parsed"] += len(staff_pubs)
            doi_count = sum(1 for p in staff_pubs if p.get('doi'))
            no_doi_count = len(staff_pubs) - doi_count
            self.stats["publications_with_doi"] += doi_count
            self.stats["publications_without_doi"] += no_doi_count

        # 使用线程池处理出版物
        with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
            future_to_pub = {
                executor.submit(self.process_single_publication, pub): pub
                for pub in staff_pubs
            }

            for future in as_completed(future_to_pub):
                pub = future_to_pub[future]
                try:
                    pub_data = future.result()
                    pub['publication_data'] = pub_data

                    if pub_data.get('abstract'):
                        with self.stats_lock:
                            self.stats["publications_with_abstract"] += 1
                except Exception as e:
                    logger.error(f"Error processing publication: {e}")
                    pub['publication_data'] = {"error": str(e)}

        chunks = self.create_rag_chunks(staff, staff_pubs)

        with self.progress_lock:
            self.progress["processed_staff_emails"].append(email)

        return chunks

    def run(self):
        """运行完整流程 - 多线程版本"""
        logger.info("="*80)
        logger.info("Multi-Source Publication Parser V2 (Multi-threaded)")
        logger.info("="*80)

        with open(CONFIG["input_file"], 'r') as f:
            staff_data = json.load(f)

        self.stats["total_staff"] = len(staff_data)
        logger.info(f"\nTotal staff: {len(staff_data)}")
        logger.info(f"Already processed: {len(self.progress['processed_staff_emails'])}")
        logger.info(f"Max workers: {CONFIG['max_workers']}")

        # 过滤未处理的staff
        pending_staff = [
            s for s in staff_data
            if s['email'] not in self.progress["processed_staff_emails"]
        ]
        logger.info(f"Pending staff: {len(pending_staff)}")

        all_chunks = []
        processed_count = 0

        try:
            # 使用线程池处理 staff（但控制并发数）
            for i, staff in enumerate(pending_staff, 1):
                logger.info(f"\n[{i}/{len(pending_staff)}] Processing {staff['full_name']}")

                chunks = self.process_staff(staff)
                all_chunks.extend(chunks)
                processed_count += 1

                if chunks:
                    logger.info(f"  ✓ {len(chunks)} chunks created")

                # 定期保存
                if processed_count % CONFIG["batch_save_interval"] == 0:
                    self.save_progress()
                    self.save_stats()
                    logger.info(f"  💾 Progress saved (batch {processed_count // CONFIG['batch_save_interval']})")

        except KeyboardInterrupt:
            logger.warning("\n\n⚠️  Interrupted. Saving...")
            self.save_progress()
            self.save_stats()
            return

        # 保存最终结果
        with open(CONFIG["output_file"], 'w') as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False)

        self.save_progress()
        self.save_stats()
        self._print_statistics()

    def _print_statistics(self):
        logger.info("\n" + "="*80)
        logger.info("STATISTICS")
        logger.info("="*80)

        total_pubs = self.stats['total_publications_parsed']
        with_doi = self.stats['publications_with_doi']
        without_doi = self.stats['publications_without_doi']
        with_abstract = self.stats['publications_with_abstract']

        logger.info(f"\nTotal publications: {total_pubs}")
        logger.info(f"Publications with DOI: {with_doi} ({with_doi/total_pubs*100:.1f}%)")
        logger.info(f"Publications without DOI: {without_doi} ({without_doi/total_pubs*100:.1f}%) - title only")
        logger.info(f"Publications with abstract: {with_abstract} ({with_abstract/total_pubs*100:.1f}%)")

        logger.info(f"\nAbstract sources:")
        for source, count in self.stats['abstract_sources'].items():
            if count > 0:
                logger.info(f"  {source}: {count}")

        logger.info(f"\nTotal chunks created: {self.stats['chunks_created']}")
        logger.info(f"Total errors: {len(self.stats['errors'])}")

if __name__ == "__main__":
    parser = PublicationParser()
    parser.run()
