"""
document_ocr.py
---------------
OCR pipeline for banking documents (cheques, account statements, KYC docs,
loan forms, property papers, PAN/Aadhaar, salary slips, court letters).

Extracts structured text fields using Tesseract as the primary engine with
a multi-pass preprocessing strategy that handles BOTH:
  - Scanned hard-copy documents (noisy raster, scanner artifacts)
  - Digitally generated/exported documents (crisp vector text, RGBA PNGs)

Key fixes vs v1:
  - RGBA images: alpha channel stripped before Tesseract (was causing blank output)
  - Multi-pass OCR: 5 strategies, best result selected by character count
  - PDF vector text: direct text extraction before OCR fallback
  - Comprehensive fraud keyword scanner covering all Indian banking doc types

Supported input formats: JPEG, PNG, TIFF, PDF, RGBA PNG.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Government institution whitelist — documents matching these patterns are
# presumed to originate from real government bodies. Institution-validity
# checks are SKIPPED for these documents to prevent false positives.
# ---------------------------------------------------------------------------

_GOVERNMENT_WHITELIST_PATTERNS: List[str] = [
    r'\b(?:district\s*magistrate|tehsildar|collector|sub\s*registrar|executive\s*magistrate)\b',
    r'\b(?:income\s*tax\s*department|GST|GSTIN|traces|nsdl|tin\s*nsdl)\b',
    r'\b(?:canara\s*bank|state\s*bank\s*of\s*india|SBI|HDFC|ICICI|PNB|BOI|BOB|kotak|axis\s*bank|union\s*bank)\b',
    r'\b(?:UIDAI|unique\s*identification\s*authority|aadhaar)\b',
    r'\b(?:ministry|government\s*of|govt\.?\s*of|NCT\s*of\s*delhi|union\s*territory|government\s*of\s*india)\b',
    r'\b(?:revenue\s*officer|revenue\s*department|revenue\s*circle)\b',
    r'\b(?:tehsildar|patwari|naib\s*tehsildar|lekhpal)\b',
    r'\b(?:municipal\s*corporation|MCD|NDMC|BBMP|nagar\s*nigam|nagar\s*palika)\b',
    r'\b(?:EPFO|provident\s*fund|ESI|ESIC|employees\s*provident)\b',
    r'\b(?:sub-registrar|stamp\s*duty|registrar\s*of|registration)\b',
    r'\b(?:notary\s*public|notarial)\b',
    r'\b(?:backward\s*class(?:es)?|OBC|SC/ST|scheduled\s*caste|scheduled\s*tribe|other\s*backward)\b',
    r'\b(?:gazette|official\s*gazette|extraordinary\s*gazette)\b',
    r'\b(?:PAN\s*card|permanent\s*account\s*number|income\s*tax\s*department)\b',
    r'\b(?:caste\s*certificate|income\s*certificate|domicile\s*certificate|birth\s*certificate|character\s*certificate)\b',
    r'\b(?:taluka|taluk|mandal|block|tehsil|sub-division|subdivision)\b',
    r'\b(?:SDM|ADM|DM|BDO|SDO|CDO)\b',  # standard government officer abbreviations
    r'\b(?:high\s*court|supreme\s*court|district\s*court|sessions\s*court|civil\s*court)\b',
    r'\b(?:police\s*station|FIR|first\s*information\s*report)\b',
]


# ---------------------------------------------------------------------------
# Definite fraud patterns — ONLY these should trigger HIGH risk
# These are unambiguous markers that appear ONLY in fake/template documents.
# ---------------------------------------------------------------------------

# Each entry: (signal_name, pattern, severity, message)
# pattern=None means it is handled by special logic below.
_DEFINITE_FRAUD_PATTERNS: List[Tuple[str, str, str, str]] = [
    # Explicit watermarks — only SAMPLE/SPECIMEN/VOID in ALL CAPS as standalone word
    # Regex uses word-boundaries and requires uppercase to avoid false match on
    # normal words like "sample size" in research docs.
    ("sample_watermark",
     r'(?<![A-Za-z])(SAMPLE|SPECIMEN)(?![A-Za-z])',
     "HIGH",
     "Document contains SAMPLE/SPECIMEN watermark"),

    ("void_watermark",
     r'(?<![A-Za-z])VOID(?![A-Za-z])',
     "HIGH",
     "Document contains VOID watermark — document is invalidated"),

    ("demo_marker",
     r'\b(?:FOR\s+DEMO(?:NSTRATION)?\s+ONLY|DEMO\s+ONLY|FOR\s+DEMONSTRATION)\b',
     "HIGH",
     "Document explicitly marked as demo/demonstration only"),

    ("not_valid_marker",
     r'\b(?:NOT\s+VALID|NOT\s+GENUINE|NOT\s+AUTHENTIC|NOT\s+A\s+REAL)\b',
     "HIGH",
     "Document explicitly marked as not valid/genuine"),

    # Placeholder text — only exact phrases, not partial words
    ("lorem_ipsum",
     r'\blorem\s+ipsum\b',
     "HIGH",
     "Placeholder text 'Lorem Ipsum' found — document is a template"),

    ("dummy_text",
     r'\b(?:DUMMY\s+TEXT|PLACEHOLDER\s+TEXT|INSERT\s+TEXT\s+HERE)\b',
     "HIGH",
     "Placeholder/dummy text marker found"),

    # Explicit fake markers — only flag if the word FAKE/FICTIONAL is directly
    # modifying a document noun (not general text like "detect fake loans")
    ("fictional_marker",
     r'\b(?:fictional|fictitious|imaginary)\s+(?:institution|bank|company|entity|document|certificate|logo)\b',
     "HIGH",
     "Document explicitly describes a fictional institution or entity"),

    ("fake_marker",
     r'\bfake\s+(?:bank|institution|company|document|certificate)\b',
     "HIGH",
     "Document references a fake bank/institution/document"),

    ("test_document_marker",
     r'\btest\s+(?:document|certificate|slip|form)\b',
     "HIGH",
     "Test document marker found"),

    # Known unregistered institution names (hardcoded specific names only)
    ("apex_national_finance",
     r'\bAPEX\s+NATIONAL\s+FINANCE\b',
     "HIGH",
     "'Apex National Finance' — known unregistered fictitious institution"),

    ("educational_use_only",
     r'\b(?:FOR\s+EDUCATIONAL\s+(?:USE|PURPOSE)|FOR\s+ACADEMIC\s+USE|EDUCATIONAL\s+PURPOSES?\s+ONLY)\b',
     "HIGH",
     "Document marked for educational/academic use only"),

    # Logo/barcode placeholders — only exact all-caps placeholder text
    ("logo_placeholder",
     r'\b(?:INSERT\s+LOGO|\[LOGO\]|LOGO\s+HERE)\b',
     "MEDIUM",
     "Logo placeholder text found instead of actual logo"),

    ("barcode_placeholder",
     r'\[BARCODE\]|BARCODE\s+HERE|INSERT\s+BARCODE',
     "MEDIUM",
     "Barcode placeholder text found"),

    # Cheque alterations (CANCELLED is MEDIUM — legitimate cancelled cheques exist)
    ("cheque_alteration",
     r'\b(?:OVERWRITTEN|ALTERED\s+AMOUNT|REISSUED)\b',
     "HIGH",
     "Cheque shows signs of alteration"),

    # Unauthorized construction (property docs)
    ("unauthorized_construction",
     r'\bUNAUTHORIZED\s+CONSTRUCTION\b',
     "HIGH",
     "Document references unauthorized construction"),
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class OCRWord:
    """A single recognised word with bounding-box and confidence."""

    text: str
    confidence: float           # 0–100 from Tesseract
    bbox: Tuple[int, int, int, int]  # (left, top, width, height)


@dataclass
class DocumentOCRResult:
    """Full OCR result for a single document page."""

    full_text: str = ""
    words: List[OCRWord] = field(default_factory=list)
    structured_fields: Dict[str, str] = field(default_factory=dict)
    average_confidence: float = 0.0
    language: str = "eng"
    page_count: int = 1
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "full_text": self.full_text,
            "structured_fields": self.structured_fields,
            "average_confidence": self.average_confidence,
            "language": self.language,
            "page_count": self.page_count,
            "word_count": len(self.words),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Field extraction patterns (banking domain)
# ---------------------------------------------------------------------------

_FIELD_PATTERNS: Dict[str, str] = {
    "account_number": r"\b\d{9,18}\b",
    "ifsc_code": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "amount": r"(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{2})?",
    "date": r"\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b",
    "pan_number": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "cheque_number": r"\b\d{6}\b",
    "micr_code": r"\b\d{9}\b",
    "phone": r"\b(?:\+91[-\s]?)?\d{10}\b",
    "email": r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b",
    "pincode": r"\b[1-9]\d{5}\b",
}


def _extract_structured_fields(text: str) -> Dict[str, str]:
    """Apply regex patterns to extract domain-specific banking fields."""
    found: Dict[str, str] = {}
    for field_name, pattern in _FIELD_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found[field_name] = match.group(0).strip()
    return found


# ---------------------------------------------------------------------------
# Image pre-processing helpers
# ---------------------------------------------------------------------------


def _pil_to_rgb(pil_img) -> "PIL.Image.Image":
    """
    Safely convert any PIL image to RGB, stripping alpha.
    RGBA PNGs cause Tesseract to output blank/garbage — this is the
    single most common cause of failed OCR on digitally generated docs.
    """
    if pil_img.mode in ("RGBA", "LA", "PA"):
        # Composite onto white background to remove alpha
        from PIL import Image
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        if pil_img.mode == "RGBA":
            bg.paste(pil_img, mask=pil_img.split()[3])
        else:
            bg.paste(pil_img)
        return bg
    return pil_img.convert("RGB")


def _preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Legacy preprocessing — only used as one pass in multi-pass strategy.
    Converts to greyscale and Otsu-binarises (good for scanned docs with
    scan noise, but destroys crisp digital text — use alongside other passes).
    """
    try:
        import cv2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    except ImportError:
        logger.warning("OpenCV not installed; skipping image pre-processing.")
        return image
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("Pre-processing failed: %s", exc)
        return image


