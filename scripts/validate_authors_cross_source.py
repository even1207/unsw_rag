"""
交叉验证作者数据的准确性

从多个外部数据源（OpenAlex, Semantic Scholar, Crossref）获取作者信息
并与数据库中的数据进行对比，生成验证报告。

功能:
1. 随机抽样N篇论文
2. 从OpenAlex, Semantic Scholar, Crossref三个数据源获取作者信息
3. 对比数据库中的authors数据与外部数据源
4. 生成详细的验证报告，包括:
   - 作者数量匹配度
   - 作者姓名匹配度
   - 作者顺序匹配度
   - 数据一致性分析

Usage:
    # 验证100篇随机论文
    python3 scripts/validate_authors_cross_source.py --sample 100

    # 验证特定DOI的论文
    python3 scripts/validate_authors_cross_source.py --doi "10.1001/jama.2023.19793"

    # 生成详细报告
    python3 scripts/validate_authors_cross_source.py --sample 50 --detailed
"""
import sys
from pathlib import Path
import argparse
import time
import json
from typing import Dict, List, Optional
import requests
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
import random
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from database.rag_schema import Publication, Author, PublicationAuthor

# Output directory for reports
REPORTS_DIR = PROJECT_ROOT / "data" / "validation_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class MultiSourceAuthorValidator:
    """从多个数据源验证作者信息"""

    def __init__(self):
        self.user_agent = "UNSW RAG Validation (mailto:z5241339@unsw.edu.au)"
        self.delay = 0.3  # Be polite to APIs

    def _rate_limit(self):
        """Rate limiting"""
        time.sleep(self.delay)

    def fetch_openalex_authors(self, doi: str) -> Optional[List[Dict]]:
        """从OpenAlex获取作者列表"""
        self._rate_limit()

        url = f"https://api.openalex.org/works/doi:{doi}"
        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                authorships = data.get("authorships", [])

                authors = []
                for idx, authorship in enumerate(authorships, 1):
                    author_info = authorship.get("author", {})
                    authors.append({
                        "position": idx,
                        "name": author_info.get("display_name", "Unknown"),
                        "openalex_id": author_info.get("id"),
                        "orcid": author_info.get("orcid"),
                        "institutions": [
                            inst.get("display_name")
                            for inst in authorship.get("institutions", [])
                        ]
                    })

                return authors

            return None
        except Exception as e:
            print(f"  OpenAlex fetch error: {e}")
            return None

    def fetch_semantic_scholar_authors(self, doi: str) -> Optional[List[Dict]]:
        """从Semantic Scholar获取作者列表"""
        self._rate_limit()

        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        params = {"fields": "authors"}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                s2_authors = data.get("authors", [])

                authors = []
                for idx, author in enumerate(s2_authors, 1):
                    authors.append({
                        "position": idx,
                        "name": author.get("name", "Unknown"),
                        "s2_id": author.get("authorId")
                    })

                return authors

            return None
        except Exception as e:
            print(f"  Semantic Scholar fetch error: {e}")
            return None

    def fetch_crossref_authors(self, doi: str) -> Optional[List[Dict]]:
        """从Crossref获取作者列表"""
        self._rate_limit()

        url = f"https://api.crossref.org/works/{doi}"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()["message"]
                cr_authors = data.get("author", [])

                authors = []
                for idx, author in enumerate(cr_authors, 1):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    name = f"{given} {family}".strip()

                    authors.append({
                        "position": idx,
                        "name": name,
                        "orcid": author.get("ORCID", "").replace("http://orcid.org/", ""),
                        "affiliation": [aff.get("name") for aff in author.get("affiliation", [])]
                    })

                return authors

            return None
        except Exception as e:
            print(f"  Crossref fetch error: {e}")
            return None


def normalize_name(name: str) -> str:
    """标准化作者姓名用于比较"""
    # 移除标点符号，转小写，去除多余空格
    import re
    name = re.sub(r'[^\w\s]', '', name.lower())
    name = ' '.join(name.split())
    return name


