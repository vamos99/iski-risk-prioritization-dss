"""
İSKİ Risk Önceliklendirme — Normalizasyon Modülü.

Track A: Min-Max Normalizasyon (PDF Bölüm 3.2)
Track B: Log(1+x) + Min-Max / Robust Scaler

Open/Closed prensibi: BaseNormalizer abstract → subclass'lar.
"""

import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from config.settings import EPSILON

logger = logging.getLogger("iski.normalizer")


class BaseNormalizer(ABC):
    """Normalizasyon yöntemleri için abstract base class."""

    @abstractmethod
    def transform(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:
        """Verilen sütunları normalize eder.

        Args:
            df: Giriş DataFrame.
            columns: Normalize edilecek sütun isimleri.

        Returns:
            Normalize edilmiş DataFrame (kopya).
        """
        ...

    def validate(self, df: pd.DataFrame, columns: list[str]) -> None:
        """Normalizasyon sonrası [0, 1] aralık kontrolü.

        Args:
            df: Normalize edilmiş DataFrame.
            columns: Kontrol edilecek sütunlar.

        Raises:
            AssertionError: Değerler [0, 1] dışındaysa.
        """
        for col in columns:
            if col not in df.columns:
                continue
            col_min = df[col].min()
            col_max = df[col].max()
            assert col_min >= -EPSILON, (
                f"Normalizasyon hatası: {col} min={col_min:.6f} (< 0)"
            )
            assert col_max <= 1 + EPSILON, (
                f"Normalizasyon hatası: {col} max={col_max:.6f} (> 1)"
            )
        logger.info("Normalizasyon doğrulaması geçildi: tüm değerler [0, 1] ✓")


class MinMaxNormalizer(BaseNormalizer):
    """PDF Bölüm 3.2: Min-Max Normalizasyon.

    x'_ij = (x_ij - min(x_j)) / (max(x_j) - min(x_j))
    max = min durumunda → x'_ij = 0
    """

    def transform(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:
        df = df.copy()
        for col in columns:
            if col not in df.columns:
                continue
            col_min = df[col].min()
            col_max = df[col].max()
            denom = col_max - col_min

            if abs(denom) < EPSILON:
                logger.warning("Sabit sütun tespit edildi: %s → 0 atandı", col)
                df[col] = 0.0
            else:
                df[col] = (df[col] - col_min) / denom

        logger.info("Min-Max normalizasyon uygulandı: %d sütun", len(columns))
        self.validate(df, columns)
        return df


class RobustLogNormalizer(BaseNormalizer):
    """Alternatif: Log(1+x) dönüşüm + Min-Max re-scaling.

    Çarpık dağılımlarda log dönüşüm simetri artırır,
    ardından [0, 1] aralığına Min-Max uygulanır.
    """

    def transform(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> pd.DataFrame:
        df = df.copy()
        for col in columns:
            if col not in df.columns:
                continue
            # Log(1 + x) dönüşüm
            df[col] = np.log1p(df[col])

            # Re-scale [0, 1]
            col_min = df[col].min()
            col_max = df[col].max()
            denom = col_max - col_min

            if abs(denom) < EPSILON:
                df[col] = 0.0
            else:
                df[col] = (df[col] - col_min) / denom

        logger.info("Log+MinMax normalizasyon uygulandı: %d sütun", len(columns))
        self.validate(df, columns)
        return df


def compute_skewness_report(
    df: pd.DataFrame,
    columns: list[str],
    label: str = "",
) -> pd.DataFrame:
    """Normalizasyon sonrası skewness ve kurtosis raporu.

    Args:
        df: Normalize edilmiş DataFrame.
        columns: Raporlanacak sütunlar.
        label: Yöntem etiketi (karşılaştırma için).

    Returns:
        Sütunlar: column, skewness, kurtosis, method
    """
    rows = []
    for col in columns:
        if col not in df.columns:
            continue
        rows.append({
            "column": col,
            "skewness": round(df[col].skew(), 4),
            "kurtosis": round(df[col].kurtosis(), 4),
            "method": label,
        })
    return pd.DataFrame(rows)
