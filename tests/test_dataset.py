from datetime import date
from pathlib import Path

from pig_finserv.data.mapping import ProductMappingEntry, TaxonomyMapper
from pig_finserv.modeling.dataset import load_masked_training_dataset
from pig_finserv.safety.pii import PiiMasker


def test_training_loader_masks_restricted_text_and_reports_exclusions(tmp_path: Path) -> None:
    source = tmp_path / "complaints.csv"
    source.write_text(
        "Complaint ID,Date received,Product,Consumer complaint narrative\n"
        "1,2025-01-01,Credit card,Email jane@example.com about billing\n"
        "2,2025-01-02,Unknown product,Not mapped\n"
        "3,2025-01-03,Credit card,\n"
    )
    mapper = TaxonomyMapper(
        (
            ProductMappingEntry(
                effective_start=date(2020, 1, 1),
                effective_end=None,
                source_product="Credit card",
                source_sub_product=None,
                canonical_product="Credit card",
                rationale="test",
                mapping_version="2026.1",
            ),
        )
    )

    dataset = load_masked_training_dataset(
        source_path=source,
        snapshot_id="snapshot",
        taxonomy_mapper=mapper,
        masker=PiiMasker(fingerprint_salt=b"test-salt"),
    )

    assert len(dataset.examples) == 1
    assert "jane@example.com" not in dataset.examples[0].masked_text
    assert dataset.unmapped_product_count == 1
    assert dataset.missing_narrative_count == 1
