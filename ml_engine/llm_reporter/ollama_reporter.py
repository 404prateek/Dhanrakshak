"""
ollama_reporter.py
------------------
Generates natural-language fraud investigation reports by querying a locally
running Ollama LLM server (default: http://localhost:11434).

The reporter accepts a structured FraudAnalysisContext (or plain dict) and
produces a concise, actionable narrative suitable for:
    - Bank fraud officers
    - Automated audit trail logs
    - Customer-facing explanations (summarised, PII-scrubbed variant)

Supported models: any model pulled into the local Ollama instance.
Default: "llama3.2" (fast and well-rounded for structured reasoning tasks).
"""

from __future__ import annotations

import json
import logging
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:1b"
DEFAULT_TIMEOUT_SECONDS = 120  # increased to allow local models enough time to generate

# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class FraudReport:
    """Output produced by OllamaReporter for a single fraud analysis context."""

    narrative: str = ""
    model: str = DEFAULT_MODEL
    prompt_tokens: int = 0
    response_tokens: int = 0
    risk_level: str = "UNKNOWN"          # LOW / MEDIUM / HIGH / CRITICAL
    recommended_action: str = ""
    error: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "narrative": self.narrative,
            "model": self.model,
            "risk_level": self.risk_level,
            "recommended_action": self.recommended_action,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are DhanRakshak's AI fraud investigation assistant.
    You analyse banking fraud signals and produce clear, structured reports.

    STRICT GROUNDING RULES — NEVER VIOLATE THESE:
    1. The ML system's risk scores and risk level are GROUND TRUTH. Never contradict them.
    2. If Risk Level is HIGH: DO NOT say the document is genuine or appears authentic.
    3. If Risk Level is LOW: DO NOT say the document is suspicious without evidence.
    4. TruFor integrity score interpretation:
       - 0.00 to 0.30 = CRITICAL tampering detected (document almost certainly forged)
       - 0.30 to 0.50 = HIGH suspicion of tampering
       - 0.50 to 0.70 = MEDIUM suspicion — further review needed
       - 0.70 to 0.85 = MILD concern — minor anomalies
       - 0.85 to 1.00 = LOW risk — document appears authentic
    5. Do NOT fabricate transaction amounts, names, or account numbers not provided.
    6. Do NOT soften HIGH risk findings — report them clearly and directly.
    7. Be concise — write exactly 80-100 words maximum. Output plain text only (no markdown headers).
    8. Always state DECISION: <action> and RISK LEVEL: <level> at the end.
    CRITICAL RULES — NEVER VIOLATE:
    - Never mention both integrity score and forgery probability in the same sentence
    - If integrity_score > 0.8: say "document appears authentic" — do NOT mention tampering
    - If integrity_score < 0.3: say "high tampering risk detected" — do NOT say appears authentic
    - Never contradict yourself in the same paragraph
