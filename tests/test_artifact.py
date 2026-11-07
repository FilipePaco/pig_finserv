from datetime import date
from pathlib import Path

import pytest

from pig_finserv.modeling.artifact import (
    ModelArtifactError,
    load_model_artifact,
    write_model_artifact,
)
from pig_finserv.modeling.model_card import ModelCard
from pig_finserv.modeling.policy import ThresholdPolicy


def _card() -> ModelCard:
    return ModelCard(
        "tfidf-v1",
        "snapshot-1",
        "2026.1",
        ((2024, 1),),
        ((2025, 1),),
        ((2025, 7),),
        "sigmoid",
        "cost-1-10-v1",
        42,
        created_at_utc=date(2026, 1, 1).isoformat(),
    )


def _policy() -> ThresholdPolicy:
    return ThresholdPolicy(0.9, 1, 10, 0.9, 50, 0.1, 1, 4)


def test_artifact_round_trip_verifies_checksum_and_taxonomy(tmp_path: Path) -> None:
    directory = write_model_artifact(
        directory=tmp_path / "model",
        estimator={"trusted": "local"},
        model_card=_card(),
        threshold_policy=_policy(),
        evaluation={"macro_f1": 0.8},
    )

    loaded = load_model_artifact(directory=directory, taxonomy_version="2026.1")

    assert loaded.estimator == {"trusted": "local"}
    assert loaded.evaluation == {"macro_f1": 0.8}
    with pytest.raises(ModelArtifactError, match="taxonomy"):
        load_model_artifact(directory=directory, taxonomy_version="2026.2")


def test_artifact_rejects_modified_or_existing_directory(tmp_path: Path) -> None:
    directory = write_model_artifact(
        directory=tmp_path / "model",
        estimator={"trusted": "local"},
        model_card=_card(),
        threshold_policy=_policy(),
        evaluation={"macro_f1": 0.8},
    )
    (directory / "evaluation.json").write_text("{}\n")

    with pytest.raises(ModelArtifactError, match="checksum"):
        load_model_artifact(directory=directory, taxonomy_version="2026.1")
    with pytest.raises(ModelArtifactError, match="already exists"):
        write_model_artifact(
            directory=directory,
            estimator={},
            model_card=_card(),
            threshold_policy=_policy(),
            evaluation={},
        )
