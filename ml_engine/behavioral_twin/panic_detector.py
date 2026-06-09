# Rule-based + statistical panic/duress detection

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


# ---------------------------------------------------------------------------
# Typed contracts
# ---------------------------------------------------------------------------

class SessionFeatures(TypedDict, total=False):
    """
    Current-session feature values produced by BehaviorFeatureExtractor.
    All keys are optional; missing values skip the corresponding rule.
    """
    avg_typing_speed: float          # chars / second
    typing_rhythm_variance: float    # ms²
    mouse_linearity: float           # 0–1
    session_duration: float          # seconds
    idle_ratio: float                # 0–1
    transaction_speed: float         # seconds from session start to first click
    transaction_amount: float        # monetary value of the transaction


class UserProfile(TypedDict, total=False):
    """
    Aggregated historical baseline for the user.
    All keys are optional; missing values disable the corresponding rule.
    """
    avg_transaction_speed: float     # seconds — historical mean
    avg_transaction_amount: float    # monetary — historical mean
    typing_rhythm_variance_mean: float   # ms² — historical mean
    typing_rhythm_variance_std: float    # ms² — historical std deviation


class PanicResult(TypedDict):
    panic_detected: bool
    confidence: float                # 0–1
    triggered_rules: List[str]


# ---------------------------------------------------------------------------
# Rule thresholds (all overridable via constructor)
# ---------------------------------------------------------------------------
_DEFAULT_SPEED_MULTIPLIER: float       = 3.0   # transaction_speed > N × baseline
_DEFAULT_AMOUNT_MULTIPLIER: float      = 2.0   # amount > N × avg_transaction_amount
_DEFAULT_RHYTHM_Z_THRESHOLD: float     = 2.5   # z-score above which variance is flagged
_DEFAULT_RHYTHM_ABS_THRESHOLD: float   = 5_000.0  # fallback abs threshold (ms²) when
                                                   # no std-dev is available in profile


