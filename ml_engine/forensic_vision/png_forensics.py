"""
png_forensics.py
----------------
PNG-specific forensic analysis module for DhanRakshak.

ELA (Error Level Analysis) is fundamentally broken for PNG files: PNG uses
lossless compression, so re-encoding to JPEG and back produces the same
error level for ALL PNGs regardless of tampering. TruFor also performs
poorly on clean, crisp, digitally-generated PNGs because its training set
is dominated by JPEG photos.

This module provides PNG-native forensic checks that detect:

1. **Flat background** — Real photographed/scanned documents have paper
   texture, grain, and noise (background std-dev >> 2.0). Digitally
   generated documents (Word, Photoshop, web export) have perfectly flat
   backgrounds (std-dev < 2.0). This is the strongest single signal.

2. **Zero/minimal metadata** — Scanned/photographed docs always have
   scanner/camera metadata (DPI, software, datetime). A PNG with ZERO
   metadata was deliberately stripped or freshly exported.

3. **Indexed color palette** — PNG images in 'P' mode use a fixed palette
   common in web graphics and generated/designed documents, but very
   uncommon in scanned paper documents.

4. **Alpha channel presence** — Real scanned documents are opaque (RGB).
   RGBA documents are almost always generated/composited digitally.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PNGForensicAnalyzer:
    """
    Forensic checks specific to lossless (PNG) format where ELA fails.

    All methods are pure-function: no model weights, no network access.
    Only numpy and Pillow are required.
    """

    # Background noise thresholds
    # Real photographed A4 paper scanned at 200dpi: std ≈ 4–15
    # Digitally generated documents:                std ≈ 0–1
    _FLAT_BG_STD_THRESHOLD: float = 2.0

    def analyze(self, image_path: str) -> Dict[str, Any]:
        """
        Run PNG forensic checks on the given file.

        Returns
        -------
        dict:
            png_risk_score : float [0, 1] — higher = more suspicious
            is_suspicious  : bool
            flags          : list of human-readable flag strings
            method         : "png_forensics"
            error          : str or None
        """
        path = Path(image_path)

        if not path.exists():
            return self._error_result(f"File not found: {image_path}")

        # Only run on PNG/lossless formats — JPEG already handled by ELA
        if path.suffix.lower() not in {".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}:
            return {
                "png_risk_score": 0.0,
                "is_suspicious": False,
                "flags": [],
                "method": "png_forensics",
                "error": f"Skipped — not a lossless format ({path.suffix})",
            }

        try:
            from PIL import Image
            import numpy as np

            img = Image.open(str(path))
            flags: List[str] = []
            risk: float = 0.0

            # ── Check 1: Metadata presence ───────────────────────────────
            # Real scanned/photographed docs almost always carry metadata
            # (DPI from scanner, software tag, datetime, camera exif).
            # Freshly generated/exported PNGs often have none.
            # Note: metadata_stripped is already flagged by metadata_analyzer;
            # this adds a complementary signal specifically for PNG context.
            png_info_keys = list(img.info.keys()) if img.info else []
            meaningful_keys = {k for k in png_info_keys if k.lower() not in {"srgb", "gamma"}}
            if len(meaningful_keys) == 0:
                flags.append(
                    "PNG has zero meaningful metadata (no DPI, software, datetime) — "
                    "inconsistent with scanner/camera origin; suggests digital generation"
                )
                risk += 0.20
                logger.debug("png_forensics: zero metadata")

            # ── Check 2: Alpha channel (RGBA) ────────────────────────────
            # Real scanned documents are opaque (RGB mode).
            # RGBA documents are composited/generated digitally.
            if img.mode in ("RGBA", "LA", "PA"):
                flags.append(
                    f"Image has alpha channel (mode={img.mode}) — real scanned documents "
                    "are opaque; transparency indicates digital compositing"
                )
                risk += 0.25
                logger.debug("png_forensics: alpha channel detected (%s)", img.mode)

            # ── Check 3: Indexed color palette ───────────────────────────
            # PNG in 'P' (palette) mode uses a fixed colour table — typical
            # of web graphics, diagrams, and generated docs. Very uncommon
            # in document scans.
            if img.mode == "P":
                flags.append(
                    "Image uses indexed color palette (PNG mode=P) — common in "
                    "generated/web graphics, uncommon in photographed/scanned documents"
                )
                risk += 0.15
                logger.debug("png_forensics: indexed palette")

            # ── Check 4: Background flatness ─────────────────────────────
            # The single strongest signal for digital vs photographed.
            # Sample the four corners (typically blank paper in official docs).
            img_gray = img.convert("L")
            arr = __import__("numpy").array(img_gray)
            h, w = arr.shape
            corner_size = max(min(h, w) // 10, 20)

            corners = [
                arr[:corner_size, :corner_size],
                arr[:corner_size, -corner_size:],
                arr[-corner_size:, :corner_size],
                arr[-corner_size:, -corner_size:],
            ]
            corner_stds = [float(c.std()) for c in corners]
            mean_corner_std = sum(corner_stds) / len(corner_stds)

            logger.debug(
                "png_forensics: corner std-dev: %.3f (threshold=%.1f)",
                mean_corner_std, self._FLAT_BG_STD_THRESHOLD,
            )

            if mean_corner_std < self._FLAT_BG_STD_THRESHOLD:
                flags.append(
                    f"Background regions are unnaturally flat (noise std={mean_corner_std:.2f}, "
                    f"threshold={self._FLAT_BG_STD_THRESHOLD}) — real paper has texture/grain; "
                    "flat backgrounds indicate digital generation (Word/Photoshop export)"
                )
                # Severity scales with how flat it is
                # std=0.0 → +0.40, std=1.9 → +0.02
                flatness_contribution = 0.40 * max(
                    0.0, (self._FLAT_BG_STD_THRESHOLD - mean_corner_std) / self._FLAT_BG_STD_THRESHOLD
                )
                risk += flatness_contribution
                logger.debug(
                    "png_forensics: flat background, risk contribution: +%.3f",
                    flatness_contribution,
                )

            risk = round(min(risk, 1.0), 4)
            logger.info(
                "PNGForensicAnalyzer: %s → risk=%.3f, flags=%d (%s)",
                path.name, risk, len(flags),
                [f[:40] + "..." for f in flags]
            )

            return {
                "png_risk_score": risk,
                "is_suspicious": risk > 0.25,
                "flags": flags,
                "method": "png_forensics",
                "corner_std": round(mean_corner_std, 3),
                "error": None,
            }

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("PNGForensicAnalyzer failed for %s: %s", image_path, exc)
            return self._error_result(str(exc))

    @staticmethod
    def _error_result(msg: str) -> Dict[str, Any]:
        return {
            "png_risk_score": 0.0,
            "is_suspicious": False,
            "flags": [],
            "method": "png_forensics",
            "error": msg,
        }
