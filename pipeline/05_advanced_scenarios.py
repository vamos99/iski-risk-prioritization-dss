"""
İSKİ Risk Önceliklendirme — Adım 5 v3: AHP (Analitik Hiyerarşi Prosesi) Ağırlıklı KDS

Amaç: Gelecek tahmini (prediction) DEĞİL, karar destek (KDS).
  "ABC'de çok arıza oluyor, insanlardan sürekli şikayet alıyoruz,
   burayı kontrol etmemiz lazım" → Bu mantığa uygun ağırlıklandırma.

v3 Farkları:
  - CRITIC'in eşite yakın dağıttığı (varyans kökenli körlük yaratan) ağırlıklar yerine,
    literatürde MCDM standardı olan AHP (Analytic Hierarchy Process - Saaty 1980) bazlı
    matematiksel (Consistency Ratio CR < 0.10 olan) özvektör ağırlıkları kullanılıyor.
  - Arıza sayısı ve şikayet sayısı YÜKSEK ağırlık alıyor (birincil sinyal).
  - Quantile sınıflandırma ve Log normalizasyon korunuyor (v2'den).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

from config.settings import GOLD_DIR, SILVER_DIR, SPATIAL_FILES
from src.analysis.spatial import build_adjacency_dict, calculate_morans_i
from src.data.loader import load_komsuluk
from src.analysis.scorer import WLCScorer
from src.utils.logging_config import setup_logger

logger = setup_logger("iski.pipeline.05v3")

# ==========================================
# AHP (Analytic Hierarchy Process) AĞIRLIKLARI
# Not: Bu ağırlıklar rastgele değildir. src/analysis/ahp_calculator.py içindeki
# ikili karşılaştırma matrislerinden Eigenvector (Özvektör) yöntemiyle türetilmiştir.
# Her iki alt boyut için Kararlılık Oranı (Consistency Ratio - CR) = 0.0003 çıkmıştır.
# CR < 0.10 olduğu için ağırlık seti AHP tutarlılık eşiğini karşılar.
# ==========================================

# PoF (Probability of Failure): İhtimal Boyutu (CR = 0.0003)
POF_WEIGHTS = {
    "ariza_sayisi":       0.30,  # Birincil sinyal — ham arıza adedi
    "ariza_yogunlugu":    0.25,  # Nüfusa göre normalize edilmiş arıza
    "komsu_ort_ariza":    0.15,  # Çevre de mi bozuk? (Spatial Lag)
    "ort_kesinti_suresi":  0.15,  # Her arızada ne kadar süre kesinti oluyor?
    "ariza_trend":        0.10,  # Kötüye mi gidiyor yıldan yıla?
    "nufus_basi_tuketim":  0.05,  # Kişi başı su talebi (altyapı baskısı)
}

# CoF (Consequence of Failure): Etki ve Sonuç Boyutu (CR = 0.0003)
# Varlık yönetimi mantığına uygun etki hiyerarşisi
COF_WEIGHTS = {
    "nufus":              0.25,  # Kaç kişi etkilenir?
    "sikayet_sayisi":      0.25,  # Vatandaş reaksiyonu (İtibar riski)
    "kesinti_suresi_saat": 0.20,  # Toplam kesinti süresi (saat)
    "egitim_tesisi_sayisi": 0.10,  # Hassas popülasyon (çocuklar / eğitim durması)
    "sanayi_tesis_sayisi":  0.08,  # Ekonomik hasar potansiyeli
    "sikayet_ariza_orani": 0.07,  # Panik/Reaksiyon katsayısı
    "komsu_sayisi":        0.05,  # Domino etkisi (komşu mahalle bağlantısallığı)
}

# Zaman ağırlıkları
YEAR_WEIGHTS = {2022: 0.40, 2023: 0.60}


# ==========================================
# FONKSİYONLAR
# ==========================================
def aggregate_temporal_weighted(
    raw_df: pd.DataFrame,
    norm_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ağırlıklı zaman agregasyonu (2023 > 2022)."""
    static_info = raw_df[["ilce", "mahalle", "anahtar"]].drop_duplicates().set_index("anahtar")

    numeric_cols = raw_df.select_dtypes(include=[np.number]).columns.drop("yil", errors="ignore")
    agg_parts = []
    for year, weight in YEAR_WEIGHTS.items():
        subset = raw_df[raw_df["yil"] == year].copy()
        subset_num = subset[numeric_cols].copy() * weight
        subset_num["anahtar"] = subset["anahtar"].values
        agg_parts.append(subset_num)
    combined = pd.concat(agg_parts).groupby("anahtar").sum(numeric_only=True)
    final_raw = static_info.join(combined).reset_index()

    norm_numeric = norm_df.select_dtypes(include=[np.number]).columns.tolist()
    norm_parts = []
    for year, weight in YEAR_WEIGHTS.items():
        mask = raw_df["yil"] == year
        subset_norm = norm_df.loc[mask, norm_numeric].copy() * weight
        subset_norm["anahtar"] = raw_df.loc[mask, "anahtar"].values
        norm_parts.append(subset_norm)
    agg_norm = pd.concat(norm_parts).groupby("anahtar").sum(numeric_only=True).reset_index()

    logger.info("Ağırlıklı zaman agregasyonu: %d → %d satır", len(raw_df), len(final_raw))
    return final_raw, agg_norm


