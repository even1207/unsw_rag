"""Knowledge-graph style collaboration endpoints (authors ↔ publications)."""

from __future__ import annotations

import re
from typing import Generator, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter()


def _get_db(request: Request) -> Generator[Session, None, None]:
    session_local = getattr(request.app.state, "SessionLocal", None)
    if session_local is None:
        raise RuntimeError("Database not initialized (SessionLocal missing on app.state)")
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def _like_pattern(name: str) -> str:
    return f"%{name.strip()}%"


def _extract_person_names(query: str, max_names: int = 2) -> list[str]:
    patterns = [
        # "Wenjie Zhang"
        re.compile(r"\b([A-Z][a-z]+(?:[-'][A-Za-z]+)*)\s+([A-Z][a-z]+(?:[-'][A-Za-z]+)*)\b"),
        # "ZHENGYI YANG"
        re.compile(r"\b([A-Z]{2,})\s+([A-Z]{2,})\b"),
    ]
    names: list[str] = []
    for pat in patterns:
        for m in pat.finditer(query):
            full = f"{m.group(1)} {m.group(2)}".strip()
            if full and full not in names:
                names.append(full)
            if len(names) >= max_names:
                return names
    return names


def _is_collaboration_query(query: str) -> bool:
    q = query.lower()
    keywords = (
        "collaborat",
        "coauthor",
        "co-author",
        "worked with",
        "work with",
        "together",
        "合作",
        "合著",
        "共同作者",
        "合作论文",
    )
    return any(k in q for k in keywords)


class CollaborationResult(BaseModel):
    publication_id: str
    title: str
    year: Optional[int] = None
    doi: Optional[str] = None
    authors: list[str] = Field(default_factory=list)


class CoauthorResult(BaseModel):
    author_id: int
    name: str
    orcid: Optional[str] = None
    last_known_institution: Optional[str] = None
    collaboration_count: int
    latest_collaboration_year: Optional[int] = None


def find_collaborations_db(
    db: Session,
    *,
    author1: str,
    author2: Optional[str],
    min_year: Optional[int],
    max_year: Optional[int],
    limit: int,
) -> list[CollaborationResult]:
    if limit <= 0:
        return []

    params: dict = {
        "a1": _like_pattern(author1),
        "min_year": min_year,
        "max_year": max_year,
        "limit": limit,
    }

    if author2:
        params["a2"] = _like_pattern(author2)
        sql = text(
            """
            WITH a1 AS (
              SELECT id FROM authors WHERE name ILIKE :a1
            ),
            a2 AS (
              SELECT id FROM authors WHERE name ILIKE :a2
            )
            SELECT
              p.id AS publication_id,
              p.title AS title,
              p.publication_year AS year,
              p.doi AS doi,
              COALESCE(
                array_agg(a.name ORDER BY pa.author_position)
                  FILTER (WHERE a.name IS NOT NULL),
                ARRAY[]::text[]
              ) AS authors
            FROM publications p
            JOIN publication_authors pa1 ON p.id = pa1.publication_id
            JOIN publication_authors pa2 ON p.id = pa2.publication_id
            JOIN a1 ON pa1.author_id = a1.id
            JOIN a2 ON pa2.author_id = a2.id
            LEFT JOIN publication_authors pa ON p.id = pa.publication_id
            LEFT JOIN authors a ON pa.author_id = a.id
            WHERE (:min_year IS NULL OR p.publication_year >= :min_year)
              AND (:max_year IS NULL OR p.publication_year <= :max_year)
            GROUP BY p.id, p.title, p.publication_year, p.doi
            ORDER BY p.publication_year DESC NULLS LAST
            LIMIT :limit
            """
        )
    else:
        sql = text(
            """
            WITH a1 AS (
              SELECT id FROM authors WHERE name ILIKE :a1
            )
            SELECT
              p.id AS publication_id,
              p.title AS title,
              p.publication_year AS year,
              p.doi AS doi,
              COALESCE(
                array_agg(a.name ORDER BY pa.author_position)
                  FILTER (WHERE a.name IS NOT NULL),
                ARRAY[]::text[]
              ) AS authors
            FROM publications p
            JOIN publication_authors pa1 ON p.id = pa1.publication_id
            JOIN a1 ON pa1.author_id = a1.id
            LEFT JOIN publication_authors pa ON p.id = pa.publication_id
            LEFT JOIN authors a ON pa.author_id = a.id
            WHERE (:min_year IS NULL OR p.publication_year >= :min_year)
              AND (:max_year IS NULL OR p.publication_year <= :max_year)
            GROUP BY p.id, p.title, p.publication_year, p.doi
            ORDER BY p.publication_year DESC NULLS LAST
            LIMIT :limit
            """
        )

    rows = db.execute(sql, params).mappings().all()
    return [
        CollaborationResult(
            publication_id=str(r["publication_id"]),
            title=r["title"],
            year=r["year"],
            doi=r["doi"],
            authors=list(r["authors"] or []),
        )
        for r in rows
    ]


