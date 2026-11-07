"""Alternative local product-routing candidate for locked-holdout comparison."""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from pig_finserv.modeling.split import LabeledNarrative
from pig_finserv.safety.text import MaskedTextPreprocessor


@dataclass
class TfidfLinearSvmProductClassifier:
    """Linear-SVM candidate using the same masked-text representation as baseline.

    ``LinearSVC`` deliberately exposes a decision function rather than uncalibrated
    probabilities; ``CalibratedProductClassifier`` converts it into probabilities
    using only the later chronological calibration partition.
    """

    pipeline: Pipeline | None = None
    preprocessor: MaskedTextPreprocessor = MaskedTextPreprocessor()

    def fit(self, examples: tuple[LabeledNarrative, ...]) -> TfidfLinearSvmProductClassifier:
        """Fit the candidate only on the supplied chronological fitting partition."""

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
                ("classifier", LinearSVC(class_weight="balanced", random_state=42)),
            ]
        )
        self.pipeline.fit(
            [self.preprocessor.prepare(example.masked_text).text for example in examples],
            [example.product_canonical for example in examples],
        )
        return self