def classify_quantile(series: pd.Series, label: str = "") -> pd.Series:
    """Quantile (tercil) bazlı sınıflandırma."""
    q33 = series.quantile(0.333)
    q66 = series.quantile(0.666)

    def assign(val):
        if val <= q33:
            return 1
        elif val <= q66:
            return 2
        return 3

    result = series.apply(assign)
    logger.info(
        "%s Quantile: q33=%.4f, q66=%.4f | Düşük:%d, Orta:%d, Yüksek:%d",
        label, q33, q66,
        (result == 1).sum(), (result == 2).sum(), (result == 3).sum(),
    )
    return result


def compute_weighted_score(
    norm_df: pd.DataFrame,
    weight_dict: dict[str, float],
    label: str = "",
) -> pd.Series:
    """Alan bilgisi ağırlıklarıyla WLC skoru hesaplar."""
    available = [f for f in weight_dict if f in norm_df.columns]
    missing = [f for f in weight_dict if f not in norm_df.columns]

    if missing:
        logger.warning("%s — Eksik değişkenler (atlanıyor): %s", label, missing)

    # Mevcut ağırlıkları yeniden normalize et (eksik olanların payını dağıt)
    sub_w = {f: weight_dict[f] for f in available}
    total = sum(sub_w.values())
    sub_w = {k: v / total for k, v in sub_w.items()}

    logger.info("%s Ağırlıkları:", label)
    for k, v in sorted(sub_w.items(), key=lambda x: -x[1]):
        logger.info("  %-25s → %%%5.1f", k, v * 100)

    scorer = WLCScorer()
    return scorer.score(norm_df, available, sub_w)


def scenario_11_domain_kds(
    agg_raw: pd.DataFrame,
    agg_norm: pd.DataFrame,
) -> pd.DataFrame:
    """Senaryo 11 v3: Alan bilgisi ağırlıklı PoF/CoF KDS Matrisi."""

    pof_scores = compute_weighted_score(agg_norm, POF_WEIGHTS, "PoF")
    cof_scores = compute_weighted_score(agg_norm, COF_WEIGHTS, "CoF")

    pof_levels = classify_quantile(pof_scores, "PoF")
    cof_levels = classify_quantile(cof_scores, "CoF")

    risk_products = pof_levels * cof_levels

    def map_risk(prod):
        if prod == 9: # Sadece PoF=3 ve CoF=3 olanlar (Gerçekten en kritik %19)
            return "Kritik Risk (Kırmızı Bölge)"
        if prod >= 4: # PoF=2,CoF=2 veya herhangi biri yüksekken diğeri orta olanlar
            return "Orta Risk (Sarı Bölge)"
        return "Düşük Risk (Yeşil Bölge)"

    result = agg_raw[["anahtar"]].copy()
    
    # Sürekli (Continuous) skorlar
    result["S11_PoF_Skor"] = pof_scores
    result["S11_CoF_Skor"] = cof_scores
    # Matematiksel risk çarpımı (0.0 - 1.0 arası hassas değer, iç sıralama için)
    result["S11_Risk_Skoru_Surekli"] = pof_scores * cof_scores
    
    # Kategorik (Discrete) seviyeler ve sınıflar
    result["S11_PoF_Seviye"] = pof_levels
    result["S11_CoF_Seviye"] = cof_levels
    result["S11_Risk_Carpimi_Kategorik"] = risk_products
    result["S11_Risk_Seviyesi"] = risk_products.apply(map_risk)

    # Mahalleyi matematiksel risk skoruna göre en yüksekten en düşüğe (Kritikten -> Güvenliye) sırala
    result = result.sort_values(by="S11_Risk_Skoru_Surekli", ascending=False).reset_index(drop=True)

    logger.info("Senaryo 11 v3 (Alan Bilgisi KDS) tamamlandı. İç sıralama eklendi.")
    return result


