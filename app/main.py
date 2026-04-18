"""
İSKİ Karar Destek Sistemi (KDS) — Streamlit Uygulaması.

Nihai Model: Senaryo 11 (PoF / CoF 2D Risk Matrisi)
Arşiv: Elenen 10 senaryo ve nedenleri
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import os
import sys
from pathlib import Path

# Proje kök dizinini ekle
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.settings import SPATIAL_FILES, GOLD_DIR
from src.utils.naming import (
    standardize_district_name,
    standardize_neighborhood_name,
)

st.set_page_config(
    page_title="İSKİ KDS - Risk Önceliklendirme",
    page_icon="🚰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# VERİ YÜKLEME
# ==========================================
@st.cache_data
def load_data():
    gdf_districts = None
    gdf_neighborhoods = None

    if os.path.exists(SPATIAL_FILES["districts_geojson"]):
        gdf_districts = gpd.read_file(SPATIAL_FILES["districts_geojson"])
        gdf_districts["ilce"] = gdf_districts["ilce"].apply(standardize_district_name)

    if os.path.exists(SPATIAL_FILES["neighborhoods_geojson"]):
        gdf_neighborhoods = gpd.read_file(SPATIAL_FILES["neighborhoods_geojson"])
        gdf_neighborhoods["ilce"] = gdf_neighborhoods["ilce"].apply(standardize_district_name)
        gdf_neighborhoods["mahalle"] = gdf_neighborhoods["mahalle"].apply(standardize_neighborhood_name)

    try:
        df_advanced = pd.read_csv(GOLD_DIR / "ileri_duzey_senaryolar_mahalle_bazli.csv")
    except Exception:
        df_advanced = pd.DataFrame()

    try:
        df_archive = pd.read_csv(GOLD_DIR / "tum_senaryo_sonuclari.csv")
        df_archive = df_archive[df_archive["yil"] == 2023].copy()
    except Exception:
        df_archive = pd.DataFrame()

    try:
        df_metrics = pd.read_csv(GOLD_DIR / "senaryo_karsilastirma.csv")
    except Exception:
        df_metrics = pd.DataFrame()

    return gdf_districts, gdf_neighborhoods, df_advanced, df_archive, df_metrics


gdf_districts, gdf_neighborhoods, df_advanced, df_archive, df_metrics = load_data()


# ==========================================
# YARDIMCI FONKSİYONLAR
# ==========================================
def get_risk_color(risk_label: str) -> str:
    if not isinstance(risk_label, str):
        return "#CCCCCC"
    label = risk_label.lower()
    if "kırmızı" in label or "yüksek" in label or "kritik" in label:
        return "#E74C3C"
    elif "sarı" in label or "orta" in label:
        return "#F39C12"
    elif "yeşil" in label or "düşük" in label:
        return "#27AE60"
    return "#CCCCCC"


def risk_emoji(risk_label: str) -> str:
    if not isinstance(risk_label, str):
        return "❓"
    label = risk_label.lower()
    if "kırmızı" in label or "kritik" in label:
        return "🔴"
    elif "sarı" in label or "orta" in label:
        return "🟡"
    elif "yeşil" in label or "düşük" in label:
        return "🟢"
    return "⚪"


def score_to_percent(score: float) -> str:
    """0-1 arası skoru %0-100 arası yüzdelik gösterime çevirir."""
    if pd.isna(score):
        return "—"
    return f"%{score * 100:.0f}"


def risk_turkish(risk_label: str) -> str:
    """Risk seviyesini sade Türkçe'ye çevirir."""
    if not isinstance(risk_label, str):
        return "Veri Yok"
    if "Kırmızı" in risk_label:
        return "ACİL - Kritik Risk"
    elif "Sarı" in risk_label:
        return "DİKKAT - Orta Risk"
    elif "Yeşil" in risk_label:
        return "NORMAL - Düşük Risk"
    return risk_label


