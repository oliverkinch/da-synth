"""Summarization generator - two LLM calls: generate document, then summarize it."""

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

_DOCUMENT_PROMPT = """\
Skriv en naturlig, velskrevet dansk tekst om samme emne som teksten herunder.
Teksten skal læses som originalt skrevet dansk - ikke som en oversættelse eller omskrivning.
Brug udelukkende korrekte danske ord — ingen engelske, tyske, franske, norske, svenske, spanske eller italienske ord. Kontrollér hvert enkelt ord i din tekst — ethvert fremmedsprogligt ord, selv ét eneste, diskvalificerer hele teksten.
Brug udelukkende danske bogstaver (å, æ, ø) — ikke de tyske/svenske varianter (ü, ä, ö).
Undgå særligt disse hyppige fejl: 'fair/unfair'→'retfærdig/urimelig', 'fight'→'kamp', 'boom'→'opsving', 'among'→'blandt', 'across'→'på tværs af', 'carefully'→'omhyggeligt', 'disaster'→'katastrofe', 'search and rescue'→'søgning og redning', 'essentiel/essentielt/essentielle'→'afgørende/nødvendige', 'fundamental'→'grundlæggende', 'pandemin'→'pandemien', 'within'→'inden for', 'thus'→'dermed', 'therefore'→'derfor', 'commitment'→'forpligtelse', 'schedule'→'tidsplan', 'setup'→'konstellation', 'vulnerabilities'→'sårbarheder', 'beyond'→'ud over', 'regarding'→'vedrørende', 'involving'→'der involverer', 'backed op'→'bakket op', 'coup'→'kup', 'factor' (fx 'farefactor')→'faktor', 'compromise/compromises' (verbum)→'kompromittere/kompromitteres', 'leading' (fx '4-0-leading')→'føring', 'initially'→'indledningsvis', 'facts'→'fakta', 'gain'→'gevinst', 'approximately'→'cirka', 'like' (fx 'like let')→'lige så', 'exceptionel'/'exceptionelle'→'usædvanlig', 'confident'→'sikker/overbevist', 'honors'→'overholder/ærer', 'successfully'→'vellykket', 'focus' (engelsk stavemåde)→'fokus', 'room' (fx 'find room')→'plads/rum', 'when'→'når/da'.
Sørg for korrekte mellemrum — ord må aldrig smelte sammen (fx ikke 'enKnusende', 'fortheir', 'fårLocaliseret').
Længde: 150–300 ord.

{seed_text}"""

_SUMMARY_PROMPT = """\
Opsummer følgende tekst kortfattet og udelukkende på dansk.
Resuméet skal:
- Dække tekstens vigtigste pointer
- Ikke indeholde oplysninger der ikke fremgår af teksten
- Kunne stå alene uden reference til "teksten ovenfor"
- Være markant kortere end originalen
- Bruge udelukkende idiomatisk dansk — ingen anglicismer (fx ikke 'essentiel', 'fair', 'unfair', 'setup', 'regarding', 'commitment', 'approximately', 'gain')

{document}"""

