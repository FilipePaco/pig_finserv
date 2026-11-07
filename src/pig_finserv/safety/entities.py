"""Conservative local rule-based entity candidate detector.

This is intentionally not a claim of full named-entity recognition. It catches a
small set of high-signal self-identification and US city/state constructions before
text reaches model features or optional providers. Human review remains required for
the known false-negative and false-positive cases documented in ``docs/safety.md``.
"""

from __future__ import annotations

import re
from collections import Counter


class LocalEntityCandidateDetector:
    """Mask narrow person and location candidates using local-only patterns."""

    _person = re.compile(
        r"\b(?i:my\s+name\s+is|i\s+am|this\s+is)\s+"
        r"(?P<entity>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
    )
    _location = re.compile(
        r"\b(?:in|from|at)\s+(?P<entity>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}),\s*"
        r"(?:AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|"
        r"MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|"
        r"WA|WI|WV|WY)\b"
    )

    def mask_candidates(self, text: str, counts: Counter[str]) -> str:
        """Replace detected candidates with typed placeholders and increment counts."""

        text = self._replace(text, self._person, "PERSON_CANDIDATE", counts)
        return self._replace(text, self._location, "LOCATION_CANDIDATE", counts)

    @staticmethod
    def _replace(
        text: str, pattern: re.Pattern[str], entity_type: str, counts: Counter[str]
    ) -> str:
        def replace(_: re.Match[str]) -> str:
            counts[entity_type] += 1
            return f"[{entity_type}_{counts[entity_type]}]"

        return pattern.sub(replace, text)