""")


def _build_user_prompt(context: Dict[str, Any]) -> str:
    """
    Build a document-specific, actionable LLM prompt from the analysis context.
    Extracts entity details (names, PAN, amounts) and includes them so the
    report is specific to the document rather than generic.
    """
    # --- Extract entity details from the analysis result ---
    entities = context.get("entities", {})
    if isinstance(entities, list) and len(entities) > 0:
        entities = entities[0]
    if not isinstance(entities, dict):
        entities = {}

    names    = entities.get("names", []) or []
    pan      = entities.get("pan", []) or []
    amounts  = entities.get("amounts", []) or []
    dates    = entities.get("dates", []) or []
    doc_type = context.get("doc_type") or entities.get("doc_type", "Unknown Document")

    # --- Risk summary ---
    score   = context.get("final_score_pct") or round((context.get("final_score") or 0) * 100, 1)
    level   = context.get("risk_level", "LOW")
    rec     = context.get("recommendation", "APPROVE")
    audit_id = context.get("audit_id", "N/A")
    factors = context.get("top_risk_factors", []) or []
    conflicts = context.get("conflicts", []) or []
    flags   = context.get("metadata_flags", []) or []
    math_passed = context.get("math_passed", True)

    # --- Format entity section ---
    entities_text = (
        f"Extracted from document:\n"
        f"  Names found   : {', '.join(str(n) for n in names[:3]) if names else 'None detected'}\n"
        f"  PAN numbers   : {', '.join(str(p) for p in pan[:2]) if pan else 'None detected'}\n"
        f"  Amounts found : {', '.join(str(a) for a in amounts[:4]) if amounts else 'None detected'}\n"
        f"  Dates found   : {', '.join(str(d) for d in dates[:3]) if dates else 'None detected'}\n"
        f"  Document type : {doc_type}"
    )

    # --- Format signals section ---
    factors_text = "\n".join(
        f"  - {f.get('factor', '')}: {f.get('detail', '')} [{f.get('severity', '')}]"
        for f in factors[:3]
    ) if factors else "  - No major risk factors detected"

    conflicts_text = "\n".join(
        f"  - [{c.get('severity', '?')}] {c.get('message', '')}"
        for c in conflicts[:4]
    ) if conflicts else "  - No conflicts detected"

    # Filter out math mismatch flags for legal docs — expected behaviour
    legal_doc_types = ("gpa", "sale", "agreement", "will", "poa", "deed",
                       "property", "legal", "conveyance", "gift")
    is_legal_doc = any(kw in str(doc_type).lower() for kw in legal_doc_types)
    effective_flags = [
        f for f in flags
        if not (is_legal_doc and "math" in f.lower())
    ]
    flags_text = "\n".join(
        f"  - {f}" for f in effective_flags[:3]
    ) if effective_flags else "  - No metadata flags"

    math_note = ""
    if not math_passed and is_legal_doc:
        math_note = ("\n\nNOTE: Math reconciliation check flagged amounts in this document. "
                     "This is EXPECTED for legal/property documents where stamp duty, "
                     "consideration price, and instalment amounts are not meant to sum. "
                     "Do NOT treat this as evidence of fraud.")

    # --- Clear, unambiguous forensic assessment (ONE interpretation only) ---
    # Read integrity_score directly — values closer to 1.0 = more authentic
    breakdown = context.get("breakdown", {}) or {}
    integrity = context.get("trufor_score")
    if integrity is None:
        # trufor_score in context IS the integrity score (passed from risk_engine)
        # forensic_score is the forgery probability (1 - integrity)
        forensic_prob = context.get("forensic_score", 0.0) or 0.0
        integrity = 1.0 - forensic_prob

    integrity = float(integrity)
    forgery_pct = round((1.0 - integrity) * 100)

    if integrity > 0.80:
        forensic_text = f"Document appears AUTHENTIC (integrity: {integrity:.3f} — {100 - forgery_pct}% authentic)"
    elif integrity > 0.60:
        forensic_text = f"Document has MINOR anomalies (integrity: {integrity:.3f} — review recommended)"
    elif integrity > 0.40:
        forensic_text = f"Document has MODERATE concerns — possible manipulation (integrity: {integrity:.3f})"
    else:
        forensic_text = f"Document shows HIGH TAMPERING RISK — likely forged (integrity: {integrity:.3f}, only {100 - forgery_pct}% authentic)"

    return f"""You are a senior fraud analyst at Canara Bank India.
A {doc_type} has been analyzed by DhanRakshak AI system.

=== MACHINE LEARNING ANALYSIS RESULTS (DO NOT CONTRADICT) ===
Audit ID       : {audit_id}
Risk Score     : {score:.0f} / 100  (higher = more fraud risk)
Risk Level     : {level}  ← THIS IS THE AUTHORITATIVE FINDING
Recommendation : {rec}
FORENSIC ASSESSMENT: {forensic_text}

{entities_text}

FRAUD SIGNALS DETECTED:
{factors_text}

DOCUMENT CONFLICTS:
{conflicts_text}

METADATA FLAGS:
{flags_text}{math_note}

=== REPORT INSTRUCTIONS ===
Write a professional underwriter report in exactly 80-100 words.

MANDATORY RULES (violation = incorrect report):
1. Start with: DECISION: {rec}
2. The Risk Level is {level} — your report MUST reflect this accurately.
3. State the FORENSIC ASSESSMENT exactly as given above — do NOT rephrase or use different numbers.
4. Only mention names, PAN, or amounts if they appear in the entity data above.
5. If names/PAN were detected: mention them specifically.
6. If no names/PAN found: state "No applicant identity confirmed in document".
7. If this is a GPA/Sale Agreement/Will/PoA/property document and math mismatch
   was flagged: note this is expected behaviour for legal docs, not evidence of fraud.
8. End with Branch Manager Instructions: a clear, specific action step.

