from datetime import date
from pathlib import Path

from pig_finserv.modeling.artifact import load_model_artifact
from pig_finserv.modeling.split import LabeledNarrative, split_by_month
from pig_finserv.modeling.training import train_and_store


def _partitions():
    examples: list[LabeledNarrative] = []
    for month_offset in range(36):
        year = 2023 + month_offset // 12
        month = month_offset % 12 + 1
        examples.extend(
            (
                LabeledNarrative(
                    f"card-{year}-{month}",
                    date(year, month, 1),
                    "credit card billing fee",
                    "Credit card",
                ),
                LabeledNarrative(
                    f"mortgage-{year}-{month}",
                    date(year, month, 2),
                    "mortgage escrow payment",
                    "Mortgage",
                ),
            )
        )
    return split_by_month(tuple(examples))


def test_training_compares_candidates_and_writes_compatible_artifact(tmp_path: Path) -> None:
    artifact_directory = tmp_path / "model"
    result = train_and_store(
        partitions=_partitions(),
        snapshot_id="cfpb-example",
        taxonomy_version="2026.1",
        artifact_directory=artifact_directory,
        source_revision="test-revision",
        created_at_utc="2026-11-07T00:00:00+00:00",
        minimum_class_support=2,
    )

    artifact = load_model_artifact(directory=artifact_directory, taxonomy_version="2026.1")

    assert result.selected_model_id in {"product-tfidf-logistic-v1", "product-tfidf-linear-svm-v1"}
    assert result.class_calibration_support == {"Credit card": 6, "Mortgage": 6}
    assert artifact.model_card.source_revision == "test-revision"
    assert artifact.model_card.calibration_class_support == {"Credit card": 6, "Mortgage": 6}
    assert set(artifact.evaluation) == {"baseline", "selected", "selected_model_id", "svm"}
