"""Configuration models for dataset generation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Task(str, Enum):
    QA = "qa"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"


class FilterConfig(BaseModel):
    min_assistant_tokens: int = 20
    max_repetition_ratio: float = 0.4
    language_check: bool = True


class DatasetConfig(BaseModel):
    task: Task
    seed_dataset: str
    seed_subset: str = "default"
    seed_split: str = "train"

    # Column mapping — single column
    text_column: str | None = None
    # Column mapping — merged columns via template
    text_template: str | None = None

    n_samples: int = 1000
    persona_sampling: bool = False
    max_seed_chars: int | None = None
    source_id_column: str | None = None

    filters: FilterConfig = Field(default_factory=FilterConfig)

    @model_validator(mode="after")
    def validate_column_mapping(self) -> DatasetConfig:
        if self.text_column is None and self.text_template is None:
            raise ValueError("Dataset configs require text_column or text_template")
        if self.text_column and self.text_template:
            raise ValueError("Specify either text_column or text_template, not both")
        return self

    def render_text(self, row: dict[str, Any]) -> str:
        """Render seed text from a dataset row using the column mapping."""
        if self.text_template:
            return self.text_template.format(**{k: (v or "") for k, v in row.items()})
        if self.text_column:
            return str(row.get(self.text_column) or "")
        raise ValueError("No text column mapping configured")

    def render_seed_text(self, row: dict[str, Any]) -> str | None:
        """Render and validate seed text; return None if the row should be skipped."""
        text = self.render_text(row=row)
        if not text or not text.strip():
            return None
        if self.max_seed_chars and len(text) > self.max_seed_chars:
            return None
        return text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_base_url: str = "https://inference.alexandra.dk/v1"
    openai_api_key: str = "placeholder"
    openai_model_name: str = "qwen3.5-397b"
    hf_token: str | None = None


def load_config(path: Path) -> DatasetConfig:
    with path.open() as f:
        data = yaml.safe_load(f)
    return DatasetConfig(**data)
