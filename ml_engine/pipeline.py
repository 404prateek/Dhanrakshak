"""
pipeline.py
-----------
DhanRakshak unified ML inference pipeline.

Orchestrates all sub-systems in a single call:
    1.  Document OCR         (ml_engine.ocr_nlp.document_ocr)
    2.  Forensic Vision      (ml_engine.forensic_vision)
    3.  Behavioral Twin      (ml_engine.behavioral_twin.behavior_analyzer)
    4.  Trust Engine         (ml_engine.trust_engine.score_fusion)
    5.  LLM Reporter         (ml_engine.llm_reporter.ollama_reporter)

Usage
-----
    from ml_engine.pipeline import DhanRakshakPipeline

    pipeline = DhanRakshakPipeline()
    result = pipeline.run(
        document_bytes=open("cheque.jpg", "rb").read(),
        document_mime="image/jpeg",
        session_data={"keystrokes": [...], "transaction": {...}},
    )
    print(result.report.narrative)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline result container
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Aggregated output from the full DhanRakshak pipeline."""

    # Sub-system outputs (None = sub-system skipped / unavailable)
    ocr_result: Optional[Any] = None
    forensic_result: Optional[Any] = None
    metadata_result: Optional[Any] = None
    behavioral_result: Optional[Any] = None
    trust_score: Optional[float] = None
    report: Optional[Any] = None

    # Meta
    processing_time_ms: float = 0.0
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def is_fraud_suspected(self) -> bool:
        """Convenience: True when trust score < 0.4 or any HIGH/CRITICAL risk."""
        if self.trust_score is not None and self.trust_score < 0.4:
            return True
        if self.report is not None:
            return getattr(self.report, "risk_level", "LOW") in ("HIGH", "CRITICAL")
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trust_score": self.trust_score,
            "is_fraud_suspected": self.is_fraud_suspected,
            "processing_time_ms": self.processing_time_ms,
            "errors": self.errors,
            "report": self.report.to_dict() if self.report else None,
            "ocr": self.ocr_result.to_dict() if self.ocr_result else None,
            "behavioral": self.behavioral_result.to_dict() if self.behavioral_result else None,
            "forensic": self.forensic_result if self.forensic_result else None,
            "metadata": self.metadata_result.to_dict() if self.metadata_result else None,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class DhanRakshakPipeline:
    """
    End-to-end fraud detection pipeline.

    Parameters
    ----------
    model_path:
        Path to the directory containing trained model checkpoints.
        Defaults to ``ml_engine/training/checkpoints/``.
    ollama_url:
        Ollama server base URL for report generation.
    ollama_model:
        Ollama model name (must be pulled locally).
    enable_llm_report:
        Whether to call the LLM reporter (requires Ollama running).
    """

    _DEFAULT_CHECKPOINT_DIR = Path(__file__).parent / "training" / "checkpoints"

    def __init__(
        self,
        model_path: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3",
        enable_llm_report: bool = True,
    ) -> None:
        self.checkpoint_dir = Path(model_path) if model_path else self._DEFAULT_CHECKPOINT_DIR
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.enable_llm_report = enable_llm_report

        # Lazily initialised sub-systems
        self._ocr: Optional[Any] = None
        self._trufor: Optional[Any] = None
        self._metadata_analyzer: Optional[Any] = None
        self._behavior_analyzer: Optional[Any] = None
        self._score_fusion: Optional[Any] = None
        self._reporter: Optional[Any] = None

        self._init_subsystems()

    # ------------------------------------------------------------------
    # Subsystem initialisation
    # ------------------------------------------------------------------

    def _init_subsystems(self) -> None:
        """Attempt to initialise all sub-systems; log warnings on failure."""

        # OCR
        try:
            from ml_engine.ocr_nlp.document_ocr import DocumentOCR

            self._ocr = DocumentOCR()
            logger.info("Pipeline: DocumentOCR ready.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Pipeline: DocumentOCR unavailable: %s", exc)

        # TruFor (forensic image analysis)
        try:
            from ml_engine.forensic_vision.trufor_wrapper import TruForDetector

            self._trufor = TruForDetector()
            logger.info("Pipeline: TruForDetector ready.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Pipeline: TruForDetector unavailable: %s", exc)

        # Metadata analyzer
        try:
            from ml_engine.forensic_vision.metadata_analyzer import MetadataAnalyzer

            self._metadata_analyzer = MetadataAnalyzer()
            logger.info("Pipeline: MetadataAnalyzer ready.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Pipeline: MetadataAnalyzer unavailable: %s", exc)

        # Behavioral analyzer
        try:
            from ml_engine.behavioral_twin.behavior_analyzer import BehaviorAnalyzer

            ifor_path = str(self.checkpoint_dir / "isolation_forest.pkl")
            self._behavior_analyzer = BehaviorAnalyzer(
                model_path=ifor_path if Path(ifor_path).exists() else None
            )
            logger.info("Pipeline: BehaviorAnalyzer ready.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Pipeline: BehaviorAnalyzer unavailable: %s", exc)

        # Score fusion / trust engine
        try:
            from ml_engine.trust_engine.score_fusion import AdaptiveTrustEngine

            self._score_fusion = AdaptiveTrustEngine()
            logger.info("Pipeline: AdaptiveTrustEngine ready.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Pipeline: AdaptiveTrustEngine unavailable: %s", exc)

        # LLM reporter
        if self.enable_llm_report:
            try:
                from ml_engine.llm_reporter.ollama_reporter import OllamaReporter

                self._reporter = OllamaReporter(
                    base_url=self.ollama_url, model=self.ollama_model
                )
                logger.info("Pipeline: OllamaReporter ready.")
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Pipeline: OllamaReporter unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        document_bytes: Optional[bytes] = None,
        document_mime: str = "image/jpeg",
        session_data: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Run the full fraud detection pipeline.

        Parameters
        ----------
        document_bytes:
            Raw bytes of the document/image to analyse.  Pass ``None`` to
            skip OCR and forensic vision steps.
        document_mime:
            MIME type of the document (``"image/jpeg"`` or ``"application/pdf"``).
        session_data:
            Dictionary with raw behavioural session signals.  Pass ``None``
            to skip the behavioural twin step.

        Returns
        -------
        PipelineResult
            Aggregated outputs from all sub-systems.
        """
        t_start = time.perf_counter()
        result = PipelineResult()
        context: Dict[str, Any] = {}

        # ----------------------------------------------------------------
        # 1. OCR
        # ----------------------------------------------------------------
        if document_bytes and self._ocr:
            try:
                result.ocr_result = self._ocr.extract_from_bytes(
                    document_bytes, mime_type=document_mime
                )
                context["ocr_fields"] = result.ocr_result.structured_fields
                logger.debug("OCR complete: %d fields extracted.", len(context["ocr_fields"]))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Pipeline OCR step failed: %s", exc)
                result.errors["ocr"] = str(exc)

        # ----------------------------------------------------------------
        # 2. Forensic vision — TruFor
        # ----------------------------------------------------------------
        if document_bytes and self._trufor:
            try:
                import io
                from PIL import Image

                img = Image.open(io.BytesIO(document_bytes)).convert("RGB")
                if self._trufor.is_available:
                    res_dict = self._trufor._analyze_trufor(img)
                else:
                    res_dict = self._trufor._analyze_ela(img)
                
                result.forensic_result = res_dict
                integrity = res_dict.get("integrity_score")
                if integrity is None:
                    integrity = 1.0
                
                context["forensic_risk"] = 1.0 - integrity
                context["forensic_flags"] = []
                if res_dict.get("is_tampered"):
                    context["forensic_flags"].append("image_tampering_detected")
                logger.debug("TruFor: integrity=%.2f", integrity)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Pipeline TruFor step failed: %s", exc)
                result.errors["forensic"] = str(exc)

        # ----------------------------------------------------------------
        # 3. Metadata analysis
        # ----------------------------------------------------------------
        if document_bytes and self._metadata_analyzer:
            try:
                result.metadata_result = self._metadata_analyzer.analyze_bytes(document_bytes)
                context.setdefault("forensic_flags", [])
                context["forensic_flags"].extend(result.metadata_result.suspicious_flags)
                logger.debug(
                    "Metadata: risk=%.2f, flags=%s",
                    result.metadata_result.risk_score,
                    result.metadata_result.suspicious_flags,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Pipeline metadata step failed: %s", exc)
                result.errors["metadata"] = str(exc)

        # ----------------------------------------------------------------
        # 4. Behavioral twin
        # ----------------------------------------------------------------
        if session_data and self._behavior_analyzer:
            try:
                result.behavioral_result = self._behavior_analyzer.analyze(session_data)
                context["behavioral_risk"] = result.behavioral_result.risk_score
                context["panic_detected"] = result.behavioral_result.panic_detected
                context["anomaly_detected"] = result.behavioral_result.anomaly_detected
                logger.debug(
                    "Behavioral: risk=%.2f, panic=%s",
                    result.behavioral_result.risk_score,
                    result.behavioral_result.panic_detected,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Pipeline behavioral step failed: %s", exc)
                result.errors["behavioral"] = str(exc)

        # ----------------------------------------------------------------
        # 5. Trust score fusion
        # ----------------------------------------------------------------
        if self._score_fusion:
            try:
                fusion_res = self._score_fusion.evaluate(
                    doc_forensic_score=context.get("forensic_risk", 0.0),
                    session_behavioral_score=context.get("behavioral_risk", 0.0),
                    graph_anomaly_score=0.0
                )
                result.trust_score = fusion_res["final_score"]
                context["trust_score"] = result.trust_score
                context["risk_level"] = fusion_res["risk_level"]
                logger.debug("Trust score: %.2f", result.trust_score)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Pipeline trust fusion step failed: %s", exc)
                result.errors["trust"] = str(exc)

        # ----------------------------------------------------------------
        # 6. LLM report
        # ----------------------------------------------------------------
        if self._reporter and context:
            try:
                result.report = self._reporter.generate_report(context)
                logger.debug("LLM report generated: risk=%s", result.report.risk_level)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Pipeline LLM reporter step failed: %s", exc)
                result.errors["llm_report"] = str(exc)

        result.processing_time_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "Pipeline complete in %.1f ms. Fraud suspected: %s",
            result.processing_time_ms,
            result.is_fraud_suspected,
        )
        return result
