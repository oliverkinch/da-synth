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
