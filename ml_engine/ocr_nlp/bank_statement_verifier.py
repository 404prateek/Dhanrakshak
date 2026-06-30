"""
bank_statement_verifier.py
--------------------------
Arithmetic fraud detection for bank statement OCR text.

Two independent verifiers:

  BankStatementVerifier.verify_running_balance(text)
      Parses a ledger-style statement and checks whether each row's
      stated closing balance equals prev_balance - debit + credit.
      Any deviation > ₹1 is flagged as a potential tampered row.

  BankStatementVerifier.verify_words_match_numbers(text)
      Finds "Amount in words: X" / "Amount in figures: Y" patterns
      and confirms the numeral representation matches.
      Mismatches > 1 % are flagged as suspicious.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_numeric(raw: str) -> Optional[float]:
    """Convert a raw amount string like '1,23,456.78' → 123456.78, or None."""
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# Module-level lookup tables (built once, not per call)
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
    "hundred":  100,
    "thousand": 1_000,
    "lakh":     1_00_000, "lac":    1_00_000,
    "lakhs":    1_00_000, "lacs":   1_00_000,
    "million":  1_000_000,
    "crore":    1_00_00_000, "crores": 1_00_00_000,
}
_INDIAN_SCALE_WORDS = {"lakh", "lac", "lakhs", "lacs", "crore", "crores"}


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
            result += (current if current else 1) * _SCALE[tok]
            current = 0
    result += current
    return float(result) if result else None


def _words_to_number(phrase: str) -> Optional[float]:
    """
    Convert an English/Indian amount phrase to a float.

    Routes Indian denomination phrases (containing lakh / crore) directly
    to the fallback parser — word2number silently truncates "Five Lakh"
    to 5.  Standard English phrases use word2number first, then fall back.
    """
    phrase = phrase.strip().rstrip("./ ").lower()
    phrase = re.sub(r"\bonly\b|\brupees?\b|\binr\b", "", phrase).strip()

    tokens = phrase.split()

    # Indian scale words: bypass word2number which doesn't know them
    if any(t in _INDIAN_SCALE_WORDS for t in tokens):
        return _fallback_parse(tokens)

    # Standard English via word2number library
    try:
        from word2number import w2n  # type: ignore
        return float(w2n.word_to_num(phrase))
    except ImportError:
        pass
    except Exception:
        pass

    return _fallback_parse(tokens)


# ---------------------------------------------------------------------------
# Transaction row parser
# ---------------------------------------------------------------------------

# Matches lines like:
#   01/04   Salary Credit   0   50000   50000
#   05/04/2024  ATM Withdrawal  10,000  -  40,000
#
# Groups: date, description, debit, credit, balance
_TXN_PATTERN = re.compile(
    r"(?P<date>\d{1,2}[\/\-\.]\d{1,2}(?:[\/\-\.]\d{2,4})?)"   # date
    r"\s+"
    r"(?P<desc>[A-Za-z][^\t\n]{0,60}?)"                         # description
    r"\s{2,}"                                                    # 2+ spaces
    r"(?P<debit>[\d,]+(?:\.\d{2})?|-|0)"                        # debit
    r"\s{2,}"
    r"(?P<credit>[\d,]+(?:\.\d{2})?|-|0)"                       # credit
    r"\s{2,}"
    r"(?P<balance>[\d,]+(?:\.\d{2})?)",                          # closing balance
    re.IGNORECASE,
)

# Also handles tab-separated formats
_TXN_TAB_PATTERN = re.compile(
    r"(?P<date>\d{1,2}[\/\-\.]\d{1,2}(?:[\/\-\.]\d{2,4})?)"
    r"\t+"
    r"(?P<desc>[^\t]{1,80}?)"
    r"\t+"
    r"(?P<debit>[\d,]+(?:\.\d{2})?|-|0)"
    r"\t+"
    r"(?P<credit>[\d,]+(?:\.\d{2})?|-|0)"
    r"\t+"
    r"(?P<balance>[\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)

# Simple space-separated 5-column pattern (for test convenience)
_TXN_SIMPLE = re.compile(
    r"^(?P<date>\S+)\s+"
    r"(?P<desc>\S+)\s+"
    r"(?P<debit>[\d,]+(?:\.\d{2})?)\s+"
    r"(?P<credit>[\d,]+(?:\.\d{2})?)\s+"
    r"(?P<balance>[\d,]+(?:\.\d{2})?)$",
    re.MULTILINE,
)


def _parse_transactions(text: str) -> List[Dict[str, Any]]:
    """Return list of transaction dicts from OCR text."""
    rows: List[Dict[str, Any]] = []
    seen_spans: set = set()

    for pattern in (_TXN_PATTERN, _TXN_TAB_PATTERN, _TXN_SIMPLE):
        for m in pattern.finditer(text):
            if m.start() in seen_spans:
                continue
            seen_spans.add(m.start())
            debit_raw  = m.group("debit")
            credit_raw = m.group("credit")
            balance_raw = m.group("balance")

            debit   = _strip_numeric(debit_raw)   or 0.0
            credit  = _strip_numeric(credit_raw)  or 0.0
            balance = _strip_numeric(balance_raw)

            if balance is None:
                continue

            rows.append({
                "line":    m.group(0).strip(),
                "date":    m.group("date"),
                "desc":    m.group("desc").strip(),
                "debit":   debit,
                "credit":  credit,
                "balance": balance,
            })

    # Sort by position in text (stable ordering)
    return rows


# ---------------------------------------------------------------------------
# Words-match-numbers patterns
# ---------------------------------------------------------------------------

_WORDS_PATTERN = re.compile(
    r"(?:amount\s+in\s+words|in\s+words|rupees\s+in\s+words)\s*[:\-]?\s*([A-Za-z\s]+?)(?:\n|only|\.)",
    re.IGNORECASE,
)
_FIGURES_PATTERN = re.compile(
    r"(?:amount\s+in\s+(?:figures?|numbers?)|in\s+figures?|rs\.?|inr|₹)\s*[:\-]?\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class BankStatementVerifier:
    """
    Arithmetic fraud detector for bank statement OCR text.

    Parameters
    ----------
    balance_tolerance:
        Maximum allowed absolute difference (₹) between expected and stated
        closing balance before flagging a row.  Default 1.0.
    words_tolerance_pct:
        Maximum allowed percentage difference between amount-in-words and
        amount-in-figures before flagging.  Default 1.0 (%).
    """

    def __init__(
        self,
        balance_tolerance: float = 1.0,
        words_tolerance_pct: float = 1.0,
    ) -> None:
        self.balance_tolerance   = balance_tolerance
        self.words_tolerance_pct = words_tolerance_pct

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_running_balance(self, text: str) -> Dict[str, Any]:
        """
        Check whether every row's stated balance follows arithmetically from
        the previous row's balance.

        Parameters
        ----------
        text:
            Raw OCR text of a bank statement.

        Returns
        -------
        dict:
            balance_consistent  : bool   — True when no rows are flagged.
            flagged_rows        : list   — [{row_num, date, desc, expected,
                                             stated, diff, line}]
            tampering_score     : float  — 0.0 clean → 1.0 heavily tampered.
            total_rows_checked  : int
        """
        rows = _parse_transactions(text)

        if not rows:
            return {
                "balance_consistent": True,
                "flagged_rows":       [],
                "tampering_score":    0.0,
                "total_rows_checked": 0,
                "note":               "No transaction rows detected in text.",
            }

        flagged: List[Dict[str, Any]] = []
        prev_balance: float = rows[0]["balance"]   # first row = opening balance

        for idx, row in enumerate(rows[1:], start=2):
            expected = prev_balance - row["debit"] + row["credit"]
            stated   = row["balance"]
            diff     = abs(expected - stated)

            if diff > self.balance_tolerance:
                flagged.append({
                    "row_num":  idx,
                    "date":     row["date"],
                    "desc":     row["desc"],
                    "expected": round(expected, 2),
                    "stated":   round(stated, 2),
                    "diff":     round(diff, 2),
                    "line":     row["line"],
                })

            prev_balance = stated   # use stated balance to propagate (catches single-row edits)

        total_checked = len(rows) - 1   # first row is just the opening balance reference
        total_checked = max(total_checked, 1)

        # Tampering score: fraction of rows flagged, with diminishing weighting
        # even 1 mismatch = score of 0.80 (very suspicious)
        if flagged:
            ratio    = len(flagged) / total_checked
            tampering = round(0.80 + 0.20 * ratio, 4)
        else:
            tampering = 0.0

        return {
            "balance_consistent": len(flagged) == 0,
            "flagged_rows":       flagged,
            "tampering_score":    tampering,
            "total_rows_checked": total_checked,
        }

    def verify_words_match_numbers(self, text: str) -> Dict[str, Any]:
        """
        Validate that the "Amount in Words" phrase matches the "Amount in
        Figures" number in the document.

        Parameters
        ----------
        text:
            Raw OCR text (cheque, DD, or bank statement).

        Returns
        -------
        dict:
            words_match         : bool
            word_phrase         : str | None
            word_value          : float | None
            numeric_value       : float | None
            mismatch_pct        : float | None
            flagged             : bool
            note                : str
        """
        word_match   = _WORDS_PATTERN.search(text)
        figure_match = _FIGURES_PATTERN.search(text)

        word_phrase   : Optional[str]   = None
        word_value    : Optional[float] = None
        numeric_value : Optional[float] = None
        mismatch_pct  : Optional[float] = None

        if word_match:
            word_phrase = word_match.group(1).strip()
            word_value  = _words_to_number(word_phrase)

        if figure_match:
            numeric_value = _strip_numeric(figure_match.group(1))

        # Can't verify if either side is missing
        if word_value is None or numeric_value is None:
            return {
                "words_match":   True,
                "word_phrase":   word_phrase,
                "word_value":    word_value,
                "numeric_value": numeric_value,
                "mismatch_pct":  None,
                "flagged":       False,
                "note": (
                    "Could not extract both word and figure amounts — "
                    "manual verification recommended."
                ),
            }

        if numeric_value != 0:
            mismatch_pct = round(abs(word_value - numeric_value) / numeric_value * 100, 4)
        else:
            mismatch_pct = 0.0 if word_value == 0 else 100.0

        flagged     = mismatch_pct > self.words_tolerance_pct
        words_match = not flagged

        return {
            "words_match":   words_match,
            "word_phrase":   word_phrase,
            "word_value":    word_value,
            "numeric_value": numeric_value,
            "mismatch_pct":  mismatch_pct,
            "flagged":       flagged,
            "note": (
                f"Mismatch of {mismatch_pct:.2f}% detected — possible alteration."
                if flagged
                else "Amount in words matches amount in figures."
            ),
        }
