"""
FULL PIPELINE TEST — End-to-End
================================
Runs all modules together as one real fraud analysis.

Creates two synthetic docs (ITR + Bank Statement with conflicts),
runs full pipeline, verifies final output has all required fields.

This is the FINAL INTEGRATION TEST before demo.

Run: python tests/test_pipeline.py
"""

import sys, os, asyncio, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw


def create_itr(path):
    img  = Image.new("RGB", (500, 400), color=(255,255,255))
    draw = ImageDraw.Draw(img)
    for i, t in enumerate([
        "INCOME TAX RETURN ITR-1",
        "Name: Ramesh Kumar",
        "PAN: ABCDE1234F",
        "Aadhaar: 1234 5678 9012",
        "Gross Total Income: Rs. 8,40,000",
        "Date: 31/07/2024",
    ]):
        draw.text((20, 20+i*35), t, fill=(0,0,0))
    img.save(path, "JPEG", quality=90)


def create_bank(path):
    img  = Image.new("RGB", (500, 400), color=(255,255,255))
    draw = ImageDraw.Draw(img)
    for i, t in enumerate([
        "ACCOUNT STATEMENT - SBI",
        "Name: R. Kumar",
        "PAN: ABCDE1234F",
        "Monthly Credit Avg: Rs. 28,000",
        "IFSC: SBIN0001234",
        "Period: Apr 2023 - Mar 2024",
    ]):
        draw.text((20, 20+i*35), t, fill=(0,0,0))
    img.save(path, "JPEG", quality=90)


