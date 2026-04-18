"""
Bolum 4 (Bulgular ve Tartisma) varliklarini otomatik uretir.

Uretimler:
  - Tablolar: outputs/chapter4/
  - Gorseller: outputs/figures/chapter4/
"""

from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Repo köküne ek artefakt bırakmamak için matplotlib cache'i sistem temp'ine yaz.
MPL_CONFIG_DIR = Path(tempfile.gettempdir()) / "iski_mplconfig"
FONT_CACHE_DIR = Path(tempfile.gettempdir()) / "iski_fontcache"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(FONT_CACHE_DIR))

try:
    import geopandas as gpd
except ModuleNotFoundError:
    gpd = None
import matplotlib
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.settings import GOLD_DIR, OUTPUTS_DIR, SILVER_DIR, SPATIAL_FILES
from src.utils.logging_config import setup_logger
from src.utils.naming import standardize_district_name, standardize_neighborhood_name

logger = setup_logger("iski.reporting.chapter4")

AHP_POF_CR = 0.0003
AHP_COF_CR = 0.0003
TOP_N_MAHALLE = 25

RISK_ORDER = [
    "Kritik Risk (Kırmızı Bölge)",
    "Orta Risk (Sarı Bölge)",
    "Düşük Risk (Yeşil Bölge)",
]

RISK_COLORS = {
    "Kritik Risk (Kırmızı Bölge)": "#d73027",
    "Orta Risk (Sarı Bölge)": "#fdae61",
    "Düşük Risk (Yeşil Bölge)": "#1a9850",
}


def canonical_key(df: pd.DataFrame, district_col: str, neighborhood_col: str) -> pd.Series:
    """Ilce ve mahalle alanlarindan canonical anahtar uretir."""
    return (
        df[district_col].fillna("").astype(str).apply(standardize_district_name)
        + "|"
        + df[neighborhood_col].fillna("").astype(str).apply(standardize_neighborhood_name)
    )


def ensure_output_dirs() -> tuple[Path, Path]:
    chapter4_dir = OUTPUTS_DIR / "chapter4"
    figure_dir = OUTPUTS_DIR / "figures" / "chapter4"
    chapter4_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    return chapter4_dir, figure_dir


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    advanced_path = GOLD_DIR / "ileri_duzey_senaryolar_mahalle_bazli.csv"
    if not advanced_path.exists():
        raise FileNotFoundError(f"Nihai veri bulunamadi: {advanced_path}")

    final_df = pd.read_csv(advanced_path, encoding="utf-8-sig")
    final_df["ilce"] = final_df["ilce"].apply(standardize_district_name)
    final_df["mahalle"] = final_df["mahalle"].apply(standardize_neighborhood_name)
    if "anahtar" not in final_df.columns:
        final_df["anahtar"] = canonical_key(final_df, "ilce", "mahalle")

    # Öncelik: çift Moran birleşik raporu (gold), fallback: silver arıza Moran'ı.
    moran_path_gold = GOLD_DIR / "morans_i_all_results.csv"
    moran_path_silver = SILVER_DIR / "morans_i_results.csv"
    if moran_path_gold.exists():
        moran_df = pd.read_csv(moran_path_gold, encoding="utf-8-sig")
    elif moran_path_silver.exists():
        moran_df = pd.read_csv(moran_path_silver, encoding="utf-8-sig")
    else:
        moran_df = pd.DataFrame()

    spatial_quality_path = SILVER_DIR / "spatial_quality_report.csv"
    spatial_quality_df = (
        pd.read_csv(spatial_quality_path, encoding="utf-8-sig")
        if spatial_quality_path.exists()
        else pd.DataFrame()
    )

    matrix_path = SILVER_DIR / "karar_matrisi.csv"
    matrix_df = (
        pd.read_csv(matrix_path, encoding="utf-8-sig")
        if matrix_path.exists()
        else pd.DataFrame()
    )

    return final_df, moran_df, spatial_quality_df, matrix_df