def build_canonical_key(df: pd.DataFrame, district_col: str, neighborhood_col: str) -> pd.Series:
    """İlçe-mahalle birleşik canonical anahtarı üretir."""
    return (
        df[district_col].fillna("").astype(str).apply(standardize_district_name)
        + "|"
        + df[neighborhood_col].fillna("").astype(str).apply(standardize_neighborhood_name)
    )


def deduplicate_geometry_by_key(gdf: gpd.GeoDataFrame, key_col: str) -> tuple[gpd.GeoDataFrame, int]:
    """Aynı anahtar için en büyük geometriyi tutar."""
    if gdf.empty:
        return gdf, 0

    work = gdf.copy()
    before = len(work)

    try:
        work["_geom_area"] = work.to_crs(epsg=3857).geometry.area
    except Exception:
        work["_geom_area"] = work.geometry.area

    work = work.sort_values("_geom_area", ascending=False).drop_duplicates(subset=[key_col], keep="first")
    work = work.drop(columns=["_geom_area"])
    removed = before - len(work)
    return work, removed


def prepare_map_join_inputs(
    neighborhoods: gpd.GeoDataFrame,
    advanced_df: pd.DataFrame,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, dict[str, float]]:
    """Harita merge'i için canonical key, tekilleştirme ve kapsam raporu üretir."""
    if neighborhoods is None or advanced_df.empty:
        return neighborhoods, advanced_df, {}

    geo = neighborhoods.copy()
    model = advanced_df.copy()

    geo["ilce"] = geo["ilce"].apply(standardize_district_name)
    geo["mahalle"] = geo["mahalle"].apply(standardize_neighborhood_name)
    geo["anahtar"] = build_canonical_key(geo, "ilce", "mahalle")
    geo, dropped_geo_dupes = deduplicate_geometry_by_key(geo, "anahtar")

    model["ilce"] = model["ilce"].apply(standardize_district_name)
    model["mahalle"] = model["mahalle"].apply(standardize_neighborhood_name)
    model["anahtar"] = build_canonical_key(model, "ilce", "mahalle")
    model = model.sort_values("S11_Risk_Skoru_Surekli", ascending=False).drop_duplicates(subset=["anahtar"])

    # Kapsam doğrulaması (merge öncesi)
    cov = geo[["anahtar"]].merge(model[["anahtar"]], on="anahtar", how="outer", indicator=True)
    counts = cov["_merge"].value_counts(dropna=False).to_dict()
    total = max(len(cov), 1)

    left_only = int(counts.get("left_only", 0))
    right_only = int(counts.get("right_only", 0))
    both = int(counts.get("both", 0))

    model_keys = set(model["anahtar"].tolist())
    geo_before_filter = len(geo)
    geo = geo[geo["anahtar"].isin(model_keys)].copy()
    geo_filtered_outside = geo_before_filter - len(geo)

    report = {
        "geo_after_dedup": len(geo),
        "model_after_dedup": len(model),
        "left_only": left_only,
        "right_only": right_only,
        "both": both,
        "left_only_ratio": left_only / total,
        "right_only_ratio": right_only / total,
        "both_ratio": both / total,
        "dropped_geo_duplicates": dropped_geo_dupes,
        "filtered_geo_outside_model": geo_filtered_outside,
    }

    return geo, model, report


# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🚰 İSKİ KDS")
st.sidebar.caption("Su Şebekesi Risk Önceliklendirme Sistemi")
st.sidebar.markdown("---")

# TAB SİSTEMİ
tab1, tab2, tab3 = st.tabs([
    "🗺️ Risk Haritası",
    "📋 Öncelik Sıralaması",
    "📂 Arşiv (Elenen Yöntemler)",
])


