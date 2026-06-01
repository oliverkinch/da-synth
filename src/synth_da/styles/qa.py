"""QA generator — two-step: extract general-knowledge facts, then generate Q+A per fact."""

from __future__ import annotations

import json
import random
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters
from synth_da.personas import persona_to_prompt, sample_persona
from synth_da.styles.base import BaseGenerator

_SYSTEM_PROMPTS = [
    "Du er en hjælpsom assistent. Svar altid på dansk.",
    "Du er en kyndig assistent der svarer præcist og kortfattet på dansk.",
    "Svar på brugerens spørgsmål på dansk.",
]

_EXTRACT_FACT_PROMPT = """\
Læs teksten herunder og identificér det bedste enkeltfaktum der kan betragtes som \
almen viden — noget en kompetent dansker sandsynligvis ville støde på i dagspressen, \
i skolen eller i hverdagen, og som en sprogmodel med rimelighed kan forventes at kende.

Returner KUN én kort faktasætning på dansk som en JSON-streng. \
Hvis teksten ikke indeholder fakta der lever op til dette, returneres null.

Eksempler på almen viden:
- "Folketinget har 179 medlemmer"
- "Danmark er et konstitutionelt monarki"

Eksempler på fakta der IKKE er almen viden:
- Meget specifikke juridiske eller tekniske detaljer
- Niche-fagtermer som kun eksperter kender
- Obskure enkeltoplysninger uden bredere relevans

Tekst:
---
{text}
---

Svar udelukkende med en JSON-streng eller null, f.eks.: "Danmark er et monarki" eller null"""

_GENERATE_QA_PROMPT = """\
Du skal generere ét spørgsmål-og-svar-par på dansk baseret på faktaoplysningen herunder.

Fakta: {fact}

Kontekst (kun til reference — må ikke citeres i svaret):
---
{text}
---
{persona_note}
Regler:
- Spørgsmålet skal være ægte åbent — brugeren kender ikke svaret og spørger fordi de vil vide det
- Undgå bekræftelsesspørgsmål: IKKE "var det ikke X?", "er det ikke rigtigt at X?", \
"kan du bekræfte at X?" — det er ikke et vidensøgende spørgsmål
- Spørgsmålet må ikke indeholde svaret eller en tydelig omformulering af det
- Spørgsmålet må gerne have en kort kontekst-sætning som optakt \
("Jeg sad og tænkte på X — hvad er Y?"), men selve spørgsmålet skal være åbent
- Spørgsmålet skal lyde naturligt og uformelt, som noget en rigtig person ville skrive i en chat
- Svaret skal være korrekt, kortfattet og på dansk
- Svaret må ikke referere til "teksten" eller "konteksten"

Svar i præcis dette format:
SPØRGSMÅL: <spørgsmål>
SVAR: <svar>"""


class QAGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config, client)

    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        raise NotImplementedError("QAGenerator uses generate_many directly")

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
        judge: bool = False,
    ) -> list[dict[str, Any]]:
        persona = sample_persona() if self.config.persona_sampling else None
        persona_text = persona_to_prompt(persona) if persona else None

        text = self.config.render_text(row)
        fact = await self._extract_fact(text)
        if not fact:
            return []

        try:
            messages = await self._generate_qa(text, fact, persona_text)
        except ValueError:
            return []

        if not passes_filters(messages, self.config.filters):
            return []

        judge_score: int | None = None
        judge_reason: str | None = None
        if judge:
            from synth_da.filters import judge_sample

            judge_score, judge_reason = await judge_sample(messages, self.client)

        return [
            self._make_sample(
                messages, seed_config, self._get_source_id(row), judge_score, judge_reason
            )
        ]

    async def _extract_fact(self, text: str) -> str | None:
        prompt = _EXTRACT_FACT_PROMPT.format(text=text[:4000])
        raw = await self.client.generate(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        try:
            value = json.loads(raw)
            if isinstance(value, str) and value.strip():
                return value.strip()
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    async def _generate_qa(self, text: str, fact: str, persona_text: str | None) -> list[Message]:
        persona_note = ""
        if persona_text:
            persona_note = (
                f"\nFormulér spørgsmålet som om det stilles af en person med denne profil:\n"
                f"{persona_text}\n"
            )

        prompt = _GENERATE_QA_PROMPT.format(
            fact=fact,
            text=text[:4000],
            persona_note=persona_note,
        )
        raw = await self.client.generate(
            [{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        question, answer = _parse_qa(raw)
        system_msgs = self._maybe_system_prompt(random.choice(_SYSTEM_PROMPTS))
        return system_msgs + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]


def _parse_qa(raw: str) -> tuple[str, str]:
    question = ""
    answer = ""
    for line in raw.splitlines():
        if line.startswith("SPØRGSMÅL:"):
            question = line.removeprefix("SPØRGSMÅL:").strip()
        elif line.startswith("SVAR:"):
            answer = line.removeprefix("SVAR:").strip()
    if not question or not answer:
        raise ValueError(f"Could not parse QA from model output: {raw!r}")
    return question, answer
