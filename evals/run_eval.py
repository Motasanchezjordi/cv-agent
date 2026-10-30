import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import Agent
from app.config import load_settings
from app.knowledge import load_curriculum
from app.llm import GroqClient


def main() -> int:
    settings = load_settings()
    agent = Agent(
        load_curriculum(settings.cv_path),
        GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_base_url),
    )
    cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
    failed = 0
    for case in cases:
        needs_model = case["path"] == "llm"
        if needs_model and not settings.groq_api_key:
            print(f"SKIP  {case['question']}")
            continue
        answer = agent.reply(case["question"], [], None, 0.2)
        problems = []
        if answer.path != case["path"]:
            problems.append(f"path {answer.path} != {case['path']}")
        text = answer.text.lower()
        for snippet in case.get("must_mention", []):
            if snippet.lower() not in text:
                problems.append(f"falta {snippet!r}")
        for snippet in case.get("must_not", []):
            if snippet.lower() in text:
                problems.append(f"no debía decir {snippet!r}")
        if problems:
            failed += 1
            print(f"FAIL  {case['question']}")
            print(f"      {'; '.join(problems)}")
            print(f"      {answer.text[:300]}")
        else:
            print(f"OK    {case['question']}")
    print(f"\n{failed} fallos")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
