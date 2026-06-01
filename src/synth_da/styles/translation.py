"""Translation generator — produces {da, en} pairs via two LLM calls."""

from __future__ import annotations

from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.styles.base import BaseGenerator


class TranslationGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config=config, client=client)

    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        raise NotImplementedError("TranslationGenerator uses generate_many directly")

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("TranslationGenerator not yet implemented")
