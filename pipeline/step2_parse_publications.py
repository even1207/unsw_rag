"""
Step 2: 解析 Publications 并获取 Abstract (多源版本 V2)

功能:
1. 解析 staff profile 中的 publication 文本，提取 DOI
2. 从多个数据源获取 abstract (OpenAlex, Semantic Scholar, Crossref, PubMed)
3. 生成 RAG chunks
4. 保存到 data/processed/rag_chunks.json

优先级: OpenAlex > Semantic Scholar > Crossref > PubMed

使用方法:
    python3 pipeline/step2_parse_publications.py

特性:
- 多线程并发处理
- 支持断点续传
- 自动保存进度
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
from pathlib import Path

# 配置日志
PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = PROJECT_ROOT / "data/cache/parsing.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置
CONFIG = {
    "input_file": PROJECT_ROOT / "data/processed/staff_with_profiles.json",
    "output_file": PROJECT_ROOT / "data/processed/rag_chunks.json",
    "progress_file": PROJECT_ROOT / "data/cache/parsing_progress.json",
    "stats_file": PROJECT_ROOT / "data/cache/parsing_statistics.json",
    "max_retries": 3,
    "retry_delay": 1.0,
    "api_delay": 0.1,
    "email": "research@unsw.edu.au",
    "max_workers": 5,
    "batch_save_interval": 5,
}


class MultiSourceFetcher:
    """多源 Abstract 获取器 - 线程安全版本"""

    def __init__(self, stats_tracker, stats_lock):
        self.stats = stats_tracker
        self.stats_lock = stats_lock

    def fetch_abstract(self, doi: str) -> Dict:
        """按优先级尝试多个源获取 abstract"""
        if not doi:
            return {"error": "no_doi"}

        # 1. OpenAlex
        result = self._fetch_openalex(doi)
        if result and result.get('abstract'):
            result['abstract_source'] = 'OpenAlex'
            with self.stats_lock:
                self.stats['abstract_sources']['openalex'] += 1
            return result

        base_data = result if result and 'error' not in result else {}

        # 2. Semantic Scholar
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

        # 4. PubMed
        abstract = self._fetch_pubmed_correct(doi)
        if abstract:
            base_data['abstract'] = abstract
            base_data['abstract_source'] = 'PubMed'
            with self.stats_lock:
                self.stats['abstract_sources']['pubmed'] += 1
            return base_data

        if base_data:
            base_data['abstract_source'] = 'none'
        return base_data if base_data else {"error": "not_found"}

    def _fetch_openalex(self, doi: str) -> Optional[Dict]:
        """从 OpenAlex 获取"""
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
        """从 Semantic Scholar 获取 abstract"""
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        params = {"fields": "abstract,tldr"}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                abstract = data.get('abstract')
                if abstract:
                    return abstract
                tldr = data.get('tldr', {}).get('text') if data.get('tldr') else None
                if tldr:
                    return f"[TLDR] {tldr}"
            return None
        except:
            return None

    def _fetch_crossref(self, doi: str) -> Optional[str]:
        """从 Crossref 获取 abstract"""
        url = f"https://api.crossref.org/works/{doi}"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()['message']
                abstract = data.get('abstract', '')
                if abstract:
                    abstract = re.sub(r'<[^>]+>', '', abstract)
                    abstract = abstract.strip()
                    return abstract if abstract else None
            return None
        except:
            return None

    def _fetch_pubmed_correct(self, doi: str) -> Optional[str]:
        """从 PubMed 获取 abstract (使用 ID Converter API)"""
        try:
            # 步骤1: 使用 ID Converter API 获取 PMID
            converter_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
            params = {"ids": doi, "format": "json"}

            response = requests.get(converter_url, params=params, timeout=10)
            if response.status_code != 200:
                return None

            data = response.json()
            records = data.get('records', [])

            if not records or not records[0].get('pmid'):
                return None

            pmid = records[0].get('pmid')

            # 步骤2: 使用 PMID 获取 abstract
            sleep(0.2)

            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            params = {"db": "pubmed", "id": pmid, "retmode": "xml"}

            response = requests.get(fetch_url, params=params, timeout=10)
            if response.status_code != 200:
                return None

            match = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>',
                            response.text, re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                abstract = re.sub(r'&lt;', '<', abstract)
                abstract = re.sub(r'&gt;', '>', abstract)
                abstract = re.sub(r'&amp;', '&', abstract)
                return abstract

            return None

        except Exception as e:
            logger.debug(f"PubMed fetch failed for {doi}: {e}")
            return None

    def _invert_abstract_index(self, inverted_index: Dict) -> str:
        """将 OpenAlex 的倒排索引转换为正常文本"""
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
            "publications_without_doi": 0,
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
                progress = json.load(f)
                # 向后兼容：如果有旧的 email 列表，转换为空的 url 列表
                if "processed_staff_emails" in progress and "processed_staff_urls" not in progress:
                    progress["processed_staff_urls"] = []
                return progress
        return {
            "processed_staff_urls": [],
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
        """解析 publication 文本"""
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
        """创建 RAG chunks"""
        chunks = []

        # 使用 profile_url 作为唯一标识符
        profile_url = staff_entry['profile_url']
        # 生成一个简短的 ID (使用 URL 最后一部分)
        staff_id = profile_url.split('/')[-1] if profile_url else hashlib.md5(staff_entry['full_name'].encode()).hexdigest()[:8]

        # Person basic chunk
        person_basic = {
            "chunk_id": f"person_basic_{staff_id}",
            "chunk_type": "person_basic",
            "content": f"{staff_entry['full_name']}\n"
                       f"Position: {staff_entry['role']}\n"
                       f"School: {staff_entry['school']}\n"
                       f"Faculty: {staff_entry['faculty']}",
            "metadata": {
                "person_name": staff_entry['full_name'],
                "person_email": staff_entry.get('email'),
                "person_profile_url": profile_url,
                "role": staff_entry['role'],
                "school": staff_entry['school'],
                "faculty": staff_entry['faculty'],
                "profile_url": profile_url,
            }
        }
        chunks.append(person_basic)

        # Person biography chunk
        biography = staff_entry.get('profile_details', {}).get('biography')
        research = staff_entry.get('profile_details', {}).get('research_interests', '')

        if biography:
            person_bio = {
                "chunk_id": f"person_bio_{staff_id}",
                "chunk_type": "person_biography",
                "content": f"{staff_entry['full_name']} - Research Profile\n\n"
                           f"{biography}\n\n"
                           f"Research Areas: {research}",
                "metadata": {
                    "person_name": staff_entry['full_name'],
                    "person_email": staff_entry.get('email'),
                    "person_profile_url": profile_url,
                    "school": staff_entry['school'],
                    "profile_url": profile_url,
                }
            }
            chunks.append(person_bio)

        # Publication chunks
        for pub in publication_data:
            pub_data = pub.get('publication_data', {})
            pub_chunks = self._create_publication_chunks(staff_entry, pub, pub_data)
            chunks.extend(pub_chunks)

        with self.stats_lock:
            self.stats["chunks_created"] += len(chunks)
        return chunks

    def _create_publication_chunks(self, staff: Dict, pub: Dict, pub_data: Dict) -> List[Dict]:
        """创建 publication chunks"""
        chunks = []

        title = pub_data.get('title') or pub.get('title', 'Unknown')
        pub_id = pub.get('doi') or hashlib.md5(title.encode()).hexdigest()
        year = pub_data.get('publication_year') or pub.get('year')
        abstract = pub_data.get('abstract', '')
        abstract_source = pub_data.get('abstract_source', 'none')

        base_metadata = {
            "person_name": staff['full_name'],
            "person_email": staff.get('email'),
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

        # Abstract chunk
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
        """处理单个出版物"""
        if pub.get('doi'):
            with self.progress_lock:
                if pub['doi'] in self.progress["publication_cache"]:
                    return self.progress["publication_cache"][pub['doi']]

            pub_data = self.fetcher.fetch_abstract(pub['doi'])

            with self.progress_lock:
                self.progress["publication_cache"][pub['doi']] = pub_data

            sleep(CONFIG["api_delay"])
            return pub_data
        else:
            # 无 DOI: 保留基本信息
            pub_data = {
                "title": pub.get('title'),
                "publication_year": pub.get('year'),
                "authors": [],
                "abstract": "",
                "abstract_source": "none",
                "type": pub.get('pub_type'),
                "venue": None,
                "citations_count": 0,
                "is_open_access": False,
                "concepts": [],
                "has_doi": False
            }
            return pub_data

    def process_staff(self, staff: Dict) -> List[Dict]:
        """处理单个 staff"""
        # 使用 profile_url 作为唯一标识
        profile_url = staff.get('profile_url')
        if not profile_url:
            return []

        with self.progress_lock:
            if profile_url in self.progress["processed_staff_urls"]:
                return []

        # 检查是否有 publications
        has_publications = (staff.get('profile_details') and
                           staff['profile_details'].get('publications'))

        staff_pubs = []

        if has_publications:
            pubs = staff['profile_details']['publications']

            for pub_type, pub_text in pubs.items():
                parsed = self.parse_publication_text(pub_text, pub_type)
                staff_pubs.extend(parsed)

            if staff_pubs:
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

        # 即使没有 publications，也生成 person_basic 和 person_biography chunks
        chunks = self.create_rag_chunks(staff, staff_pubs)

        with self.progress_lock:
            self.progress["processed_staff_urls"].append(profile_url)

        return chunks

    def run(self):
        """运行完整流程"""
        logger.info("="*80)
        logger.info("Step 2: 解析 Publications 并获取 Abstract")
        logger.info("="*80)

        with open(CONFIG["input_file"], 'r') as f:
            staff_data = json.load(f)

        self.stats["total_staff"] = len(staff_data)
        logger.info(f"\nTotal staff: {len(staff_data)}")
        logger.info(f"Already processed: {len(self.progress['processed_staff_urls'])}")
        logger.info(f"Max workers: {CONFIG['max_workers']}")

        pending_staff = [
            s for s in staff_data
            if s.get('profile_url') and s['profile_url'] not in self.progress["processed_staff_urls"]
        ]
        logger.info(f"Pending staff: {len(pending_staff)}")

        all_chunks = []
        processed_count = 0

        try:
            for i, staff in enumerate(pending_staff, 1):
                logger.info(f"\n[{i}/{len(pending_staff)}] Processing {staff['full_name']}")

                chunks = self.process_staff(staff)
                all_chunks.extend(chunks)
                processed_count += 1

                if chunks:
                    logger.info(f"  ✓ {len(chunks)} chunks created")

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

        if total_pubs > 0:
            logger.info(f"\nTotal publications: {total_pubs}")
            logger.info(f"Publications with DOI: {with_doi} ({with_doi/total_pubs*100:.1f}%)")
            logger.info(f"Publications without DOI: {without_doi} ({without_doi/total_pubs*100:.1f}%)")
            logger.info(f"Publications with abstract: {with_abstract} ({with_abstract/total_pubs*100:.1f}%)")

        logger.info(f"\nAbstract sources:")
        for source, count in self.stats['abstract_sources'].items():
            if count > 0:
                logger.info(f"  {source}: {count}")

        logger.info(f"\nTotal chunks created: {self.stats['chunks_created']}")
        logger.info(f"Total errors: {len(self.stats['errors'])}")


def main():
    """主函数"""
    if not CONFIG["input_file"].exists():
        logger.error(f"错误: 输入文件不存在: {CONFIG['input_file']}")
        logger.error("请先运行 step1_fetch_staff.py")
        return

    parser = PublicationParser()
    parser.run()

    logger.info(f"\n✓ RAG chunks 已保存到: {CONFIG['output_file']}")
    logger.info("="*80)


if __name__ == "__main__":
    main()
