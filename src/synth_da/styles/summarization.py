"""Summarization generator - uses real source documents, synthesises the summary."""

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

_NON_LATIN_RE = re.compile(r"[Ѐ-ӿ؀-ۿ　-ヿ一-鿿]")

_EXAMPLES_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "assets"
    / "summarization_judge_rejection_examples.jsonl"
)

_SUMMARY_PROMPT = """\
Opsummer følgende dokument kortfattet og udelukkende på dansk.

Her er et eksempel på et resumé til inspiration — skriv et nyt, selvstændigt resumé med egne ord:
{original_summary}

Resuméet skal:
- Dække dokumentets vigtigste pointer
- Ikke indeholde oplysninger der ikke fremgår af dokumentet
- Kunne stå alene uden reference til "teksten ovenfor" eller "dokumentet"
- Være markant kortere end originalen
- Bruge udelukkende idiomatisk dansk
- Skriv i løbende prosatekst — ingen overskrifter, ingen markdown-formatering (fx ikke **fed** eller # overskrifter)
- Brug kun oplysninger der fremgår af det medfølgende dokument — tilføj ikke viden om EU-lovgivning, fremtidige ændringer, domme eller andre oplysninger fra din træning

Dokument:
{document}"""

_RETRY_SUMMARY_PROMPT = """\
Dit forrige resumé blev afvist: {reason}

Skriv et nyt resumé af dokumentet herunder udelukkende på korrekt dansk. Resuméet skal:
- Dække alle vigtige pointer i hele dokumentet (ikke kun de første sætninger)
- Ikke introducere oplysninger der ikke fremgår af dokumentet
- Kunne stå alene uden referencer til "ovenstående tekst"
- Være markant kortere end dokumentet
- Skriv i løbende prosatekst — ingen overskrifter, ingen markdown-formatering

Dokument:
{document}"""


@functools.lru_cache(maxsize=1)
def _load_examples() -> tuple[dict[str, str], ...]:
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


def _build_judge_prompt(document: str, summary: str) -> str:
    examples = _load_examples()
    parts = [
        "Du er kvalitetsdommer for et dansk opsummeringsdatasæt.\n"
        "Dokumentet er en reel kildeartikel — vurder KUN kvaliteten af resuméet, ikke dokumentet.\n\n"
        "Gennemlæs dokumentet og resuméet, og afvis resuméet hvis ét eller flere af følgende gælder:\n"
        "- Resuméet nævner fakta eller detaljer der ikke fremgår af dokumentet\n"
        "- Resuméet dækker kun de første sætninger og ignorerer resten af dokumentet\n"
        "- Resuméet er næsten lige så langt som dokumentet — mere genfortælling end komprimering\n"
        '- Resuméet refererer til "ovenstående tekst" eller "dokumentet" eller bruger pronominer uden klar reference\n'
        "- Resuméet indeholder ikke-dansk tekst: ikke-latinske tegn (fx kinesiske, arabiske) eller fremmedsprogede ord der klart ikke er etablerede lånord i dansk\n"
        "- Resuméet indeholder åbenlyse stavefejl, ord der ikke eksisterer på dansk, eller klar grammatisk fejl\n"
    ]
    if examples:
        parts.append("\nAfvis resuméer som disse:\n")
        for e in examples:
            parts.append(f"Resumé: {e['summary']}\n" f"Grund: {e['reason']}\n")
    parts.append(
        f"\nDokument:\n{document}\n\n"
        f"Resumé:\n{summary}\n\n"
        'Returner KUN et JSON-objekt: {"verdict": true, "reason": ""} eller '
        '{"verdict": false, "reason": "kort begrundelse på dansk"}.\n'
        "Ved afvisning er reason PÅKRÆVET — skriv altid en konkret begrundelse på 5–20 ord."
    )
    return "\n".join(parts)


