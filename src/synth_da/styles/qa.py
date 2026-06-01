"""QA generator — single LLM call: extract general-knowledge fact and generate Q+A."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters, qa_judge
from synth_da.personas import sample_persona
from synth_da.styles.base import BaseGenerator

_SYSTEM_PROMPTS_PATH = (
    Path(__file__).parent.parent.parent.parent / "assets" / "system_prompts" / "qa.txt"
)
_SYSTEM_PROMPTS = [
    line.strip()
    for line in _SYSTEM_PROMPTS_PATH.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

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

    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        raise NotImplementedError("QAGenerator uses generate_many directly")

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        persona = sample_persona() if self.config.persona_sampling else None

        text = self.config.render_text(row=row)
        messages = await self._generate_qa(text=text, persona=persona)
        if messages is None:
            return []

        if not passes_filters(messages=messages, cfg=self.config.filters):
            return []

        if not await qa_judge(messages=messages, client=self.client):
            return []

        return [
            self._make_sample(
                messages=messages,
                seed_config=seed_config,
                source_id=self._get_source_id(row=row),
            )
        ]

    async def _generate_qa(self, text: str, persona: dict[str, Any] | None) -> list[Message] | None:
        persona_note = _build_persona_note(persona) if persona else ""

        safe_text = text[:4000].replace("{", "{{").replace("}", "}}")
        safe_persona = persona_note.replace("{", "{{").replace("}", "}}")
        prompt = _PROMPT.format(persona_note=safe_persona, text=safe_text)
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

        system_msgs = self._maybe_system_prompt(content=random.choice(_SYSTEM_PROMPTS))
        return system_msgs + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