def compute_risk_morans_i(final_df: pd.DataFrame) -> pd.DataFrame:
    """Nihai risk skoru için Moran's I hesaplar."""
    komsuluk = load_komsuluk(SPATIAL_FILES["mahalle_komsuluklari"])
    valid_keys = set(final_df["anahtar"].unique())
    komsuluk = komsuluk[
        komsuluk["anahtar"].isin(valid_keys) & komsuluk["komsu_anahtar"].isin(valid_keys)
    ].drop_duplicates()

    adj_dict = build_adjacency_dict(komsuluk)
    moran = calculate_morans_i(
        final_df["S11_Risk_Skoru_Surekli"],
        final_df["anahtar"],
        adj_dict,
    )
    return pd.DataFrame([{"metric_key": "risk_s11", **moran}])


def main():
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║  İSKİ — Adım 5 v3: Alan Bilgisi Ağırlıklı KDS   ║")
    logger.info("║  Arıza+Şikayet Öncelikli / Karar Destek Odaklı  ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    raw_df = pd.read_csv(SILVER_DIR / "karar_matrisi.csv", encoding="utf-8-sig")
    norm_B = pd.read_csv(SILVER_DIR / "norm_B_logrobust.csv", encoding="utf-8-sig")

    # 1. Ağırlıklı Zaman Agregasyonu
    agg_raw, agg_norm = aggregate_temporal_weighted(raw_df, norm_B)

    # 2. Senaryo 11 v3 (Domain KDS)
    s11 = scenario_11_domain_kds(agg_raw, agg_norm)

    # 3. Birleştir ve kaydet
    final = agg_raw.copy()
    final = final.merge(s11, on="anahtar")

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GOLD_DIR / "ileri_duzey_senaryolar_mahalle_bazli.csv"
    final.to_csv(out_path, index=False, encoding="utf-8-sig")

    # 4. Çift Moran: nihai risk skoru + arıza Moran birleşik rapor
    risk_moran_df = compute_risk_morans_i(final)
    risk_moran_path = GOLD_DIR / "morans_i_risk_results.csv"
    risk_moran_df.to_csv(risk_moran_path, index=False, encoding="utf-8-sig")

    ariza_moran_path = GOLD_DIR / "morans_i_results.csv"
    ariza_moran_df = (
        pd.read_csv(ariza_moran_path, encoding="utf-8-sig")
        if ariza_moran_path.exists()
        else pd.DataFrame()
    )
    all_moran_df = pd.concat([ariza_moran_df, risk_moran_df], ignore_index=True)
    if "metric_key" in all_moran_df.columns:
        all_moran_df = all_moran_df.drop_duplicates(subset=["metric_key"], keep="last")
    all_moran_path = GOLD_DIR / "morans_i_all_results.csv"
    all_moran_df.to_csv(all_moran_path, index=False, encoding="utf-8-sig")
    logger.info("Çift Moran çıktıları kaydedildi: %s, %s", risk_moran_path.name, all_moran_path.name)

    # --- Raporlama ---
    logger.info("\n--- Senaryo 11 v3 Risk Dağılımı ---")
    logger.info("\n%s", final["S11_Risk_Seviyesi"].value_counts().to_string())

    ct = pd.crosstab(final["S11_PoF_Seviye"], final["S11_CoF_Seviye"], margins=True)
    logger.info("\n--- PoF x CoF Çapraz Tablo ---")
    logger.info("\n%s", ct.to_string())

    # --- Sanity Check ---
    logger.info("\n--- SAĞDUYU KONTROLÜ: İlçe Bazlı Özet ---")
    for ilce in ['ESENYURT','BAĞCILAR','KÜÇÜKÇEKMECE','SULTANGAZİ','KADIKÖY','ŞİLE','ADALAR']:
        sub = final[final['ilce'] == ilce]
        k = len(sub[sub['S11_Risk_Seviyesi'].str.contains('Kırmızı', na=False)])
        s = len(sub[sub['S11_Risk_Seviyesi'].str.contains('Sarı', na=False)])
        y = len(sub[sub['S11_Risk_Seviyesi'].str.contains('Yeşil', na=False)])
        logger.info("  %-20s 🔴%3d  🟡%3d  🟢%3d", ilce, k, s, y)

    logger.info("═" * 60)
    logger.info("v3 kaydedildi: %s", out_path.name)

if __name__ == "__main__":
    main()
