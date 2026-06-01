"""QA generator — single LLM call: extract general-knowledge fact and generate Q+A."""

from __future__ import annotations

import json
from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters, qa_judge
from synth_da.personas import sample_persona
from synth_da.styles.base import BaseGenerator

_PROMPT = """\
Find det bedste alment kendte faktum fra teksten.
{persona_note}Genér et naturligt, åbent dansk spørgsmål som faktaet besvarer.
Faktaet er svaret — det må ikke fremgå af spørgsmålet.
Returner som JSON eller null.

{{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915."}}

{text}"""


def _build_persona_note(persona: dict[str, Any]) -> str:
    parts = []
    if age := persona.get("age"):
        parts.append(f"{age} år")
    desc = str(persona.get("persona", "")).strip()
    header = f"[{', '.join(parts)}]" if parts else ""
    profile = f"{header} {desc}".strip() if header else desc
    return (
        f"Lad personaprofilen påvirke spørgsmålets tone og register"
        f" — nævn ikke personaen eksplicit.\n{profile}\n"
    )


class QAGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config=config, client=client)

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        persona = sample_persona() if self.config.persona_sampling else None

        text = self.config.render_seed_text(row=row)
        if text is None:
            return []

        result = await self._generate_qa(text=text, persona=persona)
        if result is None:
            return []

        question, answer = result

        if not passes_filters(text=answer, cfg=self.config.filters):
            return []

        if not await qa_judge(question=question, answer=answer, client=self.client):
            return []

        return [
            self._make_record(
                fields={"question": question, "answer": answer},
                seed_config=seed_config,
                row=row,
            )
        ]

    async def _generate_qa(
        self, text: str, persona: dict[str, Any] | None
    ) -> tuple[str, str] | None:
        persona_note = _build_persona_note(persona=persona) if persona else ""
        prompt = self._fmt(_PROMPT, persona_note=persona_note, text=text[:4000])
        raw = await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(value, dict):
            return None

        question = value.get("question", "").strip()
        answer = value.get("answer", "").strip()
        if not question or not answer:
            return None

        return question, answer
