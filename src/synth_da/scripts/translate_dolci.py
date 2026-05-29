"""Translate a subset of allenai/Dolci-Instruct-SFT to Danish."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from datasets import Dataset, load_dataset
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from synth_da.client import GenerationClient, Message
from synth_da.config import Settings
from synth_da.filters import is_danish, passes_filters
from synth_da.config import FilterConfig

# Subsets to skip — verifiable format constraints break on translation
_SKIP_SOURCE_PATTERNS = ("Precise IF", "precise_if")

_SYSTEM_PROMPT = (
    "Du er en præcis oversætter. Oversæt hele samtalen til naturligt dansk. "
    "Bevar roller (user/assistant) og formatering. Svar kun med den oversatte samtale."
)


def _should_skip(row: dict[str, Any]) -> bool:
    source = str(row.get("source_dataset", ""))
    return any(p in source for p in _SKIP_SOURCE_PATTERNS)


def _messages_to_text(messages: list[dict[str, Any]]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if role in ("user", "assistant"):
            parts.append(f"{role.upper()}: {content}")
    return "\n\n".join(parts)


def _parse_translated(raw: str, original: list[dict[str, Any]]) -> list[Message]:
    """Parse translated messages back into the messages format."""
    result: list[Message] = []
    lines = raw.strip().splitlines()
    current_role: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_role and current_lines:
            result.append({"role": current_role, "content": "\n".join(current_lines).strip()})

    for line in lines:
        if line.startswith("USER:"):
            flush()
            current_role = "user"
            current_lines = [line.removeprefix("USER:").strip()]
        elif line.startswith("ASSISTANT:"):
            flush()
            current_role = "assistant"
            current_lines = [line.removeprefix("ASSISTANT:").strip()]
        elif current_role:
            current_lines.append(line)

    flush()

    # Fallback: if parsing failed, return original structure with translated content
    if not result:
        return [{"role": m["role"], "content": m.get("content") or ""} for m in original
                if m["role"] in ("user", "assistant")]
    return result


async def run(n: int, settings: Settings, concurrency: int = 20, dry_run: bool = False) -> None:
    from rich.console import Console
    console = Console()

    client = GenerationClient(settings)

    ds = load_dataset("allenai/Dolci-Instruct-SFT", split="train", token=settings.hf_token)
    rows: list[dict[str, Any]] = [r for r in ds if not _should_skip(r)]  # type: ignore[union-attr]
    random.shuffle(rows)
    rows = rows[:n]

    console.print(f"[blue]Translating {len(rows)} samples from Dolci-Instruct-SFT[/blue]")

    results: list[dict[str, Any]] = []
    errors = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def _translate(row: dict[str, Any]) -> dict[str, Any] | None:
        async with semaphore:
            try:
                messages: list[dict[str, Any]] = row.get("messages") or []
                # Skip if already contains Danish (Aya subset)
                first_content = next(
                    (m.get("content") for m in messages if m.get("role") == "user"), ""
                ) or ""
                if is_danish(first_content):
                    return {
                        "messages": [
                            {"role": m["role"], "content": m.get("content") or ""}
                            for m in messages if m["role"] in ("user", "assistant")
                        ],
                        "source_dataset": row.get("source_dataset", ""),
                        "domain": row.get("domain", ""),
                        "translated": False,
                    }

                text = _messages_to_text(messages)
                translated_raw = await client.generate(
                    [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.3,
                    max_tokens=4096,
                )
                translated_msgs = _parse_translated(translated_raw, messages)

                filter_cfg = FilterConfig(language_check=True, min_assistant_tokens=10)
                if not passes_filters(translated_msgs, filter_cfg):
                    return None

                return {
                    "messages": translated_msgs,
                    "source_dataset": row.get("source_dataset", ""),
                    "domain": row.get("domain", ""),
                    "translated": True,
                }
            except Exception:
                return None

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        MofNCompleteColumn(),
    ) as progress:
        task_id = progress.add_task("Translating Dolci", total=len(rows))
        translated = await asyncio.gather(*[_translate(r) for r in rows])
        for t in translated:
            progress.advance(task_id)
            if t is None:
                errors += 1
            else:
                results.append(t)

    console.print(f"[green]✓ Translated {len(results)} samples ({errors} skipped)[/green]")

    if not dry_run:
        from synth_da.pipeline import HF_REPO, push_to_hub
        from synth_da.config import Task
        # Push as a separate "translated" subset
        ds_out = Dataset.from_list(results)
        ds_out.push_to_hub(HF_REPO, config_name="translated", token=settings.hf_token)
        console.print("[green]✓ Pushed to Hub — subset: translated[/green]")
