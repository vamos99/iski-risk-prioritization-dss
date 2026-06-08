"""Reconcile ISKI SQLite analytics views against their source tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from scripts.build_analytics_sqlite import DEFAULT_OUTPUT


def fetch_one(conn: sqlite3.Connection, query: str) -> sqlite3.Row:
    row = conn.execute(query).fetchone()
    if row is None:
        raise ValueError(f"Query returned no rows: {query}")
    return row


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def reconcile_database(database_path: Path) -> dict[str, Any]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row

        city_view = fetch_one(conn, "SELECT * FROM city_risk_summary")
        city_source = fetch_one(conn, "SELECT * FROM chapter4_city_risk_summary")
        district_view = fetch_one(
            conn,
            """
            SELECT
                SUM(neighborhood_count) AS neighborhoods,
                SUM(critical_neighborhoods) AS critical,
                SUM(medium_neighborhoods) AS medium,
                SUM(low_neighborhoods) AS low
            FROM district_risk_summary
            """,
        )
        priority_count = fetch_one(conn, "SELECT COUNT(*) AS rows FROM risk_priority_neighborhoods")
        gold_count = fetch_one(conn, "SELECT COUNT(*) AS rows FROM gold_risk_neighborhoods")

    checks = [
        check(
            "city_view_matches_city_source_total",
            int(city_view["total_neighborhoods"]) == int(city_source["toplam_mahalle"]),
            f"view={city_view['total_neighborhoods']} source={city_source['toplam_mahalle']}",
        ),
        check(
            "district_view_totals_match_city_view",
            int(district_view["neighborhoods"]) == int(city_view["total_neighborhoods"]),
            f"district={district_view['neighborhoods']} city={city_view['total_neighborhoods']}",
        ),
        check(
            "district_risk_bands_match_city_view",
            int(district_view["critical"]) == int(city_view["critical_neighborhoods"])
            and int(district_view["medium"]) == int(city_view["medium_neighborhoods"])
            and int(district_view["low"]) == int(city_view["low_neighborhoods"]),
            (
                f"district=({district_view['critical']},{district_view['medium']},{district_view['low']}) "
                f"city=({city_view['critical_neighborhoods']},{city_view['medium_neighborhoods']},{city_view['low_neighborhoods']})"
            ),
        ),
        check(
            "priority_view_matches_gold_rows",
            int(priority_count["rows"]) == int(gold_count["rows"]),
            f"priority_rows={priority_count['rows']} gold_rows={gold_count['rows']}",
        ),
    ]

    failed = [item for item in checks if item["status"] != "pass"]
    return {
        "database": str(database_path),
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_count": len(failed),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_OUTPUT, help="SQLite database path.")
    return parser.parse_args()


def main() -> None:
    result = reconcile_database(parse_args().database)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
