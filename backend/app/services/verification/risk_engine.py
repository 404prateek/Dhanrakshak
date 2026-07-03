"""
risk_engine.py
--------------
Real ML risk engine — replaces mock implementation.
Calls ml_engine pipeline for actual fraud detection.

Module-level singletons are loaded once at import time so the expensive
TruFor checkpoint is not reloaded on every request.
"""

import sys
import os
import re
import concurrent.futures
import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Project root is 4 levels up: risk_engine.py → verification → services → app → backend → PROJECT
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml_engine.forensic_vision.trufor_wrapper    import TruForDetector
from ml_engine.forensic_vision.metadata_analyzer import MetadataAnalyzer
from ml_engine.ocr_nlp.document_ocr             import IndianDocumentOCR, CrossDocValidator
from ml_engine.ocr_nlp.benford_checker           import BenfordChecker
from ml_engine.ocr_nlp.math_reconciler           import MathReconciler
from ml_engine.behavioral_twin.behavior_analyzer  import BehaviorAnalyzer
from ml_engine.trust_engine.score_fusion          import TrustEngine
from ml_engine.llm_reporter.ollama_reporter       import OllamaReporter
from ml_engine.ocr_nlp.text_risk_analyzer         import TextRiskAnalyzer
# LLMSemanticScanner REMOVED — caused critical false positives on legitimate
# government documents (OBC certs, income certs, DM office letters).
# The tiny llama3.2:1b model hallucinated 'unregistered_institution' for real
# government bodies like 'District Magistrate, Dwarka'.
# Institution checking is now done ONLY via the deterministic
# GOVERNMENT_WHITELIST_PATTERNS + DEFINITE_FRAUD_PATTERNS in document_ocr.py.


# Hardcoded lists replaced by LLMSemanticScanner


# ---------------------------------------------------------------------------
# Image-level watermark / repeated-text detector
# ---------------------------------------------------------------------------

def _detect_watermark_image(file_path: str) -> List[Dict[str, Any]]:
    """
    Detect diagonal or repeated large-text watermarks (SAMPLE, VOID, SPECIMEN)
    using simple image analysis. Returns a list of OCR-conflict-style dicts.
    """
    conflicts: List[Dict[str, Any]] = []
    try:
        import numpy as np
        from PIL import Image

        img = Image.open(file_path).convert("L")  # greyscale
        arr = np.array(img, dtype=np.float32)

        # Heuristic: check variance of rows vs columns.
        # A diagonal watermark creates periodic low-frequency patterns.
        # More reliably: check if large fractions of the image are mid-grey (watermark opacity ~30-50%)
        # Real clean documents are bimodal (very dark text + very white background).
        hist, _ = np.histogram(arr, bins=10, range=(0, 255))
        total = arr.size
        # Mid-grey range [80, 200] proportion
        mid_grey_fraction = hist[3:8].sum() / total
        if mid_grey_fraction > 0.99:   # Disabled: too many false positives on textured backgrounds
            conflicts.append({
                "type":     "watermark_detected",
                "severity": "HIGH",
                "message":  f"Image analysis suggests a semi-transparent watermark or overlay (mid-grey pixel fraction: {mid_grey_fraction:.1%})",
            })
            logger.warning("Watermark heuristic triggered: mid_grey_fraction=%.3f", mid_grey_fraction)
    except Exception as exc:
        logger.debug("Watermark image scan failed: %s", exc)
    return conflicts

# ---------------------------------------------------------------------------
# Module-level singletons (loaded once, reused on every request)
# ---------------------------------------------------------------------------

