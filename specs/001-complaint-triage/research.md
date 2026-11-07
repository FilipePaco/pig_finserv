# Research Notes: external data contract and evidence policy

**Status:** Initial fact check completed 2026-11-06; revisit immediately before ingestion.

## Confirmed from first-party CFPB sources

| Topic | Finding | Design consequence |
| --- | --- | --- |
| Data availability | The CFPB makes published complaint data available for download and through its API. | Support both reproducible bulk snapshot ingestion and a bounded API mode; persist acquisition metadata. |
| Publication scope | Published complaints are those sent to companies, after response/relationship confirmation or 15 days; referrals to some other regulators are not published. | State coverage limitations in every data card/report; do not describe the dataset as all complaints or all consumer experiences. |
| Representativeness | The CFPB says the database is not a statistical sample of marketplace experiences. | Do not make population-prevalence claims from volume/trend output. |
| Volume comparisons | CFPB advises considering company size and market share when interpreting company complaint volume. | Show count and selected-product share; explicitly withhold customer-base normalized ranking without a valid denominator. |
| Field semantics | `Product` and `Issue` are categorical; issue values depend on product. `Timely response?` is a yes/no field; `Company response to consumer` is categorical. | Train product first; only implement issue as product-conditional/bonus. Use the documented denominators in the spec. |
| Taxonomy history | CFPB preserves selections that were valid at submission time and documents updates in 2017, 2023, and 2026. The current 2026 form revision began 2026-10-29. | Taxonomy mapping must be date-aware and versioned; do not overwrite original labels. |
| Regulatory evidence | CFPB hosts a filterable enforcement-actions index with filed dates and case pages. | CFPB is the preferred primary source for official enforcement context; cite page/date and characterize only what the source says. |

## Sources

- [CFPB Consumer Complaint Database overview](https://www.consumerfinance.gov/data-research/consumer-complaints/) — availability, publication scope, representativeness, company-size caution, and taxonomy-update links.
- [CFPB API field reference](https://cfpb.github.io/api/ccdb/fields.html) — published field definitions.
- [CFPB 2026 product and issue options](https://files.consumerfinance.gov/f/documents/cfpb_consumer-complaint-form-product-issue-options_2026.pdf) — effective date and current taxonomy context.
- [CFPB enforcement actions](https://www.consumerfinance.gov/enforcement/actions/) — primary-source index for enforcement material.
- [Jev decision API documentation](https://jev-ai.org/docs/) — typed choice/yes-no/score decisions, probability responses, and provider API contract.

## To verify during implementation (not assumptions)

1. Current API query syntax, pagination limits, response shape, rate limits, and reliability for the selected time range.
2. Exact bulk-file columns and types in the downloaded snapshot, including whether narrative availability and response fields align with the current field reference.
3. The historical mappings required for the actually selected data window, including split/moved labels; mappings must be reviewed, not inferred by an LLM.
4. License/terms and retention limits for any non-CFPB news/search provider.
5. Provider privacy, retention, and commercial terms for Gemini, Jev, and any configured news-search adapter before any live call. Jev is an optional masked-text benchmark only.

## Evidence policy refined from this research

- Prefer first-party CFPB sources for CFPB actions, taxonomy, and complaint data context.
- Record publication date separately from retrieval date; use neither undated snippets nor snippets outside the configured lookback period as report evidence.
- A cited event can be presented as external context. It cannot be presented as the cause of a complaint trend without a separately supported causal analysis, which is out of scope.
- If an external source names an organization, reuse only attributable, neutral wording and do not merge that identity with a CFPB company row unless an approved canonicalization record supports it.
