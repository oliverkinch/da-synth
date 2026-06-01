"""Post-generation quality filters."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from lingua import Language, LanguageDetectorBuilder

from synth_da.config import FilterConfig

if TYPE_CHECKING:
    from synth_da.client import GenerationClient

Message = dict[str, str]

_detector = LanguageDetectorBuilder.from_languages(
    Language.DANISH, Language.ENGLISH, Language.SWEDISH, Language.BOKMAL, Language.NYNORSK
).build()


def _assistant_content(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m["role"] == "assistant":
            return m["content"]
    return ""


def _token_count(text: str) -> int:
    return len(text.split())


def _repetition_ratio(text: str, n: int = 4) -> float:
    """Fraction of n-grams that are repeated."""
    words = text.split()
    if len(words) < n:
        return 0.0
    ngrams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    counts = Counter(ngrams)
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    return repeated / len(ngrams)


def is_danish(text: str) -> bool:
    detected = _detector.detect_language_of(text)
    return bool(detected == Language.DANISH)


def passes_filters(messages: list[Message], cfg: FilterConfig) -> bool:
    content = _assistant_content(messages=messages)
    if not content:
        return False
    if _token_count(text=content) < cfg.min_assistant_tokens:
        return False
    if _repetition_ratio(text=content) > cfg.max_repetition_ratio:
        return False
    return not cfg.language_check or is_danish(text=content)


_QA_JUDGE_PROMPT = """\
Du er kvalitetsdommer for et knowledge-QA datasæt på dansk.
Kildeteksten er ikke tilgængelig — spørgsmålet skal kunne besvares af en veltrænet sprogmodel fra dens træningsviden alene.

Spørgsmål: {question}
Svar: {answer}

Underkend eksemplet hvis:
- Spørgsmålet kun kan besvares med adgang til en specifik kildetekst
- Spørgsmålet indeholder eller parafraserer svaret

Returner KUN JSON: {{"pass": true}} eller {{"pass": false}}"""


async def qa_judge(messages: list[Message], client: GenerationClient) -> bool:
    import json

    question = next((m["content"] for m in messages if m["role"] == "user"), "")
    answer = next((m["content"] for m in messages if m["role"] == "assistant"), "")
    prompt = _QA_JUDGE_PROMPT.format(question=question, answer=answer)
    raw = await client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=16,
    )
    try:
        return bool(json.loads(raw).get("pass", False))
    except Exception:
        return False
