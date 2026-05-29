"""Configuration models for dataset generation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Task(str, Enum):
    QA = "qa"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"


class TranslationDirection(str, Enum):
    EN_TO_DA = "en->da"
    DA_TO_EN = "da->en"


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
    # Column mapping — translation only
    source_column: str | None = None
    target_column: str | None = None
    direction: TranslationDirection | None = None

    n_samples: int = 1000
    persona_sampling: bool = True
    system_prompt_rate: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5

    filters: FilterConfig = Field(default_factory=FilterConfig)

    @model_validator(mode="after")
    def validate_column_mapping(self) -> DatasetConfig:
        if self.task == Task.TRANSLATION:
            if not self.source_column or not self.target_column:
                raise ValueError("Translation configs require source_column and target_column")
            if not self.direction:
                raise ValueError("Translation configs require direction")
        else:
            if self.text_column is None and self.text_template is None:
                raise ValueError("Non-translation configs require text_column or text_template")
            if self.text_column and self.text_template:
                raise ValueError("Specify either text_column or text_template, not both")
        return self

    def render_text(self, row: dict[str, str]) -> str:
        """Render seed text from a dataset row using the column mapping."""
        if self.text_template:
            return self.text_template.format(**row)
        if self.text_column:
            return row[self.text_column]
        raise ValueError("No text column mapping configured")


class Settings(BaseSettings):  # type: ignore[misc]
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_base_url: str = "https://inference.alexandra.dk/v1"
    openai_api_key: str = "placeholder"
    openai_model_name: str = "qwen3.5-397b"
    hf_token: str | None = None


def load_config(path: Path) -> DatasetConfig:
    with path.open() as f:
        data = yaml.safe_load(f)
    return DatasetConfig(**data)
