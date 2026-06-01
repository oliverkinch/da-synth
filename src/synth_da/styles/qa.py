"""QA generator - single LLM call: extract up to 3 facts and generate Q+A pairs."""

from __future__ import annotations

import json
from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters
from synth_da.styles.base import BaseGenerator

_PROMPT = """\
Find op til 3 gode, indbyrdes forskellige fakta fra teksten der egner sig til et vidensbaseret datasæt.
Genér et direkte dansk spørgsmål per faktum - ingen indledende sætninger eller kontekst.
Faktaet er svaret - det må ikke fremgå af spørgsmålet.
Svaret skal direkte og præcist besvare spørgsmålet.
Returner som JSON-liste eller null.

[{{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915."}}, \
{{"question": "Hvem var statsminister da kvinder fik stemmeret i Danmark?", "answer": "Carl Theodor Zahle."}}]

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

        pairs = await self._generate_qa(text=text)

        records = []
        for question, answer in pairs:
            if not passes_filters(text=answer, cfg=self.config.filters):
                continue
            records.append(
                self._make_record(
                    fields={"question": question, "answer": answer},
                    seed_config=seed_config,
                    row=row,
                )
            )
        return records

    async def _generate_qa(self, text: str) -> list[tuple[str, str]]:
        prompt = self._fmt(_PROMPT, text=text[:4000])
        raw = await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

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
            question = (item.get("question") or "").strip()
            answer = (item.get("answer") or "").strip()
            if question and answer:
                pairs.append((question, answer))
        return pairs
