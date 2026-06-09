# Weighted fusion of all module scores

from __future__ import annotations

from typing import Dict, Literal, Optional, TypedDict

# Weights and thresholds are sourced from the central config module so that a
# single environment-variable change propagates everywhere at runtime.
try:
    from backend.config import (
        TRUST_WEIGHT_DOC_FORENSIC,
        TRUST_WEIGHT_BEHAVIORAL,
        TRUST_WEIGHT_GRAPH_ANOMALY,
        RISK_THRESHOLD_HIGH,
        RISK_THRESHOLD_MEDIUM,
    )
except ModuleNotFoundError:  # allow standalone / test usage
    TRUST_WEIGHT_DOC_FORENSIC  = 0.45
    TRUST_WEIGHT_BEHAVIORAL    = 0.35
    TRUST_WEIGHT_GRAPH_ANOMALY = 0.20
    RISK_THRESHOLD_HIGH        = 0.65
    RISK_THRESHOLD_MEDIUM      = 0.35


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class TrustResult(TypedDict):
    """Return type of AdaptiveTrustEngine.evaluate()."""
    final_score: float
    risk_level: RiskLevel
    component_scores: Dict[str, float]


class AdaptiveTrustEngine:
    """
    Fuses forensic, behavioral, and graph-anomaly scores into a single
    normalised risk score with an associated risk level.

    Score semantics
    ---------------
    All input scores and the final_score are in **[0, 1]**:
      * 0.0 = no risk detected
      * 1.0 = maximum risk / certain fraud

    Weights
    -------
    Loaded from ``backend.config`` (env-var overridable).  They are
    automatically re-normalised to sum to 1.0, so passing raw relative
    weights is safe.

    Risk levels
    -----------
    Derived by comparing final_score against two configurable thresholds
    (also from config)::

        final_score >= RISK_THRESHOLD_HIGH   → HIGH
        final_score >= RISK_THRESHOLD_MEDIUM → MEDIUM
        otherwise                            → LOW

    Usage
    -----
    engine = AdaptiveTrustEngine()
    result = engine.evaluate(
        doc_forensic_score=0.72,
        session_behavioral_score=0.41,
        graph_anomaly_score=0.15,
    )
    # {"final_score": 0.514, "risk_level": "MEDIUM", "component_scores": {...}}
    """

    def __init__(
        self,
        weight_doc_forensic:  Optional[float] = None,
        weight_behavioral:    Optional[float] = None,
        weight_graph_anomaly: Optional[float] = None,
        threshold_high:       Optional[float] = None,
        threshold_medium:     Optional[float] = None,
    ) -> None:
        """
        Parameters
        ----------
        weight_doc_forensic  : Weight for the document forensic score.
                               Defaults to ``TRUST_WEIGHT_DOC_FORENSIC`` from config.
        weight_behavioral    : Weight for the behavioral session score.
                               Defaults to ``TRUST_WEIGHT_BEHAVIORAL`` from config.
        weight_graph_anomaly : Weight for the graph anomaly score.
                               Defaults to ``TRUST_WEIGHT_GRAPH_ANOMALY`` from config.
        threshold_high       : final_score >= this → HIGH risk.
        threshold_medium     : final_score >= this → MEDIUM risk.
        """
        w_doc  = weight_doc_forensic  if weight_doc_forensic  is not None else TRUST_WEIGHT_DOC_FORENSIC
        w_beh  = weight_behavioral    if weight_behavioral    is not None else TRUST_WEIGHT_BEHAVIORAL
        w_grph = weight_graph_anomaly if weight_graph_anomaly is not None else TRUST_WEIGHT_GRAPH_ANOMALY

        total = w_doc + w_beh + w_grph
        if total <= 0:
            raise ValueError("Sum of weights must be positive.")

        # Normalise so weights always sum to exactly 1.0.
        self._w_doc  = w_doc  / total
        self._w_beh  = w_beh  / total
        self._w_grph = w_grph / total

        self._threshold_high   = threshold_high   if threshold_high   is not None else RISK_THRESHOLD_HIGH
        self._threshold_medium = threshold_medium if threshold_medium is not None else RISK_THRESHOLD_MEDIUM

        if not (0.0 < self._threshold_medium < self._threshold_high < 1.0):
            raise ValueError(
                "Thresholds must satisfy 0 < threshold_medium < threshold_high < 1."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp(value: float, name: str) -> float:
        """Validate and clamp a component score to [0, 1]."""
        if not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a numeric value, got {type(value).__name__}.")
        return max(0.0, min(float(value), 1.0))

    def _classify(self, score: float) -> RiskLevel:
        if score >= self._threshold_high:
            return "HIGH"
        if score >= self._threshold_medium:
            return "MEDIUM"
        return "LOW"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        doc_forensic_score:      float,
        session_behavioral_score: float,
        graph_anomaly_score:     float,
    ) -> TrustResult:
        """
        Fuse three component scores into a final trust assessment.

        Parameters
        ----------
        doc_forensic_score       : ELA / forgery classifier score (0–1).
        session_behavioral_score : Isolation Forest / LSTM anomaly score (0–1).
        graph_anomaly_score      : Neo4j entity relationship anomaly score (0–1).

        Returns
        -------
        TrustResult TypedDict::

            {
                "final_score":      float,          # weighted sum, 0–1
                "risk_level":       "LOW"|"MEDIUM"|"HIGH",
                "component_scores": {
                    "doc_forensic":      float,
                    "session_behavioral": float,
                    "graph_anomaly":      float,
                    "weights": {
                        "doc_forensic":       float,
                        "session_behavioral": float,
                        "graph_anomaly":      float,
                    },
                },
            }
        """
        s_doc  = self._clamp(doc_forensic_score,       "doc_forensic_score")
        s_beh  = self._clamp(session_behavioral_score, "session_behavioral_score")
        s_grph = self._clamp(graph_anomaly_score,      "graph_anomaly_score")

        final_score = round(
            self._w_doc * s_doc + self._w_beh * s_beh + self._w_grph * s_grph,
            6,
        )

        return TrustResult(
            final_score=final_score,
            risk_level=self._classify(final_score),
            component_scores={
                "doc_forensic":       round(s_doc,  6),
                "session_behavioral": round(s_beh,  6),
                "graph_anomaly":      round(s_grph, 6),
                "weights": {
                    "doc_forensic":       round(self._w_doc,  6),
                    "session_behavioral": round(self._w_beh,  6),
                    "graph_anomaly":      round(self._w_grph, 6),
                },
            },
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"AdaptiveTrustEngine("
            f"w_doc={self._w_doc:.3f}, "
            f"w_beh={self._w_beh:.3f}, "
            f"w_grph={self._w_grph:.3f}, "
            f"thresholds=[{self._threshold_medium}, {self._threshold_high}])"
        )