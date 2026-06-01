"""Translation generator — two LLM calls: generate Danish passage, then translate to English."""

from __future__ import annotations

from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters
from synth_da.styles.base import BaseGenerator

_DA_GENERATION_PROMPT = """\
Skriv en naturlig, velskrevet dansk tekst om samme emne som teksten herunder.
Teksten skal:
- Læses som originalt skrevet dansk — ikke som en oversættelse
- Have samme register som kildeteksten (formelt forbliver formelt, hverdagslig forbliver hverdagslig)
- Være 100–200 ord lang

{seed_text}"""

_EN_TRANSLATION_PROMPT = """\
Translate the following Danish text to English.

- Preserve the exact meaning — nothing added, omitted, or distorted
- Preserve the register of the original (formal stays formal, conversational stays conversational)
- Write natural English, not a word-for-word rendering of Danish syntax
- Translate only — add no commentary or explanations

{da_text}"""


class TranslationGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config=config, client=client)

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        seed_text = self.config.render_seed_text(row=row)
        if seed_text is None:
            return []

        da_text = await self._generate_danish(seed_text=seed_text)
        if not da_text or not da_text.strip():
            return []

        if not passes_filters(text=da_text, cfg=self.config.filters):
            return []

        en_text = await self._generate_english(da_text=da_text)
        if not en_text or not en_text.strip():
            return []

        return [
            self._make_record(
                fields={"da": da_text, "en": en_text},
                seed_config=seed_config,
                row=row,
            )
        ]

    async def _generate_danish(self, seed_text: str) -> str:
        prompt = self._fmt(_DA_GENERATION_PROMPT, seed_text=seed_text[:4000])
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

    async def _generate_english(self, da_text: str) -> str:
        prompt = self._fmt(_EN_TRANSLATION_PROMPT, da_text=da_text)
        return await self.client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
