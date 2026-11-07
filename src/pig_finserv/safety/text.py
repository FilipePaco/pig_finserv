"""Deterministic preparation of locally masked complaint text."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


class TextPreparationError(ValueError):
    """Raised when a text representation cannot be prepared safely."""


@dataclass(frozen=True, slots=True)
class TextPreparationStats:
    """Aggregate, non-sensitive preparation outcome for a single text."""

    truncated: bool
    original_characters: int
    prepared_characters: int


@dataclass(frozen=True, slots=True)
class PreparedText:
    """Normalized model input and non-sensitive preparation metadata."""

    text: str
    stats: TextPreparationStats


@dataclass(frozen=True, slots=True)
class MaskedTextPreprocessor:
    """Normalize only masked text, identically for training and inference.

    The preprocessor deliberately preserves negation and ordinary words. It replaces
    CFPB-style runs of redaction characters with one stable token and bounds length
    so extreme narratives cannot dominate feature extraction.
    """

    max_characters: int = 6_000

    _whitespace = re.compile(r"\s+")
    _redaction = re.compile(r"(?<!\w)X{3,}(?!\w)", re.IGNORECASE)
    _repeated_punctuation = re.compile(r"([!?.,;:])\1{2,}")

    def __post_init__(self) -> None:
        if self.max_characters < 1:
            raise TextPreparationError("max_characters must be positive")

    def prepare(self, masked_text: str) -> PreparedText:
        """Return a stable, bounded representation without accessing raw text."""

        if not isinstance(masked_text, str):
            raise TextPreparationError("masked_text must be text")
        normalized = unicodedata.normalize("NFKC", masked_text)
        normalized = self._redaction.sub(" [CFPB_REDACTED] ", normalized)
        normalized = self._repeated_punctuation.sub(r"\1\1", normalized)
        normalized = self._whitespace.sub(" ", normalized).strip()
        original_characters = len(normalized)
        prepared = normalized[: self.max_characters]
        return PreparedText(
            text=prepared,
            stats=TextPreparationStats(
                truncated=len(prepared) < original_characters,
                original_characters=original_characters,
                prepared_characters=len(prepared),
            ),
        )
