"""Local Streamlit operator console for bounded Pig FinServ workflows."""

from __future__ import annotations

import csv
from io import StringIO

import streamlit as st

from pig_finserv.domain import ReviewOutcome
from pig_finserv.ui.configuration import UiConfiguration, UiConfigurationError
from pig_finserv.ui.presentation import triage_view
from pig_finserv.ui.services import UiOperationError, UiServices
from pig_finserv.workflows import ReportWorkflowResult


def main() -> None:
    """Render the local-only application shell and one bounded workflow page."""

    st.set_page_config(page_title="Pig FinServ", page_icon="🐖", layout="wide")
    st.title("Pig FinServ")
    st.caption("Local complaint triage and insights proof of concept")
    st.warning(
        "PoC safety notice: outputs are operator suggestions, not customer decisions. "
        "Follow the displayed human-review action. Do not expose this unauthenticated app publicly."
    )
    services = UiServices(UiConfiguration.from_environment())
    page = st.sidebar.radio("Workflow", ("Demo guide", "Triage", "Insights", "Review", "Audit"))
    if page == "Demo guide":
        _render_demo_guide()
    elif page == "Triage":
        _render_triage(services)
    elif page == "Insights":
        _render_insights(services)
    elif page == "Review":
        _render_review(services)
    else:
        _render_audit(services)


def _render_demo_guide() -> None:
    """Present a concise, explicitly fictional interview walkthrough."""

    st.header("Interview demo guide")
    st.info(
        "All companies, complaints, and metrics in this walkthrough are fictional "
        "synthetic data. They do not describe a real bank or CFPB records."
    )
    st.subheader("1. Customer protection")
    st.write(
        "In Triage, submit the fictional narrative below. The local PII guard masks the "
        "email-shaped value before model inference and audit persistence. The result is "
        "a proposal, not an automatic customer outcome."
    )
    st.code(
        "My credit card was charged twice for a subscription. Please contact me at "
        "case@example.test.",
        language=None,
    )
    st.subheader("2. Operations signal")
    current, change, timely = st.columns(3)
    current.metric("Current credit-card complaints", "120", "80 more than prior period")
    change.metric("Volume change", "+200%", "120 current vs 40 previous")
    timely.metric("Timely response rate", "71.7%", "86 of 120 known responses")
    st.write(
        "In Insights, choose **Credit card** and **2025-12-01**. The report shows "
        "Duplicate charge as the leading issue and Northstar Bank with 70 complaints."
    )
    st.subheader("3. Responsible bank action")
    st.write(
        "An operations analyst can prioritize the billing-dispute queue, investigate "
        "response capacity, and append a human correction when appropriate. The evidence "
        "does **not** prove that Northstar caused the increase or is worse than peers: "
        "complaint counts are not normalized by customer base and do not establish causality."
    )
    st.caption(
        "Suggested closing: “The value is not an autonomous decision. It makes a safe "
        "customer-routing proposal auditable and turns complaint operations into a "
        "measurable, reviewable workflow.”"
    )


def _render_triage(services: UiServices) -> None:
    st.header("Triage")
    st.write("Submit one complaint for a local, masked routing proposal.")
    with st.form("triage-form", clear_on_submit=True):
        narrative = st.text_area(
            "Complaint narrative",
            help="The narrative is processed in memory and cleared after submission.",
            max_chars=10_000,
        )
        submitted = st.form_submit_button("Run triage")
    if not submitted:
        return
    try:
        result = triage_view(services.triage(narrative))
    except (UiConfigurationError, UiOperationError) as exc:
        st.error(str(exc))
        return
    if result.requires_human_review:
        st.warning(f"{result.action}: human review is required before any follow-up.")
    else:
        st.success("AUTO_ROUTE is a proposal only; confirm it in the approved operating process.")
    left, right = st.columns(2)
    left.metric("Confidence", result.confidence_percent)
    left.write(f"**Proposed product:** {result.predicted_product or 'Not available'}")
    right.write(f"**Audit ID:** `{result.audit_id}`")
    right.write(f"**PII guard:** {result.guardrail_status}")
    st.caption(f"Reason code: {result.reason_code}")


