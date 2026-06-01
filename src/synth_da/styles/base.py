"""Base generator interface."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig


class BaseGenerator(ABC):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        self.config = config
        self.client = client

    @abstractmethod
    async def generate_many(
        self,
        row: dict[str, Any],
        seed_config: str,
    ) -> list[dict[str, Any]]:
        """Generate zero or more records from one seed row."""
        ...

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
            source_id = str(row.get(self.config.source_id_column, "")) or None
            if source_id is not None:
                record["source_id"] = source_id
        return record
