"""OCR extraction service — wraps ml_engine DocumentOCR."""
import os
import sys
from typing import Any, Dict

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml_engine.ocr_nlp.document_ocr import DocumentOCR


class OCRService:
    def __init__(self) -> None:
        self.ocr = DocumentOCR()

    async def extract_text(self, file_path: str) -> Dict[str, Any]:
        """Extract text and named entities from a document image or PDF."""
        result = self.ocr.extract(file_path).to_dict()
        return {
            "status": "PASS" if result["confidence"] > 0.7 else "WARNING",
            "extracted_text": result["raw_text"],
            "confidence": result["confidence"],
            "entities": result["entities"],
        }


ocr_service = OCRService()
