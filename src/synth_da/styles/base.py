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

    def _make_sample(
        self,
        messages: list[Message],
        seed_config: str,
        judge_score: int | None = None,
        judge_reason: str | None = None,
    ) -> dict[str, Any]:
        sample: dict[str, Any] = {
            "messages": messages,
            "run_id": str(uuid.uuid4()),
            "style": self.config.task.value,
            "seed_dataset": self.config.seed_dataset,
            "seed_config": seed_config,
        }
        if judge_score is not None:
            sample["judge_score"] = judge_score
            sample["judge_reason"] = judge_reason
        return sample

    async def generate_one(
        self,
        row: dict[str, Any],
        seed_config: str,
        judge: bool = False,
    ) -> dict[str, Any] | None:
        """Generate a single sample from one seed row. Returns None if filtered out."""
        persona = sample_persona() if self.config.persona_sampling else None
        persona_text = persona_to_prompt(persona) if persona else None

        prompt = await self.build_prompt(row, persona_text)
        response = await self.client.generate(prompt)

        messages = prompt + [{"role": "assistant", "content": response}]

        if not passes_filters(messages, self.config.filters):
            return None

        judge_score: int | None = None
        judge_reason: str | None = None
        if judge:
            from synth_da.filters import judge_sample

            judge_score, judge_reason = await judge_sample(messages, self.client)

        return self._make_sample(messages, seed_config, judge_score, judge_reason)
