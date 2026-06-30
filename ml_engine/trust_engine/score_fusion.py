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
    TRUST_WEIGHT_DOC_FORENSIC  = 0.60
    TRUST_WEIGHT_BEHAVIORAL    = 0.30
    TRUST_WEIGHT_GRAPH_ANOMALY = 0.10
    RISK_THRESHOLD_HIGH        = 0.65   # was 0.45 — too aggressive; flagged clean docs
    RISK_THRESHOLD_MEDIUM      = 0.35   # was 0.22 — any doc with weak signals hit MEDIUM



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


# ---------------------------------------------------------------------------
# TrustEngine — high-level façade used by the DhanRakshak pipeline
# ---------------------------------------------------------------------------

_RECOMMENDATION: Dict[str, str] = {
    "LOW":    "APPROVE",
    "MEDIUM": "MANUAL_REVIEW",
    "HIGH":   "REJECT",
}

_OCR_SEVERITY_WEIGHT: Dict[str, float] = {
    "HIGH":   1.0,
    "MEDIUM": 0.6,
    "LOW":    0.3,
}


class TrustEngine:
    """
    High-level wrapper around :class:`AdaptiveTrustEngine` that accepts the
    full set of DhanRakshak signals and exposes the API expected by the
    verification pipeline.

    Inputs
    ------
    trufor_score    : TruFor forgery probability [0, 1].
    ela_score       : ELA anomaly score [0, 1].
    ocr_conflicts   : List of OCR conflict dicts (keys: type, severity, message).
    behavioral_score: Behavioral anomaly score [0, 1].
    metadata_flags  : List of metadata red-flag strings.
    rule_base_score : Legacy rule engine score [0, 100] (normalised internally).

    Output of compute_risk()
    ------------------------
    Dict with keys: final_score, risk_level, recommendation, component_scores,
    anomaly_flags, anomaly_type.
    """

    # Relative weights within the doc-forensic component
    # Must sum to 1.0.
    _W_TRUFOR  = 0.30   # TruFor/ELA integrity (inverted to forgery prob)
    _W_ELA     = 0.20   # ELA anomaly
    _W_INCOME  = 0.20   # Income discrepancy fraud score
    _W_OCR     = 0.20   # OCR cross-document conflicts
    _W_META    = 0.05   # Metadata flags
    _W_RULE    = 0.05   # Legacy rule-engine score

    def __init__(
        self,
        weight_doc_forensic:  Optional[float] = None,
        weight_behavioral:    Optional[float] = None,
        weight_graph_anomaly: Optional[float] = None,
        threshold_high:       Optional[float] = None,
        threshold_medium:     Optional[float] = None,
    ) -> None:
        self._engine = AdaptiveTrustEngine(
            weight_doc_forensic=weight_doc_forensic,
            weight_behavioral=weight_behavioral,
            weight_graph_anomaly=weight_graph_anomaly,
            threshold_high=threshold_high,
            threshold_medium=threshold_medium,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ocr_score(conflicts: list) -> float:
        """Convert OCR conflict list to a [0, 1] severity score (accumulative, capped at 1)."""
        if not conflicts:
            return 0.0
        total = 0.0
        for c in conflicts:
            sev = (c.get("severity") or "LOW").upper()
            total += _OCR_SEVERITY_WEIGHT.get(sev, 0.3)
        return min(total, 1.0)

    @staticmethod
    def _metadata_score(flags: list) -> float:
        """Convert metadata flag list to a [0, 1] score."""
        if not flags:
            return 0.0
        return min(len(flags) * 0.25, 1.0)

    def _doc_forensic_score(
        self,
        trufor_score: float,
        ela_score: float,
        ocr_conflicts: list,
        metadata_flags: list,
        rule_base_score: float,
        income_fraud_score: float = 0.0,
        benford_score: float = 0.0,
    ) -> float:
        """
        Aggregate document-level signals into one [0, 1] forgery risk score.

        Note on trufor_score / ela_score semantics
        ------------------------------------------
        TruForDetector.analyze() returns ``integrity_score`` where
        **higher = more authentic**.  The public compute_risk() signature
        accepts these as-is and the inversion is applied HERE so that the
        rest of the pipeline consistently works with forgery probability
        (0 = clean, 1 = forged).
        """
        # Convert integrity scores -> forgery probability
        trufor_forgery = 1.0 - max(0.0, min(float(trufor_score), 1.0))
        ela_forgery    = 1.0 - max(0.0, min(float(ela_score),    1.0))

        ocr     = self._ocr_score(ocr_conflicts)
        meta    = self._metadata_score(metadata_flags)
        rule    = max(0.0, min(float(rule_base_score) / 100.0, 1.0))
        income  = max(0.0, min(float(income_fraud_score), 1.0))
        benford = max(0.0, min(float(benford_score), 1.0))

        raw = (
            self._W_TRUFOR * trufor_forgery
            + self._W_ELA    * ela_forgery
            + self._W_INCOME * income
            + self._W_OCR    * ocr
            + self._W_META   * meta
            + self._W_RULE   * rule
        )

        # Benford blended at 5% on top — only when data is available
        if benford > 0.0:
            raw = raw * 0.95 + benford * 0.05

        return round(min(raw, 1.0), 6)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_risk(
        self,
        trufor_score:        float,
        ela_score:           float,
        ocr_conflicts:       list,
        behavioral_score:    float,
        metadata_flags:      list,
        rule_base_score:     float,
        graph_anomaly_score: float = 0.0,
        income_fraud_score:  float = 0.0,
        benford_score:       float = 0.0,
        applicant_name:      str   = "",
        pan_number:          str   = "",
        doc_type:            str   = "Document",
        audit_id:            str   = "",
    ) -> dict:
        """
        Compute a unified fraud risk assessment.

        Parameters
        ----------
        trufor_score         : TruFor integrity score [0, 1]  (higher = cleaner).
        ela_score            : ELA anomaly score [0, 1].
        ocr_conflicts        : List of OCR conflict dicts.
        behavioral_score     : Behavioral anomaly score [0, 1].
        metadata_flags       : List of metadata red-flag strings.
        rule_base_score      : Legacy rule score [0, 100].
        graph_anomaly_score  : Graph/entity anomaly score [0, 1] (optional).
        income_fraud_score   : Income discrepancy score [0, 1] (optional).
        benford_score        : Benford's Law chi-square normalised score [0, 1] (optional).
        applicant_name       : Applicant display name (for report context).
        pan_number           : PAN number (for report context).
        doc_type             : Document type label (for report context).
        audit_id             : Audit reference ID (for report context).

        Returns
        -------
        dict with keys:
            final_score, final_score_pct, risk_level, recommendation,
            component_scores, anomaly_flags, anomaly_type,
            applicant_name, pan_number, doc_type, audit_id,
            top_risk_factors, conflicts
        """
        # Income fraud gets its own dedicated component weight
        effective_rule = max(0.0, min(float(rule_base_score), 100.0))

        doc_score = self._doc_forensic_score(
            trufor_score, ela_score, ocr_conflicts, metadata_flags,
            effective_rule, income_fraud_score, benford_score,
        )

        base: TrustResult = self._engine.evaluate(
            doc_forensic_score=doc_score,
            session_behavioral_score=max(0.0, min(float(behavioral_score), 1.0)),
            graph_anomaly_score=max(0.0, min(float(graph_anomaly_score), 1.0)),
        )

        risk_level: RiskLevel = base["risk_level"]
        final_score: float = base["final_score"]

        # Build anomaly flag list for downstream use
        anomaly_flags: list = list(metadata_flags)
        for c in ocr_conflicts:
            msg = c.get("message") or c.get("type") or "ocr_conflict"
            anomaly_flags.append(msg)

        anomaly_type: str
        if risk_level == "HIGH":
            anomaly_type = "document_fraud"
        elif risk_level == "MEDIUM":
            anomaly_type = "suspicious_activity"
        else:
            anomaly_type = "none"

        # Build top risk factors list for reporter
        top_risk_factors: list = []
        if trufor_score < 0.85:
            top_risk_factors.append({
                "factor":   "Document integrity",
                "detail":   f"TruFor integrity score {trufor_score:.3f}",
                "severity": "HIGH" if trufor_score < 0.7 else "MEDIUM",
                "score":    round(1.0 - trufor_score, 3),
            })
        if income_fraud_score > 0.2:
            top_risk_factors.append({
                "factor":   "Income discrepancy",
                "detail":   f"Income fraud score {income_fraud_score:.3f}",
                "severity": "HIGH" if income_fraud_score > 0.4 else "MEDIUM",
                "score":    round(income_fraud_score, 3),
            })
        for c in ocr_conflicts[:3]:
            top_risk_factors.append({
                "factor":   c.get("type", "conflict"),
                "detail":   c.get("message", ""),
                "severity": c.get("severity", "MEDIUM"),
                "score":    0.8 if c.get("severity") == "HIGH" else 0.5,
            })

        return {
            "final_score":       final_score,
            "final_score_pct":   round(final_score * 100, 2),
            "risk_level":        risk_level,
            "recommendation":    _RECOMMENDATION[risk_level],
            "applicant_name":    applicant_name,
            "pan_number":        pan_number,
            "doc_type":          doc_type,
            "audit_id":          audit_id or f"AUD-{abs(hash(applicant_name + pan_number)) % 100000:05d}",
            "component_scores": {
                **base["component_scores"],
                "doc_forensic_breakdown": {
                    "trufor":         round(trufor_score, 6),
                    "ela":            round(ela_score, 6),
                    "ocr":            round(self._ocr_score(ocr_conflicts), 6),
                    "metadata":       round(self._metadata_score(metadata_flags), 6),
                    "rule":           round(effective_rule / 100.0, 6),
                    "income_fraud":   round(income_fraud_score, 6),
                    "benford":        round(benford_score, 6),
                },
            },
            "anomaly_flags":     anomaly_flags,
            "anomaly_type":      anomaly_type,
            "top_risk_factors":  top_risk_factors,
            "conflicts":         ocr_conflicts,
        }


    def explain_text(self, risk_result: dict) -> str:
        """
        Return a human-readable explanation string for a compute_risk() result.

        Parameters
        ----------
        risk_result : dict returned by :meth:`compute_risk`.

        Returns
        -------
        str — multi-line explanation suitable for logging or UI display.
        """
        lines = [
            f"Risk Assessment Summary",
            f"======================",
            f"Risk Level   : {risk_result.get('risk_level', 'N/A')}",
            f"Final Score  : {risk_result.get('final_score', 0.0):.4f}",
            f"Recommendation: {risk_result.get('recommendation', 'N/A')}",
            f"Anomaly Type : {risk_result.get('anomaly_type', 'none')}",
            "",
        ]

        comp = risk_result.get("component_scores", {})
        lines.append("Component Scores:")
        lines.append(f"  Document Forensic : {comp.get('doc_forensic', 0.0):.4f}")
        lines.append(f"  Behavioral        : {comp.get('session_behavioral', 0.0):.4f}")
        lines.append(f"  Graph Anomaly     : {comp.get('graph_anomaly', 0.0):.4f}")

        breakdown = comp.get("doc_forensic_breakdown", {})
        if breakdown:
            lines.append("")
            lines.append("Document Forensic Breakdown:")
            lines.append(f"  TruFor  : {breakdown.get('trufor', 0.0):.4f}")
            lines.append(f"  ELA     : {breakdown.get('ela', 0.0):.4f}")
            lines.append(f"  OCR     : {breakdown.get('ocr', 0.0):.4f}")
            lines.append(f"  Metadata: {breakdown.get('metadata', 0.0):.4f}")
            lines.append(f"  Rules   : {breakdown.get('rule', 0.0):.4f}")

        flags = risk_result.get("anomaly_flags", [])
        if flags:
            lines.append("")
            lines.append(f"Anomaly Flags ({len(flags)}):")
            for f_ in flags:
                lines.append(f"  • {f_}")

        return "\n".join(lines)