"""Post-generation quality filters."""

from __future__ import annotations

import contextlib
import json
import warnings
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lingua import Language, LanguageDetectorBuilder

from synth_da.config import FilterConfig

if TYPE_CHECKING:
    from synth_da.client import GenerationClient

_EXAMPLES_PATH = Path(__file__).parent.parent.parent / "assets" / "qa_judge_examples.jsonl"
_examples_cache: list[dict[str, Any]] | None = None

_detector = LanguageDetectorBuilder.from_languages(
    Language.DANISH, Language.ENGLISH, Language.SWEDISH, Language.BOKMAL, Language.NYNORSK
).build()


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


def passes_filters(text: str, cfg: FilterConfig) -> bool:
    if not text:
        return False
    if _token_count(text=text) < cfg.min_assistant_tokens:
        return False
    if _repetition_ratio(text=text) > cfg.max_repetition_ratio:
        return False
    return not cfg.language_check or is_danish(text=text)


def _load_examples() -> list[dict[str, Any]]:
    global _examples_cache
    if _examples_cache is None:
        _examples_cache = []
        if _EXAMPLES_PATH.exists():
            with _EXAMPLES_PATH.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        with contextlib.suppress(json.JSONDecodeError):
                            _examples_cache.append(json.loads(line))
    return _examples_cache


def _build_judge_prompt(question: str, answer: str) -> str:
    examples = _load_examples()
    approved = [e for e in examples if e.get("pass") is True]
    rejected = [e for e in examples if e.get("pass") is False]

    lines = ["Du er kvalitetsdommer for et vidensbaseret dansk QA-datasæt.\n"]

    if approved:
        lines.append("Eksempler på godkendte par:\n")
        for e in approved:
            lines.append(f"Q: {e['question']}\nA: {e['answer']}\n")

    if rejected:
        lines.append("Eksempler på underkende par:\n")
        for e in rejected:
            lines.append(f"Q: {e['question']}\nA: {e['answer']}\n")

    lines.append(
        f'Vurder dette par og returner KUN JSON: {{"pass": true}} eller {{"pass": false}}'
        f"\n\nQ: {question}\nA: {answer}"
    )
    return "\n".join(lines)


async def qa_judge(question: str, answer: str, client: GenerationClient) -> bool:
    prompt = _build_judge_prompt(question=question, answer=answer)
    raw = await client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=16,
    )
    try:
        return bool(json.loads(raw).get("pass", False))
    except Exception:
        warnings.warn(f"qa_judge: could not parse response {raw!r:.80}", stacklevel=2)
        return False