_trufor   = TruForDetector()
_meta     = MetadataAnalyzer()
_ocr      = IndianDocumentOCR()
_cv       = CrossDocValidator()
_benford  = BenfordChecker()
_math_rec = MathReconciler()
_behavior = BehaviorAnalyzer()
_trust    = TrustEngine()
_reporter = OllamaReporter()
_text_risk = TextRiskAnalyzer()
# _llm_scanner removed — see note above imports


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_document(
    file_path: str,
    behavior_data: dict = None,
    rule_base_score: int = 0,
) -> dict:
    """
    Run the full DhanRakshak ML pipeline on a single document.

    Parameters
    ----------
    file_path       : Absolute or relative path to the document.
    behavior_data   : Optional dict of behavioral telemetry signals.
    rule_base_score : Optional legacy rule-engine score [0, 100].

    Returns
    -------
    dict with keys:
        risk_score, risk_level, recommendation, entities, forensic,
        metadata_flags, behavioral, breakdown, conflicts, llm_report,
        heatmap_b64, audit_id, analysis_status
    """
    behavior_data = behavior_data or {}

    t_start = time.time()

    # -------------------------------------------------------------------
    # Stages 1-4 run IN PARALLEL — all are independent of each other
    # -------------------------------------------------------------------
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_forensic  = executor.submit(_trufor.analyze,    file_path)
        future_metadata  = executor.submit(_meta.analyze,      file_path)
        future_ocr       = executor.submit(_ocr.extract,       file_path)
        future_behavior  = executor.submit(_behavior.analyze,  behavior_data)

        try:
            forensic     = future_forensic.result(timeout=240)
        except concurrent.futures.TimeoutError:
            logger.warning("TruFor timed out; using neutral forensic result")
            forensic = {"integrity_score": 0.5, "heatmap_b64": "", "is_tampered": False, "method": "TIMEOUT"}

        try:
            metadata     = future_metadata.result(timeout=10)
        except concurrent.futures.TimeoutError:
            logger.warning("Metadata analysis timed out")
            metadata = {"flags": [], "risk_score": 0.0}

        try:
            entities     = future_ocr.result(timeout=90)
        except concurrent.futures.TimeoutError:
            logger.warning("OCR timed out")
            entities = {"names": [], "pan": [], "amounts": [], "full_text": "", "doc_type": "Unknown"}

        try:
            beh_result   = future_behavior.result(timeout=10)
        except concurrent.futures.TimeoutError:
            logger.warning("Behavioral analysis timed out")
            beh_result = type('B', (), {'risk_score': 0.0})()  # minimal stub

    logger.info("Parallel stages 1-4 done in %.1fs", time.time() - t_start)

    # When format is unsupported or render failed, integrity_score is None.
    # Use 0.5 (completely neutral) instead of 0.0 which falsely implies tampering.
    raw_integrity = forensic.get("integrity_score")
    analysis_status = "complete"
    if raw_integrity is None:
        integrity_score = 0.5   # neutral — we simply don't know
        analysis_status = forensic.get("method", "UNSUPPORTED_FORMAT").lower()
    else:
        integrity_score = float(raw_integrity)

    # -------------------------------------------------------------------
    # Benford + Math reconciliation (fast, sequential is fine here)
    # -------------------------------------------------------------------
    benford_result = _benford.check(entities.get('amounts', []))
    math_result    = _math_rec.check_totals(entities.get('full_text', ''))

    # Collect extra risk flags from supplementary detectors
    extra_flags = list(metadata.get('flags', []))
    if benford_result['is_suspicious']:
        extra_flags.append(f"Benford anomaly: {benford_result['flag']}")
    if not math_result['reconciliation_passed']:
        extra_flags.append('Math mismatch: claimed total does not match sub-totals')

    # If forensic analysis could not run, add an informational flag (not a risk flag)
    if analysis_status not in ("complete",):
        extra_flags.append(
            f"Note: Forensic scan unavailable for this document format "
            f"({forensic.get('method', 'unknown')}). "
            f"Manual visual inspection recommended."
        )

    # -------------------------------------------------------------------
    # Stage 5a: OCR Fraud Signal Detection (deterministic, offline)
    # -------------------------------------------------------------------
    # NOTE: LLM semantic institution checking was REMOVED here.
    # It caused false positives on legitimate government documents.
    # Fraud signals now come exclusively from the whitelist-first
    # _detect_fraud_signals() in document_ocr.py (Stage 3 of OCR pipeline).
    ocr_full_text = entities.get('full_text', '')
    ocr_conflicts = list(entities.get('fraud_signals', []))  # from OCR Stage 3

    # Add NLP Semantic Text checks
    if ocr_full_text:
        nlp_conflicts = _text_risk.analyze_text(ocr_full_text)
        ocr_conflicts.extend(nlp_conflicts)

    # Also attempt image-level watermark detection for image files
    _img_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
    if os.path.splitext(file_path)[1].lower() in _img_exts:
        ocr_conflicts.extend(_detect_watermark_image(file_path))

    if ocr_conflicts:
        logger.warning(
            "Document semantic fraud signals detected: %d conflicts — %s",
            len(ocr_conflicts),
            [c['message'][:60] for c in ocr_conflicts],
        )

    # -------------------------------------------------------------------
    # Stage 5b: Trust / risk scoring (needs stage 1-4 results)
    # -------------------------------------------------------------------
    trufor_forgery = 1.0 - integrity_score
    risk = _trust.compute_risk(
        trufor_score     = integrity_score,
        ela_score        = integrity_score,
        ocr_conflicts    = ocr_conflicts,
        behavioral_score = beh_result.risk_score,
        metadata_flags   = extra_flags,
        rule_base_score  = rule_base_score,
        benford_score    = benford_result['benford_score'],
        doc_type         = entities.get('doc_type', 'Unknown'),
        applicant_name   = (entities.get('names') or ['Unknown'])[0],
        pan_number       = (entities.get('pan') or [''])[0],
    )

    # -------------------------------------------------------------------
    # Stage 6: LLM narrative report (needs trust result)
    # -------------------------------------------------------------------
    # Pass trufor integrity score explicitly so the LLM prompt can reference it correctly
    risk_with_trufor = {**risk, 'trufor_score': integrity_score, 'forensic_score': trufor_forgery}
    report = _reporter.generate_report(risk_with_trufor)

    return {
        'risk_score':      int(risk.get('final_score_pct', 0)),
        'risk_level':      risk.get('risk_level', 'LOW'),
        'recommendation':  risk.get('recommendation', 'APPROVE'),
        'final_score':     risk.get('final_score', 0.0),
        'final_score_pct': risk.get('final_score_pct', 0.0),
        'escalated':       risk.get('escalated', False),
        'escalation_reason': risk.get('escalation_reason', None),
        'applicant_name':  (entities.get('names') or ['Unknown'])[0],
        'pan_number':      (entities.get('pan') or [''])[0],
        'doc_type':        entities.get('doc_type', 'Unknown'),
        'entities':        entities,
        'conflicts':       ocr_conflicts,
        'metadata_flags':  extra_flags,
        'forensic_score':  trufor_forgery,
        'behavioral_score': beh_result.risk_score,
        'heatmap_b64':     forensic.get('heatmap_b64', ''),
        'llm_report':      report,
        'benford_score':   benford_result.get('benford_score', 0.0),
        'math_passed':     math_result.get('reconciliation_passed', True),
        'breakdown':       risk.get('component_scores', {}),
        'audit_id':        risk.get('audit_id', 'N/A'),
        'top_risk_factors': risk.get('top_risk_factors', []),
        'analysis_status': analysis_status,
        'benford_flag':    benford_result.get('flag', ''),
        'math_score':      math_result.get('reconciliation_score', 0.0),
    }



