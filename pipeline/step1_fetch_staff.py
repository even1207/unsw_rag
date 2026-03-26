"""
Step 1: 爬取 UNSW Staff 数据（支持多 Faculty、断点续传、自动重试）

用法:
    # 爬取单个 faculty
    python3 pipeline/step1_fetch_staff.py --faculty engineering
    python3 pipeline/step1_fetch_staff.py --faculty arts
    python3 pipeline/step1_fetch_staff.py --faculty business

    # 查看所有可用 faculty 及配置
    python3 pipeline/step1_fetch_staff.py --list

    # 断点续传（默认行为：检测到 checkpoint 自动恢复）
    python3 pipeline/step1_fetch_staff.py --faculty engineering

    # 强制从头开始（忽略 checkpoint）
    python3 pipeline/step1_fetch_staff.py --faculty engineering --fresh

    # 只保存 JSON，不写入数据库
    python3 pipeline/step1_fetch_staff.py --faculty engineering --no-db

输出文件:
    data/processed/staff_{faculty}_profiles.json   ← 最终结果
    data/cache/checkpoint_{faculty}.json           ← 断点文件（完成后自动删除）
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# Faculty 配置
# ============================================================================
# 关于 funnelback_faculty: 必须和 UNSW Funnelback 索引里 staffFaculty 元数据
# 的值完全一致（大小写敏感）。如果某 faculty 返回 0 结果，先用 --list 确认配置，
# 再尝试调整这个值。
#
# 关于 gscope1: Funnelback 服务端预定义的"全局过滤桶"，只有 Engineering 的值
# 已确认为 "engineeringStaff"。其他 faculty 不传 gscope1，靠 staffFaculty
# facet 过滤，效果等价。如果某 faculty 结果异常，可以补充对应的 gscope1 值。
#
# 关于 Law: UNSW Law & Justice 的 staff 目录可能走独立入口，
# 建议先用默认配置试跑，如果结果为 0 再单独调查。

FACULTY_CONFIGS: Dict[str, Dict[str, Any]] = {
    # gscope1 值来自各 faculty "Our People" 页面的 data-scope 属性
    # 数量为不过滤 role 的总数（含 casual/adjunct/visiting/honorary）
    "engineering": {
        "display_name": "Faculty of Engineering",
        "gscope1": "engineeringStaff",   # ~790 staff
    },
    "arts": {
        "display_name": "Arts, Design & Architecture",
        "gscope1": "adaStaff",            # ~781 staff
    },
    "business": {
        "display_name": "UNSW Business School",
        "gscope1": "businessStaff",       # ~384 staff
    },
    "law": {
        "display_name": "Law & Justice",
        "gscope1": "lawStaff",            # ~177 staff
    },
    "medicine": {
        "display_name": "Medicine & Health",
        "gscope1": "medicineStaff",       # ~2010 staff
    },
    "science": {
        "display_name": "Faculty of Science",
        "gscope1": "scienceStaff",        # ~841 staff
    },
    "canberra": {
        "display_name": "UNSW Canberra",
        "gscope1": "canberraStaff",       # ~428 staff
    },
}

FUNNELBACK_BASE_URL = "https://unsw-search.funnelback.squiz.cloud/s/search.html"
HEADERS = {"User-Agent": "UNSW-AI-RAG-Research-Bot/0.1"}


# ============================================================================
# 重试工具
# ============================================================================

def with_retry(fn, max_attempts: int = 3, base_delay: float = 2.0):
    """执行 fn()，网络失败时指数退避重试，最后一次失败时抛出异常。"""
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                f"  尝试 {attempt}/{max_attempts} 失败: {exc}"
                f"  → {delay:.0f}s 后重试..."
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ============================================================================
# Part 1: Funnelback API — 获取 Staff 基础列表
# ============================================================================

def fetch_staff_from_api(
    faculty_slug: str,
    page_size: int = 50,
    request_delay: float = 1.0,
) -> List[Dict[str, Any]]:
    """分页调用 Funnelback API，返回指定 faculty 的所有 staff 基础信息。"""
    config = FACULTY_CONFIGS[faculty_slug]
    logger.info(f"从 Funnelback API 获取 [{config['display_name']}] staff...")

    base_params: Dict[str, Any] = {
        "form": "json",
        "collection": "unsw~unsw-search",
        "profile": "profiles",
        "query": "!padrenull",
        "sort": "metastaffLastName",
        "gscope1": config["gscope1"],
    }

    all_staff: List[Dict[str, Any]] = []
    start_rank = 1

    while True:
        params = {**base_params, "start_rank": start_rank, "num_ranks": page_size}

        try:
            data = with_retry(
                lambda p=params: requests.get(
                    FUNNELBACK_BASE_URL, params=p, timeout=15, headers=HEADERS
                ).json(),
                max_attempts=3,
            )
        except Exception as exc:
            # 单页失败不中断，记录后继续下一页
            logger.error(f"  第 {start_rank} 页请求最终失败，跳过: {exc}")
            start_rank += page_size
            time.sleep(request_delay)
            continue

        results = data.get("response", {}).get("resultPacket", {}).get("results", [])
        if not results:
            break

        for record in results:
            meta = record.get("metaData", {})
            all_staff.append(
                {
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
                }
            )

        logger.info(
            f"  rank {start_rank}–{start_rank + len(results) - 1}: "
            f"{len(results)} 位，累计 {len(all_staff)} 位"
        )
        start_rank += page_size
        time.sleep(request_delay)

    logger.info(f"✓ 共获取 {len(all_staff)} 位 [{config['display_name']}] staff")
    if len(all_staff) == 0:
        logger.warning(
            "  返回 0 结果。如果预期有数据，请检查 funnelback_faculty 的值"
            "（大小写需与 UNSW 索引完全一致），或尝试添加 gscope1 参数。"
        )
    return all_staff


# ============================================================================
# Part 2: 爬取单个 Profile 页面
# ============================================================================

def scrape_profile_page(url: str) -> Dict[str, Any]:
    """爬取单个 staff profile 页面，提取结构化字段。"""

    def _fetch():
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.content

    try:
        content = with_retry(_fetch, max_attempts=3)
    except Exception as exc:
        return {"scrape_error": str(exc)}

    soup = BeautifulSoup(content, "html.parser")
    data: Dict[str, Any] = {}

    # 职位
    pos = soup.find("div", class_="field--name-field-job-title")
    if pos:
        data["position"] = pos.get_text(strip=True)

    org = soup.find("div", class_="field--name-field-organisation")
    if org:
        data["organisation"] = org.get_text(strip=True)

    # 联系方式（profile 页面上的补充，以 API 数据为主）
    email_tag = soup.find("a", href=lambda x: x and x.startswith("mailto:"))
    if email_tag:
        data["email_scraped"] = email_tag.get_text(strip=True)

    phone = soup.find("div", class_="field--name-field-phone")
    if phone:
        data["phone_scraped"] = phone.get_text(strip=True)

    location = soup.find("div", class_="field--name-field-location")
    if location:
        data["location"] = location.get_text(strip=True)

    # 个人简介
    bio = soup.find("div", class_="field--name-field-biography")
    if bio:
        data["biography"] = bio.get_text(strip=True)

    # 研究兴趣
    research = soup.find("div", class_="field--name-field-research-interests")
    if research:
        data["research_interests"] = research.get_text(strip=True)

    # 教育背景
    edu = soup.find("div", class_="field--name-field-education")
    if edu:
        data["education"] = edu.get_text(strip=True)

    # Publications（按类型分组，供后续 step2 解析用）
    publications: Dict[str, str] = {}
    for div in soup.find_all(
        "div",
        class_=lambda cls_list: cls_list
        and any("field--name-field-publication" in c for c in cls_list),
    ):
        for cls in div.get("class", []):
            if cls.startswith("field--name-field-publication-"):
                pub_type = cls.replace("field--name-field-publication-", "").replace("-", "_")
                text = div.get_text(strip=True)
                if text:
                    publications[pub_type] = text
    if publications:
        data["publications"] = publications

    return data


# ============================================================================
# Part 3: 断点续传
# ============================================================================

def _checkpoint_path(faculty_slug: str) -> Path:
    p = PROJECT_ROOT / "data" / "cache" / f"checkpoint_{faculty_slug}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_checkpoint(faculty_slug: str) -> Optional[Dict]:
    path = _checkpoint_path(faculty_slug)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_checkpoint(
    faculty_slug: str,
    staff_basic: List,
    completed_urls: List[str],
    results: List,
) -> None:
    path = _checkpoint_path(faculty_slug)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "faculty_slug": faculty_slug,
                "staff_basic": staff_basic,
                "completed_urls": completed_urls,
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def clear_checkpoint(faculty_slug: str) -> None:
    path = _checkpoint_path(faculty_slug)
    if path.exists():
        path.unlink()
        logger.info(f"✓ checkpoint 已清除: {path.name}")


# ============================================================================
# Part 4: 爬取所有 Profile（含断点续传）
# ============================================================================

def scrape_all_profiles(
    faculty_slug: str,
    staff_list: List[Dict],
    completed_urls: List[str],
    partial_results: List[Dict],
    profile_delay: float = 2.0,
    checkpoint_interval: int = 10,
) -> List[Dict]:
    """
    遍历 staff_list 爬取详细 profile 页面。
    completed_urls 中的 URL 会跳过（断点续传）。
    每 checkpoint_interval 条保存一次断点。
    """
    completed_set = set(completed_urls)
    results = list(partial_results)
    pending = [s for s in staff_list if s.get("profile_url") not in completed_set]

    logger.info(
        f"共 {len(staff_list)} 位，已完成 {len(completed_set)}，"
        f"待爬取 {len(pending)} 位"
    )

    for i, staff in enumerate(pending, 1):
        url = staff.get("profile_url")
        name = staff.get("full_name", "Unknown")

        if not url:
            logger.warning(f"[{i}/{len(pending)}] 跳过（无 URL）: {name}")
            results.append({**staff, "profile_details": {"scrape_error": "No profile URL"}})
            continue

        logger.info(f"[{i}/{len(pending)}] {name}")
        profile_details = scrape_profile_page(url)
        results.append({**staff, "profile_details": profile_details})
        completed_set.add(url)

        if i % checkpoint_interval == 0:
            save_checkpoint(faculty_slug, staff_list, list(completed_set), results)
            logger.info(f"  💾 断点保存（{i}/{len(pending)}）")

        time.sleep(profile_delay)

    success = sum(1 for r in results if "scrape_error" not in r.get("profile_details", {}))
    failed = len(results) - success
    logger.info(f"✓ 爬取完成，成功 {success}，失败 {failed}")
    return results


# ============================================================================
# Part 5: 保存 CSV
# ============================================================================

# CSV 列顺序（按重要性排列）
CSV_COLUMNS = [
    # 基础信息（来自 Funnelback API）
    "full_name", "first_name", "last_name", "role", "faculty", "school",
    "email", "phone", "profile_url", "photo_url", "summary",
    # 详细信息（来自 profile 页面爬取）
    "position", "organisation", "location",
    "biography", "research_interests", "education",
    # 爬取补充的联系方式（profile 页面上抓到的，API 没有时用）
    "email_scraped", "phone_scraped",
    # 出版物（JSON 字符串，按类型分组）
    "publications",
    # 错误标记
    "scrape_error",
]


def _flatten_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """将含嵌套 profile_details 的记录展平为一行 CSV 数据。"""
    details = r.get("profile_details", {})
    return {
        "full_name":          r.get("full_name"),
        "first_name":         r.get("first_name"),
        "last_name":          r.get("last_name"),
        "role":               r.get("role"),
        "faculty":            r.get("faculty"),
        "school":             r.get("school"),
        "email":              r.get("email"),
        "phone":              r.get("phone"),
        "profile_url":        r.get("profile_url"),
        "photo_url":          r.get("photo_url"),
        "summary":            r.get("summary"),
        "position":           details.get("position"),
        "organisation":       details.get("organisation"),
        "location":           details.get("location"),
        "biography":          details.get("biography"),
        "research_interests": details.get("research_interests"),
        "education":          details.get("education"),
        "email_scraped":      details.get("email_scraped"),
        "phone_scraped":      details.get("phone_scraped"),
        "publications":       json.dumps(details["publications"], ensure_ascii=False)
                              if details.get("publications") else None,
        "scrape_error":       details.get("scrape_error"),
    }


def save_to_csv(results: List[Dict], csv_path: Path) -> None:
    """将爬取结果展平后保存为 CSV 文件（utf-8-sig 编码，Excel 可直接打开）。"""
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(_flatten_record(r))
    logger.info(f"✓ CSV 已保存: {csv_path}  ({len(results)} 行)")


# ============================================================================
# Part 6: 写入数据库（upsert 到 rag_schema.staff 表）
# ============================================================================

def upsert_to_db(results: List[Dict]) -> None:
    """将结果 upsert 到主 staff 表（rag_schema.Staff）。"""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.orm import sessionmaker

        from config.settings import settings
        from database.rag_schema import Base, Staff
    except ImportError as exc:
        logger.warning(f"数据库模块不可用，跳过 DB 写入: {exc}")
        return

    engine = create_engine(settings.postgres_dsn, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    upserted = 0
    try:
        for r in results:
            url = r.get("profile_url")
            if not url:
                continue
            details = r.get("profile_details", {})
            values = {
                "profile_url": url,
                "full_name": r.get("full_name") or "Unknown",
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "role": r.get("role"),
                "faculty": r.get("faculty"),
                "school": r.get("school"),
                # API 数据优先；如果 API 没有，回退到页面抓取的值
                "email": r.get("email") or details.get("email_scraped"),
                "phone": r.get("phone") or details.get("phone_scraped"),
                "photo_url": r.get("photo_url"),
                "summary": r.get("summary"),
                "biography": details.get("biography"),
                "research_text": details.get("research_interests"),
            }
            stmt = pg_insert(Staff).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["profile_url"],
                set_={k: stmt.excluded[k] for k in values if k != "profile_url"},
            )
            session.execute(stmt)
            upserted += 1

        session.commit()
        logger.info(f"✓ 已 upsert {upserted} 条记录到 staff 表")
    except Exception as exc:
        session.rollback()
        logger.error(f"✗ 数据库写入失败: {exc}")
        raise
    finally:
        session.close()


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="爬取 UNSW Staff profiles（支持多 faculty、断点续传、自动重试）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--faculty",
        choices=list(FACULTY_CONFIGS.keys()),
        help="要爬取的 faculty（如 engineering、arts）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_faculties",
        help="列出所有 faculty 配置并退出",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="忽略已有 checkpoint，从头开始",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        dest="no_db",
        help="只保存 JSON，不写入数据库",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=50,
        dest="page_size",
        help="Funnelback 每页结果数（默认 50）",
    )
    parser.add_argument(
        "--api-delay",
        type=float,
        default=1.0,
        dest="api_delay",
        help="API 翻页间隔秒（默认 1.0）",
    )
    parser.add_argument(
        "--profile-delay",
        type=float,
        default=2.0,
        dest="profile_delay",
        help="爬取 profile 页面间隔秒（默认 2.0）",
    )
    args = parser.parse_args()

    if args.list_faculties:
        print("\n可用 Faculty 配置:\n")
        for slug, cfg in FACULTY_CONFIGS.items():
            print(f"  {slug:<12}  {cfg['display_name']}")
            print(f"               gscope1 = {cfg['gscope1']!r}")
            print()
        return

    if not args.faculty:
        parser.error("请指定 --faculty，或用 --list 查看可用选项")

    faculty_slug = args.faculty
    config = FACULTY_CONFIGS[faculty_slug]
    output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json = output_dir / f"staff_{faculty_slug}_profiles.json"
    output_csv  = output_dir / f"staff_{faculty_slug}_profiles.csv"

    logger.info("=" * 70)
    logger.info(f"Step 1: 爬取 {config['display_name']} Staff 数据")
    logger.info("=" * 70)

    # ── 断点续传 ──────────────────────────────────────────────────────────────
    staff_basic: List[Dict] = []
    completed_urls: List[str] = []
    partial_results: List[Dict] = []

    if not args.fresh:
        checkpoint = load_checkpoint(faculty_slug)
        if checkpoint:
            staff_basic = checkpoint["staff_basic"]
            completed_urls = checkpoint["completed_urls"]
            partial_results = checkpoint["results"]
            logger.info(
                f"✓ 读取到断点：{len(staff_basic)} 位 staff，"
                f"已完成 {len(completed_urls)} 位"
            )
    else:
        clear_checkpoint(faculty_slug)

    # ── Step 1: 从 API 获取基础列表（若断点已包含则跳过）───────────────────
    if not staff_basic:
        staff_basic = fetch_staff_from_api(
            faculty_slug,
            page_size=args.page_size,
            request_delay=args.api_delay,
        )
        save_checkpoint(faculty_slug, staff_basic, [], [])

    # ── Step 2: 爬取 profile 页面 ─────────────────────────────────────────────
    results = scrape_all_profiles(
        faculty_slug=faculty_slug,
        staff_list=staff_basic,
        completed_urls=completed_urls,
        partial_results=partial_results,
        profile_delay=args.profile_delay,
    )

    # ── Step 3: 保存 JSON + CSV ──────────────────────────────────────────────
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ JSON 已保存: {output_json}")
    save_to_csv(results, output_csv)

    # ── Step 4: 写入数据库 ───────────────────────────────────────────────────
    if not args.no_db:
        upsert_to_db(results)
    else:
        logger.info("（--no-db 模式，跳过数据库写入）")

    # ── Step 5: 清除 checkpoint ──────────────────────────────────────────────
    clear_checkpoint(faculty_slug)

    logger.info("=" * 70)
    logger.info(f"✓ [{config['display_name']}] 完成，共 {len(results)} 位 staff")
    logger.info(f"  CSV: {output_csv}")
    logger.info(f"  JSON: {output_json}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
