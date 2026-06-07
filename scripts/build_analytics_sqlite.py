"""Build a local SQLite analytics layer from curated ISKI CSV outputs."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "iski_analytics.db"
VIEW_DIR = PROJECT_ROOT / "sql" / "views"

DATASETS = {
    "gold_risk_neighborhoods": PROJECT_ROOT / "data" / "gold" / "ileri_duzey_senaryolar_mahalle_bazli.csv",
    "chapter4_district_risk_summary": PROJECT_ROOT / "outputs" / "chapter4" / "ilce_risk_ozeti.csv",
    "chapter4_city_risk_summary": PROJECT_ROOT / "outputs" / "chapter4" / "sehir_geneli_risk_ozeti.csv",
    "chapter4_top_neighborhoods": PROJECT_ROOT / "outputs" / "chapter4" / "en_riskli_mahalleler_top_list.csv",
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [column.strip().replace("\ufeff", "") for column in df.columns]
    return df


def write_dataset(conn: sqlite3.Connection, table_name: str, path: Path) -> int:
    df = read_csv(path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    return len(df)


def apply_views(conn: sqlite3.Connection, view_dir: Path = VIEW_DIR) -> list[str]:
    applied: list[str] = []
    for view_path in sorted(view_dir.glob("*.sql")):
        conn.executescript(view_path.read_text(encoding="utf-8"))
        applied.append(view_path.name)
    return applied


def build_database(output_path: Path) -> dict[str, object]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(output_path) as conn:
        table_counts = {
            table_name: write_dataset(conn, table_name, path)
            for table_name, path in DATASETS.items()
        }
        applied_views = apply_views(conn)
        conn.execute("PRAGMA optimize")

    return {
        "database": str(output_path),
        "tables": table_counts,
        "views": applied_views,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="SQLite database output path.",
    )
    return parser.parse_args()


def main() -> None:
    result = build_database(parse_args().output)
    print(f"SQLite database: {result['database']}")
    for table_name, row_count in result["tables"].items():
        print(f"- {table_name}: {row_count} rows")
    print(f"Applied views: {', '.join(result['views'])}")


if __name__ == "__main__":
    main()
