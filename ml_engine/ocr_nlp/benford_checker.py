"""
benford_checker.py
------------------
Benford's Law anomaly detector for financial amounts extracted from documents.

Benford's Law states that in genuine financial datasets, the leading digit D
appears with probability log10(1 + 1/D).  Fabricated or manipulated numbers
tend to deviate from this distribution — fraudsters avoid digit 1 and cluster
around "large-looking" digits like 8 and 9.

Works 100 % offline using pure NumPy math.  No external API calls.

Usage
-----
    from ml_engine.ocr_nlp.benford_checker import BenfordChecker

    b = BenfordChecker()
    result = b.check(['1,20,000', '2,30,000', '8,40,000', ...])
    print(result['benford_score'], result['is_suspicious'])
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benford expected probabilities for leading digits 1–9
# ---------------------------------------------------------------------------

BENFORD_EXPECTED: Dict[int, float] = {
    d: math.log10(1 + 1 / d) for d in range(1, 10)
}

# Chi-square critical value at p=0.05 with 8 degrees of freedom ≈ 15.51
_CHI2_THRESHOLD = 15.0
_MIN_SAMPLE_SIZE = 7        # Benford's Law is not reliable with < 7 numbers
_SCORE_NORMALISER = 20.0    # chi_square / this → [0, 1] score


# ---------------------------------------------------------------------------
# Amount parser
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"[^\d.]")   # remove ₹, Rs., commas, spaces, etc.


def _parse_amount(text: str) -> float | None:
    """
    Parse an OCR amount string to a positive float.

    Handles Indian formatting:  '8,40,000'  →  840000.0
                                'Rs. 1,50,000.50' → 150000.5
                                '₹2,00,000'  →  200000.0
    Returns None for strings that don't yield a valid positive number.
    """
    cleaned = _STRIP_RE.sub("", str(text)).strip(".")
    if not cleaned:
        return None
    try:
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def _leading_digit(value: float) -> int | None:
    """Return the leading (most significant) digit of a positive float."""
    if value <= 0:
        return None
    s = f"{value:.0f}".lstrip("0")
    return int(s[0]) if s else None


# ---------------------------------------------------------------------------
# BenfordChecker
# ---------------------------------------------------------------------------


class BenfordChecker:
    """
    Applies Benford's Law to a list of financial amounts and returns a
    fraud suspicion score based on the chi-square deviation from the
    expected leading-digit distribution.

    Parameters
    ----------
    chi2_threshold :
        Chi-square value above which the distribution is flagged as
        suspicious.  Default 15.0 (≈ p=0.05 with 8 degrees of freedom).
    min_samples :
        Minimum number of valid amounts required for a meaningful test.
        Results with fewer samples always return ``is_suspicious=False``.
    score_normaliser :
        Divisor used to map chi-square → benford_score in [0, 1].
        ``benford_score = min(chi_square / score_normaliser, 1.0)``.
    """

    def __init__(
        self,
        chi2_threshold: float = _CHI2_THRESHOLD,
        min_samples: int = _MIN_SAMPLE_SIZE,
        score_normaliser: float = _SCORE_NORMALISER,
    ) -> None:
        self.chi2_threshold = chi2_threshold
        self.min_samples = min_samples
        self.score_normaliser = score_normaliser

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, amounts: List[str]) -> Dict[str, Any]:
        """
        Run Benford's Law check on a list of OCR-extracted amount strings.

        Parameters
        ----------
        amounts :
            Raw amount strings, e.g. ``['8,40,000', 'Rs. 28,000', '1,50,000']``.
            Formatting characters (₹, commas, spaces) are stripped before
            parsing.

        Returns
        -------
        dict with keys:
            benford_score      : float in [0, 1]  — 0 = clean, 1 = suspicious
            is_suspicious      : bool
            chi_square         : float — deviation from Benford distribution
            leading_digit_dist : dict  — actual digit → proportion
            expected_dist      : dict  — Benford digit → proportion
            sample_size        : int   — number of valid amounts parsed
            flag               : str   — human-readable finding
        """
        # Step 1 — parse amounts to floats
        values: List[float] = []
        for raw in amounts:
            v = _parse_amount(raw)
            if v is not None:
                values.append(v)

        sample_size = len(values)

        # Build the expected distribution dict (rounded for display)
        expected_dist = {d: round(p, 4) for d, p in BENFORD_EXPECTED.items()}

        # Not enough data for a meaningful test
        if sample_size < self.min_samples:
            return {
                "benford_score":       0.0,
                "is_suspicious":       False,
                "chi_square":          0.0,
                "leading_digit_dist":  {d: 0.0 for d in range(1, 10)},
                "expected_dist":       expected_dist,
                "sample_size":         sample_size,
                "flag": (
                    f"Insufficient data ({sample_size} amounts; "
                    f"need >= {self.min_samples} for Benford analysis)."
                ),
            }

        # Step 2 — extract leading digits
        digits: List[int] = []
        for v in values:
            d = _leading_digit(v)
            if d is not None:
                digits.append(d)

        if not digits:
            return {
                "benford_score":       0.0,
                "is_suspicious":       False,
                "chi_square":          0.0,
                "leading_digit_dist":  {d: 0.0 for d in range(1, 10)},
                "expected_dist":       expected_dist,
                "sample_size":         0,
                "flag":                "No valid leading digits extracted.",
            }

        n = len(digits)

        # Step 3 — compute actual frequency of each digit 1–9
        counts = np.zeros(9, dtype=np.float64)  # index 0 = digit 1, …, index 8 = digit 9
        for d in digits:
            if 1 <= d <= 9:
                counts[d - 1] += 1

        actual_proportions = counts / n

        # Step 4 — Benford expected proportions as array
        expected_props = np.array(
            [BENFORD_EXPECTED[d] for d in range(1, 10)], dtype=np.float64
        )
        expected_counts = expected_props * n

        # Step 5 — chi-square test  Σ (O - E)² / E
        # Avoid division by zero (expected_counts are all > 0 for n > 0)
        chi_square = float(
            np.sum((counts - expected_counts) ** 2 / expected_counts)
        )

        # Step 6 — normalise to [0, 1] score
        benford_score = round(min(chi_square / self.score_normaliser, 1.0), 4)

        # Step 7 — is suspicious only when sample is large enough AND chi^2 exceeds threshold
        is_suspicious = (chi_square > self.chi2_threshold) and (n >= self.min_samples)

        # Human-readable leading digit distribution
        leading_digit_dist = {
            d: round(float(actual_proportions[d - 1]), 4) for d in range(1, 10)
        }

        # Build flag message
        if is_suspicious:
            # Find the most over-represented digit
            deviations = {
                d: actual_proportions[d - 1] - expected_props[d - 1]
                for d in range(1, 10)
            }
            most_over = max(deviations, key=lambda d: deviations[d])
            flag = (
                f"Benford deviation detected (chi2={chi_square:.2f} > {self.chi2_threshold}). "
                f"Leading digit {most_over} appears {leading_digit_dist[most_over]:.1%} "
                f"(expected {expected_dist[most_over]:.1%}). "
                f"Possible fabricated amounts."
            )
        elif chi_square > self.chi2_threshold * 0.5:
            flag = (
                f"Mild Benford deviation (chi2={chi_square:.2f}). "
                f"Monitor with additional samples."
            )
        else:
            flag = (
                f"Amounts consistent with Benford's Law "
                f"(chi2={chi_square:.2f}, n={n})."
            )

        logger.debug(
            "BenfordChecker: n=%d chi2=%.3f score=%.4f suspicious=%s",
            n, chi_square, benford_score, is_suspicious,
        )

        return {
            "benford_score":       benford_score,
            "is_suspicious":       is_suspicious,
            "chi_square":          round(chi_square, 4),
            "leading_digit_dist":  leading_digit_dist,
            "expected_dist":       expected_dist,
            "sample_size":         n,
            "flag":                flag,
        }