async def _summarization_judge(
    document: str,
    summary: str,
    client: GenerationClient,
) -> tuple[bool, str]:
    prompt = _build_judge_prompt(document=document, summary=summary)
    raw = await client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=800,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            verdict = bool(parsed.get("verdict", False))
            reason = str(parsed.get("reason", ""))
            return verdict, reason
    except json.JSONDecodeError:
        pass
    m = re.search(r'"verdict"\s*:\s*(true|false)', raw)
    if m:
        verdict = m.group(1) == "true"
        r_m = re.search(r'"reason"\s*:\s*"([^"]*)"', raw)
        reason = r_m.group(1) if r_m else ""
        return verdict, reason
    warnings.warn(f"summarization_judge: could not parse response {raw!r:.80}", stacklevel=2)
    return False, ""


class SummarizationGenerator(BaseGenerator):
    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        document = self.config.render_text(row=row)
        if not document or not document.strip():
            return []

        if self.config.min_document_chars and len(document) < self.config.min_document_chars:
            self.stats["skipped_too_short"] += 1
            return []

        if self.config.max_document_chars and len(document) > self.config.max_document_chars:
            self.stats["skipped_too_long"] += 1
            return []

        original_summary = ""
        if self.config.summary_column:
            original_summary = str(row.get(self.config.summary_column) or "")

        summary = await self._generate_summary(document=document, original_summary=original_summary)
        if not summary or not summary.strip():
            return []

        if not passes_filters(text=summary, cfg=self.config.filters) or _NON_LATIN_RE.search(
            summary
        ):
            self.stats["skipped_filter"] += 1
            return []

        verdict, reason = await _summarization_judge(
            document=document, summary=summary, client=self.client
        )
        if self.on_verdict is not None:
            self.on_verdict(
                {
                    "document": document[:1000],
                    "summary": summary,
                    "verdict": verdict,
                    "reason": reason,
                    "stage": "first_pass",
                }
            )

        if verdict:
            self.stats["accepted"] += 1
            return [
                self._make_record(
                    fields={"document": document, "summary": summary},
                    seed_config=seed_config,
                    row=row,
                )
            ]

        self.stats["skipped_judge"] += 1

        if not reason:
            return []

        retry_summary = await self._retry_summary(document=document, reason=reason)
        if not retry_summary or not retry_summary.strip():
            return []
        if not passes_filters(text=retry_summary, cfg=self.config.filters) or _NON_LATIN_RE.search(
            retry_summary
        ):
            return []

        retry_verdict, retry_reason = await _summarization_judge(
            document=document, summary=retry_summary, client=self.client
        )
        if self.on_verdict is not None:
            self.on_verdict(
                {
                    "document": document[:1000],
                    "summary": retry_summary,
                    "verdict": retry_verdict,
                    "reason": retry_reason,
                    "stage": "retry",
                }
            )

        if retry_verdict:
            self.stats["retry_accepted"] += 1
            return [
                self._make_record(
                    fields={"document": document, "summary": retry_summary},
                    seed_config=seed_config,
                    row=row,
                )
            ]

        self.stats["retry_skipped_judge"] += 1
        return []

    def stats_rows(self) -> list[tuple[str, int]]:
        s = self.stats
        if not s:
            return []
        rows: list[tuple[str, int]] = []
        if s.get("skipped_too_short"):
            rows.append(("  – too short", s["skipped_too_short"]))
        if s["skipped_too_long"]:
            rows.append(("  – too long", s["skipped_too_long"]))
        if s["skipped_filter"]:
            rows.append(("  – filters", s["skipped_filter"]))
        if s["skipped_judge"]:
            rows.append(("  – judge", s["skipped_judge"]))
            rows.append(("  + retry accepted", s.get("retry_accepted", 0)))
            rows.append(("  – retry judge", s.get("retry_skipped_judge", 0)))
        rows.append(("Accepted", s["accepted"] + s.get("retry_accepted", 0)))
        return rows

    async def _generate_summary(self, document: str, original_summary: str) -> str:
        prompt = self._fmt(_SUMMARY_PROMPT, document=document, original_summary=original_summary)
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

    async def _retry_summary(self, document: str, reason: str) -> str:
        prompt = self._fmt(_RETRY_SUMMARY_PROMPT, document=document, reason=reason)
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
