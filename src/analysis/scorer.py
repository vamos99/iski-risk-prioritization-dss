"""
İSKİ Risk Önceliklendirme — Bileşik Skor Hesaplama Modülü.

Track A : WLC (Weighted Linear Combination) — PDF Bölüm 3.5
Track B1: Multiplikatif (Geometrik Ortalama)
Track B2: TOPSIS

Her üç yöntem de aynı interface'e sahiptir: .score(df, columns, weights) → Series
"""

import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from config.settings import EPSILON

logger = logging.getLogger("iski.scorer")


class BaseScorer(ABC):
    """Bileşik skor yöntemleri için abstract base class."""

    @abstractmethod
    def score(
        self,
        df: pd.DataFrame,
        columns: list[str],
        weights: dict[str, float],
    ) -> pd.Series:
        """Bileşik risk skorunu hesaplar.

        Args:
            df: Normalize edilmiş DataFrame.
            columns: Kriter sütunları.
            weights: Kriter ağırlıkları {sütun: ağırlık}.

        Returns:
            Her mahalle için bileşik risk skoru (pd.Series).
        """
        ...


class WLCScorer(BaseScorer):
    """PDF Bölüm 3.5: Ağırlıklı Doğrusal Birleşim.

    R_i = Σ (w_j × x'_ij)
    Toplamsal: compensability var.
    """

    def score(
        self,
        df: pd.DataFrame,
        columns: list[str],
        weights: dict[str, float],
    ) -> pd.Series:
        result = pd.Series(0.0, index=df.index)

        for col in columns:
            w = weights.get(col, 0)
            result += w * df[col]

        logger.info(
            "WLC bileşik skor hesaplandı: min=%.4f, max=%.4f, mean=%.4f",
            result.min(), result.max(), result.mean(),
        )
        return result


class MultiplicativeScorer(BaseScorer):
    """Multiplikatif (Geometrik Ortalama) skor.

    R_i = Π (x'_ij + ε) ^ w_j
    Compensability yok: tek bir boyutta sıfır olan mahalle cezalandırılır.
    """

    def score(
        self,
        df: pd.DataFrame,
        columns: list[str],
        weights: dict[str, float],
    ) -> pd.Series:
        result = pd.Series(1.0, index=df.index)

        for col in columns:
            w = weights.get(col, 0)
            # Epsilon ekleme: 0^w = 0 sorununu önler
            values = df[col] + EPSILON
            result *= values ** w

        logger.info(
            "Multiplikatif skor hesaplandı: min=%.4f, max=%.4f, mean=%.4f",
            result.min(), result.max(), result.mean(),
        )
        return result


class TOPSISScorer(BaseScorer):
    """TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution).

    Adımlar:
      1. Ağırlıklı normalize matris: v_ij = w_j × x'_ij
      2. İdeal en iyi (A+) ve en kötü (A-) noktalar
      3. Her mahallenin mesafesi: D+ ve D-
      4. Skor: S_i = D- / (D+ + D-)
    """

    def score(
        self,
        df: pd.DataFrame,
        columns: list[str],
        weights: dict[str, float],
    ) -> pd.Series:
        # Ağırlıklı matris
        weighted = pd.DataFrame(index=df.index)
        for col in columns:
            w = weights.get(col, 0)
            weighted[col] = w * df[col]

        # İdeal çözümler (tüm kriterler "benefit" → yüksek = kötü = riskli)
        ideal_best = weighted.max()   # En riskli nokta (A+)
        ideal_worst = weighted.min()  # En güvenli nokta (A-)

        # Öklid mesafeleri
        d_positive = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
        d_negative = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

        # TOPSIS skoru
        denom = d_positive + d_negative
        result = np.where(denom > EPSILON, d_negative / denom, 0)
        result = pd.Series(result, index=df.index)

        logger.info(
            "TOPSIS skor hesaplandı: min=%.4f, max=%.4f, mean=%.4f",
            result.min(), result.max(), result.mean(),
        )
        return result
