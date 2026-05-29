"""QA generator."""

from __future__ import annotations

import random
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.styles.base import BaseGenerator

_SYSTEM_PROMPTS = [
    "Du er en hjælpsom assistent. Svar altid på dansk.",
    "Du er en vidende assistent der svarer præcist og kortfattet på dansk.",
    "Besvar brugerens spørgsmål på dansk baseret på den givne tekst.",
]

_QUALITY_CRITERIA = """\
Et højkvalitets QA-eksempel:
- Stiller et naturligt, konkret spørgsmål som en person faktisk ville stille
- Spørgsmålet afslører ikke svaret i sin formulering
- Svaret er korrekt, præcist og direkte — ingen unødvendig omformulering af spørgsmålet
- Svaret er udelukkende baseret på den givne tekst (ved grundet QA)
- Sproget er naturligt dansk
"""


class QAGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config, client)

    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        text = self.config.render_text(row)

        persona_note = ""
        if persona_text:
            persona_note = f"\n\nFormulér spørgsmålet som om det stilles af en person med følgende profil:\n{persona_text}"

        generation_prompt = f"""\
Du skal generere ét højkvalitets spørgsmål-og-svar-par på dansk baseret på teksten herunder.

{_QUALITY_CRITERIA}
{persona_note}

Tekst:
---
{text[:4000]}
---

Svar i præcis dette format:
SPØRGSMÅL: <spørgsmål>
SVAR: <svar>"""

        generation_messages: list[Message] = [
            {"role": "user", "content": generation_prompt},
        ]

        raw = await self.client.generate(generation_messages, temperature=0.9)
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
