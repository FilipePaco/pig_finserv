"""Non-sensitive model-card metadata for reproducible routing artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModelCard:
    model_id: str
    snapshot_id: str
    taxonomy_version: str
    fit_months: tuple[tuple[int, int], ...]
    calibration_months: tuple[tuple[int, int], ...]
    test_months: tuple[tuple[int, int], ...]
    calibration_method: str
    threshold_policy_version: str
    random_seed: int
    source_revision: str = "unknown"
    dependency_lock_reference: str = "uv.lock"
    created_at_utc: str | None = None

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")

    @classmethod
    def read(cls, path: Path) -> ModelCard:
        """Read a previously written, non-sensitive model card."""

        payload = json.loads(path.read_text())
        for field in ("fit_months", "calibration_months", "test_months"):
            payload[field] = tuple(tuple(month) for month in payload[field])
        return cls(**payload)
