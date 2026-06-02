"""Base generator interface."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig


class BaseGenerator(ABC):
    def __init__(
        self,
        config: DatasetConfig,
        client: GenerationClient,
        on_verdict: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.stats: Counter[str] = Counter()
        self.on_verdict = on_verdict

    @abstractmethod
    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        """Generate zero or more records from one seed row."""
        ...

    def stats_rows(self) -> list[tuple[str, int]]:
        """Return labelled rows for the post-run stats display. Override in subclasses."""
        return []

    @staticmethod
    def _fmt(template: str, **kwargs: str) -> str:
        """Format a prompt template, escaping braces in all substituted values."""
        return template.format(
            **{k: v.replace("{", "{{").replace("}", "}}") for k, v in kwargs.items()}
        )

    def _make_record(
        self,
        fields: dict[str, Any],
        seed_config: str,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            **fields,
            "run_id": str(uuid.uuid4()),
            "seed_dataset": self.config.seed_dataset,
            "seed_config": seed_config,
        }
        if self.config.source_id_column:
            source_id = row.get(self.config.source_id_column)
            if source_id:
                record["source_id"] = str(source_id)
        return record
