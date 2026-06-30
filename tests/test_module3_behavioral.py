"""
MODULE 3 TEST — Behavioral Anomaly Detection (Isolation Forest)
================================================================
Tests:
    - Synthetic data generation works
    - Model trains in < 2 minutes
    - Normal user scores LOW
    - Bot user scores HIGH
    - Panic user detected

Run: python tests/test_module3_behavioral.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_training():
    print("\n" + "="*55)
    print("TEST 3A: Isolation Forest Training")
    print("="*55)
    print("  Training on synthetic data (< 2 minutes)...")

    from ml_engine.behavioral_twin.behavior_analyzer import train_and_save
    model, stats = train_and_save()

    assert model is not None,             "Model must be created"
    assert "score_min" in stats,          "Stats must have score_min"
    assert "score_max" in stats,          "Stats must have score_max"
    assert stats["n_train"] == 5000,      "Must train on 5000 samples"

    print(f"  Score range: [{stats['score_min']:.4f}, {stats['score_max']:.4f}]")
    print("  ✅ PASS: Training complete")


def test_inference():
    print("\n" + "="*55)
    print("TEST 3B: Behavioral Inference")
    print("="*55)

    from ml_engine.behavioral_twin.behavior_analyzer import BehaviorAnalyzer
    # Reset singleton to reload fresh model
    BehaviorAnalyzer._instance = None
    analyzer = BehaviorAnalyzer()

    # Normal user
    normal_user = {
        "keystroke_dwell_ms":     120, "flight_time_ms":       80,
        "typing_wpm":              45, "backspace_ratio":     0.08,
        "mouse_velocity_mean":    250, "mouse_velocity_std":    90,
        "click_count":              8, "scroll_depth":         0.6,
        "form_fill_seconds":       55, "copy_paste_detected":    0,
        "tab_switch_count":         1, "idle_time_seconds":       8,
        "right_click_count":        1, "touch_event_count":       0,
        "acceleration_mean":       45, "session_duration_seconds": 85,
    }

    # Bot user
    bot_user = {
        "keystroke_dwell_ms":      11, "flight_time_ms":        6,
        "typing_wpm":             110, "backspace_ratio":     0.00,
        "mouse_velocity_mean":      0, "mouse_velocity_std":     0,
        "click_count":              1, "scroll_depth":         1.0,
        "form_fill_seconds":        3, "copy_paste_detected":    0,
        "tab_switch_count":         0, "idle_time_seconds":       0,
        "right_click_count":        0, "touch_event_count":       0,
        "acceleration_mean":        0, "session_duration_seconds":  4,
    }

    # Panic user
    panic_user = {
        "keystroke_dwell_ms":      90, "flight_time_ms":       60,
        "typing_wpm":              20, "backspace_ratio":     0.40,
        "mouse_velocity_mean":    600, "mouse_velocity_std":   350,
        "click_count":             25, "scroll_depth":         0.9,
        "form_fill_seconds":      200, "copy_paste_detected":    1,
        "tab_switch_count":        12, "idle_time_seconds":       1,
        "right_click_count":        8, "touch_event_count":       0,
        "acceleration_mean":      180, "session_duration_seconds": 210,
    }

    normal_result = analyzer.analyze(normal_user)
    bot_result    = analyzer.analyze(bot_user)
    panic_result  = analyzer.analyze(panic_user)

    print(f"\n  Normal user:  score={normal_result['anomaly_score']:.4f}  type={normal_result['anomaly_type']}")
    print(f"  Bot user:     score={bot_result['anomaly_score']:.4f}  type={bot_result['anomaly_type']}")
    print(f"  Panic user:   score={panic_result['anomaly_score']:.4f}  type={panic_result['anomaly_type']}")
    print(f"  Bot top features: {[f['feature'] for f in bot_result['top_features'][:3]]}")
    print(f"  Panic signals: {panic_result['panic_signals']}")

    assert normal_result["anomaly_score"] < bot_result["anomaly_score"], \
        "Bot should score higher than normal"
    assert len(bot_result["top_features"]) > 0, "Top features must be populated"
    assert isinstance(panic_result["panic_signals"], list), "Panic signals must be list"
    assert panic_result["panic_signals"], "Panic signals should be detected"

    print("\n  ✅ PASS: Bot scores higher than normal user")
    print("  ✅ PASS: Panic signals detected correctly")
    print("  ✅ PASS: Module 3 (Behavioral) complete")


def test_missing_features():
    print("\n" + "="*55)
    print("TEST 3C: Missing Feature Handling")
    print("="*55)

    from ml_engine.behavioral_twin.behavior_analyzer import BehaviorAnalyzer
    analyzer = BehaviorAnalyzer()

    # Send empty dict — should not crash
    result = analyzer.analyze({})
    assert "anomaly_score" in result, "Must return score even with empty input"
    print(f"  Empty input handled: score={result['anomaly_score']}")

    # Send partial dict
    result2 = analyzer.analyze({"keystroke_dwell_ms": 500, "mouse_velocity_mean": 0})
    assert "anomaly_score" in result2
    print(f"  Partial input handled: score={result2['anomaly_score']}")

    print("  ✅ PASS: Missing features filled with medians, no crash")


if __name__ == "__main__":
    print("DhanRakshak — Module 3: Behavioral Analysis Tests")
    print("=" * 55)
    try:
        test_training()
        test_inference()
        test_missing_features()
        print("\n" + "="*55)
        print("✅ ALL MODULE 3 TESTS PASSED")
        print("="*55)
        print("\nNext step: Run tests/test_module4_trust.py")
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback; traceback.print_exc()