def name_similarity(name1: str, name2: str) -> float:
    """计算两个姓名的相似度（0-1）"""
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def compare_author_lists(db_authors: List[Dict], external_authors: List[Dict], source_name: str) -> Dict:
    """比较数据库中的作者列表与外部数据源"""
    result = {
        "source": source_name,
        "db_count": len(db_authors),
        "external_count": len(external_authors),
        "count_match": len(db_authors) == len(external_authors),
        "position_matches": 0,
        "name_exact_matches": 0,
        "name_fuzzy_matches": 0,
        "mismatches": []
    }

    # 按位置比较作者
    max_len = max(len(db_authors), len(external_authors))

    for i in range(max_len):
        db_author = db_authors[i] if i < len(db_authors) else None
        ext_author = external_authors[i] if i < len(external_authors) else None

        if db_author and ext_author:
            db_name = db_author.get("name", "")
            ext_name = ext_author.get("name", "")

            similarity = name_similarity(db_name, ext_name)

            if normalize_name(db_name) == normalize_name(ext_name):
                result["name_exact_matches"] += 1
                result["position_matches"] += 1
            elif similarity > 0.8:  # 高相似度视为匹配
                result["name_fuzzy_matches"] += 1
                result["position_matches"] += 1
            else:
                result["mismatches"].append({
                    "position": i + 1,
                    "db_name": db_name,
                    "external_name": ext_name,
                    "similarity": round(similarity, 2)
                })
        elif db_author and not ext_author:
            result["mismatches"].append({
                "position": i + 1,
                "db_name": db_author.get("name"),
                "external_name": None,
                "reason": "Missing in external source"
            })
        elif ext_author and not db_author:
            result["mismatches"].append({
                "position": i + 1,
                "db_name": None,
                "external_name": ext_author.get("name"),
                "reason": "Missing in database"
            })

    # 计算匹配率
    if len(db_authors) > 0:
        result["match_rate"] = (result["name_exact_matches"] + result["name_fuzzy_matches"]) / len(db_authors)
    else:
        result["match_rate"] = 0.0

    return result


def validate_publication(session, publication: Publication, validator: MultiSourceAuthorValidator, detailed: bool = False) -> Dict:
    """验证单篇论文的作者数据"""
    print(f"\n{'='*80}")
    print(f"验证论文: {publication.title[:70]}")
    print(f"DOI: {publication.doi}")
    print(f"{'='*80}")

    result = {
        "publication_id": publication.id,
        "doi": publication.doi,
        "title": publication.title,
        "validation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": {}
    }

    # 获取数据库中的作者
    stmt = select(PublicationAuthor, Author).join(Author).where(
        PublicationAuthor.publication_id == publication.id
    ).order_by(PublicationAuthor.author_position)

    db_author_records = session.execute(stmt).all()
    db_authors = [
        {
            "position": pa.author_position,
            "name": author.name,
            "openalex_id": author.openalex_id,
            "orcid": author.orcid
        }
        for pa, author in db_author_records
    ]

    print(f"数据库中的作者数: {len(db_authors)}")

    # 从OpenAlex验证
    print("\n[1/3] 从OpenAlex获取数据...")
    openalex_authors = validator.fetch_openalex_authors(publication.doi)
    if openalex_authors:
        print(f"  ✓ OpenAlex作者数: {len(openalex_authors)}")
        comparison = compare_author_lists(db_authors, openalex_authors, "OpenAlex")
        result["sources"]["openalex"] = comparison

        if detailed:
            print(f"  - 精确匹配: {comparison['name_exact_matches']}")
            print(f"  - 模糊匹配: {comparison['name_fuzzy_matches']}")
            print(f"  - 匹配率: {comparison['match_rate']:.1%}")
    else:
        print("  ✗ OpenAlex未找到数据")
        result["sources"]["openalex"] = {"error": "Not found"}

    # 从Semantic Scholar验证
    print("\n[2/3] 从Semantic Scholar获取数据...")
    s2_authors = validator.fetch_semantic_scholar_authors(publication.doi)
    if s2_authors:
        print(f"  ✓ Semantic Scholar作者数: {len(s2_authors)}")
        comparison = compare_author_lists(db_authors, s2_authors, "Semantic Scholar")
        result["sources"]["semantic_scholar"] = comparison

        if detailed:
            print(f"  - 精确匹配: {comparison['name_exact_matches']}")
            print(f"  - 模糊匹配: {comparison['name_fuzzy_matches']}")
            print(f"  - 匹配率: {comparison['match_rate']:.1%}")
    else:
        print("  ✗ Semantic Scholar未找到数据")
        result["sources"]["semantic_scholar"] = {"error": "Not found"}

    # 从Crossref验证
    print("\n[3/3] 从Crossref获取数据...")
    crossref_authors = validator.fetch_crossref_authors(publication.doi)
    if crossref_authors:
        print(f"  ✓ Crossref作者数: {len(crossref_authors)}")
        comparison = compare_author_lists(db_authors, crossref_authors, "Crossref")
        result["sources"]["crossref"] = comparison

        if detailed:
            print(f"  - 精确匹配: {comparison['name_exact_matches']}")
            print(f"  - 模糊匹配: {comparison['name_fuzzy_matches']}")
            print(f"  - 匹配率: {comparison['match_rate']:.1%}")
    else:
        print("  ✗ Crossref未找到数据")
        result["sources"]["crossref"] = {"error": "Not found"}

    return result


