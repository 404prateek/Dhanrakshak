"""
behavior_analyzer.py
--------------------
High-level behavioral analysis orchestrator for the DhanRakshak Behavioral
Twin sub-system.

This module ties together:
    - BehaviorFeatureExtractor  (ml_engine.behavioral_twin.feature_extractor)
    - BehavioralAnomalyDetector (ml_engine.behavioral_twin.isolation_forest)
    - PanicDetector             (ml_engine.behavioral_twin.panic_detector)

…to produce a unified BehavioralRiskAssessment for a given transaction or
user-session context.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class BehavioralRiskAssessment:
    """
    Unified behavioral risk output.

    Attributes
    ----------
    risk_score:
        Composite risk score in [0, 1].  Higher = more anomalous.
    anomaly_detected:
        True when the Isolation Forest flags the session as an outlier.
    panic_detected:
        True when the panic detector fires (rapid/unusual motor patterns).
    feature_vector:
        Raw feature array extracted from the session.
    contributing_factors:
        Human-readable list of factors that pushed the risk score up.
    processing_time_ms:
        Wall-clock time taken to produce this assessment.
    error:
        Non-None when an exception occurred during analysis.
    """

    risk_score: float = 0.0
    anomaly_detected: bool = False
    panic_detected: bool = False
    feature_vector: List[float] = field(default_factory=list)
    contributing_factors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "anomaly_score": self.risk_score,          # alias expected by callers
            "anomaly_detected": self.anomaly_detected,
            "anomaly_type": (
                "behavioral_anomaly" if self.anomaly_detected
                else "panic" if self.panic_detected
                else "none"
            ),
            "panic_detected": self.panic_detected,
            "contributing_factors": self.contributing_factors,
            "processing_time_ms": self.processing_time_ms,
            "feature_dimension": len(self.feature_vector),
            "error": self.error,
        }

    # Allow dict-style access: result['anomaly_score']
    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()


# ---------------------------------------------------------------------------
# BehaviorAnalyzer
# ---------------------------------------------------------------------------


class BehaviorAnalyzer:
    """
    Orchestrates behavioral twin analysis for a user session.

    Parameters
    ----------
    model_path:
        Path to a serialised BehavioralAnomalyDetector checkpoint (``.pkl``).
        Pass ``None`` to operate in stub mode (no anomaly scoring).
    anomaly_threshold:
        Score threshold above which a session is considered anomalous.
        Default ``0.5`` (normalised [0, 1] scale from BehavioralAnomalyDetector).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        anomaly_threshold: float = 0.5,
    ) -> None:
        self.model_path = model_path
        self.anomaly_threshold = anomaly_threshold

        self._feature_extractor = self._load_feature_extractor()
        self._anomaly_detector = self._load_anomaly_detector()
        self._panic_detector = self._load_panic_detector()

    # ------------------------------------------------------------------
    # Component loaders
    # ------------------------------------------------------------------

    def _load_feature_extractor(self):
        try:
            from ml_engine.behavioral_twin.feature_extractor import BehaviorFeatureExtractor

            logger.debug("BehaviorAnalyzer: BehaviorFeatureExtractor loaded.")
            return BehaviorFeatureExtractor()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("FeatureExtractor unavailable: %s", exc)
            return None

    def _load_anomaly_detector(self):
        try:
            from ml_engine.behavioral_twin.isolation_forest import (
                BehavioralAnomalyDetector,
            )

            detector = BehavioralAnomalyDetector()
            if self.model_path:
                detector.load_model(self.model_path)
            logger.debug("BehaviorAnalyzer: BehavioralAnomalyDetector loaded.")
            return detector
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AnomalyDetector unavailable: %s", exc)
            return None

    def _load_panic_detector(self):
        try:
            from ml_engine.behavioral_twin.panic_detector import PanicDetector

            logger.debug("BehaviorAnalyzer: PanicDetector loaded.")
            return PanicDetector()  # uses default thresholds
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("PanicDetector unavailable: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, session_data: Dict[str, Any]) -> BehavioralRiskAssessment:
        """
        Perform a full behavioral risk assessment on session data.

        Parameters
        ----------
        session_data:
            Dictionary containing raw session signals such as:
            - ``keydown``     : list of {t: epoch_ms} dicts
            - ``mousemove``   : list of {t, x, y} dicts
            - ``scroll``      : list of {t, dy} dicts
            - ``click``       : list of {t, x, y} dicts
            - ``transaction`` : dict with amount, target_account, etc.

        Returns
        -------
        BehavioralRiskAssessment
            Supports both attribute access and dict-style subscript access.
        """
        t_start = time.perf_counter()
        result = BehavioralRiskAssessment()

        try:
            # 1. Feature extraction
            features = None
            if self._feature_extractor is not None:
                try:
                    features = self._feature_extractor.extract(session_data)
                    result.feature_vector = features.tolist()
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("Feature extraction failed: %s", exc)
                    result.contributing_factors.append("feature_extraction_error")

            # 2. Anomaly detection
            if self._anomaly_detector is not None and features is not None:
                try:
                    if self._anomaly_detector._fitted:
                        score = self._anomaly_detector.predict(features)
                        anomaly = score >= self.anomaly_threshold
                        result.anomaly_detected = anomaly
                        if anomaly:
                            result.contributing_factors.append(
                                f"isolation_forest_anomaly(score={score:.3f})"
                            )
                    else:
                        logger.debug("AnomalyDetector not fitted; skipping scoring.")
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("AnomalyDetector scoring failed: %s", exc)
                    result.contributing_factors.append("anomaly_detection_error")

            # 3. Panic detection
            if self._panic_detector is not None:
                try:
                    panic_result = self._panic_detector.detect(session_data)
                    result.panic_detected = panic_result["panic_detected"]
                    if result.panic_detected:
                        result.contributing_factors.append("panic_pattern_detected")
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("PanicDetector failed: %s", exc)
                    result.contributing_factors.append("panic_detection_error")

            # 4. Fuse into composite risk score
            result.risk_score = self._fuse_scores(result)

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("BehaviorAnalyzer.analyze: unexpected error: %s", exc)
            result.error = str(exc)
            result.risk_score = 0.5

        result.processing_time_ms = (time.perf_counter() - t_start) * 1000
        return result

    # ------------------------------------------------------------------
    # Score fusion
    # ------------------------------------------------------------------

    def _fuse_scores(self, assessment: BehavioralRiskAssessment) -> float:
        """
        Combine sub-signals into a single risk score in [0, 1].

        Weights:
            - Isolation Forest anomaly: 0.55
            - Panic signal:             0.30
            - Feature extraction error: 0.15 (uncertainty penalty)
        """
        score = 0.0
        if assessment.anomaly_detected:
            score += 0.55
        if assessment.panic_detected:
            score += 0.30
        if "feature_extraction_error" in assessment.contributing_factors:
            score += 0.10  # uncertainty
        return min(score, 1.0)

    def analyze_batch(
        self, sessions: List[Dict[str, Any]]
    ) -> List[BehavioralRiskAssessment]:
        """Run :meth:`analyze` for a list of session dictionaries."""
        return [self.analyze(s) for s in sessions]
