# Environment variables, DB URLs, API keys

from __future__ import annotations

import os
from typing import Union


def _float_env(key: str, default: float) -> float:
    """Read a float from an environment variable, falling back to *default*."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    value = float(raw)
    return value


# ---------------------------------------------------------------------------
# Trust-engine score fusion weights
# Override any of these via environment variables at deploy time.
# All three weights are normalised to sum to 1.0 inside AdaptiveTrustEngine,
# so relative magnitude is what matters — not the absolute values.
# ---------------------------------------------------------------------------
TRUST_WEIGHT_DOC_FORENSIC:   float = _float_env("TRUST_WEIGHT_DOC_FORENSIC",   0.45)
TRUST_WEIGHT_BEHAVIORAL:     float = _float_env("TRUST_WEIGHT_BEHAVIORAL",     0.35)
TRUST_WEIGHT_GRAPH_ANOMALY:  float = _float_env("TRUST_WEIGHT_GRAPH_ANOMALY",  0.20)

# ---------------------------------------------------------------------------
# Risk-level thresholds  (final_score is in [0, 1]; higher = riskier)
# ---------------------------------------------------------------------------
RISK_THRESHOLD_HIGH:   float = _float_env("RISK_THRESHOLD_HIGH",   0.65)
RISK_THRESHOLD_MEDIUM: float = _float_env("RISK_THRESHOLD_MEDIUM", 0.35)

# ---------------------------------------------------------------------------
# Database / service URLs  (populated from .env in production)
# ---------------------------------------------------------------------------
POSTGRES_URL: str = os.environ.get("POSTGRES_URL", "postgresql://user:pass@localhost:5432/dhanrakshak")
NEO4J_URI:    str = os.environ.get("NEO4J_URI",    "bolt://localhost:7687")
NEO4J_USER:   str = os.environ.get("NEO4J_USER",   "neo4j")
NEO4J_PASS:   str = os.environ.get("NEO4J_PASS",   "")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
JWT_SECRET_KEY:    str = os.environ.get("JWT_SECRET_KEY",    "")
JWT_ALGORITHM:     str = os.environ.get("JWT_ALGORITHM",     "HS256")
JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))