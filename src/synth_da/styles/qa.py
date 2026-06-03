"""QA generator - single LLM call: extract up to 3 facts and generate Q+A pairs."""

from __future__ import annotations

import contextlib
import functools
import json
import warnings
from pathlib import Path
from typing import Any

from synth_da.client import GenerationClient
from synth_da.styles.base import BaseGenerator

_EXAMPLES_PATH = (
    Path(__file__).parent.parent.parent.parent / "assets" / "qa_rejection_examples.jsonl"
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
        "Et godt par er tidløst (ikke forældet om et år), selvstændigt (kræver ikke adgang til "
        "kildeteksten), og spørgsmålet introducerer alle navne og enheder en fremmed har brug for "
        "— det må ikke forudsætte kontekst fra andre spørgsmål.\n"
    ]

    if examples:
        lines.append("Afvis par som disse:\n")
        for e in examples:
            reason = e.get("reason", "")
            entry = f"Q: {e['question']}\nA: {e['answer']}\n"
            lines.append(entry if not reason else entry + f"Grund: {reason}\n")

    pair_lines = [f"Par {i}:\nQ: {q}\nA: {a}" for i, (q, a) in enumerate(pairs, 1)]
    lines.append(
        f"Vurder disse {len(pairs)} par. Returner KUN en JSON-liste med ét objekt per par:\n"
        '[{"verdict": true, "reason": ""}, {"verdict": false, "reason": "kort begrundelse"}]\n\n'
        + "\n\n".join(pair_lines)
    )

    return "\n".join(lines)


async def _qa_judge(
    pairs: list[tuple[str, str]], client: GenerationClient
) -> list[tuple[bool, str]]:
    if not pairs:
        return []
    prompt = _build_judge_prompt(pairs=pairs)
    max_tokens = len(pairs) * 200
    raw = await client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) == len(pairs):
            results = []
            for item in parsed:
                if isinstance(item, dict):
                    results.append((bool(item.get("verdict", False)), str(item.get("reason", ""))))
                elif isinstance(item, bool):
                    results.append((item, ""))
                else:
                    results.append((False, ""))
            return results
    except json.JSONDecodeError:
        pass
    warnings.warn(f"qa_judge: could not parse response {raw!r:.80}", stacklevel=2)
    return [(False, "")] * len(pairs)


_PROMPT = """\
Find op til 3 gode, indbyrdes forskellige fakta fra kildeteksten der egner sig til et vidensbaseret datasæt.
Vælg de bedste og mest informative fakta du kan finde — historiske begivenheder, opdagelser, kulturelle bidrag, tekniske principper, geografisk og biologisk viden. Generér altid op til 3 par; returner kun null hvis kildeteksten er indholdsfattig og ikke giver præcise, verificerbare fakta.
Genér et selvstændigt dansk spørgsmål per faktum — inkluder den kontekst en fremmed har brug for (hvem er personen, hvad er det for et dyr, hvilken begivenhed). Hvert spørgsmål skal kunne forstås og besvares uden kendskab til de andre spørgsmål i listen. Ingen referencer til 'kildeteksten', 'filmen' eller 'programmet' — brug det konkrete navn.
Brug kun fakta der tydeligt og konkret fremgår af kildeteksten — spring et faktum over hvis kildeteksten ikke giver et præcist svar, og vælg et andet. Svaret er en konkret oplysning fra kildeteksten, aldrig en forklaring af hvad kildeteksten ikke indeholder.
Faktaet er svaret - det må ikke fremgå af spørgsmålet.
Stil ét spørgsmål om ét faktum — aldrig to delspørgsmål med 'og'/'samt' i ét.
Svaret skal direkte og præcist besvare spørgsmålet.
Returner som JSON-liste eller null.

<example-output>
[{{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915."}}, \
{{"question": "Hvem var statsminister da kvinder fik stemmeret i Danmark?", "answer": "Carl Theodor Zahle."}}]
</example-output>

<kildetekst>
{text}
</kildetekst>"""

