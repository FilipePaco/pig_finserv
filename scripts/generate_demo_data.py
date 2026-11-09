"""Create ignored, synthetic CFPB-shaped files for a local Pig FinServ demo."""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path


def main() -> None:
    """Write a deterministic 36-month demo dataset and reviewed mappings."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    arguments = parser.parse_args()
    create_demo_data(arguments.output_directory)


def create_demo_data(output: Path) -> None:
    """Write the deterministic fictional complaint scenario to an ignored directory."""

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
    for month_offset in range(33):
        year = 2023 + month_offset // 12
        month = month_offset % 12 + 1
        received = date(year, month, 1)
        _add_cards(rows, received_dates=(received,) * 8, current_period=False)
        _add_mortgages(rows, received, count=8)

    prior_start = date(2025, 10, 3)
    _add_cards(
        rows,
        received_dates=tuple(prior_start + timedelta(days=index % 30) for index in range(40)),
        current_period=False,
    )
    current_start = date(2025, 11, 2)
    _add_cards(
        rows,
        received_dates=tuple(current_start + timedelta(days=index % 30) for index in range(120)),
        current_period=True,
    )
    for received in (date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)):
        _add_mortgages(rows, received, count=8)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _add_cards(
    rows: list[dict[str, str]], *, received_dates: tuple[date, ...], current_period: bool
) -> None:
    companies = (
        ("Northstar Bank",) * 70 + ("Harbor Financial",) * 30 + ("Summit Credit",) * 20
        if current_period
        else ("Northstar Bank", "Harbor Financial", "Summit Credit", "Northstar Bank")
    )
    issues = (
        ("Duplicate charge",) * 75
        + ("Billing statement",) * 25
        + ("Card payment fee",) * 12
        + ("Payment pending",) * 8
        if current_period
        else ("Billing statement", "Duplicate charge", "Card payment fee", "Payment pending")
    )
    responses = (
        ("Closed with explanation",) * 75
        + ("In progress",) * 30
        + ("Closed with monetary relief",) * 15
        if current_period
        else ("Closed with explanation",) * 3 + ("In progress",)
    )
    timely_yes_count = 86 if current_period else max(1, len(received_dates) - 2)
    for index, received in enumerate(received_dates):
        issue = issues[index % len(issues)]
        rows.append(
            {
                "Complaint ID": f"demo-card-{len(rows) + 1}",
                "Date received": received.isoformat(),
                "Product": "Credit card",
                "Company": companies[index % len(companies)],
                "Company response to consumer": responses[index % len(responses)],
                "Timely response?": "Yes" if index < timely_yes_count else "No",
                "Issue": issue,
                "Consumer complaint narrative": f"credit card {issue.casefold()} billing concern",
            }
        )


def _add_mortgages(rows: list[dict[str, str]], received: date, *, count: int) -> None:
    for index in range(count):
        rows.append(
            {
                "Complaint ID": f"demo-mortgage-{len(rows) + 1}",
                "Date received": received.isoformat(),
                "Product": "Mortgage",
                "Company": "Harbor Financial" if index % 2 else "Summit Credit",
                "Company response to consumer": "Closed with explanation",
                "Timely response?": "Yes",
                "Issue": "Escrow",
                "Consumer complaint narrative": "mortgage escrow payment concern",
            }
        )


def _write_product_mappings(path: Path) -> None:
    path.write_text(
        "effective_start,effective_end,source_product,source_sub_product,canonical_product,"
        "rationale,mapping_version\n"
        "2020-01-01,,Credit card,,Credit card,fictional demo mapping,2026.1\n"
        "2020-01-01,,Mortgage,,Mortgage,fictional demo mapping,2026.1\n",
        encoding="utf-8",
    )


def _write_company_aliases(path: Path) -> None:
    path.write_text(
        "company_source,company_canonical,rationale,reviewer,alias_version\n"
        "Northstar Bank,Northstar Bank,fictional demo mapping,demo,2026.1\n"
        "Harbor Financial,Harbor Financial,fictional demo mapping,demo,2026.1\n"
        "Summit Credit,Summit Credit,fictional demo mapping,demo,2026.1\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
