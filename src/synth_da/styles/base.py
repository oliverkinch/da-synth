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

    def _get_source_id(self, row: dict[str, Any]) -> str | None:
        if self.config.source_id_column:
            return str(row.get(self.config.source_id_column, "")) or None
        return None

    def _make_record(
        self,
        fields: dict[str, Any],
        seed_config: str,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            **fields,
            "run_id": str(uuid.uuid4()),
            "seed_dataset": self.config.seed_dataset,
            "seed_config": seed_config,
        }
        if source_id is not None:
            record["source_id"] = source_id
        return record
