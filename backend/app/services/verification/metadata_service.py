"""Metadata analysis service — wraps ml_engine MetadataAnalyzer."""
import os
import sys
from typing import Any, Dict

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml_engine.forensic_vision.metadata_analyzer import MetadataAnalyzer


class MetadataService:
    def __init__(self) -> None:
        self.analyzer = MetadataAnalyzer()

    async def analyze_metadata(self, file_path: str) -> Dict[str, Any]:
        """Analyze PDF/image metadata for suspicious creation or editing tools."""
        result = self.analyzer.analyze_file(file_path).to_dict()
        score = result["risk_score"]

        if score >= 0.5:
            status = "FAIL"
        elif score > 0:
            status = "WARNING"
        else:
            status = "PASS"

        return {
            "status": status,
            "details": ", ".join(result["suspicious_flags"]) or "Clean metadata",
            "metadata": {"risk_score": score, "software": result["software_tags"]},
        }


metadata_service = MetadataService()
