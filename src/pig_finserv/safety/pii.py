"""Local, conservative PII masking for untrusted complaint narratives."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections import Counter
from dataclasses import dataclass

from pig_finserv.domain import MaskingStatus


class PiiMaskingError(ValueError):
    """Raised when a safe masking result cannot be produced."""


@dataclass(frozen=True, slots=True)
class MaskedText:
    """Safe output passed to models, providers, and audit records."""

    text: str
    input_fingerprint: str
    status: MaskingStatus
    entity_counts: dict[str, int]


class PiiMasker:
    """Mask high-risk structured identifiers before any downstream processing.

    This component intentionally favors high-precision identifiers. A future local NLP
    detector can extend it for person/location candidates without changing consumers.
    """

    _email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    _ssn = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    _dob = re.compile(
        r"\b(?:dob|date of birth)\s*[:#-]?\s*"
        r"(?:0?[1-9]|1[0-2])[/.-](?:0?[1-9]|[12]\d|3[01])[/.-](?:19|20)\d{2}\b",
        re.IGNORECASE,
    )
    _account = re.compile(
        r"\b(?:account|acct|card)\s*(?:number|no\.?|#)?\s*[:#-]\s*[A-Z0-9][A-Z0-9 -]{4,}\b",
        re.IGNORECASE,
    )
    _card_candidate = re.compile(r"\b(?:\d[ -]?){13,19}\b")
    _phone = re.compile(
        r"(?<!\w)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]\d{4}(?!\w)"
    )

    def __init__(self, *, fingerprint_salt: bytes) -> None:
        if not fingerprint_salt:
            raise PiiMaskingError("fingerprint_salt must not be empty")
        self._fingerprint_salt = fingerprint_salt

    def mask(self, narrative: str) -> MaskedText:
        """Return masked text and an HMAC fingerprint without retaining entity values."""

        if not isinstance(narrative, str):
            raise PiiMaskingError("narrative must be text")
        counts: Counter[str] = Counter()
        text = narrative
        text = self._replace(text, self._email, "EMAIL", counts)
        text = self._replace(text, self._ssn, "SSN", counts)
        text = self._replace(text, self._dob, "DATE_OF_BIRTH", counts)
        text = self._replace(text, self._account, "ACCOUNT_ID", counts)
        text = self._replace_card_numbers(text, counts)
        text = self._replace(text, self._phone, "PHONE", counts)
        return MaskedText(
            text=text,
            input_fingerprint=hmac.new(
                self._fingerprint_salt, narrative.encode("utf-8"), hashlib.sha256
            ).hexdigest(),
            status=MaskingStatus.MASKED,
            entity_counts=dict(sorted(counts.items())),
        )

    @staticmethod
    def _replace(
        text: str, pattern: re.Pattern[str], entity_type: str, counts: Counter[str]
    ) -> str:
        def replace(_: re.Match[str]) -> str:
            counts[entity_type] += 1
            return f"[{entity_type}_{counts[entity_type]}]"

        return pattern.sub(replace, text)

    def _replace_card_numbers(self, text: str, counts: Counter[str]) -> str:
        def replace(match: re.Match[str]) -> str:
            digits = re.sub(r"\D", "", match.group())
            if not _passes_luhn(digits):
                return match.group()
            counts["CARD_NUMBER"] += 1
            return f"[CARD_NUMBER_{counts['CARD_NUMBER']}]"

        return self._card_candidate.sub(replace, text)


def _passes_luhn(digits: str) -> bool:
    """Return whether a digit string passes the Luhn checksum."""

    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
