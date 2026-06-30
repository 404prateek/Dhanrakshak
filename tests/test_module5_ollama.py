"""
MODULE 5 TEST — Ollama Reporter + Full Pipeline
================================================
Tests:
    - Ollama health check
    - Template fallback works (no Ollama needed to pass)
    - Report contains required sections
    - Full pipeline runs end-to-end without crashing

Run: python tests/test_module5_ollama.py
Run: python tests/test_pipeline.py   (for full pipeline)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_ollama_reporter():
    print("\n" + "="*55)
    print("TEST 5A: Ollama Reporter")
    print("="*55)

    from ml_engine.llm_reporter.ollama_reporter import OllamaReporter
    reporter = OllamaReporter()

    print(f"\n  Ollama available: {reporter._available}")
    if reporter._available:
        print("  ✅ Ollama is running — will use LLM")
    else:
        print("  ⚠️  Ollama not running — template fallback will be used")
        print("       To start Ollama: ollama serve")
        print("       To pull model:   ollama pull qwen2.5:3b")

    # Build a fake risk result to test report generation
    fake_risk = {
        "audit_id":         "test-uuid-1234",
        "applicant_name":   "Ramesh Kumar",
        "pan_number":       "ABCDE1234F",
        "doc_type":         "ITR",
        "final_score":      0.82,
        "final_score_pct":  82.0,
        "risk_level":       "HIGH",
        "recommendation":   "BLOCK",
        "breakdown": {
            "forensic_score": 0.85,
            "forensic_contrib": 0.30,
            "ocr_score": 0.60,
            "ocr_contrib": 0.15,
            "behavioral_score": 0.70,
            "behavioral_contrib": 0.14,
            "conflict_count": 2,
        },
        "top_risk_factors": [
            {"factor": "Document tampering detected", "detail": "ELA shows 85% tamper probability", "severity": "HIGH", "score": 0.85},
            {"factor": "Name mismatch",               "detail": "Ramesh Kumar vs R. Kumar",         "severity": "HIGH", "score": 0.80},
            {"factor": "Income inflation",             "detail": "60% deviation ITR vs bank",        "severity": "HIGH", "score": 0.75},
        ],
        "conflicts": [
            {"type": "name_mismatch",   "severity": "HIGH", "message": "Name: Ramesh Kumar vs R. Kumar"},
            {"type": "income_mismatch", "severity": "HIGH", "message": "ITR ₹8.4L vs bank-derived ₹3.36L — 60% gap"},
        ]
    }

    report = reporter.generate_report(fake_risk)
    print(f"\n  Generated report:\n{'-'*40}\n{report}\n{'-'*40}")

    assert len(report) > 50,         "Report must be substantive"
    assert "DECISION:" in report,    "Must contain DECISION"
    assert "BLOCK" in report,        "Must mention BLOCK for HIGH risk"
    print("  ✅ PASS: Report generated with correct structure")


def test_template_fallback():
    print("\n" + "="*55)
    print("TEST 5B: Template Fallback (works without Ollama)")
    print("="*55)

    from ml_engine.llm_reporter.ollama_reporter import OllamaReporter

    reporter = OllamaReporter()
    # Force template mode
    reporter._available = False

    fake_risk = {
        "audit_id": "test-123", "applicant_name": "Test User",
        "pan_number": "XXXXX1234X", "doc_type": "PAN",
        "final_score": 0.45, "final_score_pct": 45.0,
        "risk_level": "MEDIUM", "recommendation": "MANUAL_REVIEW",
        "breakdown": {}, "top_risk_factors": [], "conflicts": []
    }

    report = reporter.generate_report(fake_risk)
    print(f"\n  Template report:\n{report}")

    assert "MANUAL_REVIEW" in report, "Template must include recommendation"
    assert "DECISION:"     in report, "Template must have DECISION line"
    print("  ✅ PASS: Template fallback works without Ollama")


if __name__ == "__main__":
    print("DhanRakshak — Module 5: Ollama Reporter Tests")
    print("=" * 55)
    try:
        test_ollama_reporter()
        test_template_fallback()
        print("\n" + "="*55)
        print("✅ ALL MODULE 5 TESTS PASSED")
        print("="*55)
        print("\nNext step: Run tests/test_pipeline.py")
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback; traceback.print_exc()
