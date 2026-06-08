from pathlib import Path

import pandas as pd

from scripts.reconcile_analytics_sqlite import reconcile_database
from scripts.validate_pipeline_outputs import build_run_summary, render_markdown
from scripts.build_analytics_sqlite import build_database


def test_pipeline_run_summary_passes_for_curated_outputs() -> None:
    summary = build_run_summary()

    assert summary["status"] == "pass"
    assert summary["failed_count"] == 0
    assert {item["name"] for item in summary["datasets"]} == {
        "gold_risk_neighborhoods",
        "chapter4_city_risk_summary",
        "chapter4_district_risk_summary",
        "chapter4_top_neighborhoods",
    }


def test_pipeline_run_summary_markdown_contains_checks() -> None:
    markdown = render_markdown(build_run_summary())

    assert "ISKI Pipeline Run Summary" in markdown
    assert "city_total_matches_gold_rows" in markdown


def test_sqlite_reconciliation_passes_after_build(tmp_path: Path) -> None:
    output_path = tmp_path / "iski_analytics.db"

    build_database(output_path)
    result = reconcile_database(output_path)

    assert result["status"] == "pass"
    assert result["failed_count"] == 0


def test_top_neighborhoods_source_is_sorted() -> None:
    top = pd.read_csv("outputs/chapter4/en_riskli_mahalleler_top_list.csv", encoding="utf-8-sig")

    assert top["S11_Risk_Skoru_Surekli"].is_monotonic_decreasing
