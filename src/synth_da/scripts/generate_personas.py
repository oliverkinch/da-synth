"""Generate Danish personas from nvidia/Nemotron-Personas-USA."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from datasets import load_dataset
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from synth_da.client import GenerationClient
from synth_da.config import Settings

ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"

MIN_AGE = 15

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

_FEMALE_NAMES = [
    "Anne",
    "Mette",
    "Kirsten",
    "Hanne",
    "Anna",
    "Helle",
    "Maria",
    "Susanne",
    "Lene",
    "Marianne",
    "Camilla",
    "Lone",
    "Louise",
    "Charlotte",
    "Pia",
    "Tina",
    "Emma",
    "Ida",
    "Gitte",
    "Julie",
]
_MALE_NAMES = [
    "Peter",
    "Michael",
    "Lars",
    "Thomas",
    "Jens",
    "Henrik",
    "Søren",
    "Christian",
    "Martin",
    "Jan",
    "Morten",
    "Jesper",
    "Anders",
    "Mads",
    "Niels",
    "Rasmus",
    "Mikkel",
    "Kim",
    "Per",
    "Ole",
]
_LAST_NAMES = [
    "Nielsen",
    "Jensen",
    "Hansen",
    "Andersen",
    "Pedersen",
    "Christensen",
    "Larsen",
    "Sørensen",
    "Rasmussen",
    "Jørgensen",
    "Petersen",
    "Madsen",
    "Kristensen",
    "Olsen",
    "Thomsen",
    "Christiansen",
    "Poulsen",
    "Johansen",
    "Møller",
    "Mortensen",
]

_NAME_PROMPT = """\
Opfind ét realistisk dansk navn til en person med køn: {sex}.

Eksempler på danske navne:
{examples}

Svar kun med fuldt navn (fornavn + efternavn), intet andet."""

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

Svar kun med et JSON-objekt (ingen forklaring, ingen markdown-blokke):
{{
  "persona": "<levende beskrivelse af karakter og personlighed — begynd med {danish_name}>",
  "sex": "<køn på dansk: Mand / Kvinde / Ikke-binær>",
  "occupation": "<erhvervstitel på dansk>",
  "education_level": "<uddannelsesniveau på dansk>",
  "hobbies_and_interests": "<hobbyer og interesser tilpasset {city} og dansk kontekst>"
}}"""


def _name_examples(sex: str) -> str:
    first_pool = _FEMALE_NAMES if sex == "Female" else _MALE_NAMES
    firsts = random.sample(first_pool, 5)
    lasts = random.sample(_LAST_NAMES, 5)
    return "\n".join(f"{first} {last}" for first, last in zip(firsts, lasts, strict=False))


def _parse_json(content: str) -> dict[str, Any]:
    content = content.strip()
    # Strip markdown code fences if the model wraps the output
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    result: dict[str, Any] = json.loads(content)
    return result


async def run(n: int, settings: Settings, dry_run: bool = False) -> None:
    from rich.console import Console

    console = Console()
    client = GenerationClient(settings)

    console.print("[blue]Downloading nvidia/Nemotron-Personas-USA…[/blue]")
    ds = load_dataset("nvidia/Nemotron-Personas-USA", split="train", token=settings.hf_token)
    console.print(f"[green]✓ Loaded {len(ds)} personas — columns: {ds.column_names}[/green]")

    all_rows = [dict(r) for r in ds]
    eligible = [r for r in all_rows if (r.get("age") or 0) >= MIN_AGE]
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

        async def _generate_name(sex: str) -> str:
            return await client.generate(
                [
                    {
                        "role": "user",
                        "content": _NAME_PROMPT.format(sex=sex, examples=_name_examples(sex)),
                    }
                ],
                temperature=0.9,
                max_tokens=16,
            )

        async def _generate_fields(
            row: dict[str, Any], danish_name: str, city: str, zipcode: str
        ) -> dict[str, Any]:
            content = await client.generate(
                [
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
            return _parse_json(content)

        async def _generate(row: dict[str, Any]) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    age = row.get("age")
                    raw_sex = str(row.get("sex") or "")
                    city, zipcode = random.choice(DANISH_CITIES)

                    danish_name = await _generate_name(raw_sex)
                    fields = await _generate_fields(row, danish_name, city, zipcode)

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

        generated = await asyncio.gather(*[_generate(r) for r in rows])
        for g in generated:
            if g:
                results.append(g)
            progress.advance(task_id)

    if errors:
        console.print(f"[red]✗ {len(errors)} errors:[/red]")
        for err in errors[:5]:
            console.print(f"  [red]{err}[/red]")
    if not results:
        console.print("[red]No personas generated — aborting.[/red]")
        return
    console.print(f"[green]✓ Generated {len(results)} Danish personas[/green]")

    if not dry_run:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        out = ASSETS_DIR / "personas.jsonl"
        with out.open("w") as f:
            for p in results:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        console.print(f"[green]✓ Saved locally to {out}[/green]")

        from datasets import Dataset

        hf_dataset = Dataset.from_list(results)
        hf_dataset.push_to_hub(
            "oliverkinch/danish-personas",
            token=settings.hf_token,
        )
        console.print("[green]✓ Pushed to oliverkinch/danish-personas on HuggingFace Hub[/green]")
