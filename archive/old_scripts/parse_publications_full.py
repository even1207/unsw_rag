"""
完整版 - 解析UNSW工程学院staff数据,提取publications并从OpenAlex获取详细信息
特性:
- 错误重试机制
- 进度保存和恢复
- 详细的统计信息
- 按sections分块(title, abstract, keywords分开)
- 支持中断后继续
"""
import json
import re
import requests
from time import sleep
from typing import List, Dict, Optional
import hashlib
import os
from datetime import datetime
from pathlib import Path

# 配置
CONFIG = {
    "input_file": "/Users/z5241339/Documents/unsw_ai_rag/engineering_staff_with_profiles_cleaned.json",
    "output_file": "/Users/z5241339/Documents/unsw_ai_rag/rag_chunks_full.json",
    "progress_file": "/Users/z5241339/Documents/unsw_ai_rag/parsing_progress.json",
    "stats_file": "/Users/z5241339/Documents/unsw_ai_rag/parsing_statistics.json",
    "max_retries": 3,
    "retry_delay": 1.0,
    "api_delay": 0.15,  # OpenAlex推荐 100ms, 我们用150ms更保险
    "email": "research@unsw.edu.au",
}

class PublicationParser:
    def __init__(self):
        self.stats = {
            "start_time": datetime.now().isoformat(),
            "total_staff": 0,
            "staff_with_publications": 0,
            "total_publications_parsed": 0,
            "publications_with_doi": 0,
            "openalex_success": 0,
            "openalex_not_found": 0,
            "openalex_errors": 0,
            "publications_with_abstract": 0,
            "publications_open_access": 0,
            "total_citations": 0,
            "chunks_created": 0,
            "errors": []
        }
        self.progress = self.load_progress()

    def load_progress(self) -> Dict:
        """加载之前的进度"""
        if os.path.exists(CONFIG["progress_file"]):
            with open(CONFIG["progress_file"], 'r') as f:
                return json.load(f)
        return {
            "processed_staff_emails": [],
            "openalex_cache": {}  # DOI -> OpenAlex data cache
        }

    def save_progress(self):
        """保存当前进度"""
        with open(CONFIG["progress_file"], 'w') as f:
            json.dump(self.progress, f, indent=2)

    def save_stats(self):
        """保存统计信息"""
        self.stats["end_time"] = datetime.now().isoformat()
        with open(CONFIG["stats_file"], 'w') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def parse_publication_text(self, pub_text: str, pub_type: str) -> List[Dict]:
        """解析publication文本字符串,提取individual publications"""
        publications = []
        pattern = rf'{re.escape(pub_type)} \| (\d{{4}})'

        try:
            entries = re.split(pattern, pub_text)

            for i in range(1, len(entries), 2):
                if i + 1 >= len(entries):
                    break

                year = entries[i]
                content = entries[i + 1].strip()

                # 提取DOI
                doi_match = re.search(r'http://dx\.doi\.org/([^\s,]+)', content)
                doi = doi_match.group(1) if doi_match else None

                # 提取标题 (在单引号之间)
                title_match = re.search(r"'([^']+)'", content)
                title = title_match.group(1) if title_match else None

                # 提取作者
                authors_text = content.split(',')[0].strip() if ',' in content else ""

                if title or doi:
                    publications.append({
                        'year': int(year) if year.isdigit() else year,
                        'title': title,
                        'doi': doi,
                        'authors_text': authors_text,
                        'raw_text': content,
                        'pub_type': pub_type
                    })
        except Exception as e:
            self.stats["errors"].append(f"Parse error in {pub_type}: {str(e)}")

        return publications

    def invert_abstract_index(self, inverted_index: Dict) -> str:
        """将OpenAlex的倒排索引转换为正常文本"""
        if not inverted_index:
            return ""

        try:
            words = {}
            for word, positions in inverted_index.items():
                for pos in positions:
                    words[pos] = word
            return " ".join([words[i] for i in sorted(words.keys())])
        except Exception as e:
            self.stats["errors"].append(f"Abstract inversion error: {str(e)}")
            return ""

    def fetch_openalex(self, doi: str) -> Dict:
        """从OpenAlex获取单篇论文信息,带重试机制"""
        if not doi:
            return {"error": "no_doi"}

        # 检查缓存
        if doi in self.progress["openalex_cache"]:
            return self.progress["openalex_cache"][doi]

        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        headers = {"User-Agent": f"mailto:{CONFIG['email']}"}

        for attempt in range(CONFIG["max_retries"]):
            try:
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    abstract = self.invert_abstract_index(data.get("abstract_inverted_index"))

                    result = {
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
                            for c in data.get("concepts", [])[:20]
                        ],
                        "type": data.get("type"),
                    }

                    # 缓存结果
                    self.progress["openalex_cache"][doi] = result
                    self.stats["openalex_success"] += 1

                    if abstract:
                        self.stats["publications_with_abstract"] += 1
                    if result["is_open_access"]:
                        self.stats["publications_open_access"] += 1
                    self.stats["total_citations"] += result["citations_count"]

                    return result

                elif response.status_code == 404:
                    result = {"error": "not_found"}
                    self.progress["openalex_cache"][doi] = result
                    self.stats["openalex_not_found"] += 1
                    return result
                else:
                    if attempt < CONFIG["max_retries"] - 1:
                        sleep(CONFIG["retry_delay"] * (attempt + 1))
                        continue
                    result = {"error": f"status_{response.status_code}"}
                    self.stats["openalex_errors"] += 1
                    return result

            except Exception as e:
                if attempt < CONFIG["max_retries"] - 1:
                    sleep(CONFIG["retry_delay"] * (attempt + 1))
                    continue
                result = {"error": str(e)}
                self.stats["openalex_errors"] += 1
                self.stats["errors"].append(f"OpenAlex fetch error for {doi}: {str(e)}")
                return result

        return {"error": "max_retries_exceeded"}

    def create_rag_chunks(self, staff_entry: Dict, publication_data: List[Dict]) -> List[Dict]:
        """
        为每个研究人员创建多个RAG chunks
        策略: 每篇论文分成多个chunks以提高检索精度
        """
        chunks = []

        # Chunk Type 1: 人员基本信息
        person_basic_chunk = {
            "chunk_id": f"person_basic_{staff_entry['email']}",
            "chunk_type": "person_basic",
            "content": f"{staff_entry['full_name']}\n"
                       f"Position: {staff_entry['role']}\n"
                       f"School: {staff_entry['school']}\n"
                       f"Faculty: {staff_entry['faculty']}\n"
                       f"Email: {staff_entry['email']}",
            "metadata": {
                "person_name": staff_entry['full_name'],
                "person_email": staff_entry['email'],
                "role": staff_entry['role'],
                "school": staff_entry['school'],
                "faculty": staff_entry['faculty'],
                "profile_url": staff_entry['profile_url'],
            }
        }
        chunks.append(person_basic_chunk)

        # Chunk Type 2: 人员研究介绍
        if staff_entry.get('biography'):
            person_bio_chunk = {
                "chunk_id": f"person_bio_{staff_entry['email']}",
                "chunk_type": "person_biography",
                "content": f"{staff_entry['full_name']} - Biography and Research Interests\n\n"
                           f"{staff_entry['biography']}\n\n"
                           f"Research Areas: {staff_entry.get('research_text', '')}",
                "metadata": {
                    "person_name": staff_entry['full_name'],
                    "person_email": staff_entry['email'],
                    "school": staff_entry['school'],
                    "faculty": staff_entry['faculty'],
                    "profile_url": staff_entry['profile_url'],
                }
            }
            chunks.append(person_bio_chunk)

        # Chunk Type 3-N: 论文chunks (每篇论文可能产生多个chunks)
        for pub in publication_data:
            oa_data = pub.get('openalex_data', {})

            if 'error' in oa_data:
                # 即使没有OpenAlex数据,也创建基本chunk
                if pub.get('title'):
                    basic_pub_chunk = self._create_basic_publication_chunk(staff_entry, pub)
                    if basic_pub_chunk:
                        chunks.append(basic_pub_chunk)
                continue

            # 为有OpenAlex数据的论文创建详细chunks
            pub_chunks = self._create_detailed_publication_chunks(staff_entry, pub, oa_data)
            chunks.extend(pub_chunks)

        self.stats["chunks_created"] += len(chunks)
        return chunks

    def _create_basic_publication_chunk(self, staff: Dict, pub: Dict) -> Optional[Dict]:
        """为没有OpenAlex数据的论文创建基本chunk"""
        title = pub.get('title')
        if not title:
            return None

        pub_id = pub.get('doi') or hashlib.md5(title.encode()).hexdigest()

        return {
            "chunk_id": f"pub_basic_{pub_id}",
            "chunk_type": "publication_basic",
            "content": f"Title: {title}\n"
                       f"Author: {staff['full_name']}\n"
                       f"Year: {pub.get('year')}\n"
                       f"Type: {pub.get('pub_type')}",
            "metadata": {
                "person_name": staff['full_name'],
                "person_email": staff['email'],
                "person_profile_url": staff['profile_url'],
                "person_school": staff['school'],
                "pub_title": title,
                "pub_year": pub.get('year'),
                "pub_type": pub.get('pub_type'),
                "pub_doi": pub.get('doi'),
                "has_abstract": False,
            }
        }

    def _create_detailed_publication_chunks(self, staff: Dict, pub: Dict, oa_data: Dict) -> List[Dict]:
        """为有完整OpenAlex数据的论文创建多个细粒度chunks"""
        chunks = []

        title = oa_data.get('title') or pub.get('title', 'Unknown Title')
        pub_id = pub.get('doi') or hashlib.md5(title.encode()).hexdigest()
        year = oa_data.get('publication_year') or pub.get('year')
        venue = oa_data.get('venue')
        abstract = oa_data.get('abstract', '')
        concepts = oa_data.get('concepts', [])

        # 共享的metadata
        base_metadata = {
            "person_name": staff['full_name'],
            "person_email": staff['email'],
            "person_profile_url": staff['profile_url'],
            "person_school": staff['school'],
            "person_faculty": staff['faculty'],
            "pub_title": title,
            "pub_year": year,
            "pub_type": pub.get('pub_type'),
            "pub_doi": pub.get('doi'),
            "pub_venue": venue,
            "citations_count": oa_data.get('citations_count', 0),
            "is_open_access": oa_data.get('is_open_access', False),
            "pdf_url": oa_data.get('pdf_url'),
        }

        # Chunk 3a: 论文标题和元数据 (用于精确匹配论文查询)
        authors = oa_data.get('authors', [])
        author_names = [a['name'] for a in authors if a.get('name')]

        title_chunk = {
            "chunk_id": f"pub_title_{pub_id}",
            "chunk_type": "publication_title",
            "content": f"Title: {title}\n"
                       f"Authors: {', '.join(author_names[:10])}\n"  # 限制作者数量
                       f"Published in: {venue} ({year})\n"
                       f"Type: {pub.get('pub_type')}\n"
                       f"Citations: {oa_data.get('citations_count', 0)}",
            "metadata": {**base_metadata, "has_abstract": bool(abstract)}
        }
        chunks.append(title_chunk)

        # Chunk 3b: 论文摘要 (如果有) - 这是最重要的内容chunk
        if abstract:
            abstract_chunk = {
                "chunk_id": f"pub_abstract_{pub_id}",
                "chunk_type": "publication_abstract",
                "content": f"Paper: {title}\n"
                           f"Author: {staff['full_name']} ({staff['school']})\n"
                           f"Year: {year}\n\n"
                           f"Abstract:\n{abstract}",
                "metadata": {**base_metadata, "has_abstract": True}
            }
            chunks.append(abstract_chunk)

        # Chunk 3c: 论文关键词/概念 (用于主题检索)
        if concepts:
            high_score_concepts = [c['name'] for c in concepts if c.get('score', 0) > 0.3]
            if high_score_concepts:
                keywords_chunk = {
                    "chunk_id": f"pub_keywords_{pub_id}",
                    "chunk_type": "publication_keywords",
                    "content": f"Paper: {title}\n"
                               f"Author: {staff['full_name']}\n"
                               f"Keywords: {', '.join(high_score_concepts)}\n"
                               f"Research Topics: {', '.join(high_score_concepts[:5])}",
                    "metadata": {
                        **base_metadata,
                        "keywords": high_score_concepts,
                        "has_abstract": bool(abstract)
                    }
                }
                chunks.append(keywords_chunk)

        return chunks

    def process_staff(self, staff: Dict) -> List[Dict]:
        """处理单个staff成员"""
        email = staff['email']

        # 检查是否已处理
        if email in self.progress["processed_staff_emails"]:
            print(f"  ⏭  Skipping {staff['full_name']} (already processed)")
            return []

        if not staff.get('profile_details') or not staff['profile_details'].get('publications'):
            self.progress["processed_staff_emails"].append(email)
            return []

        pubs = staff['profile_details']['publications']
        staff_pubs = []

        # 解析publications
        for pub_type, pub_text in pubs.items():
            parsed = self.parse_publication_text(pub_text, pub_type)
            staff_pubs.extend(parsed)

        if not staff_pubs:
            self.progress["processed_staff_emails"].append(email)
            return []

        self.stats["staff_with_publications"] += 1
        self.stats["total_publications_parsed"] += len(staff_pubs)

        # 获取OpenAlex数据
        for pub in staff_pubs:
            if pub.get('doi'):
                self.stats["publications_with_doi"] += 1
                pub['openalex_data'] = self.fetch_openalex(pub['doi'])
                sleep(CONFIG["api_delay"])  # 礼貌性延迟
            else:
                pub['openalex_data'] = {"error": "no_doi"}

        # 创建chunks
        chunks = self.create_rag_chunks(staff, staff_pubs)

        # 标记为已处理
        self.progress["processed_staff_emails"].append(email)

        return chunks

    def run(self):
        """运行完整的解析流程"""
        print("="*80)
        print("UNSW Engineering Staff Publications Parser - Full Version")
        print("="*80)

        # 加载数据
        print("\n[1/4] Loading staff data...")
        with open(CONFIG["input_file"], 'r') as f:
            staff_data = json.load(f)

        self.stats["total_staff"] = len(staff_data)
        already_processed = len(self.progress["processed_staff_emails"])

        print(f"✓ Total staff: {len(staff_data)}")
        if already_processed > 0:
            print(f"✓ Already processed: {already_processed}")
            print(f"✓ Remaining: {len(staff_data) - already_processed}")

        # 处理每个staff
        print(f"\n[2/4] Processing staff members...")
        all_chunks = []

        try:
            for i, staff in enumerate(staff_data, 1):
                if staff['email'] in self.progress["processed_staff_emails"]:
                    continue

                print(f"\n[{i}/{len(staff_data)}] {staff['full_name']}")
                print(f"  School: {staff['school']}")

                chunks = self.process_staff(staff)
                all_chunks.extend(chunks)

                if chunks:
                    print(f"  ✓ Created {len(chunks)} chunks")

                # 每10个staff保存一次进度
                if i % 10 == 0:
                    self.save_progress()
                    print(f"\n  💾 Progress saved (processed {len(self.progress['processed_staff_emails'])}/{len(staff_data)})")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user. Saving progress...")
            self.save_progress()
            self.save_stats()
            print("✓ Progress saved. You can resume later.")
            return

        # 保存最终结果
        print(f"\n[3/4] Saving chunks...")
        with open(CONFIG["output_file"], 'w') as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {len(all_chunks)} chunks to {CONFIG['output_file']}")

        # 保存统计
        print(f"\n[4/4] Saving statistics...")
        self.save_progress()
        self.save_stats()
        print(f"✓ Statistics saved to {CONFIG['stats_file']}")

        # 打印统计
        self._print_statistics()

    def _print_statistics(self):
        """打印详细统计信息"""
        print("\n" + "="*80)
        print("FINAL STATISTICS")
        print("="*80)

        print(f"\n📊 Staff Statistics:")
        print(f"  Total staff: {self.stats['total_staff']}")
        print(f"  Staff with publications: {self.stats['staff_with_publications']}")

        print(f"\n📚 Publication Statistics:")
        print(f"  Total publications parsed: {self.stats['total_publications_parsed']}")
        print(f"  Publications with DOI: {self.stats['publications_with_doi']}")

        print(f"\n🌐 OpenAlex Fetch Results:")
        print(f"  Successful: {self.stats['openalex_success']}")
        print(f"  Not found: {self.stats['openalex_not_found']}")
        print(f"  Errors: {self.stats['openalex_errors']}")

        if self.stats['openalex_success'] > 0:
            abstract_rate = self.stats['publications_with_abstract'] / self.stats['openalex_success'] * 100
            oa_rate = self.stats['publications_open_access'] / self.stats['openalex_success'] * 100
            avg_citations = self.stats['total_citations'] / self.stats['openalex_success']

            print(f"\n📄 Content Quality:")
            print(f"  Publications with abstract: {self.stats['publications_with_abstract']} ({abstract_rate:.1f}%)")
            print(f"  Open access publications: {self.stats['publications_open_access']} ({oa_rate:.1f}%)")
            print(f"  Average citations: {avg_citations:.1f}")

        print(f"\n📦 Chunks Created:")
        print(f"  Total chunks: {self.stats['chunks_created']}")

        if self.stats['errors']:
            print(f"\n⚠️  Errors encountered: {len(self.stats['errors'])}")
            print(f"  (See {CONFIG['stats_file']} for details)")

if __name__ == "__main__":
    parser = PublicationParser()
    parser.run()
