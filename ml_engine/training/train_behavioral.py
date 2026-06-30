#!/usr/bin/env python3
"""
train_behavioral.py
-------------------
Train and save the Isolation Forest model used by DhanRakshak's Behavioral
Twin sub-system.

This script generates synthetic behavioral feature data that approximates
real banking-session distributions, fits a BehavioralAnomalyDetector, runs a
quick evaluation, and saves the checkpoint to:

    ml_engine/training/checkpoints/isolation_forest.pkl

Run from the PROJECT ROOT (the directory containing ml_engine/):

    python ml_engine/training/train_behavioral.py

Or from anywhere using an explicit path:

    python /path/to/DHANRAKSHAK/ml_engine/training/train_behavioral.py

Feature vector (6 dimensions — matches BehaviorFeatureExtractor.FEATURE_NAMES):
    0  avg_typing_speed        characters/sec
    1  typing_rhythm_variance  inter-key interval variance (ms²)
    2  mouse_linearity         0=erratic … 1=straight line
    3  session_duration        seconds
    4  idle_ratio              fraction of session with no events
    5  transaction_speed       seconds from session start to first click
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path regardless of CWD
# ---------------------------------------------------------------------------
# This file lives at: <project_root>/ml_engine/training/train_behavioral.py
_SCRIPT_DIR = Path(__file__).resolve().parent          # …/training/
_ML_ENGINE_DIR = _SCRIPT_DIR.parent                    # …/ml_engine/
_PROJECT_ROOT = _ML_ENGINE_DIR.parent                  # …/DHANRAKSHAK/

for _p in (_PROJECT_ROOT, _ML_ENGINE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ---------------------------------------------------------------------------
# Imports (after sys.path is fixed)
# ---------------------------------------------------------------------------
from ml_engine.behavioral_twin.isolation_forest import BehavioralAnomalyDetector  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHECKPOINT_DIR = _SCRIPT_DIR / "checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "isolation_forest.pkl"

# Synthetic data parameters
N_NORMAL_SAMPLES = 2_000     # legitimate user sessions
N_ANOMALY_SAMPLES = 200      # fraudulent / duress sessions (held-out eval only)
RANDOM_SEED = 42

# IsolationForest training parameters
N_ESTIMATORS = 200
CONTAMINATION = 0.05          # ~5 % expected outliers in real traffic


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def _generate_normal_sessions(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate synthetic feature vectors for *normal* banking sessions.

    Distributions are designed to reflect plausible real-world ranges:
        - typing speed:     4–8 chars/sec  (comfortable, deliberate)
        - rhythm variance:  500–3000 ms²   (slightly irregular but steady)
        - mouse linearity:  0.6–1.0        (mostly smooth trajectories)
        - session duration: 30–180 sec     (short to moderate sessions)
        - idle ratio:       0.0–0.25       (occasional brief pauses)
        - transaction speed: 5–60 sec      (takes a few seconds to decide)
    """
    features = np.column_stack([
        rng.uniform(4.0,   8.0,    n),   # avg_typing_speed
        rng.uniform(500,   3000,   n),   # typing_rhythm_variance
        rng.uniform(0.6,   1.0,    n),   # mouse_linearity
        rng.uniform(30,    180,    n),   # session_duration
        rng.uniform(0.0,   0.25,   n),   # idle_ratio
        rng.uniform(5,     60,     n),   # transaction_speed
    ]).astype(np.float32)
    return features


