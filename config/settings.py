"""
İSKİ Risk Önceliklendirme — Merkezi Konfigürasyon.

Tüm sabitler, dosya yolları ve hiperparametreler burada tanımlanır.
Magic number yasağı: pipeline kodlarında doğrudan sayısal değer kullanılmaz.
"""

from pathlib import Path

# ==============================================================
# PROJE KÖKLÜ YOLLARI
# ==============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Veri katmanları (Medallion Architecture)
DATA_DIR = PROJECT_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

# Mekânsal ve ek veri kaynakları
EXTERNAL_DIR = DATA_DIR / "external"
SPATIAL_DIR = DATA_DIR / "spatial"

# Çıktılar
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# ==============================================================
# HAM VERİ DOSYALARI (BRONZE)
# ==============================================================
RAW_FILES = {
    "ariza_2022": "iski_ariza_2022.csv",
    "ariza_2023": "iski_ariza_2023.csv",
    "tuketim_2022": "ilce_tuketim_2015_2022.csv",
    "tuketim_2023": "ilce_tuketim_2023.csv",
    "sikayet_2022": "iski_sikayet_2022.csv",
    "sikayet_2023": "iski_sikayet_2023.csv",
    "kesinti_2022_2023": "su_kesintileri_2022_2023.csv",
    "kesinti_2023_2024": "su_kesintileri_2023_2024.csv",
    "nufus": "nufus_mahalle_2022_2023.csv",
}

# Mekânsal ek dosyalar
SPATIAL_FILES = {
    "neighborhoods_geojson": SPATIAL_DIR / "istanbul_neighborhoods.geojson",
    "districts_geojson": SPATIAL_DIR / "istanbul_districts.geojson",
    "mahalle_komsuluklari": EXTERNAL_DIR / "mahalle_komsuluklari.csv",
    "ilce_komsuluklari": EXTERNAL_DIR / "ilce_komsuluklari.csv",
    "poi_istatistik": EXTERNAL_DIR / "mahalle_poi_istatistik.csv",
}

# ==============================================================
# SILVER ÇIKTI DOSYALARI
# ==============================================================
SILVER_FILES = {
    "ariza_temiz": SILVER_DIR / "ariza_temiz.csv",
    "tuketim_temiz": SILVER_DIR / "tuketim_temiz.csv",
    "sikayet_temiz": SILVER_DIR / "sikayet_temiz.csv",
    "kesinti_temiz": SILVER_DIR / "kesinti_temiz.csv",
    "nufus_temiz": SILVER_DIR / "nufus_temiz.csv",
    "poi_temiz": SILVER_DIR / "poi_temiz.csv",
    "dasimetrik_tuketim": SILVER_DIR / "dasimetrik_tuketim.csv",
    "karar_matrisi": SILVER_DIR / "karar_matrisi.csv",
}

# ==============================================================
# GOLD ÇIKTI DOSYALARI
# ==============================================================
GOLD_FILES = {
    "risk_skorlari": GOLD_DIR / "risk_skorlari.csv",
    "kume_sonuclari": GOLD_DIR / "kume_sonuclari.csv",
    "kombinasyon_karsilastirma": GOLD_DIR / "kombinasyon_karsilastirma.csv",
}

# ==============================================================
# ANALİZ SABİTLERİ
# ==============================================================

# Zaman penceresi
ANALYSIS_YEARS: list[int] = [2022, 2023]

# İstanbul ilçe sayısı (doğrulama)
EXPECTED_DISTRICT_COUNT: int = 39

# IQR Winsorization çarpanı
IQR_MULTIPLIER: float = 1.5

# Korelasyon filtresi eşiği
CORRELATION_THRESHOLD: float = 0.85

# Normalizasyon
EPSILON: float = 1e-6  # Sıfıra bölme koruması

# K-Means hiperparametreleri
RANDOM_STATE: int = 42
KMEANS_N_INIT: int = 20
KMEANS_MAX_ITER: int = 300
K_RANGE: range = range(2, 8)  # k=2..7 test aralığı

# Doğrulama sabitleri
VOLUME_TOLERANCE: float = 0.01  # Dasimetrik hacim korunumu toleransı
WEIGHT_SUM_TOLERANCE: float = 1e-10  # Ağırlık toplamı toleransı
STABILITY_RANDOM_STATES: list[int] = [42, 0, 123, 456]  # Kümeleme kararlılık testi

# ==============================================================
# FEATURE SET TANIMLARI
# ==============================================================

# PDF'teki orijinal 5 temel kriter
BASE_FEATURES: list[str] = [
    "ariza_sayisi",
    "tuketim_dasimetrik",
    "kesinti_suresi_saat",
    "sikayet_sayisi",
    "nufus",
]

# Operasyonel türev değişkenler
DERIVED_FEATURES: list[str] = [
    "ariza_yogunlugu",
    "boru_stres_endeksi",
    "sikayet_ariza_orani",
    "ort_kesinti_suresi",
    "ariza_trend",
    "nufus_basi_tuketim",
]

# POI türev değişkenler
POI_FEATURES: list[str] = [
    "egitim_tesisi_sayisi",
    "sanayi_tesis_sayisi",
]

# Spatial lag değişkenler
SPATIAL_FEATURES: list[str] = [
    "komsu_ort_ariza",
    "komsu_ort_risk",
    "komsu_sayisi",
]

# Feature set kombinasyonları (Adım 5'teki 9 senaryo için)
FEATURE_SETS = {
    "temel": BASE_FEATURES,
    "temel_turev_poi": BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES,
    "full_spatial": BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES + SPATIAL_FEATURES,
}

# ==============================================================
# PoF / CoF GRUPLANDIRMASI
# ==============================================================
POF_INDICATORS: list[str] = [
    "ariza_sayisi",
    "ariza_yogunlugu",
    "ariza_trend",
    "nufus_basi_tuketim",
    "komsu_ort_ariza",
    "ort_kesinti_suresi",
]

COF_INDICATORS: list[str] = [
    "kesinti_suresi_saat",
    "sikayet_sayisi",
    "nufus",
    "sikayet_ariza_orani",
    "egitim_tesisi_sayisi",
    "sanayi_tesis_sayisi",
    "komsu_sayisi",
]
