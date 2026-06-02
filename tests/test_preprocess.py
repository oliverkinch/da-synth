"""Tests for seed-text preprocessing."""

from synth_da.preprocess import strip_birth_parenthetical


def test_strip_date_only() -> None:
    result = strip_birth_parenthetical(
        "Nicklas Bendtner (født 16. januar 1988) er en tidligere dansk professionel fodboldspiller."
    )
    assert result == "Nicklas Bendtner er en tidligere dansk professionel fodboldspiller."


def test_strip_date_and_place() -> None:
    result = strip_birth_parenthetical(
        "Karen Blixen (født 17. april 1885 i Rungsted) var en dansk forfatter."
    )
    assert result == "Karen Blixen var en dansk forfatter."


def test_strip_date_place_and_death() -> None:
    result = strip_birth_parenthetical(
        "H.C. Andersen (født 2. april 1805 i Odense; død 4. august 1875) var digter."
    )
    assert result == "H.C. Andersen var digter."


def test_no_parenthetical_unchanged() -> None:
    text = "Danmark er et nordeuropæisk land."
    assert strip_birth_parenthetical(text) == text


def test_strip_mid_sentence() -> None:
    result = strip_birth_parenthetical("Spilleren (født 1990) debuterede tidligt.")
    assert result == "Spilleren debuterede tidligt."
