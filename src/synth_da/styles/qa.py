"""QA generator — two-step: extract general-knowledge fact, then generate Q+A."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters
from synth_da.personas import persona_to_prompt, sample_persona
from synth_da.styles.base import BaseGenerator

_EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "qa_examples"

_SYSTEM_PROMPTS = [
    "Du er en hjælpsom assistent. Svar altid på dansk.",
    "Du er en kyndig assistent der svarer præcist og kortfattet på dansk.",
    "Svar på brugerens spørgsmål på dansk.",
]

_EXTRACT_FACT_PROMPT = """\
Find det bedste alment kendte faktum fra teksten. \
Returner som JSON-streng, eller null hvis ingen kvalificerer.

{text}"""

_GENERATE_QA_PROMPT = """\
Fakta: {fact}
{persona_note}
Genér ét naturligt, åbent dansk spørgsmål og svar baseret på faktaet.

SPØRGSMÅL: {example_question}
SVAR: {example_answer}

SPØRGSMÅL: <spørgsmål>
SVAR: <svar>"""


def _load_examples() -> list[dict[str, str]]:
    examples = []
    for path in sorted(_EXAMPLES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        msgs = data.get("messages", [])
        q = next((m["content"] for m in msgs if m["role"] == "user"), None)
        a = next((m["content"] for m in msgs if m["role"] == "assistant"), None)
        if q and a:
            examples.append({"question": q, "answer": a})
    return examples


_EXAMPLES = _load_examples()


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
            messages = await self._generate_qa(fact, persona_text)
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

    async def _generate_qa(self, fact: str, persona_text: str | None) -> list[Message]:
        example = random.choice(_EXAMPLES)
        persona_note = ""
        if persona_text:
            persona_note = (
                f"\nFormulér spørgsmålet som om det stilles af en person med denne profil:\n"
                f"{persona_text}\n"
            )

        prompt = _GENERATE_QA_PROMPT.format(
            fact=fact,
            persona_note=persona_note,
            example_question=example["question"],
            example_answer=example["answer"],
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
