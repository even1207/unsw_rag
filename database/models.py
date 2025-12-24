"""Data classes describing staff and publication entities."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Publication:
    title: str
    venue: str | None = None
    year: int | None = None


@dataclass
class Staff:
    staff_id: str
    name: str
    title: str | None = None
    email: str | None = None
    profile_url: str | None = None
    publications: List[Publication] = field(default_factory=list)
