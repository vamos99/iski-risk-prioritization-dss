"""Validate curated ISKI pipeline outputs and write a compact run summary."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    path: Path
    required_columns: tuple[str, ...]
    min_rows: int = 1


DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        name="gold_risk_neighborhoods",
        path=PROJECT_ROOT / "data" / "gold" / "ileri_duzey_senaryolar_mahalle_bazli.csv",
        required_columns=(
            "anahtar",
            "ilce",
            "mahalle",
            "S11_Risk_Seviyesi",
            "S11_Risk_Skoru_Surekli",
            "S11_PoF_Skor",
            "S11_CoF_Skor",
        ),
        min_rows=100,
    ),
    DatasetSpec(
        name="chapter4_city_risk_summary",
        path=PROJECT_ROOT / "outputs" / "chapter4" / "sehir_geneli_risk_ozeti.csv",
        required_columns=(
            "toplam_mahalle",
            "kritik_adet",
            "orta_adet",
            "dusuk_adet",
            "kritik_oran",
            "ortalama_surekli_risk",
            "medyan_surekli_risk",
        ),
    ),
    DatasetSpec(
        name="chapter4_district_risk_summary",
        path=PROJECT_ROOT / "outputs" / "chapter4" / "ilce_risk_ozeti.csv",
        required_columns=(
            "ilce",
            "mahalle_sayisi",
            "ortalama_surekli_risk",
            "ortalama_pof",
            "ortalama_cof",
            "kirmizi_adet",
            "sari_adet",
            "yesil_adet",
            "kirmizi_oran",
        ),
        min_rows=10,
    ),
    DatasetSpec(
        name="chapter4_top_neighborhoods",
        path=PROJECT_ROOT / "outputs" / "chapter4" / "en_riskli_mahalleler_top_list.csv",
        required_columns=(
            "anahtar",
            "ilce",
            "mahalle",
            "S11_Risk_Seviyesi",
            "S11_Risk_Skoru_Surekli",
            "S11_PoF_Skor",
            "S11_CoF_Skor",
        ),
        min_rows=10,
    ),
)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def inspect_dataset(spec: DatasetSpec) -> tuple[dict[str, Any], pd.DataFrame | None]:
    if not spec.path.exists():
        return {
            "name": spec.name,
            "path": str(spec.path.relative_to(PROJECT_ROOT)),
            "exists": False,
            "status": "fail",
            "reason": "missing_file",
        }, None

    df = read_csv(spec.path)
    missing_columns = [column for column in spec.required_columns if column not in df.columns]
    row_count = int(len(df))
    modified_at = datetime.fromtimestamp(spec.path.stat().st_mtime, timezone.utc).isoformat()
    status = "pass" if row_count >= spec.min_rows and not missing_columns else "fail"

    return {
        "name": spec.name,
        "path": str(spec.path.relative_to(PROJECT_ROOT)),
        "exists": True,
        "rows": row_count,
        "columns": len(df.columns),
        "required_columns": list(spec.required_columns),
        "missing_columns": missing_columns,
        "modified_at": modified_at,
        "status": status,
    }, df


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def build_cross_checks(dataframes: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    gold = dataframes.get("gold_risk_neighborhoods")
    city = dataframes.get("chapter4_city_risk_summary")
    district = dataframes.get("chapter4_district_risk_summary")
    top = dataframes.get("chapter4_top_neighborhoods")

    if gold is not None:
        duplicate_keys = int(gold["anahtar"].duplicated().sum()) if "anahtar" in gold.columns else -1
        checks.append(check("gold_keys_unique", duplicate_keys == 0, f"duplicate_keys={duplicate_keys}"))

    if gold is not None and city is not None and not city.empty:
        city_total = int(city.iloc[0]["toplam_mahalle"])
        checks.append(
            check(
                "city_total_matches_gold_rows",
                city_total == len(gold),
                f"city_total={city_total} gold_rows={len(gold)}",
            )
        )

    if city is not None and district is not None and not city.empty:
        district_total = int(district["mahalle_sayisi"].sum())
        city_total = int(city.iloc[0]["toplam_mahalle"])
        checks.append(
            check(
                "district_total_matches_city_total",
                district_total == city_total,
                f"district_total={district_total} city_total={city_total}",
            )
        )

        risk_total = int(
            district["kirmizi_adet"].sum()
            + district["sari_adet"].sum()
            + district["yesil_adet"].sum()
        )
        checks.append(
            check(
                "district_risk_counts_match_city_total",
                risk_total == city_total,
                f"district_risk_total={risk_total} city_total={city_total}",
            )
        )

    if gold is not None and top is not None:
        gold_keys = set(gold["anahtar"].dropna().astype(str))
        top_keys = set(top["anahtar"].dropna().astype(str))
        missing_top_keys = sorted(top_keys - gold_keys)
        checks.append(
            check(
                "top_neighborhoods_subset_of_gold",
                not missing_top_keys,
                f"missing_top_keys={len(missing_top_keys)}",
            )
        )

        sorted_desc = top["S11_Risk_Skoru_Surekli"].is_monotonic_decreasing
        checks.append(
            check(
                "top_neighborhoods_sorted_by_risk",
                bool(sorted_desc),
                f"rows={len(top)}",
            )
        )

    return checks


def build_run_summary() -> dict[str, Any]:
    dataset_results = []
    dataframes: dict[str, pd.DataFrame] = {}

    for spec in DATASETS:
        result, df = inspect_dataset(spec)
        dataset_results.append(result)
        if df is not None and result["status"] == "pass":
            dataframes[spec.name] = df

    cross_checks = build_cross_checks(dataframes)
    all_checks = dataset_results + cross_checks
    failed = [item for item in all_checks if item.get("status") != "pass"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not failed else "fail",
        "datasets": dataset_results,
        "checks": cross_checks,
        "failed_count": len(failed),
    }


def write_summary(summary: dict[str, Any], summary_output: Path | None, report_output: Path | None) -> None:
    if summary_output:
        summary_output.parent.mkdir(parents=True, exist_ok=True)
        summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if report_output:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(render_markdown(summary), encoding="utf-8")


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# ISKI Pipeline Run Summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Failed checks: `{summary['failed_count']}`",
        "",
        "## Datasets",
        "",
        "| Dataset | Rows | Status | Modified At |",
        "| --- | ---: | --- | --- |",
    ]

    for item in summary["datasets"]:
        rows = item.get("rows", "n/a")
        lines.append(
            f"| {item['name']} | {rows} | {item['status']} | {item.get('modified_at', 'n/a')} |"
        )

    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for item in summary["checks"]:
        lines.append(f"| {item['name']} | {item['status']} | {item['detail']} |")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-output", type=Path, help="Optional JSON summary output path.")
    parser.add_argument("--report-output", type=Path, help="Optional Markdown summary output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_run_summary()
    write_summary(summary, args.summary_output, args.report_output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
