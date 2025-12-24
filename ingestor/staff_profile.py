"""Scrape staff profile pages for structured data."""

from __future__ import annotations

from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "UNSW-AI-RAG-Research-Bot/0.1"}


def fetch_html(url: str) -> str:
    """Fetch a profile page."""
    resp = requests.get(url, timeout=10, headers=HEADERS)
    resp.raise_for_status()
    return resp.text


def _extract_biography(soup: BeautifulSoup) -> Optional[str]:
    bio_block = soup.select_one(".profile-bio, .person-bio, .unsw-person-bio")
    if bio_block:
        return bio_block.get_text(" ", strip=True)

    # 如果找不到特定的 bio class，尝试提取前几个段落作为简介
    paragraphs = soup.find_all('p')
    if paragraphs:
        # 提取前3个有意义的段落作为简介
        bio_parts = []
        for p in paragraphs[:5]:
            text = p.get_text(" ", strip=True)
            if len(text) > 50:  # 只保留有意义的段落
                bio_parts.append(text)
                if len(bio_parts) >= 3:
                    break
        if bio_parts:
            return " ".join(bio_parts)

    return None


def _extract_research_text(soup: BeautifulSoup) -> Optional[str]:
    for heading in soup.find_all(["h2", "h3"]):
        text = heading.get_text(" ", strip=True).lower()
        if any(word in text for word in ("research", "expertise", "interest")):
            # 查找标题后的所有内容，直到下一个标题
            research_parts = []
            for elem in heading.find_all_next():
                # 如果遇到另一个标题，停止
                if elem.name in ['h1', 'h2', 'h3'] and elem != heading:
                    break
                # 提取段落、列表项等有意义的内容
                if elem.name in ['p', 'li']:
                    elem_text = elem.get_text(" ", strip=True)
                    if len(elem_text) > 20:
                        research_parts.append(elem_text)
                        if len(research_parts) >= 3:  # 最多提取3段
                            break
            if research_parts:
                return " ".join(research_parts)
    return None


def parse_staff_profile(url: str) -> Dict[str, Optional[str]]:
    """Parse biography and research sections for a staff profile."""
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    return {
        "biography": _extract_biography(soup),
        "research_text": _extract_research_text(soup),
    }
