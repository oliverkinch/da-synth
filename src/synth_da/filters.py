"""Post-generation quality filters."""

from __future__ import annotations

from collections import Counter

from lingua import Language, LanguageDetectorBuilder

from synth_da.config import FilterConfig

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
