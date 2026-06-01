"""Summarization generator — two LLM calls: generate document, then summarize it."""

from __future__ import annotations

from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters
from synth_da.styles.base import BaseGenerator

_DOCUMENT_PROMPT = """\
Skriv en naturlig, velskrevet dansk tekst om samme emne som teksten herunder.
Teksten skal læses som originalt skrevet dansk — ikke som en oversættelse eller omskrivning.
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


class SummarizationGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config=config, client=client)

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        seed_text = self.config.render_text(row=row)
        if not seed_text or not seed_text.strip():
            return []
        if self.config.max_seed_chars and len(seed_text) > self.config.max_seed_chars:
            return []

        document = await self._generate_document(seed_text=seed_text)
        if not document or not document.strip():
            return []

        summary = await self._generate_summary(document=document)
        if not summary or not summary.strip():
            return []

        if not passes_filters(text=summary, cfg=self.config.filters):
            return []

        return [
            self._make_record(
                fields={"document": document, "summary": summary},
                seed_config=seed_config,
                source_id=self._get_source_id(row=row),
            )
        ]

    async def _generate_document(self, seed_text: str) -> str:
        safe_seed = seed_text.replace("{", "{{").replace("}", "}}")
        prompt = _DOCUMENT_PROMPT.format(seed_text=safe_seed)
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

    async def _generate_summary(self, document: str) -> str:
        safe_doc = document.replace("{", "{{").replace("}", "}}")
        prompt = _SUMMARY_PROMPT.format(document=safe_doc)
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
