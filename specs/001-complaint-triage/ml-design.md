# Machine Learning Design

**Status:** SDD v1 draft
**Primary outcome:** An auditable, calibrated product-routing classifier.
**Bonus outcome:** A conditional issue classifier if quality and support justify it.

## 1. ML decision boundaries

- A locally trained classifier is the required prediction engine for product routing.
- The model predicts labels; a separate routing policy determines whether to suggest an automatic route or request human review.
- Gemini never predicts labels. Jev may be evaluated as a masked-text zero-shot benchmark or review-only second opinion, never as the required trained classifier.
- No online learning occurs. Human corrections are saved as review data for a future, versioned retraining run.

## 2. Target definitions

### Product target

`product_canonical` is the required multi-class target. It includes only reviewed canonical labels from the taxonomy mapping. `UNMAPPED`, `AMBIGUOUS`, empty labels, and labels below the documented support rule are excluded from the supervised training target and reported as coverage exclusions.

### Issue target

`issue_canonical` is optional and conditional on a known or predicted canonical product. An issue model is eligible only when its parent product has at least 500 training narratives and each included issue class has at least 50 fitting-partition examples. Lower-support classes are returned as `UNSUPPORTED` for review rather than silently merged. Product prediction errors are reported separately from issue-model error.

## 3. Text preparation

Training consumes restricted narrative text only from the local training zone. Every narrative is passed through the local PII guard before feature generation; training and inference use the same masked, locally normalized representation. The pipeline does not send training text to any provider. Transformations must be fitted only on the fitting partition:

- replace known CFPB redaction spans such as repeated `X` with a stable token;
- normalize Unicode, whitespace, and repeated punctuation;
- preserve negation and product-relevant terms; do not remove all stop words blindly;
- apply a maximum length chosen from observed percentile statistics, recording truncation rate;
- retain raw restricted input only where the data-retention policy permits; artifact reports contain aggregate examples only after manual privacy review.

The raw restricted training source is retained only according to the data-retention policy. It is not a model feature representation and is never emitted in model artifacts, evaluation outputs, or normal logs.

## 4. Chronological split protocol

The default 36-month snapshot is sorted by `date_received` and split by whole calendar months:

| Partition | Default share | Purpose |
| --- | --- | --- |
| Fit | First 24 completed months | Fit taxonomy-derived target encoder, text transforms, and candidate model. |
| Calibration and threshold validation | Next 6 completed months | Fit probability calibration and choose routing threshold; do not refit candidate on this partition before final test. |
| Locked test | Most recent 6 completed months | One final comparison of all frozen choices. |

If the snapshot is longer, preserve the last 6 months for test and the preceding 6 for calibration, with older data for fit. If it is shorter, the run fails rather than silently switching to a random split. Rows sharing the boundary month remain in one partition. Deduplication occurs before the split by `complaint_id`; duplicate or near-duplicate analysis is reported as a leakage risk.

## 5. Candidate models

| Candidate | Role | Why it is included |
| --- | --- | --- |
| Word and character TF-IDF + multinomial Logistic Regression | Required baseline | Fast, interpretable, robust to spelling/redaction variants, and produces usable class probabilities. |
| Sentence embeddings + regularized linear classifier | Improved candidate | Tests whether semantic representation improves rare/lexically variable classes. Embeddings must be locally runnable or cached with full model/version provenance. |
| TF-IDF + linear SVM + probability calibration | Alternative improved candidate | Efficient high-dimensional text classifier; evaluated if embedding runtime/quality is not suitable. |
| Jev typed choice on masked text | Optional external benchmark | Compares a zero-shot decision model against trained local models; never the production decision owner. |

At least one improved local candidate must be compared against the baseline. All candidates use identical targets, split boundaries, and evaluation metrics. The selected candidate is the simplest model that meets the decision criteria below; a more complex model cannot win solely on marginal macro-F1.

## 6. Probability calibration

