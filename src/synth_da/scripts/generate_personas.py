"""Generate Danish personas from nvidia/Nemotron-Personas-USA."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from datasets import load_dataset
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from synth_da.client import GenerationClient
from synth_da.config import Settings

ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"

DANISH_CITIES = [
    ("København", "1000"),
    ("Aarhus", "8000"),
    ("Odense", "5000"),
    ("Aalborg", "9000"),
    ("Esbjerg", "6700"),
    ("Randers", "8900"),
    ("Kolding", "6000"),
    ("Horsens", "8700"),
    ("Vejle", "7100"),
    ("Roskilde", "4000"),
    ("Herning", "7400"),
    ("Silkeborg", "8600"),
    ("Næstved", "4700"),
    ("Fredericia", "7000"),
    ("Viborg", "8800"),
    ("Køge", "4600"),
    ("Holstebro", "7500"),
    ("Taastrup", "2630"),
    ("Slagelse", "4200"),
    ("Hillerød", "3400"),
]

_TRANSLATE_PROMPT = """\
Oversæt følgende persona-beskrivelse til naturligt dansk. \
Bevar tonen og personligheden. Svar kun med den oversatte tekst, intet andet.

{persona}"""


async def run(n: int, settings: Settings, dry_run: bool = False) -> None:
    client = GenerationClient(settings)

    ds = load_dataset("nvidia/Nemotron-Personas-USA", split="train", token=settings.hf_token)
    rows: list[dict[str, Any]] = random.sample([dict(r) for r in ds], min(n, len(ds)))

    results: list[dict[str, Any]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        MofNCompleteColumn(),
    ) as progress:
        task_id = progress.add_task("Translating personas", total=len(rows))

        import asyncio

        semaphore = asyncio.Semaphore(20)

        async def _translate(row: dict[str, Any]) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    persona_text = str(row.get("persona", ""))
                    translated = await client.generate(
                        [
                            {
                                "role": "user",
                                "content": _TRANSLATE_PROMPT.format(persona=persona_text),
                            }
                        ],
                        temperature=0.7,
                        max_tokens=256,
                    )
                    city, zipcode = random.choice(DANISH_CITIES)
                    return {
                        "uuid": row.get("uuid", ""),
                        "persona": translated,
                        "age": row.get("age"),
                        "sex": row.get("sex"),
                        "occupation": row.get("occupation"),
                        "education_level": row.get("education_level"),
                        "hobbies_and_interests": row.get("hobbies_and_interests"),
                        "city": city,
                        "zipcode": zipcode,
                        "country": "Danmark",
                    }
                except Exception:
                    return None

        translated = await asyncio.gather(*[_translate(r) for r in rows])
        for t in translated:
            if t:
                results.append(t)
            progress.advance(task_id)

    from rich.console import Console

    console = Console()
    console.print(f"[green]✓ Generated {len(results)} Danish personas[/green]")

    if not dry_run:
        # Save locally as fallback
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        out = ASSETS_DIR / "personas.jsonl"
        with out.open("w") as f:
            for p in results:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        console.print(f"[green]✓ Saved locally to {out}[/green]")

        # Push to HuggingFace Hub
        from datasets import Dataset

        hf_dataset = Dataset.from_list(results)
        hf_dataset.push_to_hub(
            "oliverkinch/danish-personas",
            token=settings.hf_token,
        )
        console.print("[green]✓ Pushed to oliverkinch/danish-personas on HuggingFace Hub[/green]")
