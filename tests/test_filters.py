"""Tests for quality filters."""

from synth_da.config import FilterConfig
from synth_da.filters import _repetition_ratio, _token_count, passes_filters

_DANISH_RESPONSE = (
    "Danmark er et lille land i Nordeuropa med en rig historie og kultur. "
    "Landet er kendt for sit velfærdssystem, sin åbne samfundsmodel og sine mange cykelstier. "
    "Hovedstaden er København, som er hjemsted for over en million mennesker."
)
_ENGLISH_RESPONSE = (
    "Denmark is a small country in Northern Europe with a rich history and culture. "
    "It is well known for its welfare system, open society, and extensive cycling infrastructure. "
    "The capital city is Copenhagen, home to over one million people."
)
_SHORT_RESPONSE = "Ja."
_REPETITIVE_RESPONSE = " ".join(["dette er en test"] * 20)


def _make_messages(content: str) -> list[dict[str, str]]:
    return [
        {"role": "user", "content": "Hvad er Danmark?"},
        {"role": "assistant", "content": content},
    ]


def test_passes_danish_response() -> None:
    cfg = FilterConfig()
    assert passes_filters(messages=_make_messages(content=_DANISH_RESPONSE), cfg=cfg) is True


def test_fails_english_response() -> None:
    cfg = FilterConfig(language_check=True)
    assert passes_filters(messages=_make_messages(content=_ENGLISH_RESPONSE), cfg=cfg) is False


def test_language_check_disabled() -> None:
    cfg = FilterConfig(language_check=False)
    assert passes_filters(messages=_make_messages(content=_ENGLISH_RESPONSE), cfg=cfg) is True


def test_fails_short_response() -> None:
    cfg = FilterConfig(min_assistant_tokens=10)
    assert passes_filters(messages=_make_messages(content=_SHORT_RESPONSE), cfg=cfg) is False


def test_fails_repetitive_response() -> None:
    cfg = FilterConfig(max_repetition_ratio=0.3)
    assert passes_filters(messages=_make_messages(content=_REPETITIVE_RESPONSE), cfg=cfg) is False


def test_token_count() -> None:
    assert _token_count(text="et to tre fire") == 4


def test_repetition_ratio_clean() -> None:
    text = "Danmark er et land i Nordeuropa med en lang historie og traditioner."
    assert _repetition_ratio(text=text) < 0.1


def test_repetition_ratio_repetitive() -> None:
    text = " ".join(["hej verden"] * 15)
    assert _repetition_ratio(text=text) > 0.5
