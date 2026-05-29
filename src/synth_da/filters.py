"""Post-generation quality filters."""

from __future__ import annotations

from collections import Counter

from lingua import Language, LanguageDetectorBuilder

from synth_da.config import FilterConfig

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
    return detected == Language.DANISH


def passes_filters(messages: list[Message], cfg: FilterConfig) -> bool:
    content = _assistant_content(messages)
    if not content:
        return False
    if _token_count(content) < cfg.min_assistant_tokens:
        return False
    if _repetition_ratio(content) > cfg.max_repetition_ratio:
        return False
    if cfg.language_check and not is_danish(content):
        return False
    return True


JUDGE_SYSTEM_PROMPT = """\
Du er en kvalitetsdommer for træningsdata til sprogmodeller. \
Du vurderer kvaliteten af et samtaleeksempel på dansk.

Bedøm eksemplet på en skala fra 1 til 5 efter følgende kriterier:
1 – Ubrugeligt: forkert sprog, meningsløst eller skadeligt indhold
2 – Dårlig kvalitet: ukorrekt, vagt eller ufuldstændigt svar
3 – Acceptabel: korrekt men banal, overfladisk eller unaturlig
4 – God kvalitet: korrekt, naturligt dansk, relevant og informativt
5 – Fremragende: præcist, velformuleret, naturligt og genuint nyttigt

Svar KUN med et JSON-objekt på formen:
{"score": <1-5>, "reason": "<én sætning>"}
"""


async def judge_sample(
    messages: list[Message],
    client: "GenerationClient",  # noqa: F821 — avoid circular import
) -> tuple[int, str]:
    from synth_da.client import GenerationClient  # local import to avoid circular

    assert isinstance(client, GenerationClient)

    prompt = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Eksempel:\n\n{messages}"},
    ]
    raw = await client.generate(prompt, temperature=0.0, max_tokens=128)
    import json

    try:
        data = json.loads(raw)
        return int(data["score"]), str(data["reason"])
    except Exception:
        return 0, "parse error"
