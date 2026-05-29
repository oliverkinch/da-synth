"""Generation pipeline: load seed data, generate samples, push to Hub."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

from datasets import Dataset, load_dataset
from huggingface_hub import HfApi
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig, Settings, Task
from synth_da.styles.base import BaseGenerator
from synth_da.styles.qa import QAGenerator
from synth_da.styles.summarization import SummarizationGenerator
from synth_da.styles.translation import TranslationGenerator

HF_REPO = "oliverkinch/danish-sft"


def _make_generator(config: DatasetConfig, client: GenerationClient) -> BaseGenerator:
    if config.task == Task.QA:
        return QAGenerator(config, client)
    if config.task == Task.SUMMARIZATION:
        return SummarizationGenerator(config, client)
    if config.task == Task.TRANSLATION:
        return TranslationGenerator(config, client)
    raise ValueError(f"Unknown task: {config.task}")


async def run_pipeline(
    config: DatasetConfig,
    config_path: Path,
    settings: Settings,
    concurrency: int = 20,
    judge: bool = False,
) -> list[dict[str, Any]]:
    client = GenerationClient(settings)
    generator = _make_generator(config, client)

    ds = load_dataset(
        config.seed_dataset,
        config.seed_subset,
        split=config.seed_split,
        token=settings.hf_token,
    )

    rows = list(ds)
    random.shuffle(rows)

    samples: list[dict[str, Any]] = []
    errors = 0
    seed_config_str = str(config_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=False,
    ) as progress:
        task_id = progress.add_task(
            f"[cyan]{config.task.value} / {config.seed_dataset}",
            total=config.n_samples,
        )

        row_idx = 0
        while len(samples) < config.n_samples and row_idx < len(rows) * 10:
            batch_rows = [rows[row_idx % len(rows)] for _ in range(concurrency)]
            row_idx += concurrency

            results = await asyncio.gather(
                *[
                    generator.generate_one(row, seed_config_str, judge=judge)
                    for row in batch_rows
                ],
                return_exceptions=True,
            )

            for r in results:
                if isinstance(r, Exception):
                    errors += 1
                    continue
                if r is None:
                    continue
                samples.append(r)
                progress.advance(task_id)
                if len(samples) >= config.n_samples:
                    break

    if errors:
        from rich.console import Console
        Console().print(f"[yellow]⚠ {errors} generation errors (skipped)[/yellow]")

    return samples[: config.n_samples]


def push_to_hub(
    samples: list[dict[str, Any]],
    task: str,
    settings: Settings,
    repo_id: str = HF_REPO,
) -> None:
    """Append samples to the Hub dataset subset for this task."""
    api = HfApi(token=settings.hf_token)

    try:
        existing = load_dataset(repo_id, task, split="train", token=settings.hf_token)
        combined = list(existing) + samples
    except Exception:
        combined = samples

    ds = Dataset.from_list(combined)
    ds.push_to_hub(repo_id, config_name=task, token=settings.hf_token)