# ==========================================
# SEKME 1: RİSK HARİTASI
# ==========================================
with tab1:
    st.title("📍 İstanbul Su Şebekesi Risk Haritası")

    # Metodoloji açıklaması (teknik olmayan kişiler için)
    with st.expander("ℹ️ Bu harita nasıl oluşturuldu? (Tıklayarak açın)"):
        st.markdown("""
        **Her mahalle için iki soru sorduk:**
        1. **Altyapı ne kadar yıpranmış?** → Arıza sayıları, boru stresi, kesinti süreleri vb. (Olasılık Skoru)
        2. **Arıza olursa ne kadar insan/kurum etkilenir?** → Nüfus, okul sayısı, sanayi tesisi vb. (Etki Skoru)

        **İki sorunun cevaplarını bir matriste birleştirdik:**
        - 🔴 **Kırmızı (Kritik):** Hem altyapısı çok yıpranmış HEM DE çok insan/kurum etkilenecek → *Acil yatırım gerekir*
        - 🟡 **Sarı (Orta):** Ya altyapı kötü ama etkilenen az, ya da altyapı iyi ama etkilenen çok → *Planlı bakım gerekir*
        - 🟢 **Yeşil (Düşük):** Hem altyapı iyi hem etkilenen az → *Standart işletme yeterli*

        *Veriler: İSKİ 2022-2023 arıza/şikayet/kesinti kayıtları, nüfus verileri ve OpenStreetMap altyapı bilgileri kullanılmıştır.*
        """)

    # İlçe filtresi
    ilceler = sorted(df_advanced["ilce"].dropna().unique().tolist()) if not df_advanced.empty else []
    secilen_ilce = st.selectbox("📌 İlçeye odaklan:", ["Tüm İstanbul"] + ilceler,
                                 help="Belirli bir ilçeyi seçerek haritayı yakınlaştırabilirsiniz.")

    if not df_advanced.empty and gdf_neighborhoods is not None:
        prepared_geo, prepared_model, join_report = prepare_map_join_inputs(gdf_neighborhoods, df_advanced)

        merged_gdf = prepared_geo.merge(
            prepared_model.drop(columns=["ilce", "mahalle"], errors="ignore"),
            on="anahtar",
            how="left",
        )

        if join_report:
            st.caption(
                "Harita kapsam kontrolü | "
                f"eşleşen={join_report['both']} (%{join_report['both_ratio'] * 100:.1f}), "
                f"left_only={join_report['left_only']} (%{join_report['left_only_ratio'] * 100:.1f}), "
                f"right_only={join_report['right_only']} (%{join_report['right_only_ratio'] * 100:.1f}), "
                f"geometri_duplikasyon_temizliği={join_report['dropped_geo_duplicates']}"
            )

        m = folium.Map(location=[41.0082, 28.9784], zoom_start=10, tiles="CartoDB positron")

        if secilen_ilce != "Tüm İstanbul":
            merged_gdf = merged_gdf[merged_gdf["ilce"] == secilen_ilce]
            if not merged_gdf.empty:
                bounds = merged_gdf.total_bounds
                m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        def style_fn(feature):
            risk_level = feature["properties"].get("S11_Risk_Seviyesi", "")
            return {
                "fillColor": get_risk_color(risk_level),
                "color": "#555555",
                "weight": 0.8,
                "fillOpacity": 0.65 if risk_level else 0.08,
            }

        # Tooltip için insan-okuyabilir sütunlar ekle
        merged_gdf["risk_aciklama"] = merged_gdf["S11_Risk_Seviyesi"].apply(risk_turkish)
        merged_gdf["altyapi_yuzde"] = merged_gdf["S11_PoF_Skor"].apply(score_to_percent)
        merged_gdf["etki_yuzde"] = merged_gdf["S11_CoF_Skor"].apply(score_to_percent)

        folium.GeoJson(
            merged_gdf,
            name="Risk Haritası",
            style_function=style_fn,
            highlight_function=lambda x: {"weight": 3, "color": "#000", "fillOpacity": 0.9},
            tooltip=folium.GeoJsonTooltip(
                fields=["mahalle", "ilce", "risk_aciklama", "altyapi_yuzde", "etki_yuzde"],
                aliases=[
                    "📍 Mahalle:",
                    "🏙️ İlçe:",
                    "⚠️ Risk Durumu:",
                    "🔧 Altyapı Yıpranma:",
                    "👥 Etkilenecek Nüfus/Kurum:",
                ],
                style="font-family: Arial; font-size: 13px; padding: 6px;",
            ),
        ).add_to(m)

        st_folium(m, width=1200, height=550)

        # Özet kartlar
        st.markdown("---")
        kirmizi = len(df_advanced[df_advanced["S11_Risk_Seviyesi"].str.contains("Kırmızı", na=False)])
        sari = len(df_advanced[df_advanced["S11_Risk_Seviyesi"].str.contains("Sarı", na=False)])
        yesil = len(df_advanced[df_advanced["S11_Risk_Seviyesi"].str.contains("Yeşil", na=False)])

        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 Kritik Risk", f"{kirmizi} mahalle", "Acil yatırım / müdahale gerekli")
        c2.metric("🟡 Orta Risk", f"{sari} mahalle", "Planlı bakım programına alınmalı")
        c3.metric("🟢 Düşük Risk", f"{yesil} mahalle", "Standart işletme yeterli")

    else:
        st.error("Veri dosyaları bulunamadı. Lütfen pipeline'ı çalıştırın.")


