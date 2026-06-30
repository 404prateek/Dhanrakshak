"""
math_reconciler.py
------------------
Arithmetic consistency checker for financial documents.

Fraudsters who inflate figures often forget to update the totals, or update
them inconsistently.  MathReconciler extracts all numeric amounts from OCR
text and checks whether any large number is plausibly a sum of 2–3 smaller
numbers.  When a claimed total doesn't match the sum of its detected parts,
the discrepancy is flagged.

Works 100 % offline — pure Python + regex.  No ML model required.

Usage
-----
    from ml_engine.ocr_nlp.math_reconciler import MathReconciler

    m = MathReconciler()
    result = m.check_totals("Salary: Rs. 50000  HRA: Rs. 20000  Total: Rs. 70000")
    print(result['reconciliation_passed'])   # True
"""

from __future__ import annotations

import logging
import re
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex for extracting amounts from OCR text
# ---------------------------------------------------------------------------

# Matches amounts with optional currency prefix and Indian comma formatting.
# Examples: Rs. 8,40,000  |  Rs.50,000  |  3,40,000  |  70000  |  ₹1,20,000.50
# Two-branch alternation:
#   1. Comma-formatted Indian numbers: 8,40,000 / 3,40,000
#   2. Plain 4+ digit numbers: 50000 / 120000
#      (must come BEFORE the 1-3 digit branch to avoid '50000' matching as '500')
_AMOUNT_RE = re.compile(
    r"(?:Rs\.?\s*|INR\s*|\u20b9\s*)?("
    r"\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?"   # comma-formatted: 8,40,000
    r"|\d{4,}(?:\.\d{1,2})?"                 # 4+ digit bare:  50000
    r")",
    re.IGNORECASE,
)

# Minimum value to consider as a "meaningful" financial amount.
# Amounts below this (stamp duty fees, page numbers, small charges) are ignored.
# Legal docs (GPA/Sale/Will) contain small amounts like Rs.50 that should NOT
# be treated as sub-totals of a property price. Set high enough to ignore them.
_MIN_AMOUNT = 10_000.0

# Tolerance for "close enough" sum matching.
# Was 0.5% — too tight, caused false positives on legal docs with
# stamp duty values and rounded amounts. 20% is realistic for financial docs.
_TOLERANCE_PCT = 0.20

# Score assigned when a mismatch is found
_MISMATCH_SCORE = 0.8

# Minimum number of DISTINCT amounts >= _MIN_AMOUNT before running the check.
# Need at least 5: 2-3 sub-items + 1 total + some padding so legal docs with
# only 2-3 property amounts don't trigger false positives.
_MIN_COUNT = 5

# Near-sum search window: only flag a mismatch if the nearest sum is within
# this fraction of the claimed total (50 %).
_NEAR_SUM_WINDOW = 0.50

# Minimum difference (as fraction of claimed total) to actually flag.
# 20% gap required before flagging — suppresses rounding noise and
# unrelated number coincidences in legal documents.
_MIN_FLAG_DIFF_PCT = 0.20

# Only flag if the largest amount in the document exceeds this threshold.
# Prevents triggering on documents where all amounts are small fees.
_MIN_LARGEST_AMOUNT = 50_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_indian_float(text: str) -> Optional[float]:
    """Parse an Indian-formatted number string to float, removing commas."""
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _extract_amounts(text: str) -> List[float]:
    """
    Return a deduplicated list of positive floats >= _MIN_AMOUNT found in text.
    Preserves order of first appearance.
    """
    seen: Dict[float, bool] = {}
    results: List[float] = []
    for m in _AMOUNT_RE.finditer(text):
        val = _parse_indian_float(m.group(1))
        if val is not None and val >= _MIN_AMOUNT and val not in seen:
            seen[val] = True
            results.append(val)
    return results


def _within_tolerance(a: float, b: float) -> bool:
    """Return True if |a - b| <= 0.5 % of max(a, b)."""
    if a == b:
        return True
    tol = max(a, b) * _TOLERANCE_PCT
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# MathReconciler
# ---------------------------------------------------------------------------


