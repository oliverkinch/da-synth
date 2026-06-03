"""Generation pipeline: load seed data, generate samples, push to Hub."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from datasets import Dataset, load_dataset
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from synth_da.client import GenerationClient
from synth_da.config import DatasetConfig, Settings, Task
from synth_da.styles.base import BaseGenerator
from synth_da.styles.qa import QAGenerator
from synth_da.styles.summarization import SummarizationGenerator
from synth_da.styles.translation import TranslationGenerator

_HF_REPOS: dict[Task, str] = {
    Task.QA: "oliverkinch/danish-qa",
    Task.SUMMARIZATION: "oliverkinch/danish-summarization",
    Task.TRANSLATION: "oliverkinch/danish-translation",
}


def _make_generator(
    config: DatasetConfig,
    client: GenerationClient,
    on_verdict: Callable[[dict[str, Any]], None] | None = None,
) -> BaseGenerator:
    if config.task == Task.QA:
        return QAGenerator(config=config, client=client, on_verdict=on_verdict)
    if config.task == Task.SUMMARIZATION:
        return SummarizationGenerator(config=config, client=client, on_verdict=on_verdict)
    if config.task == Task.TRANSLATION:
        return TranslationGenerator(config=config, client=client, on_verdict=on_verdict)
    raise ValueError(f"Unknown task: {config.task}")


_console = Console()


async def run_pipeline(
    config: DatasetConfig,
    config_path: Path,
    settings: Settings,
    concurrency: int = 20,
    seen_ids: set[str] | None = None,
    on_sample: Callable[[dict[str, Any]], None] | None = None,
    on_verdict: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    client = GenerationClient(settings=settings)
    generator = _make_generator(config=config, client=client, on_verdict=on_verdict)

    ds = load_dataset(
        config.seed_dataset,
        config.seed_subset,
        split=config.seed_split,
        token=settings.hf_token,
    )

    all_rows = list(ds)
    if seen_ids is not None and config.source_id_column:
        rows = [r for r in all_rows if str(r.get(config.source_id_column, "")) not in seen_ids]
    else:
        rows = all_rows
    random.shuffle(rows)

    if not rows:
        _console.print("[yellow]No unseen rows after deduplication - nothing to generate.[/yellow]")
        return []

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
        while (config.n_samples is None or len(samples) < config.n_samples) and row_idx < len(rows):
            batch_rows = [rows[(row_idx + i) % len(rows)] for i in range(concurrency)]
            row_idx += concurrency

            results = await asyncio.gather(
                *[
                    generator.generate_many(row=row, seed_config=seed_config_str)
                    for row in batch_rows
                ],
                return_exceptions=True,
            )

            batch_had_success = False
            for r in results:
                if isinstance(r, Exception):
                    errors += 1
                    key = type(r).__name__
                    if key not in _logged_errors:
                        _logged_errors.add(key)
                        _console.print(f"[red]Error ({key}): {r}[/red]")
                    continue
                if isinstance(r, BaseException):
                    raise r
                for sample in r:
                    batch_had_success = True
                    samples.append(sample)
                    if on_sample is not None:
                        on_sample(sample)
                    progress.advance(task_id)
                    if config.n_samples is not None and len(samples) >= config.n_samples:
                        break
                if config.n_samples is not None and len(samples) >= config.n_samples:
                    break

            if batch_had_success:
                consecutive_error_batches = 0
            else:
                consecutive_error_batches += 1
                if consecutive_error_batches >= 5:
                    _console.print("[red]5 consecutive all-error batches - aborting.[/red]")
                    break

    if errors:
        _console.print(f"[yellow]⚠ {errors} generation errors (skipped)[/yellow]")

    if rows := generator.stats_rows():
        table = Table(title="Filter funnel", show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold")
        table.add_column(justify="right")
        for label, value in rows:
            table.add_row(label, str(value))
        _console.print(table)

    return samples if config.n_samples is None else samples[: config.n_samples]


def push_to_hub(
    records: list[dict[str, Any]],
    task: Task,
    settings: Settings,
) -> None:
    """Append records to the Hub dataset for this task type."""
    from datasets.exceptions import DatasetNotFoundError

    repo_id = _HF_REPOS[task]
    try:
        existing = load_dataset(repo_id, split="train", token=settings.hf_token)
        combined = list(existing) + records
    except DatasetNotFoundError:
        combined = records

    ds = Dataset.from_list(combined)
    ds.push_to_hub(repo_id, token=settings.hf_token)
