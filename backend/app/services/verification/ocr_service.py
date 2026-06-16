from typing import Dict, Any

class OCRService:
    @staticmethod
    async def extract_text(file_path: str) -> Dict[str, Any]:
        """
        Mock implementation for OCR extraction.
        In Phase 2, this will integrate with cloud OCR or local models like Tesseract.
        """
        return {
            "status": "PASS",
            "extracted_text": "Mock extracted text...",
            "confidence": 0.95
        }

ocr_service = OCRService()
