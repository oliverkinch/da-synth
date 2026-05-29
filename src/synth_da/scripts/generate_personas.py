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

_SEX_DA: dict[str, str] = {
    "Male": "Mand",
    "Female": "Kvinde",
    "Non-binary": "Ikke-binær",
}

_EDUCATION_DA: dict[str, str] = {
    "less_than_9th": "Grundskole (under 9. klasse)",
    "9th_to_12th": "Grundskole (9.–12. klasse)",
    "high_school": "Gymnasial uddannelse",
    "some_college": "Påbegyndt videregående uddannelse",
    "associates": "Mellemlang videregående uddannelse",
    "bachelors": "Bacheloruddannelse",
    "graduate": "Kandidat- eller ph.d.-uddannelse",
}

_OCCUPATION_DA: dict[str, str] = {
    "not_in_workforce": "Ikke i arbejdsstyrken",
    "general_or_operations_manager": "Leder/driftschef",
    "accountant_or_auditor": "Revisor/bogholder",
    "engineer": "Ingeniør",
    "air_traffic_controller_or_airfield_operations_specialist": "Flyveleder/lufthavnsspecialist",
    "stocker_or_order_filler": "Lagermedarbejder",
    "software_developer": "Softwareudvikler",
    "registered_nurse": "Sygeplejerske",
    "teacher": "Lærer",
    "retail_salesperson": "Detailsælger",
    "driver": "Chauffør",
    "construction_worker": "Bygningsarbejder",
    "chef_or_cook": "Kok",
    "administrative_assistant": "Administrativ assistent",
    "financial_analyst": "Finansanalytiker",
    "physician_or_surgeon": "Læge/kirurg",
    "lawyer": "Advokat",
    "social_worker": "Socialrådgiver",
    "marketing_manager": "Marketingchef",
    "scientist_or_researcher": "Forsker/videnskabsperson",
}

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


def _name_examples(sex: str) -> str:
    first_pool = _FEMALE_NAMES if sex == "Female" else _MALE_NAMES
    firsts = random.sample(first_pool, 5)
    lasts = random.sample(_LAST_NAMES, 5)
    return "\n".join(f"{first} {last}" for first, last in zip(firsts, lasts, strict=False))


_TRANSLATE_PROMPT = """\
Oversæt følgende tekst til naturligt dansk. Bevar tonen og personligheden. \
Erstat samtidig alle udenlandske stednavne (byer, kvarterer, stater, regioner) \
med relevante danske steder i eller omkring {city} ({zipcode}), Danmark. \
Svar kun med den oversatte og lokaliserede tekst, intet andet.

{text}"""


async def run(n: int, settings: Settings, dry_run: bool = False) -> None:
    from rich.console import Console

    console = Console()
    client = GenerationClient(settings)

    console.print("[blue]Downloading nvidia/Nemotron-Personas-USA…[/blue]")
    ds = load_dataset("nvidia/Nemotron-Personas-USA", split="train", token=settings.hf_token)
    console.print(f"[green]✓ Loaded {len(ds)} personas — columns: {ds.column_names}[/green]")
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

        errors: list[str] = []

        async def _translate_text(text: str, city: str, zipcode: str) -> str:
            return await client.generate(
                [
                    {
                        "role": "user",
                        "content": _TRANSLATE_PROMPT.format(text=text, city=city, zipcode=zipcode),
                    }
                ],
                temperature=0.7,
                max_tokens=512,
            )

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

        async def _translate(row: dict[str, Any]) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    raw_persona = str(row.get("persona") or row.get("description") or "")
                    raw_hobbies = str(row.get("hobbies_and_interests") or "")
                    raw_sex = str(row.get("sex") or "")

                    city, zipcode = random.choice(DANISH_CITIES)

                    # Translate, localize, and generate name — all in parallel
                    persona_da, hobbies_da, danish_name = await asyncio.gather(
                        _translate_text(raw_persona, city, zipcode)
                        if raw_persona
                        else asyncio.sleep(0, result=""),
                        _translate_text(raw_hobbies, city, zipcode)
                        if raw_hobbies
                        else asyncio.sleep(0, result=""),
                        _generate_name(raw_sex),
                    )

                    # Replace the original name in the persona text with the Danish name
                    original_name = str(row.get("name") or "").strip()
                    if original_name and danish_name:
                        persona_da = persona_da.replace(original_name, danish_name)
                        hobbies_da = hobbies_da.replace(original_name, danish_name)
                    # Also replace first name alone (handles "Firstname" references in text)
                    if original_name and danish_name:
                        orig_first = original_name.split()[0]
                        da_first = danish_name.split()[0]
                        persona_da = persona_da.replace(orig_first, da_first)
                        hobbies_da = hobbies_da.replace(orig_first, da_first)

                    raw_occ = str(row.get("occupation") or "")
                    raw_edu = str(row.get("education_level") or "")

                    return {
                        "uuid": row.get("uuid", ""),
                        "name": danish_name.strip(),
                        "persona": persona_da,
                        "age": row.get("age"),
                        "sex": _SEX_DA.get(raw_sex, raw_sex),
                        "occupation": _OCCUPATION_DA.get(raw_occ, raw_occ),
                        "education_level": _EDUCATION_DA.get(raw_edu, raw_edu),
                        "hobbies_and_interests": hobbies_da,
                        "city": city,
                        "zipcode": zipcode,
                        "country": "Danmark",
                    }
                except Exception as e:
                    errors.append(str(e))
                    return None

        translated = await asyncio.gather(*[_translate(r) for r in rows])
        for t in translated:
            if t:
                results.append(t)
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