def get_coauthors_db(
    db: Session,
    *,
    author_name: str,
    min_collaborations: int,
    limit: int,
) -> list[CoauthorResult]:
    if limit <= 0:
        return []

    # Prefer an exact match if possible; otherwise choose the highest works_count match.
    author_id = db.execute(
        text(
            """
            SELECT id
            FROM authors
            WHERE lower(name) = lower(:name)
            ORDER BY works_count DESC NULLS LAST, cited_by_count DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"name": author_name.strip()},
    ).scalar()

    if author_id is None:
        author_id = db.execute(
            text(
                """
                SELECT id
                FROM authors
                WHERE name ILIKE :pat
                ORDER BY works_count DESC NULLS LAST, cited_by_count DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"pat": _like_pattern(author_name)},
        ).scalar()

    if author_id is None:
        return []

    rows = db.execute(
        text(
            """
            SELECT
              a2.id AS author_id,
              a2.name AS name,
              a2.orcid AS orcid,
              a2.last_known_institution AS last_known_institution,
              COUNT(*)::int AS collaboration_count,
              MAX(p.publication_year) AS latest_collaboration_year
            FROM publication_authors pa1
            JOIN publication_authors pa2
              ON pa1.publication_id = pa2.publication_id
             AND pa1.author_id <> pa2.author_id
            JOIN authors a2 ON pa2.author_id = a2.id
            JOIN publications p ON pa1.publication_id = p.id
            WHERE pa1.author_id = :author_id
            GROUP BY a2.id, a2.name, a2.orcid, a2.last_known_institution
            HAVING COUNT(*) >= :min_collaborations
            ORDER BY collaboration_count DESC, latest_collaboration_year DESC NULLS LAST, a2.name
            LIMIT :limit
            """
        ),
        {
            "author_id": author_id,
            "min_collaborations": max(1, min_collaborations),
            "limit": limit,
        },
    ).mappings().all()

    return [
        CoauthorResult(
            author_id=int(r["author_id"]),
            name=r["name"],
            orcid=r["orcid"],
            last_known_institution=r["last_known_institution"],
            collaboration_count=int(r["collaboration_count"]),
            latest_collaboration_year=r["latest_collaboration_year"],
        )
        for r in rows
    ]


def build_kg_context_for_query(
    db: Session, query: str, *, max_items: int = 5
) -> tuple[Optional[str], list[dict]]:
    if not _is_collaboration_query(query):
        return None, []

    names = _extract_person_names(query, max_names=2)
    if not names:
        return None, []

    author1 = names[0]
    author2 = names[1] if len(names) > 1 else None
    papers = find_collaborations_db(
        db,
        author1=author1,
        author2=author2,
        min_year=None,
        max_year=None,
        limit=max_items,
    )
    if not papers:
        return None, []

    title_lines = []
    kg_sources: list[dict] = []
    for p in papers[:max_items]:
        year = f"{p.year}" if p.year else "Unknown year"
        doi = f"doi:{p.doi}" if p.doi else "doi:None"
        title_lines.append(f"- {year} | {doi} | {p.title}")
        kg_sources.append(
            {
                "type": "kg_publication",
                "title": p.title,
                "authors": p.authors[:3],
                "year": p.year,
                "doi": p.doi,
                "url": f"https://doi.org/{p.doi}" if p.doi else None,
            }
        )

    heading = f"Knowledge Graph: coauthored papers for '{author1}'"
    if author2:
        heading += f" and '{author2}'"

    return "\n".join([heading, *title_lines]), kg_sources


@router.get("/api/collaborations", response_model=list[CollaborationResult])
def find_collaborations(
    author1: str = Query(..., description="第一位作者姓名"),
    author2: Optional[str] = Query(None, description="第二位作者姓名(可选)"),
    min_year: Optional[int] = Query(None, description="最早年份"),
    max_year: Optional[int] = Query(None, description="最晚年份"),
    limit: int = Query(50, description="返回结果数量", ge=1, le=200),
    db: Session = Depends(_get_db),
) -> list[CollaborationResult]:
    """
    查找作者合作论文

    示例:
    - /api/collaborations?author1=Wenjie Zhang&author2=Zhengyi Yang
    - /api/collaborations?author1=Martin Green&min_year=2020
    """
    return find_collaborations_db(
        db,
        author1=author1,
        author2=author2,
        min_year=min_year,
        max_year=max_year,
        limit=limit,
    )


@router.get("/api/authors/{author_name}/coauthors", response_model=list[CoauthorResult])
def get_coauthors(
    author_name: str,
    min_collaborations: int = Query(1, description="最小合作次数", ge=1),
    limit: int = Query(50, description="返回结果数量", ge=1, le=200),
    db: Session = Depends(_get_db),
) -> list[CoauthorResult]:
    """查找某作者的所有合作者,按合作次数排序"""
    return get_coauthors_db(
        db,
        author_name=author_name,
        min_collaborations=min_collaborations,
        limit=limit,
    )
