"""QA generator - single LLM call: extract up to 3 facts and generate Q+A pairs."""

from __future__ import annotations

import contextlib
import functools
import json
import re
import warnings
from pathlib import Path
from typing import Any

from synth_da.client import GenerationClient
from synth_da.filters import passes_filters
from synth_da.styles.base import BaseGenerator

_SKIP_QUESTION_RE = re.compile(r"\bfødt\b|\bi dag\b", re.IGNORECASE)

_EXAMPLES_PATH = (
    Path(__file__).parent.parent.parent.parent / "assets" / "qa_judge_rejection_examples.jsonl"
)


@functools.lru_cache(maxsize=1)
def _load_examples() -> tuple[dict[str, Any], ...]:
    if not _EXAMPLES_PATH.exists():
        return ()
    examples = []
    with _EXAMPLES_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                with contextlib.suppress(json.JSONDecodeError):
                    examples.append(json.loads(line))
    return tuple(examples)


def _build_judge_prompt(pairs: list[tuple[str, str]]) -> str:
    examples = _load_examples()

    lines = [
        "Du er kvalitetsdommer for et vidensbaseret dansk QA-datasæt.\n"
        "Et godt par har et svar der er tidløst (ikke forældet om et år) og selvstændigt "
        "(kræver ikke adgang til kildeteksten).\n"
    ]

    if examples:
        lines.append("Afvis par som disse:\n")
        for e in examples:
            reason = e.get("reason", "")
            entry = f"Q: {e['question']}\nA: {e['answer']}\n"
            lines.append(entry if not reason else entry + f"Grund: {reason}\n")

    pair_lines = [f"Par {i}:\nQ: {q}\nA: {a}" for i, (q, a) in enumerate(pairs, 1)]
    lines.append(
        f"Vurder disse {len(pairs)} par og returner KUN en JSON-liste med true/false per par, "
        f"f.eks. [true, false].\n\n" + "\n\n".join(pair_lines)
    )

    return "\n".join(lines)


async def _qa_judge(pairs: list[tuple[str, str]], client: GenerationClient) -> list[bool]:
    if not pairs:
        return []
    prompt = _build_judge_prompt(pairs=pairs)
    max_tokens = len(pairs) * 12
    raw = await client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) == len(pairs):
            return [bool(v) for v in parsed]
    except json.JSONDecodeError:
        pass
    warnings.warn(f"qa_judge: could not parse response {raw!r:.80}", stacklevel=2)
    return [False] * len(pairs)


_PROMPT = """\
Find op til 3 gode, indbyrdes forskellige fakta fra teksten der egner sig til et vidensbaseret datasæt.
Genér et direkte dansk spørgsmål per faktum - ingen indledende sætninger eller kontekst.
Faktaet er svaret - det må ikke fremgå af spørgsmålet.
Svaret skal direkte og præcist besvare spørgsmålet.
Returner som JSON-liste eller null.

[{{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915."}}, \
{{"question": "Hvem var statsminister da kvinder fik stemmeret i Danmark?", "answer": "Carl Theodor Zahle."}}]

{text}"""


class QAGenerator(BaseGenerator):
    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        text = self.config.render_seed_text(row=row)
        if text is None:
            return []

        pairs = await self._generate_qa(text=text)
        self.stats["extracted"] += len(pairs)

        candidates = []
        for q, a in pairs:
            if _SKIP_QUESTION_RE.search(q):
                self.stats["skipped_regex"] += 1
            elif not passes_filters(text=a, cfg=self.config.filters):
                self.stats["skipped_filter"] += 1
            else:
                candidates.append((q, a))

        if not candidates:
            return []

        verdicts = await _qa_judge(pairs=candidates, client=self.client)
        records = []
        for (q, a), verdict in zip(candidates, verdicts, strict=True):
            if verdict:
                self.stats["accepted"] += 1
                records.append(
                    self._make_record(
                        fields={"question": q, "answer": a}, seed_config=seed_config, row=row
                    )
                )
            else:
                self.stats["skipped_judge"] += 1
        return records

    def stats_rows(self) -> list[tuple[str, int]]:
        s = self.stats
        if not s:
            return []
        rows: list[tuple[str, int]] = [("Extracted", s["extracted"])]
        if s["skipped_regex"]:
            rows.append(("  – regex", s["skipped_regex"]))
        if s["skipped_filter"]:
            rows.append(("  – filters", s["skipped_filter"]))
        if s["skipped_judge"]:
            rows.append(("  – judge", s["skipped_judge"]))
        rows.append(("Accepted", s["accepted"]))
        return rows

    async def _generate_qa(self, text: str) -> list[tuple[str, str]]:
        prompt = self._fmt(_PROMPT, text=text[:4000])
        raw = await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []

        if not isinstance(value, list):
            return []

        pairs = []
        for item in value[:3]:
            if not isinstance(item, dict):
                continue
            question = (item.get("question") or "").strip()
            answer = (item.get("answer") or "").strip()
            if question and answer:
                pairs.append((question, answer))
        return pairs