def _generate_anomaly_sessions(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate synthetic feature vectors for *anomalous* sessions.

    Anomaly patterns modelled:
        - Very fast typing (script/bot):        15–30 chars/sec
        - High rhythm variance (duress/panic):  10000–50000 ms²
        - Erratic mouse (remote-takeover):      0.0–0.3
        - Very short sessions (scripted fraud): 1–10 sec
        - No idle time (bot):                   0.0–0.02
        - Instant transactions (pre-programmed):0–2 sec
    """
    bot_n = n // 2
    duress_n = n - bot_n

    # Bot-like sessions
    bot = np.column_stack([
        rng.uniform(15,    30,     bot_n),   # typing too fast
        rng.uniform(10,    100,    bot_n),   # suspiciously uniform rhythm
        rng.uniform(0.95,  1.0,    bot_n),   # perfectly straight mouse
        rng.uniform(1,     10,     bot_n),   # very short sessions
        rng.uniform(0.0,   0.02,   bot_n),   # zero idle
        rng.uniform(0,     2,      bot_n),   # instant transaction
    ]).astype(np.float32)

    # Duress / panic sessions
    duress = np.column_stack([
        rng.uniform(0.5,   2.0,    duress_n),  # hunting-and-pecking
        rng.uniform(10000, 50000,  duress_n),  # massive rhythm variance
        rng.uniform(0.0,   0.3,    duress_n),  # erratic mouse
        rng.uniform(300,   600,    duress_n),  # very long (confused/coerced)
        rng.uniform(0.5,   0.9,    duress_n),  # lots of idle time
        rng.uniform(120,   300,    duress_n),  # very slow to transact
    ]).astype(np.float32)

    return np.vstack([bot, duress])


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _evaluate(
    detector: BehavioralAnomalyDetector,
    normal: np.ndarray,
    anomaly: np.ndarray,
) -> None:
    """Print basic evaluation metrics (no external dependencies)."""
    normal_scores  = np.array([detector.predict(r) for r in normal])
    anomaly_scores = np.array([detector.predict(r) for r in anomaly])

    threshold = 0.5   # score > 0.5 → flagged as anomalous

    true_positives  = int((anomaly_scores  > threshold).sum())
    false_negatives = int((anomaly_scores  <= threshold).sum())
    true_negatives  = int((normal_scores   <= threshold).sum())
    false_positives = int((normal_scores   > threshold).sum())

    precision = true_positives / max(true_positives + false_positives, 1)
    recall    = true_positives / max(true_positives + false_negatives, 1)
    f1        = 2 * precision * recall / max(precision + recall, 1e-9)

    print(f"  Normal  sessions — mean score : {normal_scores.mean():.4f}")
    print(f"  Anomaly sessions — mean score : {anomaly_scores.mean():.4f}")
    print(f"  Threshold @ {threshold} -> Precision: {precision:.3f}  "
          f"Recall: {recall:.3f}  F1: {f1:.3f}")
    print(f"  TP={true_positives}  FP={false_positives}  "
          f"TN={true_negatives}  FN={false_negatives}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=" * 60)
    print("  DhanRakshak — Behavioral Isolation Forest Training")
    print("=" * 60)
    print()

    rng = np.random.default_rng(RANDOM_SEED)

    # ── 1. Generate data ───────────────────────────────────────────────
    print(f"[1/4] Generating synthetic data …")
    print(f"      Normal sessions  : {N_NORMAL_SAMPLES:,}")
    print(f"      Anomaly sessions : {N_ANOMALY_SAMPLES:,}  (eval only)")
    normal_data  = _generate_normal_sessions(N_NORMAL_SAMPLES,  rng)
    anomaly_data = _generate_anomaly_sessions(N_ANOMALY_SAMPLES, rng)
    print(f"      Feature shape    : {normal_data.shape}")
    print()

    # ── 2. Train ───────────────────────────────────────────────────────
    print(f"[2/4] Training IsolationForest  "
          f"(n_estimators={N_ESTIMATORS}, contamination={CONTAMINATION}) …")
    t0 = time.perf_counter()
    detector = BehavioralAnomalyDetector(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_SEED,
    )
    detector.train(normal_data)
    elapsed = time.perf_counter() - t0
    print(f"      Training complete in {elapsed:.2f}s")
    print()

    # ── 3. Evaluate ────────────────────────────────────────────────────
    print("[3/4] Quick evaluation …")
    eval_normal  = _generate_normal_sessions(200, rng)
    eval_anomaly = _generate_anomaly_sessions(100, rng)
    _evaluate(detector, eval_normal, eval_anomaly)
    print()

    # ── 4. Save ────────────────────────────────────────────────────────
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[4/4] Saving checkpoint to:")
    print(f"      {CHECKPOINT_PATH}")
    detector.save_model(str(CHECKPOINT_PATH))
    size_kb = CHECKPOINT_PATH.stat().st_size / 1024
    print(f"      Saved successfully ({size_kb:.1f} KB)")
    print()
    print("=" * 60)
    print("  Done! Run `python verify_setup.py` to confirm the checkpoint.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()