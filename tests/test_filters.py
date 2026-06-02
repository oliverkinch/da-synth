"""Tests for quality filters."""

from synth_da.config import FilterConfig
from synth_da.filters import _repetition_ratio, _token_count, passes_filters

_DANISH_TEXT = (
    "Danmark er et lille land i Nordeuropa med en rig historie og kultur. "
    "Landet er kendt for sit velfærdssystem, sin åbne samfundsmodel og sine mange cykelstier. "
    "Hovedstaden er København, som er hjemsted for over en million mennesker."
)
_ENGLISH_TEXT = (
    "Denmark is a small country in Northern Europe with a rich history and culture. "
    "It is well known for its welfare system, open society, and extensive cycling infrastructure. "
    "The capital city is Copenhagen, home to over one million people."
)
_SHORT_TEXT = "Ja."
_REPETITIVE_TEXT = " ".join(["dette er en test"] * 20)


def test_passes_danish_text() -> None:
    cfg = FilterConfig()
    assert passes_filters(text=_DANISH_TEXT, cfg=cfg) is True


def test_fails_english_text() -> None:
    cfg = FilterConfig(language_check=True)
    assert passes_filters(text=_ENGLISH_TEXT, cfg=cfg) is False


def test_language_check_disabled() -> None:
    cfg = FilterConfig(language_check=False)
    assert passes_filters(text=_ENGLISH_TEXT, cfg=cfg) is True


def test_fails_short_text() -> None:
    cfg = FilterConfig(min_assistant_tokens=10)
    assert passes_filters(text=_SHORT_TEXT, cfg=cfg) is False


def test_fails_repetitive_text() -> None:
    cfg = FilterConfig(max_repetition_ratio=0.3)
    assert passes_filters(text=_REPETITIVE_TEXT, cfg=cfg) is False


def test_token_count() -> None:
    assert _token_count(text="et to tre fire") == 4


def test_repetition_ratio_clean() -> None:
    text = "Danmark er et land i Nordeuropa med en lang historie og traditioner."
    assert _repetition_ratio(text=text) < 0.1


def test_repetition_ratio_repetitive() -> None:
    text = " ".join(["hej verden"] * 15)
    assert _repetition_ratio(text=text) > 0.5
