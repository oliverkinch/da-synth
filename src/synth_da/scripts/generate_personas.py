"""Generate Danish personas from nvidia/Nemotron-Personas-USA."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Literal

from datasets import load_dataset
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from synth_da.client import GenerationClient
from synth_da.config import Settings

ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"
_NAMES_DIR = ASSETS_DIR / "names"

MIN_AGE = 15


def _read_names(filename: str) -> list[str]:
    return [n for n in (_NAMES_DIR / filename).read_text(encoding="utf-8").splitlines() if n]


_FEMALE_FIRST = _read_names(filename="first_names_female.txt")
_MALE_FIRST = _read_names(filename="first_names_male.txt")
_LAST_NAMES = _read_names(filename="last_names.txt")
_ALL_FIRST = _FEMALE_FIRST + _MALE_FIRST


def _sample_name(sex: str) -> str:
    if sex == "Female":
        first = random.choice(_FEMALE_FIRST)
    elif sex == "Male":
        first = random.choice(_MALE_FIRST)
    else:
        first = random.choice(_ALL_FIRST)
    return f"{first} {random.choice(_LAST_NAMES)}"


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

_GENERATE_PROMPT = """\
Her er en engelsk personaprofil som inspiration:

Alder: {age}
Køn: {sex}
Erhverv: {occupation}
Uddannelse: {education_level}
Personabeskrivelse: {persona}
Hobbyer og interesser: {hobbies}

Generer en komplet dansk personaprofil for {danish_name}, {age} år, bosiddende i \
{city} ({zipcode}), Danmark. Brug den engelske profil som inspiration til personlighedstræk, \
karakter og interesser, men skriv alt som frisk, naturlig dansk tekst med danske kulturelle \
referencer og steder nær {city}.

Sørg for at erhverv og uddannelsesniveau er realistisk konsistente med hinanden.

Svar kun med et JSON-objekt (ingen forklaring, ingen markdown-blokke):
{{
  "persona": "<levende beskrivelse af karakter og personlighed - begynd med {danish_name}>",
  "sex": "<køn på dansk: Mand / Kvinde / Ikke-binær>",
  "occupation": "<erhvervstitel på dansk>",
  "education_level": "<uddannelsesniveau på dansk>",
  "hobbies_and_interests": "<hobbyer og interesser tilpasset {city} og dansk kontekst>"
}}"""


def _parse_json(content: str) -> dict[str, Any]:
    content = content.strip()
    # Strip markdown code fences if the model wraps the output
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    result: dict[str, Any] = json.loads(content)
    return result


async def run(n: int, settings: Settings, dry_run: bool = False, append: bool = False) -> None:
    from rich.console import Console

    console = Console()
    client = GenerationClient(settings=settings)

    existing_uuids: set[str] = set()
    existing_personas: list[dict[str, Any]] = []
    if append:
        out = ASSETS_DIR / "personas.jsonl"
        if out.exists():
            with out.open() as f:
                for line in f:
                    p = json.loads(line)
                    existing_uuids.add(p["uuid"])
                    existing_personas.append(p)
            console.print(f"[blue]Loaded {len(existing_personas)} existing personas[/blue]")

    console.print("[blue]Downloading nvidia/Nemotron-Personas-USA…[/blue]")
    ds = load_dataset("nvidia/Nemotron-Personas-USA", split="train", token=settings.hf_token)
    console.print(f"[green]✓ Loaded {len(ds)} personas - columns: {ds.column_names}[/green]")

    all_rows = [dict(r) for r in ds]
    eligible = [
        r
        for r in all_rows
        if (r.get("age") or 0) >= MIN_AGE and r.get("uuid") not in existing_uuids
    ]
    console.print(f"[green]✓ {len(eligible)} personas with age ≥ {MIN_AGE}[/green]")
    rows = random.sample(eligible, min(n, len(eligible)))

    results: list[dict[str, Any]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        MofNCompleteColumn(),
    ) as progress:
        task_id = progress.add_task("Generating personas", total=len(rows))

        import asyncio

        semaphore = asyncio.Semaphore(20)

        errors: list[str] = []

        async def _generate_fields(
            row: dict[str, Any], danish_name: str, city: str, zipcode: str
        ) -> dict[str, Any]:
            content = await client.generate(
                messages=[
                    {
                        "role": "user",
                        "content": _GENERATE_PROMPT.format(
                            age=row.get("age", "ukendt"),
                            sex=row.get("sex", ""),
                            occupation=row.get("occupation", ""),
                            education_level=row.get("education_level", ""),
                            persona=str(row.get("persona") or row.get("description") or ""),
                            hobbies=str(row.get("hobbies_and_interests") or ""),
                            danish_name=danish_name,
                            city=city,
                            zipcode=zipcode,
                        ),
                    }
                ],
                temperature=0.8,
                max_tokens=1024,
            )
            return _parse_json(content=content)

        async def _generate(row: dict[str, Any]) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    age = row.get("age")
                    raw_sex = str(row.get("sex") or "")
                    city, zipcode = random.choice(DANISH_CITIES)

                    danish_name = _sample_name(sex=raw_sex)
                    fields = await _generate_fields(
                        row=row, danish_name=danish_name, city=city, zipcode=zipcode
                    )

                    return {
                        "uuid": row.get("uuid", ""),
                        "name": danish_name.strip(),
                        "persona": fields.get("persona", ""),
                        "age": age,
                        "sex": fields.get("sex", ""),
                        "occupation": fields.get("occupation", ""),
                        "education_level": fields.get("education_level", ""),
                        "hobbies_and_interests": fields.get("hobbies_and_interests", ""),
                        "city": city,
                        "zipcode": zipcode,
                        "country": "Danmark",
                    }
                except Exception as e:
                    errors.append(str(e))
                    return None

        generated = await asyncio.gather(*[_generate(row=r) for r in rows])
        for g in generated:
            if g:
                results.append(g)
            progress.advance(task_id)

    if errors:
        console.print(f"[red]✗ {len(errors)} errors:[/red]")
        for err in errors[:5]:
            console.print(f"  [red]{err}[/red]")
    if not results:
        console.print("[red]No personas generated - aborting.[/red]")
        return
    console.print(f"[green]✓ Generated {len(results)} Danish personas[/green]")

    if not dry_run:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        out = ASSETS_DIR / "personas.jsonl"
        open_mode: Literal["a", "w"] = "a" if append else "w"
        with out.open(open_mode) as f:
            for p in results:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        console.print(f"[green]✓ Saved locally to {out}[/green]")

        from datasets import Dataset

        all_personas = existing_personas + results if append else results
        hf_dataset = Dataset.from_list(all_personas)
        hf_dataset.push_to_hub(
            "oliverkinch/danish-personas",
            token=settings.hf_token,
        )
        console.print("[green]✓ Pushed to oliverkinch/danish-personas on HuggingFace Hub[/green]")