def analyze_document_pair(
    primary_path: str,
    secondary_path: str,
    primary_type: str = 'ITR',
    secondary_type: str = 'Bank Statement',
    behavior_data: dict = None,
    rule_base_score: int = 0,
    income_itr: float = None,
    income_bank_monthly: float = None,
) -> dict:
    """
    Analyze two documents together, performing cross-document validation
    (name matching, PAN consistency, income discrepancy detection).

    Parameters
    ----------
    primary_path       : Path to primary document (e.g. ITR).
    secondary_path     : Path to secondary document (e.g. Bank Statement).
    primary_type       : Label for primary doc type.
    secondary_type     : Label for secondary doc type.
    behavior_data      : Behavioral telemetry signals (optional).
    rule_base_score    : Legacy rule-engine score [0, 100] (optional).
    income_itr         : Annual ITR income for discrepancy check (optional).
    income_bank_monthly: Average monthly bank credit for discrepancy check (optional).

    Returns
    -------
    dict — same schema as analyze_document() plus 'cross_doc_conflicts'
    and 'income_fraud_score' keys.
    """
    behavior_data = behavior_data or {}

    # Analyze both documents individually
    forensic1 = _trufor.analyze(primary_path)
    forensic2 = _trufor.analyze(secondary_path)

    # Use the worse integrity score as the combined forensic signal
    combined_integrity = min(forensic1['integrity_score'], forensic2['integrity_score'])

    metadata1 = _meta.analyze(primary_path)
    metadata2 = _meta.analyze(secondary_path)
    all_flags = list(set(metadata1['flags'] + metadata2['flags']))

    entities1 = _ocr.extract(primary_path)
    entities2 = _ocr.extract(secondary_path)

    beh_result = _behavior.analyze(behavior_data)

    # Cross-document validation
    cross_result = _cv.validate(entities1, entities2, primary_type, secondary_type)
    conflicts = cross_result['conflicts']

    # Include base OCR fraud signals
    conflicts.extend(entities1.get('fraud_signals', []))
    conflicts.extend(entities2.get('fraud_signals', []))

    # Add NLP Semantic Text checks for both documents
    if entities1.get('full_text'):
        conflicts.extend(_text_risk.analyze_text(entities1['full_text']))
    if entities2.get('full_text'):
        conflicts.extend(_text_risk.analyze_text(entities2['full_text']))
        
    # Attempt image-level watermark detection for image files
    _img_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
    if os.path.splitext(primary_path)[1].lower() in _img_exts:
        conflicts.extend(_detect_watermark_image(primary_path))
    if os.path.splitext(secondary_path)[1].lower() in _img_exts:
        conflicts.extend(_detect_watermark_image(secondary_path))

    # Income fraud detection (if amounts provided)
    income_fraud_score = 0.0
    income_flags = []
    if income_itr and income_bank_monthly:
        income_result = _cv.validate_income(income_itr, income_bank_monthly, None)
        income_fraud_score = income_result['income_fraud_score']
        if income_result['flags']:
            conflicts.append({
                'type':      'income_mismatch',
                'severity':  'HIGH',
                'message':   income_result['flags'][0],
                'doc1_value': str(income_itr),
                'doc2_value': str(income_bank_monthly * 12),
            })

    combined_forgery = 1.0 - combined_integrity
    risk = _trust.compute_risk(
        trufor_score       = combined_forgery,
        ela_score          = combined_forgery,
        ocr_conflicts      = conflicts,
        behavioral_score   = beh_result['anomaly_score'],
        metadata_flags     = all_flags,
        rule_base_score    = rule_base_score,
        income_fraud_score = income_fraud_score,
        doc_type           = f'{primary_type} + {secondary_type}',
        applicant_name     = (entities1.get('names') or ['Unknown'])[0],
        pan_number         = (entities1.get('pan') or [''])[0],
    )

    report = _reporter.generate_report(risk)

    return {
        'risk_score':          int(risk.get('final_score_pct', 0)),
        'risk_level':          risk.get('risk_level', 'LOW'),
        'recommendation':      risk.get('recommendation', 'APPROVE'),
        'final_score':         risk.get('final_score', 0.0),
        'final_score_pct':     risk.get('final_score_pct', 0.0),
        'applicant_name':      (entities1.get('names') or ['Unknown'])[0],
        'pan_number':          (entities1.get('pan') or [''])[0],
        'doc_type':            f'{primary_type} + {secondary_type}',
        'entities':            entities1,
        'entities_primary':    entities1,
        'entities_secondary':  entities2,
        'forensic_primary':    forensic1,
        'forensic_secondary':  forensic2,
        'metadata_flags':      all_flags,
        'behavioral_score':    beh_result.risk_score,
        'forensic_score':      combined_forgery,
        'behavioral':          beh_result,
        'breakdown':           risk.get('component_scores', {}),
        'conflicts':           conflicts,
        'income_fraud_score':  income_fraud_score,
        'llm_report':          report,
        'heatmap_b64':         forensic1.get('heatmap_b64', ''),
        'audit_id':            risk.get('audit_id', 'N/A'),
        'top_risk_factors':    risk.get('top_risk_factors', []),
        'benford_score':       0.0,
        'math_passed':         True,
    }


# ---------------------------------------------------------------------------
# Legacy compatibility shim — keeps old RiskEngine class working
# ---------------------------------------------------------------------------

class RiskEngine:
    """
    Legacy class preserved for backward compatibility with existing routers.
    New code should call analyze_document() / analyze_document_pair() directly.
    """

    def __init__(self):
        pass  # Singletons already loaded at module level

    async def calculate_risk(self, verification_results: list) -> float:
        """Convert legacy verification_results list to a risk score [0, 100]."""
        if not verification_results:
            return 0.0
        scores = []
        for res in verification_results:
            conf = res.get('confidence', 0.5)
            score = 1.0 - conf
            if res.get('status') == 'FAIL':
                score = max(score, 0.8)
            scores.append(score)
        avg = sum(scores) / len(scores)
        return round(avg * 100.0, 2)


risk_engine = RiskEngine()
