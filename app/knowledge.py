from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    keywords: tuple[str, ...]
    text: str

    def blob(self) -> str:
        return f"{self.title}\n{self.text}\n{' '.join(self.keywords)}"


@dataclass(frozen=True)
class Curriculum:
    person_name: str
    headline: str
    location: str
    email: str
    sections: tuple[Section, ...]
    limits: str

    def by_id(self, section_id: str) -> Section | None:
        for section in self.sections:
            if section.id == section_id:
                return section
        return None


def load_curriculum(path: Path) -> Curriculum:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    person = raw["person"]
    sections = tuple(
        Section(
            id=item["id"],
            title=item["title"],
            keywords=tuple(str(word) for word in (item.get("keywords") or ())),
            text=" ".join(item["text"].split()),
        )
        for item in raw["sections"]
    )
    return Curriculum(
        person_name=person["name"],
        headline=person["headline"],
        location=person["location"],
        email=person["email"],
        sections=sections,
        limits=" ".join(raw["limits"].split()),
    )