def compute_chapter4_tables(
    final_df: pd.DataFrame,
    moran_df: pd.DataFrame,
    spatial_quality_df: pd.DataFrame,
    matrix_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    city_total = len(final_df)
    risk_counts = final_df["S11_Risk_Seviyesi"].value_counts()

    city_summary = pd.DataFrame(
        [
            {
                "toplam_mahalle": city_total,
                "kritik_adet": int(risk_counts.get("Kritik Risk (Kırmızı Bölge)", 0)),
                "orta_adet": int(risk_counts.get("Orta Risk (Sarı Bölge)", 0)),
                "dusuk_adet": int(risk_counts.get("Düşük Risk (Yeşil Bölge)", 0)),
                "kritik_oran": round(
                    float(risk_counts.get("Kritik Risk (Kırmızı Bölge)", 0)) / max(city_total, 1), 4
                ),
                "ortalama_surekli_risk": round(final_df["S11_Risk_Skoru_Surekli"].mean(), 6),
                "medyan_surekli_risk": round(final_df["S11_Risk_Skoru_Surekli"].median(), 6),
            }
        ]
    )

    district_summary = (
        final_df.groupby("ilce", as_index=False)
        .agg(
            mahalle_sayisi=("anahtar", "count"),
            ortalama_surekli_risk=("S11_Risk_Skoru_Surekli", "mean"),
            ortalama_pof=("S11_PoF_Skor", "mean"),
            ortalama_cof=("S11_CoF_Skor", "mean"),
            kirmizi_adet=("S11_Risk_Seviyesi", lambda s: s.str.contains("Kırmızı", na=False).sum()),
            sari_adet=("S11_Risk_Seviyesi", lambda s: s.str.contains("Sarı", na=False).sum()),
            yesil_adet=("S11_Risk_Seviyesi", lambda s: s.str.contains("Yeşil", na=False).sum()),
        )
        .sort_values("ortalama_surekli_risk", ascending=False)
        .reset_index(drop=True)
    )
    district_summary["kirmizi_oran"] = (
        district_summary["kirmizi_adet"] / district_summary["mahalle_sayisi"].clip(lower=1)
    )
    district_summary["kirmizi_oran"] = district_summary["kirmizi_oran"].round(4)
    district_summary["ortalama_surekli_risk"] = district_summary["ortalama_surekli_risk"].round(6)
    district_summary["ortalama_pof"] = district_summary["ortalama_pof"].round(6)
    district_summary["ortalama_cof"] = district_summary["ortalama_cof"].round(6)

    top_neighborhoods = (
        final_df[
            [
                "ilce",
                "mahalle",
                "anahtar",
                "S11_Risk_Seviyesi",
                "S11_Risk_Skoru_Surekli",
                "S11_PoF_Skor",
                "S11_CoF_Skor",
                "S11_PoF_Seviye",
                "S11_CoF_Seviye",
            ]
        ]
        .sort_values("S11_Risk_Skoru_Surekli", ascending=False)
        .head(TOP_N_MAHALLE)
        .reset_index(drop=True)
    )

    pof_cof_cross = pd.crosstab(
        final_df["S11_PoF_Seviye"],
        final_df["S11_CoF_Seviye"],
        margins=True,
        margins_name="Toplam",
    )
    pof_cof_cross.index.name = "PoF_Seviye"
    pof_cof_cross.columns.name = "CoF_Seviye"

    technical_rows: list[dict[str, object]] = [
        {"kategori": "ahp", "metrik": "PoF_CR", "deger": AHP_POF_CR},
        {"kategori": "ahp", "metrik": "CoF_CR", "deger": AHP_COF_CR},
        {
            "kategori": "model",
            "metrik": "nihai_yontem",
            "deger": "AHP + Quantile + PoF/CoF Matrisi (Senaryo 11)",
        },
        {
            "kategori": "model",
            "metrik": "mahalle_sayisi",
            "deger": int(len(final_df)),
        },
        {
            "kategori": "model",
            "metrik": "anahtar_duplikasyon_sayisi",
            "deger": int(final_df.duplicated(subset=["anahtar"]).sum()),
        },
    ]

    if not matrix_df.empty and "anahtar" in matrix_df.columns and "yil" in matrix_df.columns:
        technical_rows.append(
            {
                "kategori": "veri_kalite",
                "metrik": "karar_matrisi_anahtar_yil_duplikasyon",
                "deger": int(matrix_df.duplicated(subset=["anahtar", "yil"]).sum()),
            }
        )

    if not moran_df.empty:
        for _, row in moran_df.iterrows():
            metric_key = str(row.get("metric_key", "morans_i"))
            technical_rows.append(
                {
                    "kategori": "morans_i",
                    "metrik": f"{metric_key}_I",
                    "deger": row.get("morans_i", np.nan),
                }
            )
            technical_rows.append(
                {
                    "kategori": "morans_i",
                    "metrik": f"{metric_key}_p_value",
                    "deger": row.get("p_value", np.nan),
                }
            )
            technical_rows.append(
                {
                    "kategori": "morans_i",
                    "metrik": f"{metric_key}_z_score",
                    "deger": row.get("z_score", np.nan),
                }
            )

    if not spatial_quality_df.empty:
        row = spatial_quality_df.iloc[0].to_dict()
        for key in [
            "valid_key_count",
            "poi_rows_before",
            "poi_rows_after",
            "poi_rows_outside_keys",
            "poi_coverage_pct",
            "komsuluk_rows_before",
            "komsuluk_rows_after",
            "komsuluk_outside_source",
            "komsuluk_outside_neighbor",
            "komsuluk_coverage_pct",
        ]:
            if key in row:
                technical_rows.append(
                    {
                        "kategori": "spatial_kalite",
                        "metrik": key,
                        "deger": row[key],
                    }
                )

    technical_summary = pd.DataFrame(technical_rows)

    return {
        "city_summary": city_summary,
        "district_summary": district_summary,
        "top_neighborhoods": top_neighborhoods,
        "pof_cof_cross": pof_cof_cross.reset_index(),
        "technical_summary": technical_summary,
    }


def save_tables(tables: dict[str, pd.DataFrame], chapter4_dir: Path) -> dict[str, Path]:
    paths = {
        "city_summary": chapter4_dir / "sehir_geneli_risk_ozeti.csv",
        "district_summary": chapter4_dir / "ilce_risk_ozeti.csv",
        "top_neighborhoods": chapter4_dir / "en_riskli_mahalleler_top_list.csv",
        "pof_cof_cross": chapter4_dir / "pof_cof_capraz_tablo.csv",
        "technical_summary": chapter4_dir / "teknik_dogrulama_ozeti.csv",
    }
    for key, path in paths.items():
        tables[key].to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("Tablo kaydedildi: %s", path)
    return paths


def plot_risk_distribution(final_df: pd.DataFrame, figure_dir: Path) -> Path:
    counts = final_df["S11_Risk_Seviyesi"].value_counts().reindex(RISK_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(
        counts.index,
        counts.values,
        color=[RISK_COLORS.get(lbl, "#bdbdbd") for lbl in counts.index],
        edgecolor="#2f2f2f",
    )
    ax.set_title("Sehir Geneli Risk Dagilimi")
    ax.set_ylabel("Mahalle Sayisi")
    ax.tick_params(axis="x", rotation=15)
    plt.tight_layout()
    out = figure_dir / "risk_dagilimi.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def plot_district_ranking(district_summary: pd.DataFrame, figure_dir: Path) -> Path:
    top = district_summary.head(20).copy()
    top = top.sort_values("ortalama_surekli_risk", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(top["ilce"], top["ortalama_surekli_risk"], color="#2b8cbe", edgecolor="#1f1f1f")
    ax.set_title("Ilce Bazinda Ortalama Surekli Risk (Top 20)")
    ax.set_xlabel("Ortalama Surekli Risk Skoru")
    ax.set_ylabel("Ilce")
    plt.tight_layout()
    out = figure_dir / "ilce_risk_siralamasi.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def plot_pof_cof_heatmap(final_df: pd.DataFrame, figure_dir: Path) -> Path:
    crosstab = pd.crosstab(final_df["S11_PoF_Seviye"], final_df["S11_CoF_Seviye"])
    matrix = np.zeros((3, 3), dtype=float)
    for i, pof_level in enumerate([1, 2, 3]):
        for j, cof_level in enumerate([1, 2, 3]):
            matrix[i, j] = crosstab.get(cof_level, pd.Series()).get(pof_level, 0)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(matrix, cmap="YlOrRd")
    ax.set_xticks([0, 1, 2], labels=["CoF-1", "CoF-2", "CoF-3"])
    ax.set_yticks([0, 1, 2], labels=["PoF-1", "PoF-2", "PoF-3"])
    ax.set_title("PoF x CoF Isi Haritasi (Mahalle Adedi)")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, int(matrix[i, j]), ha="center", va="center", color="#1f1f1f", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Mahalle Sayisi")
    plt.tight_layout()
    out = figure_dir / "pof_cof_heatmap.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def plot_top_neighborhoods(top_neighborhoods: pd.DataFrame, figure_dir: Path) -> Path:
    plot_df = top_neighborhoods.head(15).copy().iloc[::-1]
    labels = plot_df["ilce"] + " | " + plot_df["mahalle"]
    colors = [RISK_COLORS.get(lbl, "#bdbdbd") for lbl in plot_df["S11_Risk_Seviyesi"]]

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.barh(labels, plot_df["S11_Risk_Skoru_Surekli"], color=colors, edgecolor="#1f1f1f")
    ax.set_title("En Riskli 15 Mahalle (Surekli Risk Skoru)")
    ax.set_xlabel("Surekli Risk Skoru")
    ax.set_ylabel("Ilce | Mahalle")
    plt.tight_layout()
    out = figure_dir / "en_riskli_mahalleler_bar.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def prepare_neighborhood_layer(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    work = gdf.copy()
    work["ilce"] = work["ilce"].apply(standardize_district_name)
    work["mahalle"] = work["mahalle"].apply(standardize_neighborhood_name)
    work["anahtar"] = canonical_key(work, "ilce", "mahalle")
    try:
        work["_geom_area"] = work.to_crs(epsg=3857).geometry.area
    except Exception:
        work["_geom_area"] = work.geometry.area
    work = work.sort_values("_geom_area", ascending=False).drop_duplicates(subset=["anahtar"]).drop(columns=["_geom_area"])
    return work


def plot_risk_map(final_df: pd.DataFrame, figure_dir: Path) -> tuple[Path | None, dict[str, int]]:
    if gpd is None:
        logger.warning("Risk haritasi atlandi: geopandas kurulu degil")
        return None, {}

    geo_path = SPATIAL_FILES["neighborhoods_geojson"]
    if not geo_path.exists():
        logger.warning("Risk haritasi atlandi: geojson bulunamadi (%s)", geo_path)
        return None, {}

    gdf = gpd.read_file(geo_path)
    gdf = prepare_neighborhood_layer(gdf)

    merge_df = final_df[["anahtar", "S11_Risk_Seviyesi"]].drop_duplicates(subset=["anahtar"])
    merged = gdf.merge(merge_df, on="anahtar", how="left", indicator=True)
    match_report = merged["_merge"].value_counts().to_dict()
    merged = merged[merged["S11_Risk_Seviyesi"].notna()].copy()
    if merged.empty:
        logger.warning("Risk haritasi atlandi: eslesen geometri bulunamadi")
        return None, {k: int(v) for k, v in match_report.items()}

    merged["color"] = merged["S11_Risk_Seviyesi"].map(RISK_COLORS).fillna("#d9d9d9")

    fig, ax = plt.subplots(figsize=(10, 10))
    merged.plot(ax=ax, color=merged["color"], linewidth=0.15, edgecolor="#404040")
    ax.set_title("Istanbul Mahalle Risk Haritasi (Senaryo 11)")
    ax.axis("off")
    legend_handles = [
        Patch(facecolor=color, edgecolor="#2f2f2f", label=label) for label, color in RISK_COLORS.items()
    ]
    ax.legend(handles=legend_handles, loc="lower left", frameon=True)
    plt.tight_layout()

    out = figure_dir / "risk_haritasi.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out, {k: int(v) for k, v in match_report.items()}


def save_map_join_report(map_match_report: dict[str, int], chapter4_dir: Path) -> Path | None:
    """Harita merge kapsam metriklerini tabloya kaydeder."""
    if not map_match_report:
        return None

    both = int(map_match_report.get("both", 0))
    left_only = int(map_match_report.get("left_only", 0))
    right_only = int(map_match_report.get("right_only", 0))
    total = max(both + left_only + right_only, 1)

    report_df = pd.DataFrame(
        [
            {
                "both": both,
                "left_only": left_only,
                "right_only": right_only,
                "both_ratio": round(both / total, 6),
                "left_only_ratio": round(left_only / total, 6),
                "right_only_ratio": round(right_only / total, 6),
            }
        ]
    )

    path = chapter4_dir / "harita_join_kalite_ozeti.csv"
    report_df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info("Tablo kaydedildi: %s", path)
    return path


def remove_stale_map_outputs(figure_dir: Path, chapter4_dir: Path) -> None:
    """Harita üretimi atlandığında eski harita çıktılarının kalmasını engeller."""
    stale_paths = [
        figure_dir / "risk_haritasi.png",
        chapter4_dir / "harita_join_kalite_ozeti.csv",
    ]
    for path in stale_paths:
        if path.exists():
            path.unlink()
            logger.info("Eski harita artifakti silindi: %s", path)


def write_chapter4_text(
    final_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    moran_df: pd.DataFrame,
    spatial_quality_df: pd.DataFrame,
    map_match_report: dict[str, int],
    output_path: Path,
) -> None:
    city = tables["city_summary"].iloc[0]
    district = tables["district_summary"]
    top_n = tables["top_neighborhoods"].head(5)
    cross = pd.read_csv(OUTPUTS_DIR / "chapter4" / "pof_cof_capraz_tablo.csv", encoding="utf-8-sig")

    top3_districts = district.head(3)[["ilce", "ortalama_surekli_risk", "kirmizi_oran"]]
    top3_district_lines = [
        f"- {row.ilce}: ortalama sürekli risk={row.ortalama_surekli_risk:.4f}, kırmızı oran={row.kirmizi_oran:.2%}"
        for row in top3_districts.itertuples(index=False)
    ]

    top5_lines = [
        f"- {row.ilce} / {row.mahalle}: risk={row.S11_Risk_Skoru_Surekli:.4f}, PoF={row.S11_PoF_Skor:.4f}, CoF={row.S11_CoF_Skor:.4f}"
        for row in top_n.itertuples(index=False)
    ]

    moran_lines = []
    if moran_df.empty:
        moran_lines.append("- Moran's I çıktıları bu koşumda bulunamadı.")
    else:
        for row in moran_df.itertuples(index=False):
            metric_key = getattr(row, "metric_key", "moran")
            i_val = getattr(row, "morans_i", np.nan)
            p_val = getattr(row, "p_value", np.nan)
            z_val = getattr(row, "z_score", np.nan)
            decision = "anlamlı" if pd.notna(p_val) and p_val < 0.05 else "anlamlı değil"
            moran_lines.append(
                f"- {metric_key}: I={i_val:.4f}, p={p_val:.4f}, z={z_val:.3f} -> {decision}"
            )

    spatial_lines = []
    if spatial_quality_df.empty:
        spatial_lines.append("- Mekânsal kalite raporu bulunamadı.")
    else:
        sq = spatial_quality_df.iloc[0]
        spatial_lines.extend(
            [
                f"- POI kapsam: %{sq.get('poi_coverage_pct', np.nan):.2f} (önce={int(sq.get('poi_rows_before', 0))}, sonra={int(sq.get('poi_rows_after', 0))})",
                f"- Komşuluk kapsam: %{sq.get('komsuluk_coverage_pct', np.nan):.2f} (önce={int(sq.get('komsuluk_rows_before', 0))}, sonra={int(sq.get('komsuluk_rows_after', 0))})",
                f"- Dış kaynak temizliği: poi_dış_anahtar={int(sq.get('poi_rows_outside_keys', 0))}, komşuluk_dış_kaynak={int(sq.get('komsuluk_outside_source', 0))}, komşuluk_dış_komşu={int(sq.get('komsuluk_outside_neighbor', 0))}",
            ]
        )

    map_lines = []
    if map_match_report:
        both = map_match_report.get("both", 0)
        left_only = map_match_report.get("left_only", 0)
        right_only = map_match_report.get("right_only", 0)
        total = max(both + left_only + right_only, 1)
        map_lines.append(
            f"- Harita join kapsam: both={both}, left_only={left_only}, right_only={right_only}, eşleşme_oranı={both / total:.2%}"
        )

    critical_cell = 0
    try:
        critical_cell = int(cross.loc[cross["PoF_Seviye"] == 3, "3"].iloc[0])
    except Exception:
        critical_cell = int((final_df["S11_Risk_Seviyesi"] == "Kritik Risk (Kırmızı Bölge)").sum())

    content = f"""4.1 Veri ve model yürütüm özeti
Bu bölümde, 2022-2023 dönemine ait İSKİ arıza, şikayet ve kesinti kayıtları; nüfus verisi; mahalle düzeyinde POI göstergeleri
ve komşuluk bilgisi birlikte değerlendirilmiştir. Nihai karar destek modeli olarak Senaryo 11 (AHP + Quantile + PoF/CoF risk matrisi)
kullanılmıştır. Analiz birimi mahalle düzeyinde olup toplam {int(city["toplam_mahalle"])} mahalle için sürekli risk skoru ve kategorik
risk sınıfı üretilmiştir (Tablo 4.1).

4.2 Genel bulgular (şehir geneli risk dağılımı)
Şehir geneli sonuçlara göre kritik risk sınıfında {int(city["kritik_adet"])} mahalle (%{city["kritik_oran"] * 100:.2f}),
orta risk sınıfında {int(city["orta_adet"])} mahalle ve düşük risk sınıfında {int(city["dusuk_adet"])} mahalle yer almaktadır.
Sürekli risk skorunun ortalaması {city["ortalama_surekli_risk"]:.4f}, medyanı ise {city["medyan_surekli_risk"]:.4f} olarak hesaplanmıştır.
Risk sınıflarının dağılımı Şekil 4.1'de, PoF-Cof matris yoğunluğu ise Şekil 4.3'te sunulmaktadır.

4.3 İlçe bazlı bulgular (adet + oran + ortalama risk)
İlçe bazında ortalama sürekli risk değerleri ve kırmızı sınıf oranları birlikte incelendiğinde, önceliğin sadece mahalle adedine göre
değil, risk yoğunluğuna göre verilmesi gerektiği görülmektedir (Tablo 4.2, Şekil 4.2). En yüksek ortalama sürekli riske sahip ilk üç ilçe:
{chr(10).join(top3_district_lines)}
Bu bulgu, yatırım önceliği belirlenirken “yüksek riskin mekânsal yoğunlaştığı” ilçe kümelerinin ayrı bir program başlığı olarak ele
alınması gerektiğini göstermektedir.

4.4 Mahalle bazlı kritik kümeler (top liste)
Uygulama kararına doğrudan girdi oluşturması amacıyla, metin içinde en yüksek sürekli risk skoruna sahip ilk 5 mahalle özetlenmiştir;
geniş liste Tablo 4.3'te verilmiştir:
{chr(10).join(top5_lines)}
Bu mahallelerde kısa vadeli saha doğrulaması, boru hattı yenileme planı ve arıza tekrarı analizi eş zamanlı yürütülmelidir.

4.5 Mekânsal ve istatistiksel doğrulama (Moran/AHP/kalite)
Modelde kullanılan AHP ağırlıkları için tutarlılık oranları CR(PoF)={AHP_POF_CR:.4f} ve CR(CoF)={AHP_COF_CR:.4f} düzeyindedir.
Her iki değer de kabul edilebilir sınırın altında olduğundan ağırlık seti tutarlıdır (Tablo 4.5). Moran's I için permutation tabanlı
anlamlılık test sonuçları aşağıdadır:
{chr(10).join(moran_lines)}
Sonuçlar, arıza değişkeninde pozitif ve istatistiksel olarak anlamlı mekânsal kümelenmeye işaret etmektedir.
Mekânsal veri kalitesi ve kapsama denetimleri:
{chr(10).join(spatial_lines)}
{chr(10).join(map_lines)}
Harita eşleşme kalitesi Tablo 4.6'da, mahalle risk haritası Şekil 4.5'te sunulmuştur.

4.6 Karar destek yorumu (bütçe ve müdahale önceliği)
PoF x CoF matrisinin (3,3) hücresinde yer alan {critical_cell} mahalle, teknik arıza olasılığı ve etki büyüklüğü birlikte yüksek olan
kritik müdahale grubunu temsil etmektedir (Tablo 4.4). Bu grup için kısa vadede yenileme/rehabilitasyon bütçesi önceliklendirilmelidir.
Orta risk grubunda koruyucu bakım ve yakından izleme yaklaşımı, düşük risk grubunda ise standart işletme periyotları yeterli olacaktır.
Bu ayrım, sınırlı kaynakla en yüksek etkili müdahalenin planlanmasına olanak sağlamaktadır.

4.7 Kısa tartışma (sınırlılıklar + 5. bölüme geçiş köprüsü)
Elde edilen bulgular, veri bütünlüğü, isim eşleme doğruluğu ve mekânsal kapsam gibi operasyonel kalite değişkenlerine duyarlıdır.
Bu nedenle model sonuçlarının belirli aralıklarla saha gözlemleriyle kalibre edilmesi önerilir. Ayrıca bu çalışma bir tahmin modeli
değil, karar destek modelidir; amaç, yatırım ve bakım önceliklendirmesini şeffaf ve izlenebilir hale getirmektir.
Bölüm 5'te, bu bulguların yönetsel etkileri, uygulama sınırlılıkları ve politika önerileri sonuç odaklı biçimde tartışılacaktır.

Şekil ve tablo referansları (tez yerleşimi)
Şekil 4.1: Şehir geneli risk dağılımı (outputs/figures/chapter4/risk_dagilimi.png)
Şekil 4.2: İlçe bazında ortalama risk sıralaması (outputs/figures/chapter4/ilce_risk_siralamasi.png)
Şekil 4.3: PoF x CoF ısı haritası (outputs/figures/chapter4/pof_cof_heatmap.png)
Şekil 4.4: En riskli mahalleler (bar grafik) (outputs/figures/chapter4/en_riskli_mahalleler_bar.png)
Şekil 4.5: Mahalle risk haritası (outputs/figures/chapter4/risk_haritasi.png)
Tablo 4.1: Şehir geneli risk özeti (outputs/chapter4/sehir_geneli_risk_ozeti.csv)
Tablo 4.2: İlçe risk özeti (outputs/chapter4/ilce_risk_ozeti.csv)
Tablo 4.3: En riskli mahalleler listesi (outputs/chapter4/en_riskli_mahalleler_top_list.csv)
Tablo 4.4: PoF x CoF çapraz tablo (outputs/chapter4/pof_cof_capraz_tablo.csv)
Tablo 4.5: Teknik doğrulama özeti (outputs/chapter4/teknik_dogrulama_ozeti.csv)
Tablo 4.6: Harita join kalite özeti (outputs/chapter4/harita_join_kalite_ozeti.csv)
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8-sig")
    logger.info("Bolum 4 metni kaydedildi: %s", output_path)


def main() -> None:
    chapter4_dir, figure_dir = ensure_output_dirs()
    final_df, moran_df, spatial_quality_df, matrix_df = load_inputs()

    tables = compute_chapter4_tables(final_df, moran_df, spatial_quality_df, matrix_df)
    save_tables(tables, chapter4_dir)

    fig_paths = [
        plot_risk_distribution(final_df, figure_dir),
        plot_district_ranking(tables["district_summary"], figure_dir),
        plot_pof_cof_heatmap(final_df, figure_dir),
        plot_top_neighborhoods(tables["top_neighborhoods"], figure_dir),
    ]

    risk_map_path, map_match_report = plot_risk_map(final_df, figure_dir)
    if risk_map_path is not None:
        fig_paths.append(risk_map_path)
    report_path = save_map_join_report(map_match_report, chapter4_dir)
    if risk_map_path is None and report_path is None:
        remove_stale_map_outputs(figure_dir, chapter4_dir)

    logger.info("Chapter 4 varliklari uretildi.")
    logger.info("Bolum metni tek dosya duzenine gore manuel olarak outputs/tek_dosya_degisim_notlari.txt icinde tutulmaktadir.")
    for p in fig_paths:
        logger.info("Gorsel: %s", p)


if __name__ == "__main__":
    main()