RISK LEVEL: {level}
Write as if briefing a branch manager who must make a final lending decision."""


# ---------------------------------------------------------------------------
# Risk level extractor
# ---------------------------------------------------------------------------

_RISK_KEYWORDS = {
    "CRITICAL": ["critical", "very high risk", "immediate block"],
    "HIGH": ["high risk", "high", "suspicious", "likely fraud"],
    "MEDIUM": ["medium", "moderate", "further review"],
    "LOW": ["low risk", "low", "legitimate", "no fraud"],
}


def _extract_risk_level(narrative: str) -> str:
    lower = narrative.lower()
    for level, keywords in _RISK_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return level
    return "UNKNOWN"


def _extract_recommended_action(narrative: str) -> str:
    """Pull the sentence containing the recommended action from the narrative."""
    for line in narrative.splitlines():
        lower = line.lower()
        if "recommend" in lower or "action" in lower or "block" in lower or "approve" in lower:
            return line.strip()
    return "Review manually."


# ---------------------------------------------------------------------------
# OllamaReporter
# ---------------------------------------------------------------------------


class OllamaReporter:
    """
    Queries a local Ollama server to generate fraud investigation narratives.

    Parameters
    ----------
    base_url:
        Ollama server base URL.  Default ``http://localhost:11434``.
    model:
        Ollama model name to use.  Must be pulled beforehand with
        ``ollama pull <model>``.
    timeout:
        HTTP request timeout in seconds.
    temperature:
        Sampling temperature (0 = deterministic, 1 = creative).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        temperature: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        # Eagerly check availability once at construction time so callers can
        # read r._available without an extra method call.
        self._available: bool = True # Obsolete, we check dynamically now

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _post_json(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON POST request and return the parsed response."""
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def is_available(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            url = f"{self.base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=5):
                return True
        except Exception:  # pylint: disable=broad-except
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(self, context: Dict[str, Any]) -> str:
        """
        Generate a fraud investigation report for the given analysis context.

        Always returns a plain **string** containing the report narrative.
        When Ollama is available the narrative is LLM-generated; when it is
        unavailable a deterministic template report is returned so callers
        never receive an error object.

        The returned string always contains:
            DECISION: <action>
            RISK LEVEL: <level>

        Parameters
        ----------
        context:
            Dict of fraud signals (new pipeline schema or legacy schema).
            New keys: final_score, risk_level, recommendation,
                      top_risk_factors, conflicts, breakdown.
            Legacy keys: trust_score, behavioral_risk, forensic_risk, etc.

        Returns
        -------
        str — report narrative.
        """
        if not self.is_available():
            return self._template_report(context)

        user_prompt = _build_user_prompt(context)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,      # low = more deterministic = faster
                "num_predict": 150,      # hard cap on output tokens (was 300+)
                "top_p": 0.9,
            },
        }

        try:
            response = self._post_json("/api/chat", payload)
            narrative = response["message"]["content"].strip()
            # Ensure mandatory lines are always present even if the LLM
            # forgot to include them.
            narrative = self._ensure_decision_line(narrative, context)
            return narrative
        except urllib.error.URLError as exc:
            logger.error("OllamaReporter: HTTP error: %s", exc)
            return self._template_report(context)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("OllamaReporter: unexpected error: %s", exc)
            return self._template_report(context)

    # ------------------------------------------------------------------
    # Fallback template report (used when Ollama is unavailable)
    # ------------------------------------------------------------------

    @staticmethod
    def _template_report(context: Dict[str, Any]) -> str:
        """Build a deterministic report from context when Ollama is offline."""
        risk_level     = context.get("risk_level", "UNKNOWN")
        recommendation = context.get("recommendation", "MANUAL_REVIEW")
        final_score    = context.get("final_score") or context.get("trust_score", 0.0)
        applicant      = context.get("applicant_name", "Unknown Applicant")
        doc_type       = context.get("doc_type", "Document")
        audit_id       = context.get("audit_id", "N/A")
        math_passed    = context.get("math_passed", True)

        factors = context.get("top_risk_factors", []) or []
        factor_lines = ""
        for rf in factors[:3]:
            factor_lines += (
                f"  - [{rf.get('severity','')}] {rf.get('factor','')}: "
                f"{rf.get('detail','')}\n"
            )

        conflicts = context.get("conflicts", []) or []
        conflict_lines = ""
        for c in conflicts[:3]:
            conflict_lines += (
                f"  - [{c.get('severity','')}] {c.get('type','')}: "
                f"{c.get('message','')}\n"
            )

        # Extract entity details for a more specific report
        entities = context.get("entities", {})
        if isinstance(entities, list) and len(entities) > 0:
            entities = entities[0]
        if not isinstance(entities, dict):
            entities = {}
        names   = entities.get("names", []) or []
        pan     = entities.get("pan", []) or []
        amounts = entities.get("amounts", []) or []

        # Detect legal documents
        legal_doc_types = ("gpa", "sale", "agreement", "will", "poa", "deed",
                           "property", "legal", "conveyance", "gift")
        is_legal_doc = any(kw in str(doc_type).lower() for kw in legal_doc_types)

        report = (
            f"### DhanRakshak Investigation Report\n"
            f"**Audit ID:** `{audit_id}` | **Applicant:** {applicant} | **Document:** {doc_type}\n\n"
            f"#### Risk Assessment\n"
            f"- **Risk Score:** `{final_score:.2f} / 1.00`\n"
            f"- **RISK LEVEL:** `{risk_level}`\n"
            f"- **DECISION:** `{recommendation}`\n\n"
        )

        # Entity summary
        if names or pan or amounts:
            report += "#### Extracted Information\n"
            if names:
                report += f"- **Parties identified:** {', '.join(str(n) for n in names[:3])}\n"
            if pan:
                report += f"- **PAN numbers:** {', '.join(str(p) for p in pan[:2])}\n"
            if amounts:
                report += f"- **Amounts referenced:** {', '.join(str(a) for a in amounts[:4])}\n"
            report += "\n"

        if factor_lines:
            # Emphasize severity tags without emojis
            factor_lines = factor_lines.replace("  - [HIGH]", "- **[HIGH]**")
            factor_lines = factor_lines.replace("  - [MEDIUM]", "- **[MEDIUM]**")
            factor_lines = factor_lines.replace("  - [LOW]", "- **[LOW]**")
            report += f"#### Key Risk Factors\n{factor_lines}\n"
            
        if conflict_lines:
            conflict_lines = conflict_lines.replace("  - [HIGH]", "- **[HIGH]**")
            conflict_lines = conflict_lines.replace("  - [MEDIUM]", "- **[MEDIUM]**")
            conflict_lines = conflict_lines.replace("  - [LOW]", "- **[LOW]**")
            report += f"#### Document Conflicts\n{conflict_lines}\n"

        # Legal doc math note
        if is_legal_doc and not math_passed:
            report += (
                "> **Note:** Math reconciliation flagged amounts in this legal document. "
                "This is expected behaviour for GPA/Sale Agreement/Will/PoA documents "
                "where stamp duty, consideration price, and instalment amounts are "
                "not intended to sum to each other. This is NOT evidence of fraud.\n\n"
            )

        verdict_map = {
            "HIGH":   "**Final Verdict:** Application presents strong indicators of fraud. Immediate escalation to risk team required.",
            "MEDIUM": "**Final Verdict:** Application shows anomalies requiring manual verification before proceeding.",
            "LOW":    "**Final Verdict:** Application appears consistent. Proceed with standard due-diligence checks.",
        }
        report += verdict_map.get(risk_level, "**Final Verdict:** Risk level undetermined. Manual review recommended.") + "\n"
        report += "\n*(Generated by DhanRakshak offline template engine)*\n"
        return report

    @staticmethod
    def _ensure_decision_line(narrative: str, context: Dict[str, Any]) -> str:
        """
        Append DECISION: and RISK LEVEL: lines if the LLM omitted them.
        """
        lower = narrative.lower()
        if "decision:" not in lower:
            rec = context.get("recommendation", "MANUAL_REVIEW")
            narrative += f"\n\nDECISION: {rec}"
        if "risk level:" not in lower and "risk_level:" not in lower:
            rl = context.get("risk_level", _extract_risk_level(narrative))
            narrative += f"\nRISK LEVEL: {rl}"
        return narrative

    def generate_summary(self, reports: list[FraudReport]) -> str:
        """
        Generate an executive-level summary from multiple FraudReports.

        Parameters
        ----------
        reports:
            List of FraudReport objects (e.g. from a batch analysis run).
        """
        if not reports:
            return "No reports to summarise."

        combined = "\n\n---\n\n".join(
            f"Report {i+1} (Risk: {r.risk_level}):\n{r.narrative}"
            for i, r in enumerate(reports)
            if r.narrative
        )

        summary_context = {
            "transaction": {"type": "batch", "amount": "N/A", "target_account": "multiple"},
            "anomaly_detected": any(r.risk_level in ("HIGH", "CRITICAL") for r in reports),
        }

        prompt = (
            f"Summarise the following {len(reports)} individual fraud reports "
            f"into a single executive summary:\n\n{combined}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
        }

        try:
            response = self._post_json("/api/chat", payload)
            return response["message"]["content"].strip()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("OllamaReporter.generate_summary: %s", exc)
            return f"Summary generation failed: {exc}"
