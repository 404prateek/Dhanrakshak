# Error Level Analysis for tamper detection

from __future__ import annotations

from io import BytesIO
from typing import Tuple

import numpy as np
from PIL import Image


class ELADetector:
    """
    Performs Error Level Analysis (ELA) to detect image tampering.

    Workflow:
      1. Load the original image.
      2. Re-save it in memory at a reduced JPEG quality (default 90%).
      3. Compute the absolute per-pixel difference between original and
         re-compressed versions.
      4. Derive a normalised tamper score in [0, 1] and a binary mask
         that highlights the most suspicious (high-error) regions.
    """

    def __init__(self, image_path: str, jpeg_quality: int = 90) -> None:
        """
        Parameters
        ----------
        image_path   : Path to the source image (any PIL-readable format).
        jpeg_quality : JPEG re-save quality level (1–95). Lower values
                       amplify authentic compression artefacts; 90 is the
                       standard ELA baseline.
        """
        if not 1 <= jpeg_quality <= 95:
            raise ValueError("jpeg_quality must be between 1 and 95.")
        self.image_path = image_path
        self.jpeg_quality = jpeg_quality

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_rgb(self) -> Image.Image:
        """Load the source image and normalise to RGB."""
        return Image.open(self.image_path).convert("RGB")

    def _resave_jpeg(self, image: Image.Image) -> Image.Image:
        """Re-compress *image* to JPEG at self.jpeg_quality in memory."""
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=self.jpeg_quality)
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    def _build_ela_map(
        self, original: np.ndarray, recompressed: np.ndarray
    ) -> np.ndarray:
        """
        Compute a per-pixel ELA error map normalised to [0, 1].

        Each pixel value is the mean absolute channel difference divided
        by 255 so the result lies in [0, 1].
        """
        diff = np.abs(original.astype(np.int16) - recompressed.astype(np.int16))
        return diff.mean(axis=2) / 255.0          # shape: (H, W), float64

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> Tuple[float, np.ndarray]:
        """
        Run ELA on the configured image.

        Returns
        -------
        tamper_score : float
            Mean ELA error across the entire image, normalised to [0, 1].
            Higher values indicate greater likelihood of tampering.
        suspicious_mask : np.ndarray, shape (H, W), dtype uint8
            Binary mask: 255 for pixels at or above the 95th-percentile
            error level, 0 elsewhere.  Highlights the most suspicious
            regions for visual inspection or downstream analysis.
        """
        original_img = self._load_rgb()
        recompressed_img = self._resave_jpeg(original_img)

        original_arr = np.asarray(original_img, dtype=np.uint8)
        recompressed_arr = np.asarray(recompressed_img, dtype=np.uint8)

        ela_map = self._build_ela_map(original_arr, recompressed_arr)

        tamper_score: float = float(np.clip(ela_map.mean(), 0.0, 1.0))

        # Threshold at the 95th percentile to isolate the top 5 % of error.
        threshold = float(np.percentile(ela_map, 95))
        suspicious_mask = np.where(ela_map >= threshold, 255, 0).astype(np.uint8)

        return tamper_score, suspicious_mask