def _extract_pdf_text_direct(pdf_path: str) -> Optional[str]:
    """
    For PDFs: try direct vector text extraction first (PyMuPDF).
    Returns the extracted text if successful, or None to signal
    the caller to fall back to image-based OCR.

    Vector text extraction is 100% accurate and handles all fonts.
    It only fails on scanned-image PDFs (no embedded text layer).
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()
        if len(full_text.strip()) > 20:
            logger.info("PDF vector text extracted: %d chars from %s", len(full_text), pdf_path)
            return full_text
        logger.info("PDF has no embedded text layer — will use image OCR fallback")
        return None
    except ImportError:
        logger.debug("PyMuPDF not available for PDF text extraction")
        return None
    except Exception as exc:
        logger.debug("PDF direct text extraction failed: %s", exc)
        return None


def _load_image_from_bytes(data: bytes) -> Optional[np.ndarray]:
    """Decode image bytes to a NumPy array via Pillow → OpenCV."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        return np.array(img)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("_load_image_from_bytes: %s", exc)
        return None


def _load_pdf_page(data: bytes) -> Optional[np.ndarray]:
    """Render the first PDF page to an image (using PyMuPDF)."""
    try:
        import fitz  # PyMuPDF
        from PIL import Image

        doc = fitz.open(stream=data, filetype="pdf")
        if len(doc) == 0:
            return None
            
        page = doc[0]
        # zoom factor of 3 -> ~300 DPI (approx depending on base DPI)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return np.array(img)
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed; cannot process PDF files. Run 'pip install PyMuPDF'.")
        return None
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("_load_pdf_page: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main OCR class
# ---------------------------------------------------------------------------


class DocumentOCR:
    """
    Multi-engine OCR processor optimised for banking documents.

    Parameters
    ----------
    lang:
        Tesseract language code(s), e.g. ``"eng"`` or ``"eng+hin"``.
    tesseract_config:
        Additional Tesseract config flags (e.g. ``"--psm 6"``).
    preprocess:
        If ``True``, apply binarisation and deskew before OCR.
    use_layoutlm:
        If ``True``, attempt to use the LayoutLM post-processor from
        ``ml_engine.ocr_nlp.layoutlm_extractor`` for field classification.
    """

    def __init__(
        self,
        lang: str = "eng",
        tesseract_config: str = "--oem 3 --psm 6",
        preprocess: bool = True,
        use_layoutlm: bool = False,
    ) -> None:
        self.lang = lang
        self.tesseract_config = tesseract_config
        self.preprocess = preprocess
        self.use_layoutlm = use_layoutlm
        self._tesseract_available = self._check_tesseract()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_tesseract() -> bool:
        try:
            import pytesseract
            import platform

            # On Windows, set the executable path explicitly if not already on PATH
            if platform.system() == "Windows":
                import os
                win_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]
                for p in win_paths:
                    if os.path.isfile(p):
                        pytesseract.pytesseract.tesseract_cmd = p
                        break

            pytesseract.get_tesseract_version()
            return True
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Tesseract not found — DocumentOCR will return stub results. "
                "Install Tesseract OCR and pytesseract to enable full OCR."
            )
            return False

    def _run_tesseract(self, image: np.ndarray) -> Tuple[str, List[OCRWord], float]:
        """
        Multi-pass Tesseract OCR.

        Runs up to 5 preprocessing strategies and picks whichever produces
        the most alphanumeric characters. This handles:
          - Scanned paper docs (noisy): Otsu binarisation + PSM 3
          - Clean digital/generated docs (crisp): upscaled + contrast + PSM 6
          - RGBA PNGs: alpha-composited onto white before any pass
          - Docs with sparse/watermark text: PSM 11

        Diagnostic confirmed: for RGBA crisp digital PNGs, the upscaled
        2x + contrast pass extracts 'Fictional institution, fictional logo,
        BARCODE' correctly while plain PSM 3/6 misses them.
        """
        import pytesseract
        from PIL import Image, ImageEnhance

        # Convert numpy array to PIL for multi-pass
        pil_base = Image.fromarray(image)
        # CRITICAL: strip alpha channel — RGBA causes blank Tesseract output
        pil_rgb = _pil_to_rgb(pil_base)

        results: List[Tuple[str, str, List[OCRWord], float]] = []  # (method, text, words, conf)

        def _tess_on_pil(pil_img, config: str, method: str):
            """Run Tesseract on a PIL image and append to results."""
            try:
                arr = np.array(pil_img)
                data = pytesseract.image_to_data(
                    arr, lang=self.lang, config=config,
                    output_type=pytesseract.Output.DICT,
                )
                wds: List[OCRWord] = []
                confs: List[float] = []
                parts: List[str] = []
                for i in range(len(data["text"])):
                    w = str(data["text"][i]).strip()
                    c = float(data["conf"][i])
                    if w and c >= 0:
                        wds.append(OCRWord(
                            text=w, confidence=c,
                            bbox=(int(data["left"][i]), int(data["top"][i]),
                                  int(data["width"][i]), int(data["height"][i]))
                        ))
                        parts.append(w)
                        confs.append(c)
                txt = " ".join(parts)
                avg = float(np.mean(confs)) if confs else 0.0
                results.append((method, txt, wds, avg))
                logger.debug("OCR pass [%s]: %d alnum chars", method,
                             sum(ch.isalnum() for ch in txt))
            except Exception as exc:
                logger.debug("OCR pass [%s] failed: %s", method, exc)

        # ── PASS 1: RGB, PSM 3 (fully automatic — best for scanned docs) ──
        _tess_on_pil(pil_rgb, "--psm 3 --oem 3", "rgb_psm3")

        # ── PASS 2: RGB, PSM 6 (uniform block — clean printed docs) ──
        _tess_on_pil(pil_rgb, "--psm 6 --oem 3", "rgb_psm6")

        # ── PASS 3: Upscaled 2x + contrast boost (KEY for digital PNGs) ──
        # Diagnostic showed this is the ONLY pass that reads
        # 'Fictional institution, fictional logo, BARCODE' on RGBA PNGs.
        try:
            w, h = pil_rgb.size
            upscaled = pil_rgb.resize((w * 2, h * 2), Image.LANCZOS)
            enhanced = ImageEnhance.Contrast(upscaled).enhance(2.0)
            _tess_on_pil(enhanced, "--psm 6 --oem 3", "upscaled_contrast")
        except Exception as exc:
            logger.debug("Upscale pass failed: %s", exc)

        # ── PASS 4: Adaptive threshold (handles mixed noise + clean text) ──
        try:
            import cv2
            gray = np.array(pil_rgb.convert("L"))
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 31, 11
            )
            _tess_on_pil(Image.fromarray(thresh), "--psm 6 --oem 3", "adaptive_thresh")
        except Exception as exc:
            logger.debug("Adaptive threshold pass failed: %s", exc)

        # ── PASS 5: PSM 11 sparse text (watermarks, scattered text) ──
        _tess_on_pil(pil_rgb, "--psm 11 --oem 3", "sparse_psm11")

        if not results:
            logger.warning("All OCR passes failed — returning empty result")
            return "", [], 0.0

        # Pick the pass with the highest aggregate confidence of valid words
        # (Using raw char count heavily penalizes clean passes and rewards noise)
        best_method, best_text, best_words, best_conf = max(
            results,
            key=lambda r: sum(w.confidence for w in r[2] if w.confidence > 50)
        )
        logger.info(
            "OCR multi-pass complete: best=%s, chars=%d, words=%d, avg_conf=%.1f",
            best_method, len(best_text), len(best_words), best_conf
        )
        return best_text, best_words, best_conf

    def _stub_result(self, reason: str) -> DocumentOCRResult:
        return DocumentOCRResult(
            full_text="",
            error=f"STUB — {reason}",
            average_confidence=0.0,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_image(self, image: np.ndarray) -> DocumentOCRResult:
        """
        Run OCR on a pre-loaded NumPy image array.

        Parameters
        ----------
        image:
            RGB or BGR image array.

        Returns
        -------
        DocumentOCRResult
        """
        if not self._tesseract_available:
            return self._stub_result("Tesseract not installed")

        try:
            full_text, words, avg_conf = self._run_tesseract(image)
            structured = _extract_structured_fields(full_text)
            return DocumentOCRResult(
                full_text=full_text,
                words=words,
                structured_fields=structured,
                average_confidence=avg_conf,
                language=self.lang,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("DocumentOCR.extract_from_image: %s", exc)
            return DocumentOCRResult(error=str(exc))

    def extract_from_bytes(self, data: bytes, mime_type: str = "image/jpeg") -> DocumentOCRResult:
        """
        Extract text from raw file bytes.

        Parameters
        ----------
        data:
            Raw file bytes (JPEG, PNG, TIFF, or PDF).
        mime_type:
            MIME type hint to select the correct decoder.
        """
        if mime_type == "application/pdf":
            image = _load_pdf_page(data)
        else:
            image = _load_image_from_bytes(data)

        if image is None:
            return DocumentOCRResult(error="Could not decode image/document bytes.")

        result = self.extract_from_image(image)
        if mime_type == "application/pdf":
            result.page_count = 1  # only first page processed
        return result

    def extract_from_file(self, file_path: str | Path) -> DocumentOCRResult:
        """Load a file from disk and run OCR."""
        path = Path(file_path)
        if not path.exists():
            return DocumentOCRResult(error=f"File not found: {file_path}")

        mime_type = "application/pdf" if path.suffix.lower() == ".pdf" else "image/jpeg"
        try:
            data = path.read_bytes()
            return self.extract_from_bytes(data, mime_type=mime_type)
        except Exception as exc:  # pylint: disable=broad-except
            return DocumentOCRResult(error=str(exc))


# ---------------------------------------------------------------------------
# CrossDocValidator — cross-document consistency and income fraud detection
# ---------------------------------------------------------------------------


class CrossDocValidator:
    """
    Validates consistency across multiple documents and detects income fraud.

    Income Fraud Logic
    ------------------
    Annualised bank income is derived from ``bank_monthly_avg × 12``.
    If salary is provided, it is also annualised (``salary_monthly × 12``).
    The best available bank-side estimate is compared to ``itr_income``.
    A discrepancy ratio above ``income_tolerance`` triggers a fraud flag.

    Cross-Document Validation
    -------------------------
    ``validate()`` compares field sets (names, PAN, account numbers, dates)
    extracted from two documents and returns a list of conflicts with severity.

    Parameters
    ----------
    income_tolerance:
        Maximum allowed fractional difference between annualised bank income
        and ITR-declared income before flagging inconsistency.
        Default ``0.25`` (25 %).
    name_similarity_threshold:
        Minimum Jaro-Winkler similarity [0, 1] to treat two names as matching.
        Default ``0.88``.
    """

    # Fields checked during cross-document validation and their severity
    _FIELD_SEVERITY: Dict[str, str] = {
        "pan":            "HIGH",
        "account_number": "HIGH",
        "names":          "HIGH",
        "ifsc_code":      "MEDIUM",
        "phone":          "MEDIUM",
        "email":          "LOW",
        "pincode":        "LOW",
    }

    def __init__(
        self,
        income_tolerance: float = 0.25,
        name_similarity_threshold: float = 0.88,
    ) -> None:
        if not 0.0 < income_tolerance < 1.0:
            raise ValueError("income_tolerance must be in (0, 1).")
        self.income_tolerance = income_tolerance
        self.name_similarity_threshold = name_similarity_threshold

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _jaro_winkler(s1: str, s2: str) -> float:
        """
        Pure-Python Jaro-Winkler similarity in [0, 1].
        Falls back to exact-match (0 or 1) on import error.
        """
        try:
            # Use jellyfish if available for accurate computation
            import jellyfish
            return jellyfish.jaro_winkler_similarity(s1, s2)
        except ImportError:
            pass

        # Minimal pure-Python Jaro implementation
        s1, s2 = s1.lower().strip(), s2.lower().strip()
        if s1 == s2:
            return 1.0
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0

        match_dist = max(len1, len2) // 2 - 1
        s1_matches = [False] * len1
        s2_matches = [False] * len2
        matches = 0
        transpositions = 0

        for i in range(len1):
            lo = max(0, i - match_dist)
            hi = min(i + match_dist + 1, len2)
            for j in range(lo, hi):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3.0

        # Winkler prefix bonus (up to 4 chars)
        prefix = 0
        for i in range(min(4, len1, len2)):
            if s1[i] == s2[i]:
                prefix += 1
            else:
                break
        return round(jaro + prefix * 0.1 * (1.0 - jaro), 6)

    def _names_match(self, names1: List[str], names2: List[str]) -> bool:
        """Return True if every name in names1 has a close match in names2."""
        for n1 in names1:
            matched = any(
                self._jaro_winkler(n1, n2) >= self.name_similarity_threshold
                for n2 in names2
            )
            if not matched:
                return False
        return True

    # ------------------------------------------------------------------
    # Income fraud detection
    # ------------------------------------------------------------------

    def validate_income(
        self,
        itr_income: float,
        bank_monthly_avg: Optional[float] = None,
        salary_monthly: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Detect income inflation / suppression fraud.

        Parameters
        ----------
        itr_income:
            Annual income declared in the ITR (rupees).
        bank_monthly_avg:
            Average monthly credit in bank statement (rupees).
            Pass ``None`` if unavailable.
        salary_monthly:
            Monthly salary from payslip (rupees).
            Pass ``None`` if unavailable.

        Returns
        -------
        dict:
            is_consistent     : bool   — True when incomes align within tolerance.
            income_fraud_score: float  — [0, 1] higher = more suspicious.
            flags             : list   — Human-readable anomaly descriptions.
            details           : dict   — Raw comparison values.
        """
        flags: List[str] = []
        discrepancy_scores: List[float] = []

        # --- Bank vs ITR ---
        if bank_monthly_avg is not None and bank_monthly_avg > 0:
            bank_annual = bank_monthly_avg * 12.0
            if itr_income > 0:
                ratio = abs(bank_annual - itr_income) / max(itr_income, bank_annual)
                if ratio > self.income_tolerance:
                    flags.append(
                        f"bank_itr_mismatch: ITR=Rs.{itr_income:,.0f} vs "
                        f"bank_annual=Rs.{bank_annual:,.0f} "
                        f"(gap={ratio:.1%})"
                    )
                    # Score scales linearly: tolerance=25% → 0, 100%+ gap → 1
                    score = min((ratio - self.income_tolerance) / (1.0 - self.income_tolerance), 1.0)
                    discrepancy_scores.append(score)
            else:
                flags.append("itr_income_zero_or_missing")
                discrepancy_scores.append(0.5)

        # --- Salary vs ITR ---
        if salary_monthly is not None and salary_monthly > 0:
            salary_annual = salary_monthly * 12.0
            if itr_income > 0:
                ratio = abs(salary_annual - itr_income) / max(itr_income, salary_annual)
                if ratio > self.income_tolerance:
                    flags.append(
                        f"salary_itr_mismatch: ITR=Rs.{itr_income:,.0f} vs "
                        f"salary_annual=Rs.{salary_annual:,.0f} "
                        f"(gap={ratio:.1%})"
                    )
                    score = min((ratio - self.income_tolerance) / (1.0 - self.income_tolerance), 1.0)
                    discrepancy_scores.append(score)

        # --- Salary vs Bank ---
        if bank_monthly_avg is not None and salary_monthly is not None:
            if bank_monthly_avg > 0 and salary_monthly > 0:
                ratio = abs(bank_monthly_avg - salary_monthly) / max(bank_monthly_avg, salary_monthly)
                if ratio > self.income_tolerance:
                    flags.append(
                        f"salary_bank_mismatch: bank_monthly=Rs.{bank_monthly_avg:,.0f} vs "
                        f"salary_monthly=Rs.{salary_monthly:,.0f} "
                        f"(gap={ratio:.1%})"
                    )
                    score = min((ratio - self.income_tolerance) / (1.0 - self.income_tolerance), 1.0)
                    discrepancy_scores.append(score)

        # Aggregate score: noisy-OR combination
        fraud_score = 0.0
        for s in discrepancy_scores:
            fraud_score = 1.0 - (1.0 - fraud_score) * (1.0 - s)
        fraud_score = round(fraud_score, 6)

        is_consistent = len(flags) == 0

        return {
            "is_consistent":       is_consistent,
            "income_fraud_score":  fraud_score,
            "flags":               flags,
            "details": {
                "itr_income":         itr_income,
                "bank_monthly_avg":   bank_monthly_avg,
                "bank_annual":        (bank_monthly_avg * 12) if bank_monthly_avg else None,
                "salary_monthly":     salary_monthly,
                "salary_annual":      (salary_monthly * 12) if salary_monthly else None,
                "income_tolerance":   self.income_tolerance,
            },
        }

    # ------------------------------------------------------------------
    # Cross-document field validation
    # ------------------------------------------------------------------

    def validate(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
        doc1_type: str = "Document 1",
        doc2_type: str = "Document 2",
    ) -> Dict[str, Any]:
        """
        Compare two structured document dicts for field-level conflicts.

        Parameters
        ----------
        doc1, doc2:
            Dicts mapping field names to values.  Field values may be scalars
            or lists (e.g. ``{"names": ["Ramesh Kumar"], "pan": ["ABCDE1234F"]}``).
        doc1_type, doc2_type:
            Human-readable document type labels used in conflict messages.

        Returns
        -------
        dict:
            conflicts    : list of conflict dicts (type, severity, message, field).
            is_consistent: bool — True when no conflicts detected.
            conflict_count: int
        """
        conflicts: List[Dict[str, str]] = []

        shared_fields = set(doc1.keys()) & set(doc2.keys()) & set(self._FIELD_SEVERITY.keys())

        for field_name in shared_fields:
            v1 = doc1[field_name]
            v2 = doc2[field_name]

            # Normalise to lists
            list1: List[str] = [v1] if isinstance(v1, str) else list(v1)
            list2: List[str] = [v2] if isinstance(v2, str) else list(v2)

            severity = self._FIELD_SEVERITY[field_name]

            if field_name == "names":
                # Use fuzzy matching for names
                if not self._names_match(list1, list2):
                    conflicts.append({
                        "type":     "name_mismatch",
                        "severity": severity,
                        "message":  (
                            f"Name mismatch between {doc1_type} and {doc2_type}: "
                            f"{', '.join(list1)} vs {', '.join(list2)}"
                        ),
                        "field": field_name,
                    })
            else:
                # Exact set comparison for identifiers
                set1 = {s.upper().strip() for s in list1}
                set2 = {s.upper().strip() for s in list2}
                if set1 != set2:
                    conflicts.append({
                        "type":     f"{field_name}_mismatch",
                        "severity": severity,
                        "message":  (
                            f"{field_name.upper()} mismatch between {doc1_type} and {doc2_type}: "
                            f"{', '.join(sorted(set1))} vs {', '.join(sorted(set2))}"
                        ),
                        "field": field_name,
                    })

        return {
            "conflicts":      conflicts,
            "is_consistent":  len(conflicts) == 0,
            "conflict_count": len(conflicts),
            "doc1_type":      doc1_type,
            "doc2_type":      doc2_type,
        }


# ---------------------------------------------------------------------------
# IndianDocumentOCR — structured entity extractor for Indian banking documents
# ---------------------------------------------------------------------------


class IndianDocumentOCR:
    """
    High-level OCR wrapper tailored for Indian banking and KYC documents.

    Extracts named entities (name, PAN, Aadhaar, account number, amounts,
    dates) from document images using regex heuristics on Tesseract OCR text.
    Falls back to empty lists gracefully when Tesseract is unavailable.

    Usage
    -----
    ocr = IndianDocumentOCR()
    entities = ocr.extract('path/to/doc.jpg')
    # {"names": [...], "pan": [...], "amounts": [...], ...}
    """

    # Pattern library for Indian document fields
    _PATTERNS: Dict[str, str] = {
        "pan":            r"\b[A-Z]{5}\d{4}[A-Z]\b",
        "aadhaar":        r"\b\d{4}\s\d{4}\s\d{4}\b",
        # Account numbers: require explicit label prefix OR 11+ digits (phones are only 10)
        "account_number": r"(?:(?:A/c|Account|Acct|Ac)\s*(?:No\.?|Number|#)?\s*[:\-]?\s*[\d\s\-]{6,20}|\b\d{11,18}\b)",
        "ifsc":           r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        "amounts":        r"(?:Rs\.?|INR|\u20b9)\s*[\d,]+(?:\.\d{2})?",
        "dates":          r"\b\d{1,2}[/\-.\\]\d{1,2}[/\-.\\]\d{2,4}\b",
        "phone":          r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b",
        "pincode":        r"\b[1-9]\d{5}\b",
    }

    # Heuristic name patterns for Indian names.
    _NAME_PATTERN = re.compile(
        r"(?:(?:Name|certify that|Mr\.?|Mrs\.?|Ms\.?|Miss|Shri|Smt)\s*[:\-]?\s*)([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){1,3})",
        re.IGNORECASE,
    )

    def __init__(self, lang: str = "eng") -> None:
        self._ocr = DocumentOCR(lang=lang)

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """Return True only for plausible human names; rejects OCR garbage."""
        # Known Indian honorifics/titles that may appear all-caps
        _ALLOWED_ALLCAPS = {'MR', 'MRS', 'MS', 'DR', 'SHRI', 'SMT', 'KUM'}

        name = name.strip()
        if len(name) < 5:   return False   # e.g. "A B" is too short overall
        if len(name) > 60:  return False   # absurdly long
        # Must contain at least one space (first + last name minimum)
        if ' ' not in name: return False
        # No digits inside a name
        if any(c.isdigit() for c in name): return False
        # Only letters, spaces, dots, and hyphens allowed
        if re.search(r"[^a-zA-Z\s\.\-]", name): return False
        # Every individual word must be at least 3 characters
        # (except known honorifics like Mr, Dr, Ms which are only 2)
        _ALLOWED_ALLCAPS = {'MR', 'MRS', 'MS', 'DR', 'SHRI', 'SMT', 'KUM'}
        words = name.split()
        for w in words:
            if w.upper() in _ALLOWED_ALLCAPS:
                continue          # allowed honorific (Dr, MR, Shri, etc.) — skip all checks
            if len(w) < 3:
                return False      # word too short
            if w.isupper():
                return False      # any other all-caps word is OCR garbage
        return True

    def _detect_fraud_signals(self, text: str) -> List[Dict[str, Any]]:
        """
        Whitelist-first fraud signal detection.

        Philosophy:
        - STEP 1: Check if any government institution pattern matches.
          If yes → document is a government doc. Only check for explicit
          watermarks/placeholders. NEVER flag institution names.
        - STEP 2: For non-government documents, scan against DEFINITE fraud
          patterns only — patterns that are unambiguous fake markers.
        - STEP 3: Run document-type-specific checks (ITR ack, Salary PF).

        False negatives (missing a real fraud) are preferable to false
        positives (rejecting a genuine government document).
        """
        conflicts: List[Dict[str, Any]] = []
        seen: set = set()

        # ── STEP 1: Government whitelist check ──────────────────────────────
        is_government_doc = any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in _GOVERNMENT_WHITELIST_PATTERNS
        )

        if is_government_doc:
            # Government docs: ONLY check for explicit watermarks/placeholder text.
            # Do NOT check institution names — we know this is a real government body.
            _GOV_SAFE_SIGNALS = {
                "sample_watermark", "void_watermark", "lorem_ipsum",
                "dummy_text", "demo_marker", "not_valid_marker",
            }
            for signal_name, pattern, severity, message in _DEFINITE_FRAUD_PATTERNS:
                if signal_name not in _GOV_SAFE_SIGNALS:
                    continue
                # Watermarks must be exactly ALL CAPS. Other text can be case-insensitive.
                flags = 0 if signal_name in ("sample_watermark", "void_watermark") else re.IGNORECASE
                if re.search(pattern, text, flags):
                    if message not in seen:
                        seen.add(message)
                        conflicts.append({
                            "type":     signal_name,
                            "severity": severity,
                            "message":  message,
                        })
                        logger.warning(
                            "Fraud signal [%s] in government doc: %s", severity, signal_name
                        )
            # Return early — skip all institution and structural checks
            return conflicts

        # ── STEP 2: Non-government doc — scan definite fraud patterns ───────
        for signal_name, pattern, severity, message in _DEFINITE_FRAUD_PATTERNS:
            flags = 0 if signal_name in ("sample_watermark", "void_watermark") else re.IGNORECASE
            if re.search(pattern, text, flags):
                if message not in seen:
                    seen.add(message)
                    conflicts.append({
                        "type":     signal_name,
                        "severity": severity,
                        "message":  message,
                    })
                    logger.warning("Fraud signal [%s]: %s", severity, signal_name)

        # ── STEP 3: Document-type-specific structural checks ─────────────────
        # ITR without 15-digit acknowledgment number
        if re.search(r'\bINCOME\s+TAX\s+RETURN\b|\bITR[-\s]?[V1-9]\b', text, re.IGNORECASE):
            if not re.search(r'\b\d{15}\b', text):
                msg = "ITR document missing valid 15-digit acknowledgment number — common in fabricated ITRs"
                if msg not in seen:
                    seen.add(msg)
                    conflicts.append({
                        "type":     "itr_missing_acknowledgment",
                        "severity": "HIGH",
                        "message":  msg,
                    })

        # Salary slip without PF/UAN number
        if re.search(r'\b(?:SALARY\s+SLIP|PAY\s+SLIP|PAYSLIP)\b', text, re.IGNORECASE):
            if not re.search(r'\bUAN\b|\bPF\s*(?:No|Number|#|A/c)\b', text, re.IGNORECASE):
                msg = "Salary slip missing PF/UAN reference — commonly absent in fabricated pay slips"
                if msg not in seen:
                    seen.add(msg)
                    conflicts.append({
                        "type":     "salary_missing_pf_uan",
                        "severity": "MEDIUM",
                        "message":  msg,
                    })

        # Freeze/attachment order without case number
        if re.search(r'\b(?:FREEZE|ATTACH)\s+(?:ACCOUNT|TRANSACTION)\b', text, re.IGNORECASE):
            if not re.search(r'\bCASE\s*(?:NO|NUMBER|#)\b', text, re.IGNORECASE):
                msg = "Court/compliance freeze order missing case number — may be fabricated"
                if msg not in seen:
                    seen.add(msg)
                    conflicts.append({
                        "type":     "freeze_order_missing_case_number",
                        "severity": "HIGH",
                        "message":  msg,
                    })

        return conflicts

    def extract(self, image_path: str) -> Dict[str, Any]:
        """
        Extract structured entities from an Indian document image.

        Parameters
        ----------
        image_path : Path to the document image (JPEG, PNG, PDF).

        Returns
        -------
        dict with keys:
            names, pan, aadhaar, account_number, ifsc, amounts,
            dates, phone, pincode, full_text, fraud_signals, doc_type, error
        """
        result: Dict[str, Any] = {
            "names":          [],
            "pan":            [],
            "aadhaar":        [],
            "account_number": [],
            "ifsc":           [],
            "amounts":        [],
            "dates":          [],
            "phone":          [],
            "pincode":        [],
            "full_text":      "",
            "fraud_signals":  [],   # NEW: inline fraud keyword conflicts
            "error":          None,
        }

        try:
            path = Path(image_path)
            text = ""

            # ── PDF: try vector text extraction first (perfect accuracy) ──
            if path.suffix.lower() == ".pdf":
                direct_text = _extract_pdf_text_direct(str(path))
                if direct_text:
                    text = direct_text
                    result["full_text"] = text
                    logger.info("PDF text extracted directly (vector): %d chars", len(text))

            # ── Image (or PDF with no text layer): use multi-pass OCR ──
            if not text:
                ocr_result = self._ocr.extract_from_file(image_path)
                if ocr_result.error and not ocr_result.full_text:
                    result["error"] = ocr_result.error
                    return result
                text = ocr_result.full_text or ""
                result["full_text"] = text
                logger.info("OCR extracted %d chars from %s", len(text), path.name)

            if not text.strip():
                logger.warning("Zero text extracted from %s — fraud signals unavailable", path.name)
                result["doc_type"] = "Unknown Document"
                return result

            # ── Entity extraction via regex ──
            for field_name, pattern in self._PATTERNS.items():
                matches = re.findall(pattern, text, re.IGNORECASE)
                result[field_name] = list(dict.fromkeys(matches))

            name_matches = self._NAME_PATTERN.findall(text)
            result["names"] = [
                n for n in dict.fromkeys(name_matches)
                if self._is_valid_name(n)
            ]

            sf = getattr(self._ocr.extract_from_file(image_path), "structured_fields", {})
            if sf.get("pan_number") and sf["pan_number"] not in result["pan"]:
                result["pan"].append(sf["pan_number"])

            # ── Fraud signal keyword scan (Stage 3) ──
            result["fraud_signals"] = self._detect_fraud_signals(text)
            if result["fraud_signals"]:
                logger.warning(
                    "IndianDocumentOCR: %d fraud signals detected in %s",
                    len(result["fraud_signals"]), path.name
                )

            # ── Document type detection ──
            lower_text = text.lower()
            if any(kw in lower_text for kw in ["sale deed", "gpa", "power of attorney", "property", "conveyance", "gift deed"]):
                result["doc_type"] = "Property/Legal Document"
            elif any(kw in lower_text for kw in ["income tax return", "itr", "assessment year"]):
                result["doc_type"] = "ITR Document"
            elif any(kw in lower_text for kw in ["statement of account", "bank statement", "account statement"]):
                result["doc_type"] = "Bank Statement"
            elif any(kw in lower_text for kw in ["salary slip", "pay slip", "payslip", "salary certificate"]):
                result["doc_type"] = "Salary Slip"
            elif any(kw in lower_text for kw in ["loan application", "loan form", "home loan", "personal loan"]):
                result["doc_type"] = "Loan Application"
            elif "permanent account number" in lower_text or "income tax department" in lower_text:
                result["doc_type"] = "PAN Card"
            elif "aadhaar" in lower_text or "unique identification authority" in lower_text:
                result["doc_type"] = "Aadhaar Card"
            elif any(kw in lower_text for kw in ["cheque", "payable to", "bearer", "micr"]):
                result["doc_type"] = "Cheque"
            # Government certificates — must come BEFORE the Unknown fallback
            elif any(kw in lower_text for kw in ["other backward class", "obc certificate", "backward class certificate"]):
                result["doc_type"] = "OBC Certificate"
            elif any(kw in lower_text for kw in ["caste certificate", "scheduled caste", "scheduled tribe", "sc/st certificate"]):
                result["doc_type"] = "Caste Certificate"
            elif any(kw in lower_text for kw in ["income certificate", "annual income", "family income"]):
                result["doc_type"] = "Income Certificate"
            elif any(kw in lower_text for kw in ["domicile certificate", "residence certificate", "residential certificate"]):
                result["doc_type"] = "Domicile Certificate"
            elif any(kw in lower_text for kw in ["character certificate", "conduct certificate"]):
                result["doc_type"] = "Character Certificate"
            elif any(kw in lower_text for kw in ["district magistrate", "tehsildar", "collector office", "revenue department"]):
                result["doc_type"] = "Government Certificate"
            else:
                result["doc_type"] = "Unknown Document"

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("IndianDocumentOCR.extract: %s", exc)
            result["error"] = str(exc)

        return result

