"""QA generator — single LLM call: extract general-knowledge fact and generate Q+A."""

from __future__ import annotations

import json
import random
from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters, qa_judge
from synth_da.styles.base import BaseGenerator

_QUESTION_TYPES = ["hvem", "hvad", "hvor", "hvornår", "hvorfor", "hvordan"]

_PROMPT = """\
Find det bedste alment kendte faktum fra teksten der kan besvare et {question_type}-spørgsmål.
Genér et kortfattet, direkte dansk {question_type}-spørgsmål som faktaet besvarer — ingen indledende sætninger eller kontekst.
Faktaet er svaret — det må ikke fremgå af spørgsmålet.
Hvis teksten ikke indeholder et godt {question_type}-faktum, returner null.
Returner som JSON eller null.

{{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915."}}

{text}"""


class QAGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config=config, client=client)

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        text = self.config.render_seed_text(row=row)
        if text is None:
            return []

        result = await self._generate_qa(text=text)
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

    async def _generate_qa(self, text: str) -> tuple[str, str] | None:
        question_type = random.choice(_QUESTION_TYPES)
        prompt = self._fmt(_PROMPT, question_type=question_type, text=text[:4000])
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
