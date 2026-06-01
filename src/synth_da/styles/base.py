"""Base generator interface."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.filters import passes_filters
from synth_da.personas import persona_to_prompt, sample_persona


class BaseGenerator(ABC):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        self.config = config
        self.client = client

    @abstractmethod
    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        """Build the generation prompt from a seed row."""
        ...

    def _maybe_system_prompt(self, content: str) -> list[Message]:
        """Return a system message list based on system_prompt_rate."""
        import random

        if random.random() < self.config.system_prompt_rate:
            return [{"role": "system", "content": content}]
        return []

    def _get_source_id(self, row: dict[str, Any]) -> str | None:
        if self.config.source_id_column:
            return str(row.get(self.config.source_id_column, "")) or None
        return None

    def _make_sample(
        self,
        messages: list[Message],
        seed_config: str,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        sample: dict[str, Any] = {
            "messages": messages,
            "run_id": str(uuid.uuid4()),
            "style": self.config.task.value,
            "seed_dataset": self.config.seed_dataset,
            "seed_config": seed_config,
        }
        if source_id is not None:
            sample["source_id"] = source_id
        return sample

    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
        judge: bool = False,
    ) -> list[dict[str, Any]]:
        """Generate zero or more samples from one seed row."""
        result = await self.generate_one(row=row, seed_config=seed_config)
        return [result] if result is not None else []

    async def generate_one(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> dict[str, Any] | None:
        """Generate a single sample from one seed row. Returns None if filtered out."""
        persona = sample_persona() if self.config.persona_sampling else None
        persona_text = persona_to_prompt(persona=persona) if persona else None

        messages = await self.build_prompt(row=row, persona_text=persona_text)

        if not messages or messages[-1]["role"] != "assistant":
            response = await self.client.generate(messages=messages)
            messages = messages + [{"role": "assistant", "content": response}]

        if not passes_filters(messages=messages, cfg=self.config.filters):
            return None

        return self._make_sample(
            messages=messages,
            seed_config=seed_config,
            source_id=self._get_source_id(row=row),
        )