# ==========================================
# SEKME 2: ÖNCELİK SIRALAMASI (RANKED LIST)
# ==========================================
with tab2:
    st.title("📋 Mahalle Öncelik Sıralaması")
    st.markdown("Mahallelerin risk seviyesine göre en acilden en güvenliye sıralanmış listesidir.")

    if not df_advanced.empty:
        # Tablo hazırla
        ranking_df = df_advanced[["ilce", "mahalle", "S11_Risk_Seviyesi", "S11_PoF_Skor", "S11_CoF_Skor", "S11_Risk_Skoru_Surekli"]].copy()

        ranking_df.columns = ["İlçe", "Mahalle", "Risk Durumu", "Altyapı Skoru", "Etki Skoru", "Risk Puanı"]
        ranking_df["Simge"] = ranking_df["Risk Durumu"].apply(risk_emoji)
        ranking_df["Durum Açıklaması"] = ranking_df["Risk Durumu"].apply(risk_turkish)
        ranking_df["Altyapı (%)"] = ranking_df["Altyapı Skoru"].apply(score_to_percent)
        ranking_df["Etki (%)"] = ranking_df["Etki Skoru"].apply(score_to_percent)

        # Sıralama (Risk Puanı en yüksek → en acil)
        ranking_df = ranking_df.sort_values("Risk Puanı", ascending=False).reset_index(drop=True)
        ranking_df.index += 1  # 1'den başlat
        ranking_df.index.name = "Sıra"

        # Filtreleme
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtre_ilce = st.selectbox("İlçe Filtresi:", ["Tümü"] + sorted(ranking_df["İlçe"].unique().tolist()), key="rank_ilce")
        with col_f2:
            filtre_risk = st.selectbox("Risk Filtresi:", ["Tümü", "🔴 Kritik", "🟡 Orta", "🟢 Düşük"], key="rank_risk")

        display_df = ranking_df.copy()
        if filtre_ilce != "Tümü":
            display_df = display_df[display_df["İlçe"] == filtre_ilce]
        if filtre_risk != "Tümü":
            if "Kritik" in filtre_risk:
                display_df = display_df[display_df["Risk Durumu"].str.contains("Kırmızı", na=False)]
            elif "Orta" in filtre_risk:
                display_df = display_df[display_df["Risk Durumu"].str.contains("Sarı", na=False)]
            elif "Düşük" in filtre_risk:
                display_df = display_df[display_df["Risk Durumu"].str.contains("Yeşil", na=False)]

        st.markdown(f"**Toplam {len(display_df)} mahalle listeleniyor** (en öncelikliden başlayarak)")

        # Gösterilecek sütunlar (teknik olmayan kişi için anlaşılır olanlar)
        show_cols = ["Simge", "İlçe", "Mahalle", "Durum Açıklaması", "Altyapı (%)", "Etki (%)", "Risk Puanı"]
        st.dataframe(
            display_df[show_cols],
            use_container_width=True,
            height=600,
        )

        # CSV İndirme
        csv_data = display_df[["İlçe", "Mahalle", "Durum Açıklaması", "Altyapı (%)", "Etki (%)", "Risk Puanı"]].to_csv(index=True)
        st.download_button(
            "📥 Listeyi CSV Olarak İndir",
            csv_data,
            file_name="iski_risk_onceliklendirme.csv",
            mime="text/csv",
        )
    else:
        st.error("Veri bulunamadı.")


