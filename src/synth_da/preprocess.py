"""Text preprocessing for seed data."""

from __future__ import annotations

import re

# Matches biographical parentheticals like "(født 16. januar 1988)" or
# "(født 16. januar 1988 i København)" or "(født ...; død ...)".
# These appear in Wikipedia lead paragraphs and reliably trigger birth-fact QA.
_BIRTH_RE = re.compile(r"\s*\(født[^)]+\)", re.IGNORECASE)


def strip_birth_parenthetical(text: str) -> str:
    """Remove '(født ...)' parentheticals from text."""
    return _BIRTH_RE.sub("", text)
