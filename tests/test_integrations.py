from datetime import date

import pytest

from pig_finserv.integrations import (
    EvidenceSource,
    _parse_json_ld_articles,
    validate_commentary,
    validate_evidence_sources,
)


def _source(source_id: str, url: str) -> EvidenceSource:
    return EvidenceSource(source_id, url, "CFPB", date(2026, 1, 1), "Title", "Bounded excerpt")


def test_evidence_validator_keeps_only_bounded_allowlisted_unique_sources() -> None:
    accepted = validate_evidence_sources(
        (
            _source("cfpb-1", "https://www.consumerfinance.gov/about-us/newsroom/example"),
            _source("duplicate", "https://www.consumerfinance.gov/about-us/newsroom/example"),
            _source("other", "https://untrusted.example/article"),
        ),
        allowed_domains=frozenset({"www.consumerfinance.gov"}),
    )

    assert accepted == (_source("cfpb-1", "https://www.consumerfinance.gov/about-us/newsroom/example"),)


def test_commentary_validator_rejects_unknown_citations_and_claims() -> None:
    payload = {
        "headline": "Draft",
        "observations": ["metric.current_count increased"],
        "contextual_notes": ["source-1 reported context"],
        "limitations": ["Scope is limited."],
        "citation_ids": ["source-1"],
    }
    commentary = validate_commentary(
        payload, metric_ids=frozenset({"metric.current_count"}), source_ids=frozenset({"source-1"})
    )

    assert commentary.headline == "Draft"
    payload["contextual_notes"] = ["source-1 proves wrongdoing"]
    with pytest.raises(ValueError, match="prohibited"):
        validate_commentary(
            payload,
            metric_ids=frozenset({"metric.current_count"}),
            source_ids=frozenset({"source-1"}),
        )


def test_cfpb_json_ld_parser_extracts_only_complete_articles() -> None:
    document = """
    <script type="application/ld+json">
    {"@graph": [{"@type": "NewsArticle", "datePublished": "2026-10-01",
    "url": "https://www.consumerfinance.gov/about-us/newsroom/example/",
    "headline": "Example", "description": "Context",
    "publisher": {"name": "CFPB"}}, {"@type": "Organization"}]}
    </script>
    """

    articles = _parse_json_ld_articles(document)

    assert articles[0].source_id == "cfpb-1"
    assert articles[0].publication_date == date(2026, 10, 1)