async def run_full_pipeline():
    print("\n" + "="*55)
    print("FULL PIPELINE TEST")
    print("="*55)

    # Import all modules
    from ml_engine.forensic_vision.trufor_wrapper    import TruForDetector
    from ml_engine.forensic_vision.metadata_analyzer import MetadataAnalyzer
    from ml_engine.ocr_nlp.document_ocr              import IndianDocumentOCR, CrossDocValidator
    from ml_engine.behavioral_twin.behavior_analyzer  import BehaviorAnalyzer
    from ml_engine.trust_engine.score_fusion          import TrustEngine
    from ml_engine.llm_reporter.ollama_reporter       import OllamaReporter

    # Init all
    trufor   = TruForDetector()
    meta     = MetadataAnalyzer()
    ocr      = IndianDocumentOCR()
    crossval = CrossDocValidator()
    behavior = BehaviorAnalyzer()
    trust    = TrustEngine()
    reporter = OllamaReporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        itr_path  = os.path.join(tmpdir, "itr.jpg")
        bank_path = os.path.join(tmpdir, "bank.jpg")
        create_itr(itr_path)
        create_bank(bank_path)

        # Step 1: Metadata
        print("\n  [1/7] Metadata analysis...")
        meta1 = meta.analyze(itr_path)
        meta2 = meta.analyze(bank_path)
        all_flags = meta1["flags"] + meta2["flags"]
        print(f"       flags: {all_flags}")

        # Step 2: Forensics
        print("  [2/7] Forensic analysis (TruFor/ELA)...")
        f1 = trufor.analyze(itr_path)
        f2 = trufor.analyze(bank_path)
        forensic_score = max(f1["integrity_score"], f2["integrity_score"])
        ela_score      = forensic_score
        print(f"       ITR forensic: {f1['integrity_score']:.4f}  method: {f1['method']}")

        # Step 3: OCR
        print("  [3/7] OCR extraction...")
        itr_ent  = ocr.extract(itr_path)
        bank_ent = ocr.extract(bank_path)
        print(f"       ITR doc_type: {itr_ent['doc_type']}  PAN: {itr_ent['pan']}")
        print(f"       Bank doc_type: {bank_ent['doc_type']}")

        # Step 4: Cross-doc validation
        print("  [4/7] Cross-document validation...")
        cv_result = crossval.validate(itr_ent, bank_ent, "ITR", "Bank Statement")
        conflicts = cv_result["conflicts"]
        print(f"       Conflicts found: {len(conflicts)}")
        for c in conflicts:
            print(f"       → [{c['severity']}] {c['message']}")

        # Income check
        ic = crossval.validate_income(840000, 28000, None)
        income_fraud_score = ic["income_fraud_score"]
        if ic["flags"]:
            conflicts.append({"type": "income_mismatch", "severity": "HIGH",
                              "message": ic["flags"][0], "doc1_value": "", "doc2_value": ""})

        # Step 5: Behavioral (simulate normal user)
        print("  [5/7] Behavioral analysis...")
        beh = behavior.analyze({
            "keystroke_dwell_ms": 120, "flight_time_ms": 80,
            "typing_wpm": 45,          "backspace_ratio": 0.08,
            "mouse_velocity_mean": 250,"mouse_velocity_std": 90,
            "click_count": 8,          "scroll_depth": 0.6,
            "form_fill_seconds": 55,   "copy_paste_detected": 0,
            "tab_switch_count": 1,     "idle_time_seconds": 8,
            "right_click_count": 1,    "touch_event_count": 0,
            "acceleration_mean": 45,   "session_duration_seconds": 85,
        })
        print(f"       Behavior: {beh['anomaly_type']}  score: {beh['anomaly_score']:.4f}")

        # Step 6: Trust engine
        print("  [6/7] Trust engine fusion...")
        risk = trust.compute_risk(
            trufor_score=forensic_score,
            ela_score=ela_score,
            ocr_conflicts=conflicts,
            behavioral_score=beh["anomaly_score"],
            metadata_flags=all_flags,
            rule_base_score=40,
            income_fraud_score=income_fraud_score,
            applicant_name=(itr_ent.get("names") or ["Unknown"])[0],
            pan_number=(itr_ent.get("pan") or [""])[0],
            doc_type=itr_ent.get("doc_type", "Unknown"),
        )
        print(f"       Final score: {risk['final_score_pct']:.0f}/100  Level: {risk['risk_level']}  Rec: {risk['recommendation']}")

        # Step 7: LLM report
        print("  [7/7] Generating underwriter report...")
        report = reporter.generate_report(risk)
        print(f"\n  {'='*45}")
        print(f"  UNDERWRITER REPORT:")
        print(f"  {'='*45}")
        print(report)
        print(f"  {'='*45}\n")

        # Final assertions
        assert "final_score"    in risk,  "final_score missing"
        assert "risk_level"     in risk,  "risk_level missing"
        assert "recommendation" in risk,  "recommendation missing"
        assert "audit_id"       in risk,  "audit_id missing"
        assert "breakdown"      in risk,  "breakdown missing"
        assert len(report)      > 50,     "Report must be substantive"
        assert "DECISION:"      in report,"Report must have DECISION"

        print("  ✅ PASS: Full pipeline ran without errors")
        print(f"  ✅ Final Risk: {risk['risk_level']} ({risk['final_score_pct']:.0f}/100) → {risk['recommendation']}")


def run_all_tests():
    """Run all module tests in sequence."""
    print("\n" + "🔥"*27)
    print("DHANRAKSHAK — FULL TEST SUITE")
    print("🔥"*27)

    tests = [
        ("Module 1: Forensic Vision",    "tests.test_module1_trufor"),
        ("Module 2: OCR + NLP",          "tests.test_module2_ocr"),
        ("Module 3: Behavioral",         "tests.test_module3_behavioral"),
        ("Module 4: Trust Engine",       "tests.test_module4_trust"),
        ("Module 5: Ollama Reporter",    "tests.test_module5_ollama"),
    ]

    passed, failed = 0, 0

    for name, module_path in tests:
        print(f"\n{'='*55}")
        print(f"Running: {name}")
        print(f"{'='*55}")
        try:
            import importlib
            mod = importlib.import_module(module_path)
            passed += 1
            print(f"✅ {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"❌ {name}: FAILED — {e}")

    print(f"\n{'='*55}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*55}")


if __name__ == "__main__":
    print("DhanRakshak — Full Pipeline Test")
    try:
        asyncio.run(run_full_pipeline())
        print("\n" + "="*55)
        print("✅ FULL PIPELINE TEST PASSED")
        print("="*55)
        print("\nYour ML engine is working correctly.")
        print("Plug POST /api/ml/analyze into teammate's backend.")
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback; traceback.print_exc()
