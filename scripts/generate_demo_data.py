"""Create ignored, synthetic CFPB-shaped files for a local Pig FinServ demo."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path


def main() -> None:
    """Write a deterministic 36-month demo dataset and reviewed mappings."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    arguments = parser.parse_args()
    output = arguments.output_directory
    output.mkdir(parents=True, exist_ok=True)
    _write_source(output / "cfpb-demo.csv")
    _write_product_mappings(output / "product-mappings.csv")
    _write_company_aliases(output / "company-aliases.csv")


def _write_source(path: Path) -> None:
    headers = (
        "Complaint ID",
        "Date received",
        "Product",
        "Company",
        "Company response to consumer",
        "Timely response?",
        "Issue",
        "Consumer complaint narrative",
    )
    rows: list[dict[str, str]] = []
    for month_offset in range(36):
        year = 2023 + month_offset // 12
        month = month_offset % 12 + 1
        received = date(year, month, 1).isoformat()
        rows.extend(
            (
                {
                    "Complaint ID": f"demo-card-{year}-{month}",
                    "Date received": received,
                    "Product": "Credit card",
                    "Company": "Example Bank",
                    "Company response to consumer": "Closed with explanation",
                    "Timely response?": "Yes",
                    "Issue": "Billing dispute",
                    "Consumer complaint narrative": "credit card billing fee",
                },
                {
                    "Complaint ID": f"demo-mortgage-{year}-{month}",
                    "Date received": received,
                    "Product": "Mortgage",
                    "Company": "Example Bank",
                    "Company response to consumer": "Closed with explanation",
                    "Timely response?": "Yes",
                    "Issue": "Escrow",
                    "Consumer complaint narrative": "mortgage escrow payment",
                },
            )
        )
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_product_mappings(path: Path) -> None:
    path.write_text(
        "effective_start,effective_end,source_product,source_sub_product,canonical_product,"
        "rationale,mapping_version\n"
        "2020-01-01,,Credit card,,Credit card,synthetic demo mapping,2026.1\n"
        "2020-01-01,,Mortgage,,Mortgage,synthetic demo mapping,2026.1\n",
        encoding="utf-8",
    )


def _write_company_aliases(path: Path) -> None:
    path.write_text(
        "company_source,company_canonical,rationale,reviewer,alias_version\n"
        "Example Bank,Example Bank,synthetic demo mapping,demo,2026.1\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
