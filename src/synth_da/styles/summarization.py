"""Summarization generator - two LLM calls: generate document, then summarize it."""

from __future__ import annotations

import json
import re
import warnings
from typing import Any

from synth_da.client import GenerationClient
from synth_da.filters import passes_filters
from synth_da.styles.base import BaseGenerator

_NON_LATIN_RE = re.compile(r"[Ѐ-ӿ؀-ۿ　-ヿ一-鿿]")

_DOCUMENT_PROMPT = """\
Skriv en naturlig, velskrevet dansk tekst om samme emne som teksten herunder.
Teksten skal læses som originalt skrevet dansk - ikke som en oversættelse eller omskrivning.
Længde: 150–300 ord.

{seed_text}"""

_SUMMARY_PROMPT = """\
Opsummer følgende tekst kortfattet på dansk.
Resuméet skal:
- Dække tekstens vigtigste pointer
- Ikke indeholde oplysninger der ikke fremgår af teksten
- Kunne stå alene uden reference til "teksten ovenfor"
- Være markant kortere end originalen

{document}"""

_RETRY_SUMMARY_PROMPT = """\
Dit forrige resumé blev afvist: {reason}

Skriv et nyt resumé af dokumentet herunder udelukkende på korrekt dansk. Resuméet skal:
- Dække alle vigtige pointer i hele dokumentet (ikke kun de første sætninger)
- Ikke introducere oplysninger der ikke fremgår af dokumentet
- Kunne stå alene uden referencer til "ovenstående tekst"
- Være markant kortere end dokumentet

{document}"""


def _build_judge_prompt(document: str, summary: str) -> str:
    return (
        "Du er kvalitetsdommer for et dansk opsummeringsdatasæt.\n"
        "Et godt par består af (1) et dokument skrevet i naturlig, originalt dansk og "
        "(2) et resumé der er trofast og dækkende.\n\n"
        "Afvis parret hvis ét eller flere af følgende gælder:\n"
        "- Resuméet nævner fakta eller detaljer der ikke fremgår af dokumentet\n"
        "- Resuméet dækker kun de første sætninger og ignorerer resten af dokumentet\n"
        "- Resuméet er næsten lige så langt som dokumentet — mere genfortælling end komprimering\n"
        '- Resuméet refererer til "ovenstående tekst" eller bruger pronominer uden klar reference\n'
        "- Dokumentet eller resuméet indeholder ikke-dansk tekst: ikke-latinske tegn (fx kinesiske, russiske, arabiske) eller fremmedsprogede ord der ikke er etablerede lånord i dansk\n"
        "- Dokumentet lyder som oversat eller kalket prosa frem for originalt dansk\n\n"
        "Dokument:\n" + document + "\n\n"
        "Resumé:\n" + summary + "\n\n"
        'Returner KUN et JSON-objekt: {"verdict": true, "reason": ""} eller '
        '{"verdict": false, "reason": "kort begrundelse på dansk"}'
    )


async def _summarization_judge(
    document: str,
    summary: str,
    client: GenerationClient,
) -> tuple[bool, str]:
    prompt = _build_judge_prompt(document=document, summary=summary)
    raw = await client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=200,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            verdict = bool(parsed.get("verdict", False))
            reason = str(parsed.get("reason", ""))
            return verdict, reason
    except json.JSONDecodeError:
        pass
    warnings.warn(f"summarization_judge: could not parse response {raw!r:.80}", stacklevel=2)
    return False, ""


class SummarizationGenerator(BaseGenerator):
    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        seed_text = self.config.render_seed_text(row=row)
        if seed_text is None:
            return []

        document = await self._generate_document(seed_text=seed_text)
        if not document or not document.strip():
            return []
        if _NON_LATIN_RE.search(document):
            self.stats["skipped_filter"] += 1
            return []

        summary = await self._generate_summary(document=document)
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
                    "document": document,
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
                    "document": document,
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
        if s["skipped_filter"]:
            rows.append(("  – filters", s["skipped_filter"]))
        if s["skipped_judge"]:
            rows.append(("  – judge", s["skipped_judge"]))
            rows.append(("  + retry accepted", s.get("retry_accepted", 0)))
            rows.append(("  – retry judge", s.get("retry_skipped_judge", 0)))
        rows.append(("Accepted", s["accepted"] + s.get("retry_accepted", 0)))
        return rows

    async def _generate_document(self, seed_text: str) -> str:
        prompt = self._fmt(_DOCUMENT_PROMPT, seed_text=seed_text)
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

    async def _generate_summary(self, document: str) -> str:
        prompt = self._fmt(_SUMMARY_PROMPT, document=document)
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