Calibration uses only the chronological calibration partition. The method is selected from sigmoid and isotonic calibration based on calibration-partition Brier score, expected calibration error (ECE), reliability curve, and class support. The selected calibration method and its fitted artifact are frozen before test evaluation.

Jev-provided probabilities are treated as unverified estimates. If Jev is benchmarked, it receives the same masked test inputs and is evaluated with the same calibration diagnostics; vendor claims do not establish calibration for CFPB complaints.

## 7. Routing threshold and actions

For selected class probability `p`, review cost `C_review`, and incremental wrong-auto-route cost `C_misroute`, the candidate expected error cost is `(1 - p) × C_misroute`. Auto-route is eligible only if this cost is no greater than `C_review` and all safety checks pass.

The project will evaluate cost ratios `C_review:C_misroute` of `1:5`, `1:10`, and `1:20` on the calibration partition. The default policy is the threshold minimizing expected validation cost at `1:10`, subject to these non-negotiable floors:

- selected-class calibrated probability is at or above the chosen threshold;
- validation selective precision for auto-routed cases is at least 0.90;
- class-specific auto-route coverage is not allowed for classes with fewer than 50 calibration examples;
- empty input, PII-guard failure, unsupported label, model load failure, or audit-store failure always becomes human review.

The output action vocabulary is fixed:

| Action | Meaning |
| --- | --- |
| `AUTO_ROUTE` | A suggestion may be shown to an operator; no external ticket is created. |
| `HUMAN_REVIEW_LOW_CONFIDENCE` | Predicted class is below policy confidence/cost requirements. |
| `HUMAN_REVIEW_EMPTY_INPUT` | No usable narrative was supplied. |
| `HUMAN_REVIEW_GUARDRAIL_FAILURE` | PII/safety processing could not complete safely. |
| `HUMAN_REVIEW_SYSTEM_FAILURE` | Model, artifact, or audit dependency failed. |
| `HUMAN_REVIEW_UNSUPPORTED_CLASS` | Taxonomy/model cannot safely cover the input. |

## 8. Evaluation and model-selection criteria

Every candidate report on the locked test set must include:

- macro-F1 as the primary class-imbalance-sensitive metric;
- weighted F1, accuracy, per-class precision/recall/F1/support, and a raw plus normalized confusion matrix;
- Brier score, ECE, and reliability diagram after calibration;
- auto-route coverage, review rate, selective precision, selective macro-F1, and expected cost at all three ratios;
- latency measured locally, model artifact size, and reproducibility configuration;
- error slices for time period, narrative length, redaction density, major/rare class, and submission channel where available.

A model is selected only when it has no regression greater than 0.02 macro-F1 versus baseline, meets the safety floors, is reproducible, and has a documented operational advantage. If no candidate qualifies, the baseline remains selected and the limitation is disclosed.

## 9. Model artifact contract

Each artifact directory contains:

- serialized preprocessing, estimator, and calibration artifact;
- `model-card.json` with model ID, source revision, snapshot ID, partitions, target mapping version, feature settings, random seed, environment/dependency lock reference, and timestamp;
- `evaluation.json` plus machine-readable confusion/calibration data;
- threshold-policy configuration and calibration cost analysis;
- checksum for every serialized file.

The application refuses to load an artifact whose taxonomy mapping version or required files do not match its model card.

## 10. Human-review feedback contract

A reviewer may record final product, optional issue, outcome, and reason code. The correction creates a new immutable event linked to the original `audit_id`. It does not overwrite the original prediction and does not change the active model. A retraining run may use corrections only after data-quality review and a new snapshot/model version are created.

## 11. ML acceptance gates

1. A valid chronological split and lineage manifest exist.
2. Baseline plus at least one improved local candidate are evaluated on the same locked test period.
3. Calibration diagnostics and threshold cost analysis are published.
4. The active model satisfies safety floors or the system is configured for review-only mode.
5. Model card, confusion matrix, and reproducibility instructions are reviewed before the artifact is used by triage.
