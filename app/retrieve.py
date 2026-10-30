import re

from app.knowledge import Curriculum, Section
from app.textutil import fold, tokens

_BROAD = (
    "cuentame",
    "hablame",
    "quien es",
    "quien eres",
    "perfil",
    "trayectoria",
    "resumen",
    "presentate",
    "sobre ti",
    "about you",
    "tell me about",
    "experiencia profesional",
    "background",
    "platicame",
    "presentame",
)


def _has_term(haystack: str, token: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack) is not None


def _score(section: Section, query_tokens: list[str]) -> int:
    haystack = fold(section.blob())
    keyword_words = set()
    for keyword in section.keywords:
        keyword_words.update(fold(keyword).split())
    score = 0
    for token in query_tokens:
        if token in keyword_words:
            score += 3
        elif _has_term(haystack, token):
            score += 1
    return score


def _is_broad(folded_query: str) -> bool:
    return any(phrase in folded_query for phrase in _BROAD)


def select_sections(cv: Curriculum, question: str, history: list[dict]) -> list[Section]:
    previous_user = " ".join(
        turn["content"] for turn in history if turn.get("role") == "user"
    )
    combined = f"{previous_user}\n{question}"
    folded = fold(combined)
    if _is_broad(fold(question)) or _is_broad(folded):
        return list(cv.sections)

    query_tokens = tokens(combined)
    if not query_tokens:
        return []

    ranked = [(section, _score(section, query_tokens)) for section in cv.sections]
    ranked.sort(key=lambda item: item[1], reverse=True)
    best = ranked[0][1]
    if best <= 0:
        return []
    floor = 1 if best < 3 else 3
    return [section for section, score in ranked if score >= floor]
