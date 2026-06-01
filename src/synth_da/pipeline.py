"""Generation pipeline: load seed data, generate samples, push to Hub."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

from datasets import Dataset, load_dataset
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
        return QAGenerator(config=config, client=client)
    if config.task == Task.SUMMARIZATION:
        return SummarizationGenerator(config=config, client=client)
    if config.task == Task.TRANSLATION:
        return TranslationGenerator(config=config, client=client)
    raise ValueError(f"Unknown task: {config.task}")


async def run_pipeline(
    config: DatasetConfig,
    config_path: Path,
    settings: Settings,
    concurrency: int = 20,
    judge: bool = False,
) -> list[dict[str, Any]]:
    client = GenerationClient(settings=settings)
    generator = _make_generator(config=config, client=client)

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
    _logged_errors: set[str] = set()
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
        consecutive_error_batches = 0
        while len(samples) < config.n_samples and row_idx < len(rows) * 10:
            batch_rows = [rows[(row_idx + i) % len(rows)] for i in range(concurrency)]
            row_idx += concurrency

            results = await asyncio.gather(
                *[
                    generator.generate_many(row=row, seed_config=seed_config_str, judge=judge)
                    for row in batch_rows
                ],
                return_exceptions=True,
            )

            batch_had_success = False
            for r in results:
                if isinstance(r, BaseException):
                    errors += 1
                    key = type(r).__name__
                    if key not in _logged_errors:
                        _logged_errors.add(key)
                        from rich.console import Console

                        Console().print(f"[red]Error ({key}): {r}[/red]")
                    continue
                batch_had_success = True
                for sample in r:
                    samples.append(sample)
                    progress.advance(task_id)
                    if len(samples) >= config.n_samples:
                        break

            if batch_had_success:
                consecutive_error_batches = 0
            else:
                consecutive_error_batches += 1
                if consecutive_error_batches >= 5:
                    from rich.console import Console

                    Console().print("[red]5 consecutive all-error batches — aborting.[/red]")
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
    try:
        existing = load_dataset(repo_id, task, split="train", token=settings.hf_token)
        combined = list(existing) + samples
    except Exception:
        combined = samples

    ds = Dataset.from_list(combined)
    ds.push_to_hub(repo_id, config_name=task, token=settings.hf_token)
