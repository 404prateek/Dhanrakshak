"""
ml_analyze.py
-------------
FastAPI router exposing the DhanRakshak ML pipeline via REST endpoints.

Routes
------
POST /api/ml/analyze          — Single-document fraud analysis.
POST /api/ml/analyze-pair     — Two-document cross-validation (ITR + Bank etc.).
GET  /api/ml/health           — Pipeline health / model status check.
"""

from __future__ import annotations

import os
import asyncio
import concurrent.futures
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.verification.risk_engine import (
    analyze_document,
    analyze_document_pair,
    _trufor,
    _reporter,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    case_id:        str              = Field(...,  description="Audit / case reference ID")
    file_paths:     List[str]        = Field(...,  description="List of document file paths on server")
    behavior_data:  Dict[str, Any]   = Field({},   description="Behavioral telemetry signals")
    rule_base_score: int             = Field(0,    description="Legacy rule-engine score [0-100]")


class AnalyzePairRequest(BaseModel):
    case_id:             str            = Field(...,  description="Audit / case reference ID")
    primary_path:        str            = Field(...,  description="Primary document path (e.g. ITR)")
    secondary_path:      str            = Field(...,  description="Secondary document path (e.g. Bank Statement)")
    primary_type:        str            = Field("ITR",            description="Label for primary doc")
    secondary_type:      str            = Field("Bank Statement", description="Label for secondary doc")
    behavior_data:       Dict[str, Any] = Field({},   description="Behavioral telemetry signals")
    rule_base_score:     int            = Field(0,    description="Legacy rule-engine score [0-100]")
    income_itr:          Optional[float] = Field(None, description="Annual ITR income (Rs)")
    income_bank_monthly: Optional[float] = Field(None, description="Avg monthly bank credit (Rs)")


# ---------------------------------------------------------------------------
# Path Resolution Helper
# ---------------------------------------------------------------------------

def resolve_path(p: str) -> Optional[str]:
    if os.path.isabs(p) and os.path.exists(p):
        return p
    if os.path.exists(p):
        return os.path.abspath(p)
    # try storage/uploads
    # __file__ is backend/app/api/routers/ml_analyze.py
    # project root is backend/
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    clean_p = p
    if clean_p.startswith("./") or clean_p.startswith(".\\"):
        clean_p = clean_p[2:]
        
    full = os.path.join(base_dir, clean_p)
    if os.path.exists(full):
        return full
        
    full_fallback = os.path.join(base_dir, "storage", "uploads", os.path.basename(p))
    if os.path.exists(full_fallback):
        return full_fallback
        
    return None

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/analyze", summary="Single-document ML analysis")
async def analyze(request: AnalyzeRequest) -> Dict[str, Any]:
    """
    Run full ML pipeline (TruFor + OCR + Behavioral + TrustEngine + LLM)
    on a single document and return a fraud risk assessment.
    """
    if not request.file_paths:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="file_paths must contain at least one path.",
        )

    resolved_path = resolve_path(request.file_paths[0])
    if not resolved_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {request.file_paths[0]}",
        )
    primary_path = resolved_path

    try:
        try:
            # Run analyze_document in a thread with a hard 45-second deadline.
            # asyncio.wait_for prevents blocking the FastAPI async event loop.
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    analyze_document,
                    primary_path,
                    request.behavior_data,
                    request.rule_base_score,
                ),
                timeout=300.0
            )
        except asyncio.TimeoutError:
            result = {
                "final_score_pct": 25,
                "risk_score":      25,
                "risk_level":      "LOW",
                "recommendation":  "MANUAL_REVIEW",
                "llm_report":      (
                    "DECISION: MANUAL_REVIEW\n"
                    "Analysis timed out. All document signals could not be "
                    "collected within the time limit. A manual branch review "
                    "is recommended before any lending decision.\n"
                    "RISK LEVEL: LOW"
                ),
                "partial":         True,
                "analysis_status": "timeout",
                "entities":        {},
                "conflicts":       [],
                "metadata_flags":  ["Analysis timed out after 5 minutes."],
                "heatmap_b64":     "",
                "breakdown":       {},
                "audit_id":        "N/A",
                "top_risk_factors": [],
            }

        result["case_id"] = request.case_id
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML pipeline error: {exc}",
        )


@router.post("/analyze-pair", summary="Cross-document ML analysis (ITR + Bank etc.)")
async def analyze_pair(request: AnalyzePairRequest) -> Dict[str, Any]:
    """
    Run full ML pipeline on two documents simultaneously, with cross-document
    field validation (name matching, PAN consistency, income discrepancy).
    """
    resolved_primary = resolve_path(request.primary_path)
    resolved_secondary = resolve_path(request.secondary_path)

    if not resolved_primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {request.primary_path}")
    if not resolved_secondary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {request.secondary_path}")

    try:
        result = analyze_document_pair(
            primary_path        = resolved_primary,
            secondary_path      = resolved_secondary,
            primary_type        = request.primary_type,
            secondary_type      = request.secondary_type,
            behavior_data       = request.behavior_data,
            rule_base_score     = request.rule_base_score,
            income_itr          = request.income_itr,
            income_bank_monthly = request.income_bank_monthly,
        )
        result["case_id"] = request.case_id
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML pipeline error: {exc}",
        )


@router.get("/health", summary="ML pipeline health check")
async def health() -> Dict[str, Any]:
    """
    Returns the status of each ML sub-system.
    Useful for deployment readiness checks.
    """
    return {
        "trufor_available":   _trufor.is_available,
        "trufor_method":      "TruFor" if _trufor.is_available else "ELA-fallback",
        "ollama_available":   _reporter._available,
        "ollama_model":       _reporter.model,
        "pipeline_status":    "ready",
    }
