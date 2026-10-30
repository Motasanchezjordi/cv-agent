import re
import unicodedata

_TOKEN = re.compile(r"[a-z0-9áéíóúüñ]{2,}", re.IGNORECASE)

STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "u", "que", "qué", "en", "con", "por", "para", "su", "sus", "es",
    "son", "se", "me", "te", "lo", "le", "les", "mi", "tu", "como", "cómo",
    "cual", "cuál", "donde", "dónde", "cuando", "cuándo", "sobre", "este",
    "esta", "esto", "hay", "mas", "más", "the", "and", "for", "you", "your",
    "what", "who", "how", "did", "does", "his", "her", "jordi", "tiene", "tienen",
}


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def tokens(value: str) -> list[str]:
    found = []
    for token in _TOKEN.findall(fold(value)):
        if token not in STOPWORDS and token not in found:
            found.append(token)
    return found