# ==========================================
# SEKME 3: ARŞİV (ELENEN YÖNTEMLER)
# ==========================================
with tab3:
    st.title("📂 Arşiv: Test Edilip Elenen Matematiksel Yöntemler")
    st.markdown("""
    Proje boyunca **10 farklı matematiksel yaklaşım** test edilmiş ve aşağıdaki nedenlerle
    nihai model olarak tercih edilmemişlerdir. Bu kayıtlar, gelecekte aynı deneylerin
    tekrarlanmasını önlemek için arşive alınmıştır.
    """)

    st.warning("""
    **Ortak Sorun: Açıklanabilirlik (Explainability)**
    İlk 9 senaryodaki en büyük sıkıntı, arıza potansiyeli (boru stresi) ile
    etki potansiyelinin (hastane/nüfus) tek bir sayıya eritilmesidir. Bir mahalle
    "85 puan" aldığında riskin sebebi bilinemez.
    """)

    if not df_metrics.empty:
        rejection_reasons = {
            1: "PDF Orijinali: POI ve Komşuluk verisi eksik. Model İstanbul gerçeğini yansıtamadı.",
            2: "Tek skorla açıklanabilirlik sorunu. 'Neden riskli?' sorusuna cevap verilemedi.",
            3: "Tek skorla açıklanabilirlik sorunu. Ağırlık değişse bile temel sorun çözülmedi.",
            4: "KRİTİK HATA: Sıfır-Değer Çökmesi. Tesis sayısı 0 olan yerlerde çarpma işlemi tüm skoru sıfırladı. Sadece 12 mahalle riskli çıktı!",
            5: "Aşırı uç değer hassasiyeti. Risk dağılımı dengesiz ve yorumlanamaz çıktı.",
            6: "13 boyutlu K-Means mantıklı bir risk çizgisi çekemedi (Silhouette: 0.39).",
            7: "Aşırı Hassasiyet: İstanbul'un %73'ünü 'yüksek riskli' ilan etti. Bütçe önceliklendirme imkansız.",
            8: "Keskin sınır çizemedi. Orta sınıf mahalleleri yanlışlıkla yüksek riske itti.",
            9: "Mekânsal veri doğruydu ama tek skor çorbasından (açıklanabilirlik) kurtulamadı.",
        }

        display_df = df_metrics.copy()
        display_df["Arşivlenme Nedeni"] = display_df["Senaryo"].map(rejection_reasons)

        st.dataframe(display_df, use_container_width=True)

        st.success("""
        **Nihai Seçim:** Senaryo 11 — 2D PoF/CoF Risk Matrisi.
        "Altyapı ne kadar yıpranmış?" ve "Arıza olursa kim etkilenir?" sorularını
        ayrı ayrı cevaplayıp bir matriste kesiştiren, bütçe tahsisi için en net
        ve açıklanabilir model budur.
        """)
    else:
        st.info("Arşiv metrikleri henüz oluşturulmamış.")