class PanicDetector:
    """
    Detects duress / panic during a financial transaction using a combination
    of rule-based checks and lightweight statistical deviation scoring.

    Rules evaluated
    ---------------
    1. ``FAST_TRANSACTION``   — transaction_speed > speed_multiplier × user baseline.
    2. ``HIGH_AMOUNT``        — transaction_amount > amount_multiplier × user average.
    3. ``ERRATIC_TYPING``     — typing_rhythm_variance deviates by more than
                                rhythm_z_threshold standard deviations from the
                                user's historical mean (z-score), or exceeds
                                rhythm_abs_threshold when no historical std is known.

    Confidence scoring
    ------------------
    Each triggered rule contributes an independent weight.  The final confidence
    is 1 − ∏(1 − wᵢ), which combines evidence without saturating to 1.0 on a
    single rule alone.

    Usage
    -----
    detector = PanicDetector()
    result = detector.detect(session_features, user_profile)
    # {"panic_detected": True, "confidence": 0.83, "triggered_rules": ["FAST_TRANSACTION", "ERRATIC_TYPING"]}
    """

    # Per-rule confidence contributions (tunable).
    _RULE_WEIGHTS: Dict[str, float] = {
        "FAST_TRANSACTION": 0.65,
        "HIGH_AMOUNT":      0.55,
        "ERRATIC_TYPING":   0.50,
    }

    def __init__(
        self,
        speed_multiplier: float = _DEFAULT_SPEED_MULTIPLIER,
        amount_multiplier: float = _DEFAULT_AMOUNT_MULTIPLIER,
        rhythm_z_threshold: float = _DEFAULT_RHYTHM_Z_THRESHOLD,
        rhythm_abs_threshold: float = _DEFAULT_RHYTHM_ABS_THRESHOLD,
        panic_confidence_threshold: float = 0.40,
    ) -> None:
        """
        Parameters
        ----------
        speed_multiplier           : Flag if transaction_speed > N × user baseline.
        amount_multiplier          : Flag if amount > N × user average amount.
        rhythm_z_threshold         : Z-score cutoff for typing rhythm variance.
        rhythm_abs_threshold       : Absolute variance (ms²) fallback when the
                                     user's historical std is unknown.
        panic_confidence_threshold : Minimum combined confidence to set
                                     ``panic_detected = True``.
        """
        if speed_multiplier <= 0 or amount_multiplier <= 0:
            raise ValueError("Multipliers must be positive.")
        if not 0.0 < panic_confidence_threshold < 1.0:
            raise ValueError("panic_confidence_threshold must be in (0, 1).")

        self.speed_multiplier = speed_multiplier
        self.amount_multiplier = amount_multiplier
        self.rhythm_z_threshold = rhythm_z_threshold
        self.rhythm_abs_threshold = rhythm_abs_threshold
        self.panic_confidence_threshold = panic_confidence_threshold

    # ------------------------------------------------------------------
    # Individual rule evaluators  (return True when rule fires)
    # ------------------------------------------------------------------

    def _rule_fast_transaction(
        self,
        session: SessionFeatures,
        profile: UserProfile,
    ) -> bool:
        """Flag if current transaction speed is unusually fast vs. baseline."""
        speed   = session.get("transaction_speed")
        baseline = profile.get("avg_transaction_speed")
        if speed is None or baseline is None or baseline <= 0:
            return False
        return speed < (baseline / self.speed_multiplier)
        # Lower transaction_speed means faster action (seconds to first click).

    def _rule_high_amount(
        self,
        session: SessionFeatures,
        profile: UserProfile,
    ) -> bool:
        """Flag if transaction amount exceeds N × user average."""
        amount  = session.get("transaction_amount")
        avg_amt = profile.get("avg_transaction_amount")
        if amount is None or avg_amt is None or avg_amt <= 0:
            return False
        return amount > self.amount_multiplier * avg_amt

    def _rule_erratic_typing(
        self,
        session: SessionFeatures,
        profile: UserProfile,
    ) -> bool:
        """Flag if typing rhythm variance deviates significantly from baseline."""
        variance = session.get("typing_rhythm_variance")
        if variance is None:
            return False

        mean = profile.get("typing_rhythm_variance_mean")
        std  = profile.get("typing_rhythm_variance_std")

        if mean is not None and std is not None and std > 0:
            z_score = (variance - mean) / std
            return z_score > self.rhythm_z_threshold

        # Fallback: absolute threshold when no statistical profile is available.
        return variance > self.rhythm_abs_threshold

    # ------------------------------------------------------------------
    # Confidence fusion
    # ------------------------------------------------------------------

    @staticmethod
    def _combine_confidence(triggered_rules: List[str], weights: Dict[str, float]) -> float:
        """
        Combine independent rule weights using the noisy-OR model:
            confidence = 1 − ∏(1 − wᵢ)
        This avoids over-confident saturation from a single strong rule.
        """
        product = 1.0
        for rule in triggered_rules:
            product *= 1.0 - weights.get(rule, 0.0)
        return round(1.0 - product, 6)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        session: SessionFeatures,
        profile: Optional[UserProfile] = None,
    ) -> PanicResult:
        """
        Evaluate all rules against the current session and user profile.

        Parameters
        ----------
        session : Feature values for the current session
                  (from BehaviorFeatureExtractor).
        profile : Historical user baseline.  Pass ``None`` or ``{}`` when no
                  profile exists; rules that require profile data are skipped.

        Returns
        -------
        PanicResult TypedDict:
            panic_detected  : True when combined confidence ≥ threshold.
            confidence      : float in [0, 1].
            triggered_rules : List of rule names that fired (empty if none).
        """
        if profile is None:
            profile = {}

        evaluators = {
            "FAST_TRANSACTION": self._rule_fast_transaction,
            "HIGH_AMOUNT":      self._rule_high_amount,
            "ERRATIC_TYPING":   self._rule_erratic_typing,
        }

        triggered: List[str] = [
            name
            for name, fn in evaluators.items()
            if fn(session, profile)
        ]

        confidence = self._combine_confidence(triggered, self._RULE_WEIGHTS)
        panic_detected = confidence >= self.panic_confidence_threshold

        return PanicResult(
            panic_detected=panic_detected,
            confidence=confidence,
            triggered_rules=triggered,
        )
