"""
İSKİ Risk Önceliklendirme — Mahalle / İlçe İsim Standardizasyonu.

Farklı veri kaynaklarındaki tutarsız mahalle ve ilçe isimlerini
ortak bir formata dönüştürür.

Sorunlar:
  - "BURGAZADA MAH" vs "Burgazada Mahallesi" vs "BURGAZADA"
  - Türkçe karakter tutarsızlıkları (İ/I, Ş/S vb.)
  - BOM karakterleri (\\ufeff)
"""

import re
import unicodedata


# Türkçe büyük harf dönüşüm tablosu
_TR_UPPER_MAP = str.maketrans(
    "abcçdefgğhıijklmnoöprsştuüvyz",
    "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ",
)


def _turkish_upper(text: str) -> str:
    """Python'un .upper() fonksiyonu Türkçe İ/I dönüşümünü yanlış yapar.
    Bu fonksiyon Türkçe locale kurallarını uygular.
    """
    return text.translate(_TR_UPPER_MAP).upper()


def _fix_district_typos(name: str) -> str:
    """İlçe isminde bilinen yazım hatalarını ve kısaltmaları düzeltir."""
    typos = {
        "B.ÇEKMECE": "BÜYÜKÇEKMECE",
        "GOP": "GAZİOSMANPAŞA",
        "G.O.PAŞA": "GAZİOSMANPAŞA",
        "K.ÇEKMECE": "KÜÇÜKÇEKMECE",
        "SALTANGAZİ": "SULTANGAZİ",
        "GENEL TOPLAM": "",
        "KÂĞITHANE": "KAĞITHANE",
        "EYÜP": "EYÜPSULTAN", # known name changes
    }
    return typos.get(name, name)

def standardize_district_name(name: str) -> str:
    """İlçe ismini standart formata dönüştürür.

    Args:
        name: Ham ilçe ismi.

    Returns:
        Büyük harfli, temizlenmiş ilçe ismi.

    Example:
        >>> standardize_district_name("  Ataşehir  ")
        'ATAŞEHİR'
    """
    if not isinstance(name, str):
        return ""
    name = name.strip()
    name = name.replace("\ufeff", "")  # BOM temizliği
    name = _turkish_upper(name)
    # Birden fazla boşluğu teke indir
    name = re.sub(r"\s+", " ", name)
    name = _fix_district_typos(name)
    return name


def standardize_neighborhood_name(name: str) -> str:
    """Mahalle ismini standart formata dönüştürür.

    Suffix'leri temizler: "MAH", "MAH.", "MAHALLESİ", "Mahallesi"
    Sonuç büyük harflidir.

    Args:
        name: Ham mahalle ismi.

    Returns:
        Suffix'siz, büyük harfli mahalle ismi.

    Example:
        >>> standardize_neighborhood_name("Burgazada Mah.")
        'BURGAZADA'
        >>> standardize_neighborhood_name("Merkez Mahallesi")
        'MERKEZ'
    """
    if not isinstance(name, str):
        return ""
    name = name.strip()
    name = name.replace("\ufeff", "")
    name = _turkish_upper(name)

    # Known typo corrections across all raw datasets
    typos = {
        "KÂZIM KARABEKİR": "KAZIM KARABEKİR",
        "100.YIL": "100. YIL",
        "YAVUZSELİM": "YAVUZ SELİM",
        "İKİTELLİ OSB": "İKITELLI OSB",
        "GÜMÜSPALA": "GÜMÜŞPALA",
        "MUSTAFA KEMAL PAŞA": "MUSTAFA KEMALPAŞA",
        "YEŞİLKENT MH": "YEŞİLKENT",
        "ATAKÖY 1.KISIM": "ATAKÖY 1. KISIM",
        "ATAKÖY 2-5-6.KISIM": "ATAKÖY 2-5-6. KISIM",
        "ATAKÖY 3-4-11.KISIM": "ATAKÖY 3-4-11. KISIM",
        "ATAKÖY 7-8-9-10.KISIM": "ATAKÖY 7-8-9-10. KISIM",
        "BAHÇEŞEHİR 1.KISIM": "BAHÇEŞEHİR 1. KISIM",
        "BAHÇEŞEHİR 2.KISIM": "BAHÇEŞEHİR 2. KISIM",
        "ZERZEVATÇI": "ZERZAVATÇI",
        "KATİP MUSTAFA ÇELEBİ": "KATİPMUSTAFA ÇELEBİ",
        "KECECİ PİRİ": "KEÇECİ PİRİ",
        "KÜCÜK PİYALE": "KÜÇÜK PİYALE",
        "MÜEYYEDZADE": "MÜEYYETZADE",
        "PİRİ PAŞA": "PİRİPAŞA",
        "MURAT ÇEŞME": "MURAT ÇESME",
        "5. LEVENT": "5.LEVENT",
        "SARIDEMİR": "DEMİRTAŞ",
        "TOPSELVİ MAHALESİ": "TOPSELVİ",
        "KEMALPASA": "KEMALPAŞA",
        "YUNUSEMRE": "YUNUS EMRE",
        "BAHÇEKÖY YENİ MAHALLE": "BAHÇEKÖY YENİ",
        "KUMKÖY [KİLYOS]": "KUMKÖY (KİLYOS)",
        "MERKEZ": "SARIYER MERKEZ",
        "50.YIL": "50. YIL",
        "75.YIL": "75. YIL",
        "YENİ": "SEYMEN",
        "AYDINLI-KOSB": "AYDINLI",
        "TEPEOREN İTOSB": "TEPEÖREN",
        "TELSİZ": "TELSIZ",
        "VELİEFENDİ": "VELIEFENDI",
        "YENİDOĞAN": "SEYİTNİZAM",
        "YEŞİLTEPE": "YEŞILTEPE",
        "FERHATPAŞA SB": "FERHATPAŞA",
        "CUMHURİYET": "CUMHURİYET",
        "DUDULLU OSB": "AŞAĞI DUDULLU",
        "SARAY": "ÇAKMAK",
        "YENİŞEHİR": "ESENŞEHİR",
        "KIZILCAKÖY": "KIZILCA",
        "İZZETPAŞA": "İZZET PAŞA",
        "NENE HATUN": "NENEHATUN",
        "İNÖNU": "İNÖNÜ",
        "NENE HATUN MAH.": "NENEHATUN",
        "BEYLİKDÜZÜ ORGANİZE SANAYİ BÖLGESİ": "MARMARA",
        "BEYLİKDÜZÜ OSB": "MARMARA",
        "AKEVLER MAHALLESİ 7 SOKAK": "AKEVLER",
        "DERİ OSB": "MESCİT",
    }

    # Apply exact or prefix matches
    for bad, good in typos.items():
        if name == bad or name.startswith(bad + " "):
            name = name.replace(bad, good)

    # Suffix kalıpları (sıra önemli: uzundan kısaya)
    suffixes = [
        " MAHALLESİ",
        " MAHALLESI",
        " MAH.",
        " MAH",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    name = re.sub(r"\s+", " ", name).strip()
    return name


def create_composite_key(district: str, neighborhood: str) -> str:
    """İlçe + mahalle birleşik anahtarı oluşturur.

    Args:
        district: Ham ilçe ismi.
        neighborhood: Ham mahalle ismi.

    Returns:
        'İLÇE|MAHALLE' formatında birleşik anahtar.

    Example:
        >>> create_composite_key("Adalar", "Burgazada Mah")
        'ADALAR|BURGAZADA'
    """
    d = standardize_district_name(district)
    n = standardize_neighborhood_name(neighborhood)
    return f"{d}|{n}"
