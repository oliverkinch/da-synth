"""Translation generator."""

from __future__ import annotations

import random
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig, TranslationDirection
from synth_da.styles.base import BaseGenerator

_EN_TO_DA_REQUESTS = [
    "Oversæt følgende tekst fra engelsk til dansk:",
    "Kan du oversætte denne engelske tekst til dansk?",
    "Oversæt venligst til dansk:",
]

_DA_TO_EN_REQUESTS = [
    "Please translate the following Danish text to English:",
    "Can you translate this text from Danish to English?",
    "Translate the following to English:",
]

_QUALITY_CRITERIA_EN_DA = """\
En højkvalitets oversættelse (EN→DA):
- Bevarer den præcise betydning — ingenting tilføjes eller udelades
- Bevarer registret: formelt → formelt dansk; hverdagslig → hverdagslig dansk
- Undgår kalkering — oversættes til naturligt dansk, ikke ord-for-ord
- Bruger etablerede danske fagudtryk (juridiske, akademiske osv.)
- Korrekt dansk ortografi (æ, ø, å), ingen store bogstaver i substantiver
"""

_QUALITY_CRITERIA_DA_EN = """\
A high-quality translation (DA→EN):
- Preserves the exact meaning — nothing added or omitted
- Preserves register: formal → formal English; casual → casual English
- Reads as text originally written in English, not calqued from Danish
- Uses established English terminology for domain-specific terms
"""


class TranslationGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config, client)
        assert config.direction is not None
        assert config.source_column is not None
        assert config.target_column is not None
        self.direction = config.direction

    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        assert self.config.source_column and self.config.target_column
        source_text = str(row[self.config.source_column])[:3000]

        if self.direction == TranslationDirection.EN_TO_DA:
            request = random.choice(_EN_TO_DA_REQUESTS)
            criteria = _QUALITY_CRITERIA_EN_DA
            user_content = f"{request}\n\n---\n\n{source_text}"
            system_content = "Du er en præcis oversætter. Oversæt udelukkende teksten — tilføj ingen kommentarer."
        else:
            request = random.choice(_DA_TO_EN_REQUESTS)
            criteria = _QUALITY_CRITERIA_DA_EN
            user_content = f"{request}\n\n---\n\n{source_text}"
            system_content = "You are a precise translator. Translate only the text — add no commentary."

        # For translation we use the gold target directly when available,
        # otherwise generate via the model. Here we generate to produce
        # diverse request phrasings around real parallel pairs.
        target_text = str(row.get(self.config.target_column, ""))

        if target_text:
            # We have a gold translation — use it directly
            system_msgs = self._maybe_system_prompt(system_content)
            return system_msgs + [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": target_text},
            ]

        # No gold translation — generate one
        gen_prompt: list[Message] = [
            {"role": "system", "content": system_content + f"\n\n{criteria}"},
            {"role": "user", "content": user_content},
        ]
        translation = await self.client.generate(gen_prompt, temperature=0.3)

        system_msgs = self._maybe_system_prompt(system_content)
        return system_msgs + [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": translation},
        ]
