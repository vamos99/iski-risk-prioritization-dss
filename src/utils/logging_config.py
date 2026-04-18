"""
İSKİ Risk Önceliklendirme — Loglama Konfigürasyonu.

Tüm modüllerde print yerine logging kullanılır.
"""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "iski",
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """Proje genelinde kullanılacak logger'ı yapılandırır.

    Args:
        name: Logger ismi.
        level: Minimum log seviyesi.
        log_file: Opsiyonel dosya çıktısı yolu.

    Returns:
        Yapılandırılmış logger nesnesi.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (opsiyonel)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
