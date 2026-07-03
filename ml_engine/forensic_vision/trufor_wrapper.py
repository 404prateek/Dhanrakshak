"""
trufor_wrapper.py
-----------------
Wrapper around the TruFor (Trusted Forensics) model for image manipulation
detection. Falls back to ELA (Error Level Analysis) if the TruFor checkpoint
is missing or fails to load.

PDF Support
-----------
PDFs are rendered to a PIL Image via PyMuPDF (fitz) at 150 DPI before analysis.
If PyMuPDF is unavailable, pdf2image is tried as a fallback.
If neither is installed, returns method='UNSUPPORTED_FORMAT' with
integrity_score=None (not 0.0, which would falsely imply tampering).
"""

from __future__ import annotations

import base64
import logging
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from ml_engine.forensic_vision.png_forensics import PNGForensicAnalyzer

logger = logging.getLogger(__name__)

# Add TruFor/TruFor_train_test to sys.path (lib/ and config/ live there)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRUFOR_TRAIN_TEST_DIR = os.path.join(_PROJECT_ROOT, "TruFor", "TruFor_train_test")
if os.path.isdir(TRUFOR_TRAIN_TEST_DIR) and TRUFOR_TRAIN_TEST_DIR not in sys.path:
    sys.path.insert(0, TRUFOR_TRAIN_TEST_DIR)


# ---------------------------------------------------------------------------
# Universal document → PIL Image loader
# ---------------------------------------------------------------------------

def _load_as_pil_image(file_path: str) -> Optional[Image.Image]:
    """
    Load any supported document as a PIL RGB Image.

    Handles:
    - JPEG, PNG, TIFF, BMP, WebP  → direct Pillow open
    - PDF                          → page 1 rendered at 150 DPI via PyMuPDF
                                     (falls back to pdf2image if PyMuPDF missing)

    Returns None when the format cannot be converted, so callers can return
    UNSUPPORTED_FORMAT instead of a misleading 0.0 integrity score.
    """
    suffix = Path(file_path).suffix.lower()

    # ── Raster images ───────────────────────────────────────────────────
    if suffix in {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".gif"}:
        try:
            return Image.open(file_path).convert("RGB")
        except Exception as exc:
            logger.error("Cannot open image %s: %s", file_path, exc)
            return None

    # ── PDF via PyMuPDF (fitz) ──────────────────────────────────────────
    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            if len(doc) == 0:
                logger.warning("PDF %s has no pages.", file_path)
                return None
            page = doc.load_page(0)
            mat = fitz.Matrix(150 / 72, 150 / 72)   # 150 DPI
            pix = page.get_pixmap(matrix=mat, alpha=False)
            return Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
        except ImportError:
            logger.debug("PyMuPDF not available; trying pdf2image for %s", file_path)
        except Exception as exc:
            logger.error("PyMuPDF failed for %s: %s — trying pdf2image.", file_path, exc)

        # ── PDF fallback: pdf2image + poppler ───────────────────────────
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(file_path, dpi=150, first_page=1, last_page=1)
            if pages:
                return pages[0].convert("RGB")
        except ImportError:
            logger.warning(
                "Neither PyMuPDF nor pdf2image installed — cannot render PDF %s.", file_path
            )
        except Exception as exc:
            logger.error("pdf2image failed for %s: %s", file_path, exc)
        return None

    # ── Unknown format ───────────────────────────────────────────────────
    logger.warning("Unsupported extension '%s' — cannot analyse %s.", suffix, file_path)
    return None


# ---------------------------------------------------------------------------
# TruForDetector
# ---------------------------------------------------------------------------