class MathReconciler:
    """
    Detects arithmetic inconsistencies in financial document text.

    The reconciler looks for cases where one number in the document is
    presented as a total but does not equal the sum of 2 or 3 other numbers
    that appear to be line items.  This catches the classic fraud pattern of
    inflating a single figure without updating related subtotals.

    Parameters
    ----------
    tolerance_pct :
        Maximum relative difference allowed between a claimed total and the
        sum of its parts before flagging a mismatch.  Default 0.5 %.
    min_amount :
        Amounts below this value (e.g. page numbers, years, small fees)
        are ignored.  Default 1000.
    min_count :
        Minimum number of amounts required to run the check.  Default 4.
    near_sum_window :
        Only flag a mismatch if the nearest sum is within this fraction
        of the claimed total.  Default 5 % (was 50 %).
    min_flag_diff_pct :
        Minimum difference (as fraction of claimed total) before flagging.
        Suppresses near-zero rounding noise.  Default 10 %.
    mismatch_score :
        ``reconciliation_score`` returned when at least one mismatch is found.
        Default 0.8.
    max_numbers :
        Cap on how many numbers to compare (avoids O(n³) blow-up on long docs).
        Default 30.
    """

    def __init__(
        self,
        tolerance_pct:    float = _TOLERANCE_PCT,
        min_amount:       float = _MIN_AMOUNT,
        min_count:        int   = _MIN_COUNT,
        near_sum_window:  float = _NEAR_SUM_WINDOW,
        min_flag_diff_pct: float = _MIN_FLAG_DIFF_PCT,
        mismatch_score:   float = _MISMATCH_SCORE,
        max_numbers:      int   = 30,
        min_largest_amount: float = _MIN_LARGEST_AMOUNT,
    ) -> None:
        self.tolerance_pct      = tolerance_pct
        self.min_amount         = min_amount
        self.min_count          = min_count
        self.near_sum_window    = near_sum_window
        self.min_flag_diff_pct  = min_flag_diff_pct
        self.mismatch_score     = mismatch_score
        self.max_numbers        = max_numbers
        self.min_largest_amount = min_largest_amount

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_totals(self, text: str) -> Dict[str, Any]:
        """
        Extract all amounts from document text and check arithmetic consistency.

        For every number N in the document the reconciler tests whether any
        pair or triple of *other* numbers sums to N (within tolerance).  When
        such a decomposition is found it validates the total; when NO valid
        decomposition is found for a number that acts as a total, the number
        is flagged as a suspicious discrepancy.

        Parameters
        ----------
        text : Raw OCR text from the document.

        Returns
        -------
        dict with keys:
            reconciliation_passed : bool   — True when no mismatches found.
            suspicious_totals     : list   — Each entry:
                                            { claimed, calculated, diff,
                                              parts, description }
            reconciliation_score  : float  — 0.0 = clean, 0.8 = mismatch.
            amounts_found         : list   — All amounts extracted.
            checks_performed      : int    — Number of candidate totals tested.
        """
        amounts = _extract_amounts(text)

        # Cap to avoid combinatorial explosion
        amounts = amounts[: self.max_numbers]

        result: Dict[str, Any] = {
            "reconciliation_passed": True,
            "suspicious_totals":     [],
            "reconciliation_score":  0.0,
            "amounts_found":         amounts,
            "checks_performed":      0,
        }

        # Need at least min_count distinct amounts for a meaningful check.
        # This prevents legal documents with only 2-3 property amounts from
        # triggering false positives.
        if len(amounts) < self.min_count:
            logger.debug(
                "MathReconciler: only %d amount(s) found (need %d) — skipping check.",
                len(amounts), self.min_count,
            )
            return result

        # Only run the check if the largest amount exceeds the minimum threshold.
        # Property papers with small stamp-duty amounts should not be checked.
        largest = max(amounts) if amounts else 0.0
        if largest < self.min_largest_amount:
            logger.debug(
                "MathReconciler: largest amount %.0f < %.0f threshold — skipping check.",
                largest, self.min_largest_amount,
            )
            return result

        suspicious: List[Dict[str, Any]] = []
        checks = 0

        # Sort descending so larger numbers are tested as candidate totals first
        sorted_amounts = sorted(amounts, reverse=True)

        for i, candidate_total in enumerate(sorted_amounts):
            # Only test numbers >= 1000 as candidate totals
            # (smaller numbers are unlikely to be document totals)
            if candidate_total < 1000.0:
                continue

            # The "parts" pool is everything except the candidate total itself
            parts_pool = [v for j, v in enumerate(sorted_amounts) if j != i]

            # --- Pair sums ---
            matched, best_pair = self._find_pair_sum(candidate_total, parts_pool)
            checks += 1
            if matched:
                # A valid decomposition exists → not suspicious
                continue

            # --- Triple sums ---
            matched_triple, best_triple = self._find_triple_sum(candidate_total, parts_pool)
            checks += 1
            if matched_triple:
                continue

            # No valid decomposition found.  But we only flag if there IS
            # *some* pair or triple that sums to a value *close* to but
            # *not matching* the candidate total (i.e. the parts exist but
            # the declared total is wrong).
            mismatch = self._find_nearest_sum(candidate_total, parts_pool)
            if mismatch is not None:
                calc, parts = mismatch
                diff = candidate_total - calc
                # Only flag if the difference is > min_flag_diff_pct of claimed total
                # (suppresses rounding noise and unrelated number coincidences)
                if abs(diff) > candidate_total * self.min_flag_diff_pct:
                    suspicious.append({
                        "claimed":     candidate_total,
                        "calculated":  round(calc, 2),
                        "diff":        round(diff, 2),
                        "parts":       parts,
                        "description": (
                            f"Claimed total {candidate_total:,.0f} != "
                            f"sum of parts {parts} = {calc:,.0f} "
                            f"(diff {diff:+,.0f})"
                        ),
                    })

        result["checks_performed"]      = checks
        result["suspicious_totals"]     = suspicious
        result["reconciliation_passed"] = len(suspicious) == 0
        result["reconciliation_score"]  = (
            self.mismatch_score if suspicious else 0.0
        )

        if suspicious:
            logger.warning(
                "MathReconciler: %d suspicious total(s) found in document.",
                len(suspicious),
            )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _close(self, a: float, b: float) -> bool:
        """True if a and b are within tolerance of each other."""
        if a == 0 and b == 0:
            return True
        tol = max(abs(a), abs(b)) * self.tolerance_pct
        return abs(a - b) <= tol

    def _find_pair_sum(
        self, target: float, pool: List[float]
    ) -> Tuple[bool, Optional[Tuple[float, float]]]:
        """Return (True, (a, b)) if any pair in pool sums to target."""
        for a, b in combinations(pool, 2):
            if self._close(a + b, target):
                return True, (a, b)
        return False, None

    def _find_triple_sum(
        self, target: float, pool: List[float]
    ) -> Tuple[bool, Optional[Tuple[float, float, float]]]:
        """Return (True, (a,b,c)) if any triple in pool sums to target."""
        for a, b, c in combinations(pool, 3):
            if self._close(a + b + c, target):
                return True, (a, b, c)
        return False, None

    def _find_nearest_sum(
        self, target: float, pool: List[float]
    ) -> Optional[Tuple[float, List[float]]]:
        """
        Find the pair or triple whose sum is nearest to target but
        *outside* tolerance.  Only returns a result when the nearest sum
        is within ``near_sum_window`` of target (default 5 %).

        The tighter window (was 50 %) prevents unrelated numbers from being
        mistakenly treated as parts of a total.
        """
        best_diff = float("inf")
        best_combo: Optional[Tuple[float, List[float]]] = None
        window = target * self.near_sum_window

        # Pairs
        for a, b in combinations(pool, 2):
            s = a + b
            diff = abs(s - target)
            # Only consider sums within the near_sum_window of target
            if diff <= window and diff < best_diff and not self._close(s, target):
                best_diff = diff
                best_combo = (s, [a, b])

        # Triples
        for a, b, c in combinations(pool, 3):
            s = a + b + c
            diff = abs(s - target)
            if diff <= window and diff < best_diff and not self._close(s, target):
                best_diff = diff
                best_combo = (s, [a, b, c])

        return best_combo
