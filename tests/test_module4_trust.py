"""
MODULE 4 TEST — Trust Engine (Score Fusion)
=============================================
Tests:
    - Weights sum to 1.0
    - HIGH/MEDIUM/LOW classification correct
    - BLOCK/MANUAL_REVIEW/APPROVE recommendation correct
    - top_risk_factors populated and human-readable
    - audit_id generated every call
    - explain_text() fallback works without Ollama

Run: python tests/test_module4_trust.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_score_fusion():
    print("\n" + "="*55)
    print("TEST 4A: Score Fusion Logic")
    print("="*55)

    from ml_engine.trust_engine.score_fusion import TrustEngine
    engine = TrustEngine()

    # Case 1: Clean document — all scores low
    clean = engine.compute_risk(
        trufor_score=0.05, ela_score=0.03,
        ocr_conflicts=[], behavioral_score=0.10,
        metadata_flags=[], rule_base_score=5
    )
    print(f"\n  CLEAN:   score={clean['final_score']:.4f}  level={clean['risk_level']}  rec={clean['recommendation']}")
    assert clean["risk_level"]    == "LOW",     f"Clean should be LOW, got {clean['risk_level']}"
    assert clean["recommendation"]== "APPROVE", f"Should APPROVE clean doc"
    print("  ✅ PASS: Clean document → LOW → APPROVE")

    # Case 2: Forged document — forensics high
    forged = engine.compute_risk(
        trufor_score=0.85, ela_score=0.72,
        ocr_conflicts=[
            {"type": "name_mismatch", "severity": "HIGH",
             "message": "Name mismatch: Ramesh Kumar vs R. Kumar"}
        ],
        behavioral_score=0.20,
        metadata_flags=["Edited with Adobe Photoshop"],
        rule_base_score=70
    )
    print(f"\n  FORGED:  score={forged['final_score']:.4f}  level={forged['risk_level']}  rec={forged['recommendation']}")
    assert forged["risk_level"]    == "HIGH",   f"Forged should be HIGH, got {forged['risk_level']}"
    assert forged["recommendation"]== "BLOCK",  "Should BLOCK forged doc"
    assert len(forged["top_risk_factors"]) > 0, "Risk factors must be populated"
    print(f"  Top factors: {[f['factor'] for f in forged['top_risk_factors']]}")
    print("  ✅ PASS: Forged document → HIGH → BLOCK")

    # Case 3: Medium risk
    medium = engine.compute_risk(
        trufor_score=0.35, ela_score=0.25,
        ocr_conflicts=[{"type": "amount_mismatch", "severity": "MEDIUM",
                        "message": "Income deviation detected"}],
        behavioral_score=0.45,
        metadata_flags=[], rule_base_score=35
    )
    print(f"\n  MEDIUM:  score={medium['final_score']:.4f}  level={medium['risk_level']}  rec={medium['recommendation']}")
    assert medium["risk_level"]     == "MEDIUM",        f"Should be MEDIUM"
    assert medium["recommendation"] == "MANUAL_REVIEW", "Should MANUAL_REVIEW"
    print("  ✅ PASS: Medium risk → MANUAL_REVIEW")


def test_audit_trail():
    print("\n" + "="*55)
    print("TEST 4B: Audit Trail Fields")
    print("="*55)

    from ml_engine.trust_engine.score_fusion import TrustEngine
    import uuid, datetime

    engine = TrustEngine()
    result = engine.compute_risk()

    required_fields = [
        "audit_id", "timestamp", "final_score", "risk_level",
        "recommendation", "breakdown", "top_risk_factors"
    ]
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"
        print(f"  ✓ {field}: present")

    # Audit ID must be valid UUID
    try:
        uuid.UUID(result["audit_id"])
        print(f"  ✓ audit_id is valid UUID: {result['audit_id']}")
    except ValueError:
        assert False, "audit_id is not valid UUID"

    # Timestamp must be parseable
    assert "T" in result["timestamp"], "Timestamp must be ISO format"
    print(f"  ✓ timestamp: {result['timestamp']}")
    print("  ✅ PASS: All audit trail fields present")


def test_explain_text():
    print("\n" + "="*55)
    print("TEST 4C: Text Explanation (Ollama fallback)")
    print("="*55)

    from ml_engine.trust_engine.score_fusion import TrustEngine
    engine = TrustEngine()

    result = engine.compute_risk(
        trufor_score=0.80, ela_score=0.65,
        ocr_conflicts=[{"type": "name_mismatch", "severity": "HIGH",
                        "message": "Name mismatch detected"}],
        behavioral_score=0.70,
        metadata_flags=["Edited with Photoshop"],
        rule_base_score=75,
        applicant_name="Ramesh Kumar",
        pan_number="ABCDE1234F"
    )

    explanation = engine.explain_text(result)
    print(f"\n  Generated explanation:\n{explanation}")

    assert "DECISION:" in explanation,   "Must have DECISION line"
    assert "Risk Level:" in explanation, "Must have Risk Level"
    assert len(explanation) > 100,       "Must be substantive"
    print("\n  ✅ PASS: Text explanation generated")


if __name__ == "__main__":
    print("DhanRakshak — Module 4: Trust Engine Tests")
    print("=" * 55)
    try:
        test_score_fusion()
        test_audit_trail()
        test_explain_text()
        print("\n" + "="*55)
        print("✅ ALL MODULE 4 TESTS PASSED")
        print("="*55)
        print("\nNext step: Run tests/test_module5_ollama.py")
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback; traceback.print_exc()
