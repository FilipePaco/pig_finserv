import pytest

from pig_finserv.safety.text import MaskedTextPreprocessor, TextPreparationError


def test_preprocessor_normalizes_redactions_unicode_whitespace_and_punctuation() -> None:
    prepared = MaskedTextPreprocessor().prepare("Card\u00a0XXXXXX   failed!!!!")

    assert prepared.text == "Card [CFPB_REDACTED] failed!!"
    assert prepared.stats.truncated is False


def test_preprocessor_bounds_text_and_reports_truncation() -> None:
    prepared = MaskedTextPreprocessor(max_characters=5).prepare("a long complaint")

    assert prepared.text == "a lon"
    assert prepared.stats.truncated is True
    assert prepared.stats.original_characters == len("a long complaint")


def test_preprocessor_requires_valid_input_and_limit() -> None:
    with pytest.raises(TextPreparationError, match="positive"):
        MaskedTextPreprocessor(max_characters=0)
    with pytest.raises(TextPreparationError, match="text"):
        MaskedTextPreprocessor().prepare(None)  # type: ignore[arg-type]
