"""Interpretable TF-IDF plus Logistic Regression product-routing baseline."""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from pig_finserv.modeling.split import LabeledNarrative


@dataclass
class TfidfLogisticProductClassifier:
    """Local baseline combining word and character features from masked text."""

    pipeline: Pipeline | None = None

    def fit(self, examples: tuple[LabeledNarrative, ...]) -> TfidfLogisticProductClassifier:
        """Fit only on the supplied chronological fitting partition."""

        if len({example.product_canonical for example in examples}) < 2:
            raise ValueError("at least two product classes are required for training")
        self.pipeline = Pipeline(
            [
                (
                    "features",
                    FeatureUnion(
                        [
                            (
                                "word",
                                TfidfVectorizer(
                                    ngram_range=(1, 2), min_df=1, sublinear_tf=True
                                ),
                            ),
                            (
                                "char",
                                TfidfVectorizer(
                                    analyzer="char_wb",
                                    ngram_range=(3, 5),
                                    min_df=1,
                                    sublinear_tf=True,
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced", max_iter=1_000, random_state=42
                    ),
                ),
            ]
        )
        self.pipeline.fit(
            [example.masked_text for example in examples],
            [example.product_canonical for example in examples],
        )
        return self

    def predict_distribution(self, masked_text: str) -> dict[str, float]:
        """Return the full local class-probability distribution for one masked narrative."""

        if self.pipeline is None:
            raise RuntimeError("classifier must be fitted before prediction")
        probabilities = self.pipeline.predict_proba([masked_text])[0]
        classes = self.pipeline.named_steps["classifier"].classes_
        return {
            label: float(probability)
            for label, probability in zip(classes, probabilities, strict=True)
        }
