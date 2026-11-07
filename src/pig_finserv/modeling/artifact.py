"""Safe local persistence and compatibility checks for routing-model artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib

from pig_finserv.modeling.model_card import ModelCard
from pig_finserv.modeling.policy import ThresholdPolicy


class ModelArtifactError(ValueError):
    """Raised when an artifact is incomplete, modified, or incompatible."""


@dataclass(frozen=True, slots=True)
class StoredModelArtifact:
    """Loaded trusted-local estimator and its verified decision lineage."""

    estimator: Any
    model_card: ModelCard
    threshold_policy: ThresholdPolicy
    evaluation: dict[str, object]


def write_model_artifact(
    *,
    directory: Path,
    estimator: Any,
    model_card: ModelCard,
    threshold_policy: ThresholdPolicy,
    evaluation: dict[str, object],
) -> Path:
    """Write a new immutable-by-convention artifact directory with checksums.

    Serialized estimators are trusted-local files only. A caller must never point this
    loader at an untrusted download because joblib deserialization executes Python.
    """

    if directory.exists():
        raise ModelArtifactError("artifact directory already exists")
    directory.mkdir(parents=True)
    estimator_path = directory / "estimator.joblib"
    card_path = directory / "model-card.json"
    policy_path = directory / "threshold-policy.json"
    evaluation_path = directory / "evaluation.json"
    joblib.dump(estimator, estimator_path)
    model_card.write(card_path)
    policy_path.write_text(json.dumps(asdict(threshold_policy), indent=2, sort_keys=True) + "\n")
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n")
    checksums = {
        path.name: _sha256_file(path)
        for path in (estimator_path, card_path, policy_path, evaluation_path)
    }
    checksum_path = directory / "checksums.json"
    checksum_path.write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n")
    return directory


def load_model_artifact(*, directory: Path, taxonomy_version: str) -> StoredModelArtifact:
    """Verify all files before loading an artifact compatible with the active taxonomy."""

    required = {
        "estimator.joblib",
        "model-card.json",
        "threshold-policy.json",
        "evaluation.json",
        "checksums.json",
    }
    present = {path.name for path in directory.iterdir()} if directory.is_dir() else set()
    missing = sorted(required - present)
    if missing:
        raise ModelArtifactError(f"artifact is missing required files: {', '.join(missing)}")
    checksums = json.loads((directory / "checksums.json").read_text())
    expected_names = required - {"checksums.json"}
    if set(checksums) != expected_names:
        raise ModelArtifactError("artifact checksum manifest does not match required files")
    for name in sorted(expected_names):
        if _sha256_file(directory / name) != checksums[name]:
            raise ModelArtifactError(f"artifact checksum mismatch: {name}")
    card = ModelCard.read(directory / "model-card.json")
    if card.taxonomy_version != taxonomy_version:
        raise ModelArtifactError("artifact taxonomy version is incompatible")
    policy = ThresholdPolicy(**json.loads((directory / "threshold-policy.json").read_text()))
    evaluation = json.loads((directory / "evaluation.json").read_text())
    return StoredModelArtifact(
        estimator=joblib.load(directory / "estimator.joblib"),
        model_card=card,
        threshold_policy=policy,
        evaluation=evaluation,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