_RETRY_SUMMARY_PROMPT = """\
Dit forrige resumé blev afvist: {reason}

Skriv et nyt resumé af dokumentet herunder udelukkende på korrekt dansk. Resuméet skal:
- Dække alle vigtige pointer i hele dokumentet (ikke kun de første sætninger)
- Ikke introducere oplysninger der ikke fremgår af dokumentet
- Kunne stå alene uden referencer til "ovenstående tekst"
- Være markant kortere end dokumentet

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


def _build_judge_prompt(document: str, summary: str, rejection_reason: str = "") -> str:
    examples = _load_examples()
    parts = [
        "Du er kvalitetsdommer for et dansk opsummeringsdatasæt.\n"
        "Et godt par består af (1) et dokument skrevet i naturlig, originalt dansk og "
        "(2) et resumé der er trofast og dækkende.\n\n"
        "Vigtig fremgangsmåde: Evaluer FØRST dokumentet alene. Gennemlæs HELE dokumentet systematisk — også de sidste sætninger — og led aktivt efter disse tre fejltyper: "
        "(1) fremmedsprogede ord og fremmede tegn (fx engelske ord som 'among', 'across', 'fair', 'unfair', 'path', 'compromise', 'through', 'while', 'however', 'routinely', der aldrig optræder i originalt dansk; eller tyske/svenske specialtegn ü, ä, ö som ALDRIG bruges i dansk — brug æ og ø i stedet: 'idrätten'→'idrætten', 'mörket'→'mørket'); "
        "(2) ord smeltet forkert sammen uden mellemrum (fx 'ivejtransporten'→'i vejtransporten', 'harinvestorer'→'har investorer', 'unødigtforsinker'→'unødigt forsinker', 'hæmmeraktivt'→'hæmmer aktivt'); "
        "(3) ord der ikke eksisterer på dansk eller er klart forvekslet med et lignende ord: fx stavefejl ('pebgede'→'pegede', 'Derudra'→'Derudover'), manglende binde-s i sammensætninger ('arbejdmarkedet'→'arbejdsmarkedet'), ord der åbenlyst har forkert betydning i konteksten ('steger'→'stiger', 'stevning'→'stigning'), og fuldstændig ikke-eksisterende ord ('ensamplet'→'en samlet', 'ubemmede'→'ubemærket'). "
        "Afvis parret straks ved én eller flere af disse fejl — resuméets kvalitet er irrelevant i så fald. Scan derefter resuméet på samme måde — et fejlbehæftet resumé diskvalificerer ligeledes parret.\n\n"
        "Afvis parret hvis ét eller flere af følgende gælder:\n"
        "- Resuméet nævner fakta eller detaljer der ikke fremgår af dokumentet\n"
        "- Resuméet dækker kun de første sætninger og ignorerer resten af dokumentet\n"
        "- Resuméet er næsten lige så langt som dokumentet — mere genfortælling end komprimering\n"
        '- Resuméet refererer til "ovenstående tekst" eller bruger pronominer uden klar reference\n'
        "- Dokumentet eller resuméet indeholder ikke-dansk tekst: ikke-latinske tegn (fx kinesiske, russiske, arabiske) eller fremmedsprogede ord der ikke er etablerede lånord i dansk. OBS: Afvis IKKE ord der er veletablerede i dansk, selvom de har udenlandsk oprindelse — fx 'succesfuldt/succesfuld', 'service', 'stress', 'effektiv', 'digital', 'strategi', 'succes', 'tilstrækkelig', 'kompromis', 'gå på kompromis'. Afvis heller ikke korrekte danske adjektivbøjninger ('effektive', 'tilstrækkelige', 'succesfulde') — disse er normale bøjningsformer, ikke anglicismer. Afvis heller ikke 'tryg', 'tryggere', 'trygge' (enkelt-g) — disse er korrekte danske former; afvis DERIMOD 'trygg' (dobbelt-g) som er norsk stavemåde. Afvis heller ikke 'innovere', 'innoverer', 'innoverede', 'innovering' — disse er korrekte danske verbumformer af 'at innovere' og skal ikke forveksles med norske former. Afvis heller ikke veletablerede danske idiomer, selvom de har paralleller i andre sprog — fx 'hvile på laurbærrene', 'tage tyren ved hornene'. Afvis KUN ord der åbenlyst stammer direkte fra et fremmedsprog og ikke er optaget i dansk (fx 'successfully', 'fair', 'unfair', 'within', 'according').\n"
        "- Dokumentet lyder som oversat, kalket eller maskinproduceret prosa: dette inkluderer norske verbs- og ordformer (fx 'legger' i stedet for 'lægger', '-plikt-' i stedet for '-pligt-', '-arbeid-' i stedet for '-arbejd-', '-vern-' i stedet for '-værn-'), svenske ordformer (fx 'trots' i stedet for 'trods', 'och' i stedet for 'og', 'till' i stedet for 'til'), forkert bøjning (fx 'har måtte' i stedet for 'har måttet'), ord der ikke eksisterer i dansk (fx 'varetiger' i stedet for 'varetager'), manglende mellemrum der smelter ord sammen (fx 'kangenrejse' i stedet for 'kan genrejse'), eller store bogstaver midt i sætninger der indikerer fejlagtig formatering\n"
    ]
    if examples:
        parts.append("\nAfvis par som disse:\n")
        for e in examples:
            parts.append(
                f"Dokument: {e['document']}\n" f"Resumé: {e['summary']}\n" f"Grund: {e['reason']}\n"
            )
    if rejection_reason:
        parts.append(
            f"\nBEMÆRK: Dette par er allerede afvist én gang med begrundelsen: «{rejection_reason}». "
            "Scan dokumentet systematisk for den nævnte fejl — et korrekt nyt resumé ændrer intet ved dokumentets egne fejl.\n"
        )
    parts.append(
        "\nDokument:\n" + document + "\n\n"
        "Resumé:\n" + summary + "\n\n"
        'Returner KUN et JSON-objekt: {"verdict": true, "reason": ""} eller '
        '{"verdict": false, "reason": "kort begrundelse på dansk"}'
    )
    return "\n".join(parts)


async def _summarization_judge(
    document: str,
    summary: str,
    client: GenerationClient,
    rejection_reason: str = "",
) -> tuple[bool, str]:
    prompt = _build_judge_prompt(
        document=document, summary=summary, rejection_reason=rejection_reason
    )
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
    # Fallback for truncated responses: extract verdict via regex
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

        if not reason or "Dokumentet " in reason:
            return []

        retry_summary = await self._retry_summary(document=document, reason=reason)
        if not retry_summary or not retry_summary.strip():
            return []
        if not passes_filters(text=retry_summary, cfg=self.config.filters) or _NON_LATIN_RE.search(
            retry_summary
        ):
            return []

        retry_verdict, retry_reason = await _summarization_judge(
            document=document,
            summary=retry_summary,
            client=self.client,
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
            temperature=0.8,
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
