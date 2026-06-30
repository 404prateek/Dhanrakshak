"""
cheque_verifier.py
------------------
Multi-signal fraud detection for Indian bank cheques.

ChequeVerifier.verify(image_path)
    Full pipeline: OCR → field extraction → arithmetic cross-check →
    date validation → ELA signature analysis → fraud score.

ChequeVerifier._compare_amount(numeric_str, words_str)
    Standalone helper: compare a digit string to an English phrase.
    Returns {'mismatch': bool, ...} — useful for unit testing.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared numeric helpers  (mirrors bank_statement_verifier to stay DRY)
# ---------------------------------------------------------------------------

def _strip_numeric(raw: str) -> Optional[float]:
    """'1,23,456.78'  →  123456.78  (or None on failure)."""
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALE = {
    "hundred": 100,
    "thousand": 1_000,
    "lakh": 1_00_000, "lac": 1_00_000, "lakhs": 1_00_000, "lacs": 1_00_000,
    "million": 1_000_000,
    "crore": 1_00_00_000, "crores": 1_00_00_000,
}


def _words_to_number(phrase: str) -> Optional[float]:
    """
    Convert an English/Indian amount phrase to float.
    Handles standard English (word2number) and Indian denominations
    (lakh, crore) via a dedicated fallback parser.
    """
    phrase = phrase.strip().rstrip("./ ").lower()
    phrase = re.sub(r"\bonly\b|\brupees?\b|\binr\b", "", phrase).strip()

    # Indian scale words — word2number doesn't know "lakh" / "crore",
    # so use the fallback parser directly when they appear.
    _INDIAN_SCALE = {"lakh", "lac", "lakhs", "lacs", "crore", "crores"}
    tokens = phrase.split()
    if any(t in _INDIAN_SCALE for t in tokens):
        return _fallback_parse(tokens)

    # word2number library for standard English phrases
    try:
        from word2number import w2n  # type: ignore
        return float(w2n.word_to_num(phrase))
    except ImportError:
        pass
    except Exception:
        pass

    return _fallback_parse(tokens)


def _fallback_parse(tokens: list) -> Optional[float]:
    """Pure-Python parser for English + Indian banking denominations."""
    current = 0
    result  = 0
    for tok in tokens:
        if tok in _ONES:
            current += _ONES[tok]
        elif tok in _TENS:
            current += _TENS[tok]
        elif tok == "hundred":
            current = current * 100 if current else 100
        elif tok in _SCALE:
            factor  = _SCALE[tok]
            result += (current if current else 1) * factor
            current = 0
    result += current
    return float(result) if result else None


# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

def _run_ocr(image_path: str) -> str:
    """Return raw OCR text for the given image, or '' on failure."""
    try:
        import pytesseract
        from PIL import Image

        # Auto-locate Tesseract on Windows
        import os, sys
        if sys.platform == "win32":
            win_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for p in win_paths:
                if os.path.isfile(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

        img = Image.open(image_path).convert("RGB")
        return pytesseract.image_to_string(img, config="--psm 6")
    except Exception as exc:
        logger.warning("cheque_verifier OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Cheque-specific regex patterns
# ---------------------------------------------------------------------------

# ₹/Rs. digit amount  — e.g. "₹ 50,000" / "Rs. 1,23,456.00"
_AMOUNT_NUM_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
# Standalone digit-only amount field (used as fallback when no ₹ prefix)
_AMOUNT_BARE_RE = re.compile(
    r"\*\*([0-9][0-9,]+(?:\.[0-9]{2})?)\*\*"  # courtesy-amount box **50,000**
    r"|(?:Amount|Amt)[:\s]*([0-9][0-9,]+(?:\.[0-9]{2})?)",
    re.IGNORECASE,
)

# "Amount in words: Fifty Thousand Only"
_AMOUNT_WORDS_RE = re.compile(
    r"(?:Rupees?|Amount\s+in\s+[Ww]ords?|In\s+[Ww]ords?)\s*[:\-]?\s*"
    r"([A-Za-z][A-Za-z\s]+?)(?:\s+Only|\.|$)",
    re.IGNORECASE | re.MULTILINE,
)

# Payee: "Pay to: XYZ"  /  "Pay: XYZ"  /  "Beneficiary: XYZ"
_PAYEE_RE = re.compile(
    r"(?:Pay\s+to(?:\s+the\s+Order\s+of)?|Pay|Beneficiary|Payee)\s*[:\-]?\s*"
    r"([A-Z][A-Za-z\s\.]{2,50}?)(?:\n|$|or\s+Bearer)",
    re.IGNORECASE,
)

# Date patterns: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
_DATE_RE = re.compile(
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b"
)

# A/C Payee crossing keyword
_AC_PAYEE_RE = re.compile(
    r"A/C\s*Payee|Account\s*Payee|&\s*Co\.|Not\s+Negotiable",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_cheque_date(text: str) -> Optional[date]:
    """Return the first valid date found in cheque OCR text."""
    for m in _DATE_RE.finditer(text):
        day, month, year_raw = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(year_raw)
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# ELA on a specific image region
# ---------------------------------------------------------------------------

def _ela_on_region(
    image_path: str,
    region: Optional[Tuple[float, float, float, float]] = None,
    jpeg_quality: int = 90,
) -> float:
    """
    Run ELA on *image_path*.  If *region* is given as (left%, top%, right%, bottom%)
    fractions (0–1), only that crop is analysed.  Returns tamper_score in [0, 1].
    Returns 0.0 gracefully if Pillow/numpy are unavailable.
    """
    try:
        from PIL import Image as PILImage
        from io import BytesIO

        img = PILImage.open(image_path).convert("RGB")

        if region is not None:
            w, h = img.size
            left  = int(region[0] * w)
            top   = int(region[1] * h)
            right = int(region[2] * w)
            bottom= int(region[3] * h)
            img = img.crop((left, top, right, bottom))

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_quality)
        buf.seek(0)
        recompressed = PILImage.open(buf).convert("RGB")

        orig_arr = np.asarray(img, dtype=np.int16)
        recp_arr = np.asarray(recompressed, dtype=np.int16)

        diff = np.abs(orig_arr - recp_arr).mean(axis=2) / 255.0
        return float(np.clip(diff.mean(), 0.0, 1.0))

    except Exception as exc:
        logger.debug("ELA region analysis failed: %s", exc)
        return 0.0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ChequeVerifier:
    """
    Multi-signal fraud detector for scanned Indian bank cheques.

    Parameters
    ----------
    amount_tolerance_pct:
        Max allowed % difference between amount-in-words and amount-in-figures.
        Default 1.0 (1 %).
    ela_signature_region:
        (left, top, right, bottom) fractions of image height/width to crop
        for signature ELA analysis.  Default = bottom-right quarter.
    ela_tamper_threshold:
        ELA score above which the signature region is considered suspicious.
        Default 0.03.
    """

    def __init__(
        self,
        amount_tolerance_pct: float = 1.0,
        ela_signature_region: Tuple[float, float, float, float] = (0.55, 0.70, 1.0, 1.0),
        ela_tamper_threshold: float = 0.03,
    ) -> None:
        self.amount_tolerance_pct  = amount_tolerance_pct
        self.ela_signature_region  = ela_signature_region
        self.ela_tamper_threshold  = ela_tamper_threshold

    # ------------------------------------------------------------------
    # Public helpers (exposed for unit testing)
    # ------------------------------------------------------------------

    def _compare_amount(
        self,
        numeric_str: str,
        words_str: str,
    ) -> Dict[str, Any]:
        """
        Compare a digit string (e.g. "50000") to a word phrase
        (e.g. "Five Lakh Only").

        Returns
        -------
        dict:
            mismatch        : bool
            numeric_value   : float | None
            word_value      : float | None
            mismatch_pct    : float | None
            note            : str
        """
        numeric_value = _strip_numeric(numeric_str)
        word_value    = _words_to_number(words_str)

        if numeric_value is None or word_value is None:
            return {
                "mismatch":      False,
                "numeric_value": numeric_value,
                "word_value":    word_value,
                "mismatch_pct":  None,
                "note":          "Could not parse one or both amounts — manual check needed.",
            }

        if numeric_value != 0:
            pct = abs(word_value - numeric_value) / numeric_value * 100.0
        else:
            pct = 0.0 if word_value == 0 else 100.0

        mismatch = pct > self.amount_tolerance_pct

        return {
            "mismatch":      mismatch,
            "numeric_value": numeric_value,
            "word_value":    word_value,
            "mismatch_pct":  round(pct, 4),
            "note": (
                f"MISMATCH: numeric {numeric_value:,.2f} vs words {word_value:,.2f} "
                f"({pct:.2f}% difference)."
                if mismatch
                else "Amounts match."
            ),
        }

    # ------------------------------------------------------------------
    # Full cheque verification pipeline
    # ------------------------------------------------------------------

    def verify(self, image_path: str) -> Dict[str, Any]:
        """
        Run the full cheque fraud-detection pipeline on a scanned image.

        Parameters
        ----------
        image_path : Path to the cheque image (JPEG, PNG, TIFF).

        Returns
        -------
        dict:
            amount_match      : bool
            amount_numeric    : float | None
            amount_words      : str | None
            amount_from_words : float | None
            is_post_dated     : bool
            cheque_date       : str | None   (ISO format)
            payee_name        : str | None
            ac_payee_crossed  : bool
            ela_signature_score: float       (0 = clean, 1 = highly suspicious)
            signature_tampered: bool
            fraud_score       : float        (0 = clean, 1 = near-certain fraud)
            flags             : list[str]
            ocr_text_preview  : str          (first 300 chars of OCR)
        """
        path = str(image_path)
        flags: List[str] = []

        # ── 1. OCR ───────────────────────────────────────────────────
        text = _run_ocr(path)

        # ── 2. Amount in numbers ─────────────────────────────────────
        amount_numeric: Optional[float] = None
        m = _AMOUNT_NUM_RE.search(text)
        if m:
            amount_numeric = _strip_numeric(m.group(1))
        else:
            # Fallback: bare patterns
            m2 = _AMOUNT_BARE_RE.search(text)
            if m2:
                raw = m2.group(1) or m2.group(2) or ""
                amount_numeric = _strip_numeric(raw)

        # ── 3. Amount in words ───────────────────────────────────────
        amount_words: Optional[str] = None
        m3 = _AMOUNT_WORDS_RE.search(text)
        if m3:
            amount_words = m3.group(1).strip()

        # ── 4 & 5. Cross-check amounts ───────────────────────────────
        amount_from_words: Optional[float] = None
        amount_match = True
        mismatch_pct: Optional[float] = None

        if amount_words:
            amount_from_words = _words_to_number(amount_words)

        if amount_numeric is not None and amount_from_words is not None:
            cmp = self._compare_amount(str(int(amount_numeric)), amount_words or "")
            amount_match  = not cmp["mismatch"]
            mismatch_pct  = cmp["mismatch_pct"]
            if cmp["mismatch"]:
                flags.append(
                    f"HIGH: Amount mismatch — numeric ₹{amount_numeric:,.0f} vs "
                    f"words ₹{amount_from_words:,.0f} ({mismatch_pct:.1f}% diff)"
                )
        elif amount_numeric is None and amount_from_words is None:
            flags.append("MEDIUM: Could not extract any amount from cheque")
        elif amount_numeric is None:
            flags.append("LOW: Amount in figures not found; only word amount detected")
        elif amount_from_words is None:
            flags.append("LOW: Amount in words not found; only numeric amount detected")

        # ── 6. Payee name ────────────────────────────────────────────
        payee_name: Optional[str] = None
        m4 = _PAYEE_RE.search(text)
        if m4:
            payee_name = m4.group(1).strip()
        if not payee_name:
            flags.append("LOW: Payee name not detected in cheque")

        # ── 7. Date — post-dating check ──────────────────────────────
        cheque_date = _parse_cheque_date(text)
        is_post_dated = False
        cheque_date_str: Optional[str] = None
        if cheque_date:
            cheque_date_str = cheque_date.isoformat()
            if cheque_date > date.today():
                is_post_dated = True
                days_ahead = (cheque_date - date.today()).days
                flags.append(
                    f"MEDIUM: Post-dated cheque — date {cheque_date_str} "
                    f"is {days_ahead} day(s) in the future"
                )
        else:
            flags.append("LOW: Cheque date not detected")

        # ── 8. A/C Payee crossing ────────────────────────────────────
        ac_payee_crossed = bool(_AC_PAYEE_RE.search(text))
        if not ac_payee_crossed:
            flags.append("LOW: 'A/C Payee' crossing not detected — bearer cheque risk")

        # ── 9. ELA on signature region ───────────────────────────────
        ela_sig_score = 0.0
        signature_tampered = False
        if Path(path).exists():
            ela_sig_score = _ela_on_region(path, region=self.ela_signature_region)
            signature_tampered = ela_sig_score > self.ela_tamper_threshold
            if signature_tampered:
                flags.append(
                    f"HIGH: Signature region ELA score {ela_sig_score:.4f} "
                    f"exceeds threshold {self.ela_tamper_threshold} — possible forgery"
                )

        # ── Fraud score aggregation ──────────────────────────────────
        fraud_score = self._compute_fraud_score(
            amount_match       = amount_match,
            mismatch_pct       = mismatch_pct,
            is_post_dated      = is_post_dated,
            signature_tampered = signature_tampered,
            ela_sig_score      = ela_sig_score,
            flags              = flags,
        )

        return {
            "amount_match":        amount_match,
            "amount_numeric":      amount_numeric,
            "amount_words":        amount_words,
            "amount_from_words":   amount_from_words,
            "mismatch_pct":        mismatch_pct,
            "is_post_dated":       is_post_dated,
            "cheque_date":         cheque_date_str,
            "payee_name":          payee_name,
            "ac_payee_crossed":    ac_payee_crossed,
            "ela_signature_score": round(ela_sig_score, 4),
            "signature_tampered":  signature_tampered,
            "fraud_score":         round(fraud_score, 4),
            "flags":               flags,
            "ocr_text_preview":    text[:300].strip(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_fraud_score(
        *,
        amount_match: bool,
        mismatch_pct: Optional[float],
        is_post_dated: bool,
        signature_tampered: bool,
        ela_sig_score: float,
        flags: List[str],
    ) -> float:
        """
        Weighted combination of individual signals → fraud_score in [0, 1].

        Weights:
          Amount mismatch   : 0.55  (most critical)
          Signature ELA     : 0.25
          Post-dated        : 0.10
          Missing fields    : 0.10
        """
        score = 0.0

        # Amount mismatch
        if not amount_match:
            pct_factor = min((mismatch_pct or 100.0) / 100.0, 1.0)
            score += 0.55 * (0.80 + 0.20 * pct_factor)

        # Signature ELA (normalised by threshold; capped at 1)
        sig_contribution = min(ela_sig_score / 0.10, 1.0)
        score += 0.25 * sig_contribution

        # Post-dating
        if is_post_dated:
            score += 0.10

        # Missing critical fields (payee / amount)
        high_missing = sum(
            1 for f in flags
            if "not detected" in f.lower() and "medium" not in f.lower()
        )
        score += 0.10 * min(high_missing / 3.0, 1.0)

        return float(np.clip(score, 0.0, 1.0))
