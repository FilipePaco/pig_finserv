"""Locked-holdout evaluation for calibrated local routing models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from pig_finserv.modeling.split import LabeledNarrative


class ProbabilisticClassifier(Protocol):
    """Prediction contract required for holdout evaluation."""

    def predict_distribution(self, masked_text: str) -> dict[str, float]: ...


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    """One calibration reliability bucket for the selected class."""

    lower_bound: float
    upper_bound: float
    count: int
    mean_confidence: float | None
    empirical_accuracy: float | None


@dataclass(frozen=True, slots=True)
class PerClassMetrics:
    """Class-level locked-holdout quality values."""

    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True, slots=True)
class SelectiveMetrics:
    """Human-review and cost outcome for one operating cost ratio."""

    review_cost: float
    misroute_cost: float
    auto_route_coverage: float
    review_rate: float
    selective_precision: float | None
    selective_macro_f1: float | None
    expected_cost: float


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Machine-readable quality report without narrative text."""

    labels: tuple[str, ...]
    macro_f1: float
    weighted_f1: float
    accuracy: float
    per_class: dict[str, PerClassMetrics]
    confusion_matrix: tuple[tuple[int, ...], ...]
    normalized_confusion_matrix: tuple[tuple[float, ...], ...]
    brier_score: float
    expected_calibration_error: float
    reliability_bins: tuple[ReliabilityBin, ...]
    selective_metrics: tuple[SelectiveMetrics, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe structure with deterministic class keys."""

        payload = asdict(self)
        payload["per_class"] = {
            label: asdict(metrics) for label, metrics in sorted(self.per_class.items())
        }
        return payload


def evaluate_classifier(
    classifier: ProbabilisticClassifier,
    examples: tuple[LabeledNarrative, ...],
    *,
    threshold: float,
    cost_ratios: tuple[tuple[float, float], ...] = ((1.0, 5.0), (1.0, 10.0), (1.0, 20.0)),
    reliability_bin_count: int = 10,
) -> EvaluationResult:
    """Evaluate one frozen classifier on the untouched chronological test set."""

    if not examples:
        raise ValueError("at least one holdout example is required")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    if reliability_bin_count < 2:
        raise ValueError("reliability_bin_count must be at least two")

    distributions = tuple(classifier.predict_distribution(item.masked_text) for item in examples)
    if any(not distribution for distribution in distributions):
        raise ValueError("classifier returned an empty probability distribution")
    labels = tuple(
        sorted(
            {item.product_canonical for item in examples}
            | {label for distribution in distributions for label in distribution}
        )
    )
    true = tuple(item.product_canonical for item in examples)
    predicted = tuple(
        max(distribution.items(), key=lambda item: item[1])[0] for distribution in distributions
    )
    confidences = tuple(max(distribution.values()) for distribution in distributions)
    correctness = tuple(
        actual == predicted_label
        for actual, predicted_label in zip(true, predicted, strict=True)
    )

    precision, recall, f1, support = precision_recall_fscore_support(
        true, predicted, labels=labels, zero_division=0
    )
    raw_confusion = confusion_matrix(true, predicted, labels=labels)
    normalized_confusion = confusion_matrix(true, predicted, labels=labels, normalize="true")
    per_class = {
        label: PerClassMetrics(
            precision=float(precision[index]),
            recall=float(recall[index]),
            f1=float(f1[index]),
            support=int(support[index]),
        )
        for index, label in enumerate(labels)
    }
    return EvaluationResult(
        labels=labels,
        macro_f1=float(f1_score(true, predicted, labels=labels, average="macro", zero_division=0)),
        weighted_f1=float(
            f1_score(true, predicted, labels=labels, average="weighted", zero_division=0)
        ),
        accuracy=float(accuracy_score(true, predicted)),
        per_class=per_class,
        confusion_matrix=tuple(tuple(int(value) for value in row) for row in raw_confusion),
        normalized_confusion_matrix=tuple(
            tuple(float(value) for value in row) for row in normalized_confusion
        ),
        brier_score=_multiclass_brier(distributions, true, labels),
        expected_calibration_error=_expected_calibration_error(
            confidences, correctness, reliability_bin_count
        ),
        reliability_bins=_reliability_bins(confidences, correctness, reliability_bin_count),
        selective_metrics=tuple(
            _selective_metrics(
                true=true,
                predicted=predicted,
                confidences=confidences,
                threshold=threshold,
                review_cost=review_cost,
                misroute_cost=misroute_cost,
                labels=labels,
            )
            for review_cost, misroute_cost in cost_ratios
        ),
    )


def _multiclass_brier(
    distributions: tuple[dict[str, float], ...], true: tuple[str, ...], labels: tuple[str, ...]
) -> float:
    errors = [
        sum((distribution.get(label, 0.0) - float(label == actual)) ** 2 for label in labels)
        for distribution, actual in zip(distributions, true, strict=True)
    ]
    return sum(errors) / len(errors)


def _expected_calibration_error(
    confidences: tuple[float, ...], correctness: tuple[bool, ...], bin_count: int
) -> float:
    return sum(
        bucket_count / len(confidences) * abs(mean_confidence - empirical_accuracy)
        for bucket_count, mean_confidence, empirical_accuracy in _non_empty_bin_values(
            confidences, correctness, bin_count
        )
    )


def _reliability_bins(
    confidences: tuple[float, ...], correctness: tuple[bool, ...], bin_count: int
) -> tuple[ReliabilityBin, ...]:
    # Retain empty bins so downstream reliability charts have fixed, clear bounds.
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bin_count)]
    for confidence, is_correct in zip(confidences, correctness, strict=True):
        buckets[min(int(confidence * bin_count), bin_count - 1)].append((confidence, is_correct))
    return tuple(
        ReliabilityBin(
            lower_bound=index / bin_count,
            upper_bound=(index + 1) / bin_count,
            count=len(bucket),
            mean_confidence=(sum(value for value, _ in bucket) / len(bucket)) if bucket else None,
            empirical_accuracy=(sum(flag for _, flag in bucket) / len(bucket)) if bucket else None,
        )
        for index, bucket in enumerate(buckets)
    )


def _non_empty_bin_values(
    confidences: tuple[float, ...], correctness: tuple[bool, ...], bin_count: int
) -> tuple[tuple[int, float, float], ...]:
    buckets: dict[int, list[tuple[float, bool]]] = {}
    for confidence, is_correct in zip(confidences, correctness, strict=True):
        buckets.setdefault(min(int(confidence * bin_count), bin_count - 1), []).append(
            (confidence, is_correct)
        )
    return tuple(
        (
            len(bucket),
            sum(confidence for confidence, _ in bucket) / len(bucket),
            sum(is_correct for _, is_correct in bucket) / len(bucket),
        )
        for _, bucket in sorted(buckets.items())
    )


def _selective_metrics(
    *,
    true: tuple[str, ...],
    predicted: tuple[str, ...],
    confidences: tuple[float, ...],
    threshold: float,
    review_cost: float,
    misroute_cost: float,
    labels: tuple[str, ...],
) -> SelectiveMetrics:
    selected = tuple(
        index for index, confidence in enumerate(confidences) if confidence >= threshold
    )
    review_count = len(true) - len(selected)
    if selected:
        selected_true = tuple(true[index] for index in selected)
        selected_predicted = tuple(predicted[index] for index in selected)
        correct_count = sum(
            actual == prediction
            for actual, prediction in zip(selected_true, selected_predicted, strict=True)
        )
        precision = correct_count / len(selected)
        macro_f1 = float(
            f1_score(
                selected_true,
                selected_predicted,
                labels=labels,
                average="macro",
                zero_division=0,
            )
        )
    else:
        correct_count = 0
        precision = None
        macro_f1 = None
    return SelectiveMetrics(
        review_cost=review_cost,
        misroute_cost=misroute_cost,
        auto_route_coverage=len(selected) / len(true),
        review_rate=review_count / len(true),
        selective_precision=precision,
        selective_macro_f1=macro_f1,
        expected_cost=(len(selected) - correct_count) * misroute_cost + review_count * review_cost,
    )
