from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    groq_base_url: str
    agent_api_key: str
    cv_path: Path
    log_bodies: bool


def load_settings() -> Settings:
    return Settings(
        groq_api_key=_env("GROQ_API_KEY"),
        groq_model=_env("GROQ_MODEL", "openai/gpt-oss-20b"),
        groq_base_url=_env("GROQ_API_KEY_BASE", "") or _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        agent_api_key=_env("AGENT_API_KEY"),
        cv_path=Path(_env("CV_PATH", str(ROOT / "knowledge" / "cv.yaml"))),
        log_bodies=_env("LOG_BODIES", "1") not in {"0", "false", "False"},
    )
