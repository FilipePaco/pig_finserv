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

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")
