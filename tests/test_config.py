"""Tests for config loading and validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from synth_da.config import DatasetConfig, Task, TranslationDirection, load_config

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


def test_qa_config_loads() -> None:
    cfg = load_config(path=CONFIGS_DIR / "qa" / "danish_wikipedia.yaml")
    assert cfg.task == Task.QA
    assert cfg.seed_dataset == "oliverkinch/danish_wikipedia"
    assert cfg.n_samples == 10000
    assert cfg.persona_sampling is True


def test_summarization_config_loads() -> None:
    cfg = load_config(path=CONFIGS_DIR / "summarization" / "eur_lex_sum.yaml")
    assert cfg.task == Task.SUMMARIZATION
    assert cfg.filters.min_assistant_tokens == 50


def test_translation_config_loads() -> None:
    cfg = load_config(path=CONFIGS_DIR / "translation" / "eur_lex_en_da.yaml")
    assert cfg.task == Task.TRANSLATION
    assert cfg.direction == TranslationDirection.EN_TO_DA
    assert cfg.source_column == "en_document"
    assert cfg.target_column == "da_document"
    assert cfg.filters.language_check is True


def test_translation_da_en_skips_language_check() -> None:
    cfg = load_config(path=CONFIGS_DIR / "translation" / "eur_lex_da_en.yaml")
    assert cfg.filters.language_check is False


def test_render_text_template() -> None:
    cfg = DatasetConfig(
        task=Task.QA,
        seed_dataset="test/ds",
        text_template="# {title}\n\n{text}",
        n_samples=10,
    )
    result = cfg.render_text(row={"title": "Min artikel", "text": "Noget indhold."})
    assert result == "# Min artikel\n\nNoget indhold."


def test_render_text_column() -> None:
    cfg = DatasetConfig(
        task=Task.QA,
        seed_dataset="test/ds",
        text_column="text",
        n_samples=10,
    )
    result = cfg.render_text(row={"text": "Hej verden"})
    assert result == "Hej verden"


def test_mutual_exclusion_raises() -> None:
    with pytest.raises(ValidationError):
        DatasetConfig(
            task=Task.QA,
            seed_dataset="test/ds",
            text_column="text",
            text_template="# {title}",
            n_samples=10,
        )


def test_translation_missing_columns_raises() -> None:
    with pytest.raises(ValidationError):
        DatasetConfig(
            task=Task.TRANSLATION,
            seed_dataset="test/ds",
            text_column="text",
            n_samples=10,
        )
