"""Restricted local CSV loading for model training only."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from pig_finserv.data.mapping import TaxonomyMapper
from pig_finserv.data.schema import resolve_schema, validate_rows
from pig_finserv.domain import MappingStatus
from pig_finserv.modeling.split import LabeledNarrative
from pig_finserv.safety.pii import PiiMasker


@dataclass(frozen=True, slots=True)
class TrainingDataset:
    """In-memory masked training examples and explicit coverage exclusions."""

    examples: tuple[LabeledNarrative, ...]
    missing_narrative_count: int
    unmapped_product_count: int
    ambiguous_product_count: int


def load_masked_training_dataset(
    *,
    source_path: Path,
    snapshot_id: str,
    taxonomy_mapper: TaxonomyMapper,
    masker: PiiMasker,
) -> TrainingDataset:
    """Load restricted source data locally without writing narratives to artifacts."""

    with source_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        schema = resolve_schema(reader.fieldnames or [])
        narrative_column = schema.source_column("narrative_restricted")
        if narrative_column is None:
            raise ValueError("source CSV has no supported complaint narrative column")
        validation = validate_rows(tuple(reader), schema=schema, snapshot_id=snapshot_id)

    examples: list[LabeledNarrative] = []
    missing_narrative = 0
    unmapped = 0
    ambiguous = 0
    for record in validation.records:
        if not record.narrative_restricted:
            missing_narrative += 1
            continue
        mapping = taxonomy_mapper.map_product(
            source_product=record.product_source,
            source_sub_product=record.sub_product_source,
            received=record.date_received,
        )
        if mapping.status is MappingStatus.UNMAPPED:
            unmapped += 1
            continue
        if mapping.status is MappingStatus.AMBIGUOUS:
            ambiguous += 1
            continue
        if mapping.canonical_product is None:
            raise ValueError("mapped product has no canonical label")
        examples.append(
            LabeledNarrative(
                complaint_id=record.complaint_id,
                date_received=record.date_received,
                masked_text=masker.mask(record.narrative_restricted).text,
                product_canonical=mapping.canonical_product,
            )
        )
    return TrainingDataset(
        examples=tuple(examples),
        missing_narrative_count=missing_narrative,
        unmapped_product_count=unmapped,
        ambiguous_product_count=ambiguous,
    )
