"""Persona sampling for diversity injection."""

from __future__ import annotations

import random
from typing import Any

HF_PERSONAS_REPO = "oliverkinch/danish-personas"


def load_personas() -> list[dict[str, Any]]:
    from datasets import load_dataset

    ds = load_dataset(HF_PERSONAS_REPO, split="train")
    return [dict(row) for row in ds]


_PERSONAS: list[dict[str, Any]] = []


def _ensure_loaded() -> None:
    global _PERSONAS
    if not _PERSONAS:
        _PERSONAS = load_personas()


def sample_persona() -> dict[str, Any] | None:
    _ensure_loaded()
    if not _PERSONAS:
        return None
    return random.choice(_PERSONAS)


def persona_to_prompt(persona: dict[str, Any]) -> str:
    """Format a persona as a short diversity prompt for the generator."""
    parts = []
    if age := persona.get("age"):
        parts.append(f"{age} år")
    if occ := persona.get("occupation"):
        parts.append(occ.lower())
    if city := persona.get("city"):
        parts.append(f"fra {city}")
    if interests := persona.get("hobbies_and_interests"):
        parts.append(f"med interesse for {interests.lower()}")
    desc = str(persona.get("persona", ""))
    if parts:
        return f"[Persona: {', '.join(parts)}] {desc}".strip()
    return desc
