"""Post-generation quality filters."""

from __future__ import annotations

import json
import warnings
from collections import Counter
from typing import TYPE_CHECKING

from lingua import Language, LanguageDetectorBuilder

from synth_da.config import FilterConfig

if TYPE_CHECKING:
    from synth_da.client import GenerationClient

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


_QA_JUDGE_PROMPT = """\
Du er kvalitetsdommer for et knowledge-QA datasæt på dansk.
Kildeteksten er ikke tilgængelig — spørgsmålet skal kunne besvares af en veltrænet sprogmodel fra dens træningsviden alene.

Spørgsmål: {question}
Svar: {answer}

Underkend eksemplet hvis:
- Spørgsmålet kun kan besvares med adgang til en specifik kildetekst
- Spørgsmålet indeholder eller parafraserer svaret, fx ved at opstille svarmulighederne ("er det X eller Y?")
- Spørgsmålet er bekræftelsessøgende eller ledende ("var det ikke...", "vidste du at...")
- Spørgsmålet bruger AI-formulering som "hvad er et centralt faktum om...", "hvad er det mest kendte faktum om...", "hvad er det bemærkelsesværdige ved..."
- Faktaet er uden vidensbaseret værdi — en veltrænet sprogmodel ville ikke have gavn af at kende det (fx ultra-specifik produktionstrivialitet, biografiske detaljer om ukendte personer, præcise mål for obskure geografiske steder)

Returner KUN JSON: {{"pass": true}} eller {{"pass": false}}"""


async def qa_judge(question: str, answer: str, client: GenerationClient) -> bool:
    prompt = _QA_JUDGE_PROMPT.format(question=question, answer=answer)
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
