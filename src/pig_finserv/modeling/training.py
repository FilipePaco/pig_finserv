"""Reproducible chronological training workflow for product routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pig_finserv.modeling.artifact import write_model_artifact
from pig_finserv.modeling.baseline import TfidfLogisticProductClassifier
from pig_finserv.modeling.calibration import CalibratedProductClassifier
from pig_finserv.modeling.candidate import TfidfLinearSvmProductClassifier
from pig_finserv.modeling.evaluation import EvaluationResult, evaluate_classifier
from pig_finserv.modeling.model_card import ModelCard
from pig_finserv.modeling.policy import CalibrationOutcome, ThresholdPolicy, select_threshold
from pig_finserv.modeling.split import LabeledNarrative, TemporalPartitions


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Selected artifact lineage and both locked-holdout candidate evaluations."""

    selected_model_id: str
    artifact_directory: Path
    threshold_policy: ThresholdPolicy
    baseline_evaluation: EvaluationResult
    svm_evaluation: EvaluationResult
    class_calibration_support: dict[str, int]


def train_and_store(
    *,
    partitions: TemporalPartitions,
    snapshot_id: str,
    taxonomy_version: str,
    artifact_directory: Path,
    source_revision: str,
    created_at_utc: str,
    minimum_class_support: int = 50,
) -> TrainingResult:
    """Fit, calibrate, compare, and persist local candidates without holdout leakage.

    The SVM can replace the baseline only after a material macro-F1 advantage of at
    least 0.02. This protects interpretability and operational simplicity from a
    marginal score-driven substitution.
    """

    baseline = TfidfLogisticProductClassifier().fit(partitions.fit)
    calibrated_baseline = CalibratedProductClassifier().fit(
        base=baseline, calibration=partitions.calibration
    )
    policy = _select_policy(
        calibrated_baseline, partitions.calibration, minimum_class_support=minimum_class_support
    )
    baseline_evaluation = evaluate_classifier(
        calibrated_baseline, partitions.test, threshold=policy.threshold
    )

    svm = TfidfLinearSvmProductClassifier().fit(partitions.fit)
    calibrated_svm = CalibratedProductClassifier().fit(base=svm, calibration=partitions.calibration)
    # Both candidates use the threshold frozen from the baseline's calibration period.
    svm_evaluation = evaluate_classifier(
        calibrated_svm, partitions.test, threshold=policy.threshold
    )

    selected_model_id, selected_estimator, selected_evaluation = _select_candidate(
        calibrated_baseline=calibrated_baseline,
        calibrated_svm=calibrated_svm,
        baseline_evaluation=baseline_evaluation,
        svm_evaluation=svm_evaluation,
    )
    support = _class_support(partitions.calibration)
    model_card = ModelCard(
        model_id=selected_model_id,
        snapshot_id=snapshot_id,
        taxonomy_version=taxonomy_version,
        fit_months=partitions.fit_months,
        calibration_months=partitions.calibration_months,
        test_months=partitions.test_months,
        calibration_method="sigmoid",
        threshold_policy_version="cost-1-10-v1",
        random_seed=42,
        source_revision=source_revision,
        created_at_utc=created_at_utc,
        calibration_class_support=support,
    )
    write_model_artifact(
        directory=artifact_directory,
        estimator=selected_estimator,
        model_card=model_card,
        threshold_policy=policy,
        evaluation={
            "selected_model_id": selected_model_id,
            "selected": selected_evaluation.as_dict(),
            "baseline": baseline_evaluation.as_dict(),
            "svm": svm_evaluation.as_dict(),
        },
    )
    return TrainingResult(
        selected_model_id=selected_model_id,
        artifact_directory=artifact_directory,
        threshold_policy=policy,
        baseline_evaluation=baseline_evaluation,
        svm_evaluation=svm_evaluation,
        class_calibration_support=support,
    )


def _select_policy(
    classifier: CalibratedProductClassifier,
    examples: tuple[LabeledNarrative, ...],
    *,
    minimum_class_support: int,
) -> ThresholdPolicy:
    outcomes = tuple(
        _calibration_outcome(classifier, example) for example in examples
    )
    return select_threshold(
        outcomes,
        review_cost=1.0,
        misroute_cost=10.0,
        minimum_class_support=minimum_class_support,
    )


def _calibration_outcome(
    classifier: CalibratedProductClassifier, example: LabeledNarrative
) -> CalibrationOutcome:
    distribution = classifier.predict_distribution(example.masked_text)
    predicted_product, confidence = max(distribution.items(), key=lambda item: item[1])
    return CalibrationOutcome(
        predicted_product=predicted_product,
        confidence=confidence,
        is_correct=predicted_product == example.product_canonical,
    )


def _class_support(examples: tuple[LabeledNarrative, ...]) -> dict[str, int]:
    labels = sorted({item.product_canonical for item in examples})
    return {
        label: sum(item.product_canonical == label for item in examples) for label in labels
    }


def _select_candidate(
    *,
    calibrated_baseline: CalibratedProductClassifier,
    calibrated_svm: CalibratedProductClassifier,
    baseline_evaluation: EvaluationResult,
    svm_evaluation: EvaluationResult,
) -> tuple[str, CalibratedProductClassifier, EvaluationResult]:
    if svm_evaluation.macro_f1 >= baseline_evaluation.macro_f1 + 0.02:
        return "product-tfidf-linear-svm-v1", calibrated_svm, svm_evaluation
    return "product-tfidf-logistic-v1", calibrated_baseline, baseline_evaluation