def _render_insights(services: UiServices) -> None:
    st.header("Insights")
    st.write("Generate deterministic product metrics. External commentary is off by default.")
    try:
        products = services.report_products()
        _, latest = services.report_bounds()
    except (UiConfigurationError, UiOperationError) as exc:
        st.info(str(exc))
        return
    with st.form("insights-form"):
        product = st.selectbox("Canonical product", products)
        as_of_date = st.date_input("As-of date", value=latest, max_value=latest)
        include_context = st.checkbox("Include optional external context", value=False)
        submitted = st.form_submit_button("Generate report")
    if not submitted:
        return
    try:
        result = services.report(
            product=product,
            as_of_date=as_of_date,
            include_external_context=include_context,
        )
    except (UiConfigurationError, UiOperationError) as exc:
        st.error(str(exc))
        return
    _render_report(result)


def _render_report(result: ReportWorkflowResult) -> None:
    metrics = result.metrics
    st.subheader(f"{metrics.product} report")
    current, previous, timely = st.columns(3)
    current.metric("Current complaints", metrics.current_count)
    previous.metric("Previous complaints", metrics.previous_count)
    timely_rate = (
        f"{metrics.timely_response_rate:.1%}"
        if metrics.timely_response_rate is not None
        else "N/A"
    )
    timely.metric("Timely response rate", timely_rate)
    st.caption(
        "Timely-response denominator: complaints with a known Yes/No timely-response value. "
        "Company volume is not normalized by customer base."
    )
    for title, rows in (
        ("Company response distribution", result.metrics.response_distribution),
        ("Top issues", result.metrics.top_issues),
        ("Top companies", result.metrics.top_companies),
        ("Daily complaints", result.metrics.daily_counts),
        ("Monthly complaints", result.metrics.monthly_counts),
    ):
        _render_table(title, rows)
    st.image(
        list(result.chart_paths),
        caption=["Daily complaint trend", "Monthly complaint trend"],
    )
    if result.commentary:
        st.subheader("Optional commentary")
        st.write(result.commentary.headline)
        for observation in result.commentary.observations:
            st.write(f"- {observation}")
    if result.evidence_sources:
        st.subheader("Vetted external context")
        for source in result.evidence_sources:
            st.link_button(
                f"{source.title} — {source.publisher} ({source.publication_date.isoformat()})",
                source.url,
            )
    else:
        st.info("No external context was included; deterministic metrics remain available.")


def _render_table(title: str, rows: tuple[tuple[object, int], ...]) -> None:
    values = [{"Value": str(value), "Count": count} for value, count in rows]
    st.subheader(title)
    st.dataframe(values, hide_index=True, use_container_width=True)
    st.download_button(
        f"Download {title.lower()} CSV",
        data=_csv(rows),
        file_name=f"{title.lower().replace(' ', '-')}.csv",
        mime="text/csv",
    )


def _csv(rows: tuple[tuple[object, int], ...]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(("value", "count"))
    writer.writerows(rows)
    return buffer.getvalue()


def _render_review(services: UiServices) -> None:
    st.header("Review")
    st.write("Append an immutable human correction to an existing audit event.")
    try:
        products = services.report_products()
    except (UiConfigurationError, UiOperationError) as exc:
        st.info(str(exc))
        return
    with st.form("review-form", clear_on_submit=True):
        audit_id = st.text_input("Audit ID")
        product = st.selectbox("Corrected product", products)
        issue = st.text_input("Corrected issue (optional)")
        outcome = st.selectbox("Review outcome", tuple(ReviewOutcome))
        reason_code = st.selectbox(
            "Reason code", ("ANALYST_CONFIRMED", "ANALYST_CORRECTION", "UNSUPPORTED_LABEL")
        )
        submitted = st.form_submit_button("Record review")
    if not submitted:
        return
    try:
        review_id = services.append_review(
            audit_id=audit_id,
            corrected_product=product,
            corrected_issue=issue or None,
            outcome=outcome,
            reason_code=reason_code,
        )
    except UiOperationError as exc:
        st.error(str(exc))
        return
    st.success(f"Immutable review event recorded: `{review_id}`")


def _render_audit(services: UiServices) -> None:
    st.header("Audit")
    st.write("Inspect a sanitized event or verify the local hash chain.")
    audit_id = st.text_input("Audit ID to inspect")
    inspect = st.button("Inspect sanitized event")
    verify = st.button("Verify audit integrity")
    if inspect:
        try:
            event = services.audit_event(audit_id)
        except UiOperationError as exc:
            st.error(str(exc))
        else:
            if event is None:
                st.info("No audit event was found.")
            else:
                st.json(event)
    if verify:
        try:
            event_count = services.verify_audit()
        except UiOperationError as exc:
            st.error(str(exc))
        else:
            st.success(f"Audit integrity verified for {event_count} event(s).")


if __name__ == "__main__":
    main()
