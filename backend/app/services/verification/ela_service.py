"""ELA / TruFor tampering detection service."""
import os
import sys
from typing import Any, Dict

# Project root → ml_engine is a top-level package
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml_engine.forensic_vision.trufor_wrapper import TruForDetector


class ELAService:
    def __init__(self) -> None:
        self.detector = TruForDetector()

    async def detect_tampering(self, file_path: str) -> Dict[str, Any]:
        """Run TruFor (or ELA fallback) to detect digital tampering."""
        result = self.detector.analyze(file_path)

        if result.get("error"):
            return {
                "status": "ERROR",
                "details": result["error"],
                "confidence": 0.0,
                "heatmap_b64": "",
            }

        tampered = result.get("is_tampered", False)
        return {
            "status": "FAIL" if tampered else "PASS",
            "details": f"{'Tampering detected' if tampered else 'No tampering'} via {result.get('method', 'Unknown')}",
            "confidence": result.get("integrity_score", 0.0),
            "heatmap_b64": result.get("heatmap_b64", ""),
        }


ela_service = ELAService()