def generate_summary_report(validation_results: List[Dict]) -> Dict:
    """生成汇总报告"""
    summary = {
        "total_publications_validated": len(validation_results),
        "validation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": {
            "openalex": {"found": 0, "avg_match_rate": 0, "exact_matches": 0, "fuzzy_matches": 0},
            "semantic_scholar": {"found": 0, "avg_match_rate": 0, "exact_matches": 0, "fuzzy_matches": 0},
            "crossref": {"found": 0, "avg_match_rate": 0, "exact_matches": 0, "fuzzy_matches": 0}
        },
        "overall_accuracy": 0,
        "publications_with_issues": []
    }

    for source in ["openalex", "semantic_scholar", "crossref"]:
        match_rates = []
        exact_total = 0
        fuzzy_total = 0

        for result in validation_results:
            source_data = result["sources"].get(source, {})

            if "error" not in source_data:
                summary["sources"][source]["found"] += 1
                match_rates.append(source_data.get("match_rate", 0))
                exact_total += source_data.get("name_exact_matches", 0)
                fuzzy_total += source_data.get("name_fuzzy_matches", 0)

                # 记录有问题的论文
                if source_data.get("match_rate", 0) < 0.9:
                    summary["publications_with_issues"].append({
                        "doi": result["doi"],
                        "title": result["title"][:60],
                        "source": source,
                        "match_rate": source_data.get("match_rate", 0)
                    })

        if match_rates:
            summary["sources"][source]["avg_match_rate"] = sum(match_rates) / len(match_rates)
            summary["sources"][source]["exact_matches"] = exact_total
            summary["sources"][source]["fuzzy_matches"] = fuzzy_total

    # 计算总体准确率
    all_match_rates = []
    for source in ["openalex", "semantic_scholar", "crossref"]:
        rate = summary["sources"][source]["avg_match_rate"]
        if rate > 0:
            all_match_rates.append(rate)

    if all_match_rates:
        summary["overall_accuracy"] = sum(all_match_rates) / len(all_match_rates)

    return summary


def print_summary_report(summary: Dict):
    """打印汇总报告"""
    print("\n" + "="*80)
    print("验证汇总报告")
    print("="*80)

    print(f"\n总验证论文数: {summary['total_publications_validated']}")
    print(f"验证时间: {summary['validation_time']}")

    print("\n数据源统计:")
    print("-" * 80)

    for source_name, source_data in summary["sources"].items():
        print(f"\n{source_name.upper()}:")
        print(f"  找到数据: {source_data['found']}/{summary['total_publications_validated']}")
        print(f"  平均匹配率: {source_data['avg_match_rate']:.1%}")
        print(f"  精确匹配总数: {source_data['exact_matches']}")
        print(f"  模糊匹配总数: {source_data['fuzzy_matches']}")

    print("\n" + "-" * 80)
    print(f"总体准确率: {summary['overall_accuracy']:.1%}")

    if summary["publications_with_issues"]:
        print(f"\n发现 {len(summary['publications_with_issues'])} 篇论文的作者数据可能有问题")
        print("详见完整报告文件")


def main():
    parser = argparse.ArgumentParser(description="交叉验证作者数据准确性")
    parser.add_argument("--sample", type=int, help="随机抽样的论文数量")
    parser.add_argument("--doi", type=str, help="验证特定DOI的论文")
    parser.add_argument("--detailed", action="store_true", help="显示详细信息")

    args = parser.parse_args()

    # Connect to database
    engine = create_engine(settings.postgres_dsn, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    validator = MultiSourceAuthorValidator()

    try:
        # 确定要验证的论文
        publications = []

        if args.doi:
            # 验证特定DOI
            stmt = select(Publication).where(Publication.doi == args.doi)
            pub = session.execute(stmt).scalar_one_or_none()
            if pub:
                publications = [pub]
            else:
                print(f"错误: 未找到DOI {args.doi}")
                return

        elif args.sample:
            # 随机抽样
            # 只选择有作者数据的论文
            stmt = select(Publication).where(
                Publication.doi.isnot(None)
            ).where(
                Publication.id.in_(
                    select(PublicationAuthor.publication_id).distinct()
                )
            )

            all_pubs = session.execute(stmt).scalars().all()

            if len(all_pubs) < args.sample:
                print(f"警告: 只有 {len(all_pubs)} 篇论文有作者数据，将全部验证")
                publications = all_pubs
            else:
                publications = random.sample(all_pubs, args.sample)

        else:
            print("错误: 请指定 --sample 或 --doi 参数")
            parser.print_help()
            return

        print(f"\n准备验证 {len(publications)} 篇论文...")
        print(f"预计时间: {len(publications) * 1.5 / 60:.1f} 分钟")

        # 验证每篇论文
        validation_results = []

        for i, pub in enumerate(publications, 1):
            print(f"\n进度: [{i}/{len(publications)}]")
            result = validate_publication(session, pub, validator, args.detailed)
            validation_results.append(result)

        # 生成汇总报告
        summary = generate_summary_report(validation_results)

        # 保存报告
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"validation_report_{timestamp}.json"

        full_report = {
            "summary": summary,
            "detailed_results": validation_results
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False)

        print_summary_report(summary)

        print("\n" + "="*80)
        print(f"完整报告已保存到: {report_file}")
        print("="*80 + "\n")

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