_RETRY_PROMPT = """\
Disse spørgsmål-svar par blev afvist. Ret fejlene og returner op til {n} forbedrede par som JSON-liste eller null.
Hvert spørgsmål skal være selvstændigt — inkluder nødvendig kontekst (hvem er personen, hvilken begivenhed). Ingen referencer til 'kildeteksten', 'filmen' eller 'programmet' — brug det konkrete navn. Stil ét spørgsmål om ét faktum. Hvert spørgsmål skal kunne forstås uden kendskab til de andre spørgsmål i listen.

<kildetekst>
{seed_text}
</kildetekst>

<rejected>
{rejected_pairs}
</rejected>

<example-output>
[{{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915."}}, \
{{"question": "Hvem var statsminister da kvinder fik stemmeret i Danmark?", "answer": "Carl Theodor Zahle."}}]
</example-output>"""


class QAGenerator(BaseGenerator):
    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        text = self.config.render_seed_text(row=row)
        if text is None:
            return []

        source_id = str(row[self.config.source_id_column]) if self.config.source_id_column else None

        candidates = await self._generate_qa(text=text)
        self.stats["extracted"] += len(candidates)

        if not candidates:
            self.stats["skipped_empty"] += 1
            if self.on_verdict:
                self.on_verdict(
                    {
                        "question": None,
                        "answer": None,
                        "verdict": False,
                        "reason": "no_extraction",
                        "stage": "extraction",
                        "seed_text": text,
                        "source_id": source_id,
                    }
                )
            return []

        verdicts = await _qa_judge(pairs=candidates, client=self.client)
        records = []
        rejected: list[tuple[str, str, str]] = []

        for (q, a), (verdict, reason) in zip(candidates, verdicts, strict=True):
            if self.on_verdict:
                self.on_verdict(
                    {
                        "question": q,
                        "answer": a,
                        "verdict": verdict,
                        "reason": reason,
                        "stage": "first_pass",
                        "seed_text": text,
                        "source_id": source_id,
                    }
                )
            if verdict:
                self.stats["accepted"] += 1
                records.append(
                    self._make_record(
                        fields={"question": q, "answer": a}, seed_config=seed_config, row=row
                    )
                )
            else:
                self.stats["skipped_judge"] += 1
                rejected.append((q, a, reason))

        if rejected:
            retry_candidates = await self._retry_qa(seed_text=text, rejected=rejected)
            retry_verdicts = await _qa_judge(pairs=retry_candidates, client=self.client)
            for (q, a), (verdict, reason) in zip(retry_candidates, retry_verdicts, strict=True):
                if self.on_verdict:
                    self.on_verdict(
                        {
                            "question": q,
                            "answer": a,
                            "verdict": verdict,
                            "reason": reason,
                            "stage": "retry",
                            "seed_text": text,
                            "source_id": source_id,
                        }
                    )
                if verdict:
                    self.stats["retry_accepted"] += 1
                    records.append(
                        self._make_record(
                            fields={"question": q, "answer": a},
                            seed_config=seed_config,
                            row=row,
                        )
                    )
                else:
                    self.stats["retry_skipped_judge"] += 1

        return records

    def stats_rows(self) -> list[tuple[str, int]]:
        s = self.stats
        if not s:
            return []
        rows: list[tuple[str, int]] = [("Extracted", s["extracted"])]
        if s.get("skipped_empty"):
            rows.append(("  – empty extraction", s["skipped_empty"]))
        if s["skipped_judge"]:
            rows.append(("  – judge", s["skipped_judge"]))
            rows.append(("  + retry accepted", s.get("retry_accepted", 0)))
            rows.append(("  – retry judge", s.get("retry_skipped_judge", 0)))
        rows.append(("Accepted", s["accepted"] + s.get("retry_accepted", 0)))
        return rows

    async def _generate_qa(self, text: str) -> list[tuple[str, str]]:
        prompt = self._fmt(_PROMPT, text=text)
        raw = await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        return self._parse_pairs(raw=raw)

    async def _retry_qa(
        self, seed_text: str, rejected: list[tuple[str, str, str]]
    ) -> list[tuple[str, str]]:
        rejected_lines = "\n\n".join(
            f"Q: {q}\nA: {a}\nGrund: {reason or '(ingen grund angivet)'}"
            for q, a, reason in rejected
        )
        prompt = self._fmt(
            _RETRY_PROMPT,
            n=str(len(rejected)),
            seed_text=seed_text,
            rejected_pairs=rejected_lines,
        )
        raw = await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        return self._parse_pairs(raw=raw)

    @staticmethod
    def _parse_pairs(raw: str) -> list[tuple[str, str]]:
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
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if question and answer:
                pairs.append((question, answer))
        return pairs
