"""
document_ocr.py
---------------
OCR pipeline for banking documents (cheques, account statements, KYC docs,
loan forms). Extracts structured text fields using Tesseract as the primary
engine with an optional LayoutLM-based post-processor for field classification.

Supported input formats: JPEG, PNG, TIFF, PDF (first page only via pdf2image).
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


def _preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Apply standard OCR pre-processing:
    - Convert to greyscale
    - Deskew (approximate via rotation)
    - Binarise with Otsu threshold
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
        """Run Tesseract on a pre-processed image array."""
        import pytesseract

        if self.preprocess:
            image = _preprocess_for_ocr(image)

        data: Dict[str, Any] = pytesseract.image_to_data(
            image,
            lang=self.lang,
            config=self.tesseract_config,
            output_type=pytesseract.Output.DICT,
        )

        words: List[OCRWord] = []
        confidences: List[float] = []
        text_parts: List[str] = []

        n = len(data["text"])
        for i in range(n):
            word_text = str(data["text"][i]).strip()
            conf = float(data["conf"][i])
            if word_text and conf >= 0:
                words.append(
                    OCRWord(
                        text=word_text,
                        confidence=conf,
                        bbox=(
                            int(data["left"][i]),
                            int(data["top"][i]),
                            int(data["width"][i]),
                            int(data["height"][i]),
                        ),
                    )
                )
                text_parts.append(word_text)
                confidences.append(conf)

        full_text = " ".join(text_parts)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        return full_text, words, avg_conf

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
    # Stops capturing at any all-caps token (2+ chars) to avoid "Ramesh Kumar PAN ABCDE" over-capture.
    _NAME_PATTERN = re.compile(
        r"(?:Name\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+(?!(?:[A-Z]{2,}\b))[A-Z][a-z]+){1,3})",
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
            dates, phone, pincode, full_text, error
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
            "error":          None,
        }

        try:
            ocr_result = self._ocr.extract_from_file(image_path)
            if ocr_result.error:
                result["error"] = ocr_result.error
                # Return stub data so pipeline continues
                return result

            text = ocr_result.full_text or ""
            result["full_text"] = text

            # Extract named entities via regex
            for field_name, pattern in self._PATTERNS.items():
                matches = re.findall(pattern, text, re.IGNORECASE)
                result[field_name] = list(dict.fromkeys(matches))  # deduplicate, preserve order

            # Extract names using the heuristic pattern and filter OCR garbage
            name_matches = self._NAME_PATTERN.findall(text)
            result["names"] = [
                n for n in dict.fromkeys(name_matches)   # deduplicate
                if self._is_valid_name(n)
            ]

            # Also check structured_fields populated by DocumentOCR
            sf = ocr_result.structured_fields
            if sf.get("pan_number") and sf["pan_number"] not in result["pan"]:
                result["pan"].append(sf["pan_number"])

            # Document type detection based on keywords
            lower_text = text.lower()
            if any(kw in lower_text for kw in ["sale deed", "gpa", "power of attorney", "property", "conveyance", "gift deed"]):
                result["doc_type"] = "Property/Legal Document"
            elif any(kw in lower_text for kw in ["income tax return", "itr", "assessment year"]):
                result["doc_type"] = "ITR Document"
            elif any(kw in lower_text for kw in ["statement of account", "bank statement", "account statement"]):
                result["doc_type"] = "Bank Statement"
            elif "permanent account number" in lower_text or "income tax department" in lower_text:
                result["doc_type"] = "PAN Card"
            elif "aadhaar" in lower_text or "unique identification authority" in lower_text:
                result["doc_type"] = "Aadhaar Card"
            else:
                result["doc_type"] = "Unknown Document"

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("IndianDocumentOCR.extract: %s", exc)
            result["error"] = str(exc)

        return result

