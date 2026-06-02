"""CLI entrypoint for synth-da."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from synth_da.config import Settings, load_config

app = typer.Typer(
    name="synth-da",
    help="Synthetic Danish instruction finetuning data generator.",
    add_completion=False,
)
console = Console()


def _load_settings() -> Settings:
    return Settings()  # reads .env automatically


@app.command()
def generate(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to a single dataset config YAML."),
    ] = None,
    dataset_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Run all configs for this dataset type (e.g. qa)."),
    ] = None,
    concurrency: Annotated[int, typer.Option(help="Number of concurrent LLM requests.")] = 20,
    dry_run: Annotated[bool, typer.Option(help="Generate but do not push to Hub.")] = False,
    n_samples: Annotated[
        int | None,
        typer.Option("--n-samples", "-n", help="Override n_samples from config."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write samples to a JSONL file instead of pushing to Hub (implies --dry-run).",
        ),
    ] = None,
) -> None:
    """Generate synthetic Danish instruction data and push to HuggingFace Hub."""
    if config is None and dataset_type is None:
        console.print("[red]Specify --config or --type.[/red]")
        raise typer.Exit(1)
    if config is not None and dataset_type is not None:
        console.print("[red]Specify either --config or --type, not both.[/red]")
        raise typer.Exit(1)

    configs_dir = Path(__file__).parent.parent.parent / "configs"

    config_paths: list[Path] = []
    if config:
        config_paths = [config]
    elif dataset_type:
        type_dir = configs_dir / dataset_type
        if not type_dir.exists():
            console.print(
                f"[red]No configs directory found for dataset type '{dataset_type}'.[/red]"
            )
            raise typer.Exit(1)
        config_paths = sorted(type_dir.glob("*.yaml"))
        if not config_paths:
            console.print(f"[yellow]No YAML configs found in {type_dir}[/yellow]")
            raise typer.Exit(0)

    settings = _load_settings()

    for cfg_path in config_paths:
        console.rule(f"[bold]{cfg_path.stem}")
        cfg = load_config(path=cfg_path)
        if n_samples is not None:
            cfg = cfg.model_copy(update={"n_samples": n_samples})

        from synth_da.pipeline import push_to_hub, run_pipeline

        seen_ids: set[str] = set()
        if output and output.exists():
            with output.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        sid = json.loads(line).get("source_id")
                        if sid:
                            seen_ids.add(sid)
                    except json.JSONDecodeError:
                        pass

        out_file = output.open("a", encoding="utf-8") if output is not None else None
        verdicts_path = output.with_stem(output.stem + "_verdicts") if output is not None else None
        verdicts_file = (
            verdicts_path.open("a", encoding="utf-8") if verdicts_path is not None else None
        )

        def _write_sample(s: dict[str, Any], _f: Any = out_file) -> None:
            if _f is not None:
                _f.write(json.dumps(s, ensure_ascii=False) + "\n")
                _f.flush()

        def _write_verdict(v: dict[str, Any], _f: Any = verdicts_file) -> None:
            if _f is not None:
                _f.write(json.dumps(v, ensure_ascii=False) + "\n")
                _f.flush()

        on_sample: Callable[[dict[str, Any]], None] | None = (
            _write_sample if out_file is not None else None
        )
        on_verdict: Callable[[dict[str, Any]], None] | None = (
            _write_verdict if verdicts_file is not None else None
        )

        try:
            samples = asyncio.run(
                run_pipeline(
                    config=cfg,
                    config_path=cfg_path,
                    settings=settings,
                    concurrency=concurrency,
                    seen_ids=seen_ids,
                    on_sample=on_sample,
                    on_verdict=on_verdict,
                )
            )
        finally:
            if out_file is not None:
                out_file.close()
            if verdicts_file is not None:
                verdicts_file.close()

        console.print(f"[green]✓ Generated {len(samples)} samples[/green]")

        if output is not None:
            console.print(f"[green]✓ Appended {len(samples)} samples to {output}[/green]")
            if verdicts_path is not None:
                console.print(f"[green]✓ Verdicts written to {verdicts_path}[/green]")
        elif not dry_run:
            push_to_hub(records=samples, task=cfg.task, settings=settings)
            console.print(f"[green]✓ Pushed to Hub - subset: {cfg.task.value}[/green]")
        else:
            console.print("[yellow]Dry run - skipping Hub push.[/yellow]")


@app.command()
def generate_personas(
    n: Annotated[int, typer.Option(help="Number of personas to generate.")] = 5000,
    dry_run: Annotated[bool, typer.Option(help="Print personas but do not save.")] = False,
    append: Annotated[
        bool, typer.Option(help="Append to existing personas.jsonl instead of overwriting.")
    ] = False,
) -> None:
    """Generate Danish personas from nvidia/Nemotron-Personas-USA and save to assets/personas.jsonl."""
    from synth_da.scripts.generate_personas import run

    asyncio.run(run(n=n, settings=_load_settings(), dry_run=dry_run, append=append))


if __name__ == "__main__":
    app()