class TruForDetector:
    """
    Detects document tampering using TruFor if available, else ELA.
    All input files (including PDFs) are converted to PIL before analysis.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Flag to ensure __init__ only runs once
            cls._instance._is_initialized = False
        return cls._instance

    def __init__(self, checkpoint_path: str = None) -> None:
        if getattr(self, "_is_initialized", False):
            return
        
        self.is_available = False
        self.model = None
        self.device = "cpu"

        if checkpoint_path is None:
            _ml_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            checkpoint_path = os.path.join(
                _ml_dir, "training", "checkpoints", "trufor", "trufor.pth.tar"
            )

        self.checkpoint_path = checkpoint_path
        self._try_load_trufor()

    # ------------------------------------------------------------------

    def _try_load_trufor(self) -> None:
        if not os.path.exists(self.checkpoint_path):
            logger.warning(
                "TruFor checkpoint not found at %s. Using ELA fallback.",
                self.checkpoint_path,
            )
            return

        original_cwd = os.getcwd()
        try:
            import torch
            from lib.config import config, update_config
            from lib.utils import get_model
            from argparse import Namespace

            os.chdir(TRUFOR_TRAIN_TEST_DIR)
            args = Namespace(experiment="trufor_ph3", opts=None)
            update_config(config, args)

            config.defrost()
            if config.MODEL.PRETRAINED:
                config.MODEL.PRETRAINED = os.path.join(
                    TRUFOR_TRAIN_TEST_DIR, config.MODEL.PRETRAINED
                )
            config.freeze()

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            checkpoint = torch.load(
                self.checkpoint_path,
                map_location=torch.device(self.device),
                weights_only=False,
            )
            self.model = get_model(config)
            self.model.load_state_dict(checkpoint["state_dict"])
            self.model = self.model.to(self.device)
            self.model.eval()
            self.is_available = True
            logger.info("TruFor model loaded successfully on %s.", self.device)
        except Exception:
            logger.exception("Failed to load TruFor model. Using ELA fallback.")
            self.is_available = False
        finally:
            os.chdir(original_cwd)
            self._is_initialized = True

    # ------------------------------------------------------------------

    def _numpy_to_b64(self, array: np.ndarray) -> str:
        if array is None:
            return ""
        try:
            import cv2
            heatmap = cv2.applyColorMap(np.uint8(255 * array), cv2.COLORMAP_JET)
            _, buffer = cv2.imencode(".jpg", heatmap)
            return base64.b64encode(buffer).decode("utf-8")
        except Exception:
            img = Image.fromarray(np.uint8(255 * array), "L")
            buf = BytesIO()
            img.save(buf, format="JPEG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, file_path: str) -> Dict[str, Any]:
        """
        Analyse a document for visual tampering.
        Supports JPEG, PNG, TIFF, BMP, WebP, and PDF.
        """
        if not os.path.exists(file_path):
            return {
                "integrity_score": None,
                "is_tampered": False,
                "method": "FILE_NOT_FOUND",
                "heatmap_b64": "",
                "error": f"File not found: {file_path}",
            }

        pil_image = _load_as_pil_image(file_path)

        if pil_image is None:
            return {
                "integrity_score": None,   # None = unknown, not "tampered"
                "is_tampered": False,
                "method": "UNSUPPORTED_FORMAT",
                "heatmap_b64": "",
                "error": "Document format cannot be rendered for forensic analysis.",
            }

        MAX_DIM = 512
        if max(pil_image.size) > MAX_DIM:
            ratio = MAX_DIM / max(pil_image.size)
            new_size = (int(pil_image.size[0]*ratio), int(pil_image.size[1]*ratio))
            pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

        # ── Run Primary Pixel Forensics (TruFor/ELA) ──
        pixel_result = (
            self._analyze_trufor(pil_image)
            if self.is_available
            else self._analyze_ela(pil_image)
        )

        # ── Run PNG-Native Forensics (if applicable) ──
        suffix = Path(file_path).suffix.lower()
        if suffix in {".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}:
            png_analyzer = PNGForensicAnalyzer()
            png_result = png_analyzer.analyze(file_path)

            if not png_result.get("error"):
                png_risk = png_result.get("png_risk_score", 0.0)
                png_integrity = round(max(0.0, 1.0 - png_risk), 6)

                # Take the worst case between pixel forensics and PNG forensics
                base_integrity = pixel_result.get("integrity_score", 1.0)
                if base_integrity is None:
                    base_integrity = 1.0
                
                final_integrity = min(base_integrity, png_integrity)
                
                pixel_result["integrity_score"] = final_integrity
                pixel_result["is_tampered"] = final_integrity < 0.6
                pixel_result["method"] = f"{pixel_result['method']} + PNG_Forensics"
                
                # Attach the PNG flags
                if "png_flags" not in pixel_result:
                    pixel_result["png_flags"] = []
                pixel_result["png_flags"].extend(png_result.get("flags", []))

        return pixel_result

    # ------------------------------------------------------------------
    # Internal analysis methods (accept PIL, not file paths)
    # ------------------------------------------------------------------

    def _analyze_trufor(self, pil_image: Image.Image) -> Dict[str, Any]:
        try:
            import torch
            import torchvision.transforms as T

            tensor = T.ToTensor()(pil_image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                pred, conf, det, npp = self.model(tensor, save_np=False)

            integrity_score = (
                1.0 - torch.sigmoid(det).item() if det is not None else 0.5
            )
            anomaly_map = (
                torch.softmax(pred.squeeze(0), dim=0)[1].cpu().numpy()
                if pred is not None
                else np.zeros((10, 10))
            )
            return {
                "integrity_score": round(float(integrity_score), 6),
                "is_tampered": integrity_score < 0.5,
                "method": "TruFor",
                "heatmap_b64": self._numpy_to_b64(anomaly_map),
                "error": None,
            }
        except Exception as exc:
            logger.error("TruFor inference failed: %s — falling back to ELA.", exc)
            return self._analyze_ela(pil_image)

    def _analyze_ela(self, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Error Level Analysis on a pre-rendered PIL image.

        ELA score for clean, unmodified documents is typically very small
        (< 0.01). The mapping  integrity = 1 - score*50  converts that to
        a score close to 1.0 (highly authentic). A heavily edited image
        with ELA score ~0.05+ will land below 0.5 (suspicious).
        """
        try:
            img_rgb = pil_image.convert("RGB")
            original_arr = np.asarray(img_rgb, dtype=np.uint8)

            buf = BytesIO()
            img_rgb.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            recompressed = np.asarray(Image.open(buf).convert("RGB"), dtype=np.uint8)

            diff = np.abs(original_arr.astype(np.int16) - recompressed.astype(np.int16))
            ela_map = diff.mean(axis=2) / 255.0   # (H, W), float in [0, 1]

            raw_score = float(np.clip(ela_map.mean(), 0.0, 1.0))

            # Scale: clean images score ~0.003–0.015 → integrity ≈ 0.85–1.0
            # Tampered images score ~0.05+             → integrity ≤ 0.0
            integrity_score = round(max(0.0, min(1.0 - raw_score * 50, 1.0)), 6)

            threshold = float(np.percentile(ela_map, 95))
            suspicious_mask = np.where(ela_map >= threshold, 255, 0).astype(np.uint8)

            return {
                "integrity_score": integrity_score,
                "is_tampered": integrity_score < 0.6,
                "method": "ELA",
                "heatmap_b64": self._numpy_to_b64(suspicious_mask),
                "error": None,
                "ela_raw_score": round(raw_score, 6),
            }
        except Exception as exc:
            logger.error("ELA analysis failed: %s", exc)
            return {
                "integrity_score": None,
                "is_tampered": False,
                "method": "ELA_ERROR",
                "heatmap_b64": "",
                "error": str(exc),
            }
