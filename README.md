# DhanRakshak — AI-Powered Fraud Detection Platform

DhanRakshak is a real-time document forgery and behavioral anomaly detection system designed for financial institutions and insurance underwriters. It combines forensic vision (TruFor), OCR-based document extraction, mathematical reconciliation, behavioral biometrics, and local LLM-based intelligent reporting into a unified trust score.

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)            │
│  CaseManagement · ML Investigation · FraudReports       │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API
┌───────────────────────▼─────────────────────────────────┐
│                   Backend (FastAPI)                     │
│  /api/v1/cases · /api/v1/ml/analyze · /api/v1/reports   │
└──────┬────────────────────────────────┬─────────────────┘
       │                                │
┌──────▼───────────────────┐     ┌──────▼────────────────┐
│      ML Engine (Python)  │     │      Database         │
│  TruFor · OCR · Ollama   │     │  SQLite / SQLAlchemy  │
└──────────────────────────┘     └───────────────────────┘
```

### ML Engine Modules

| Module | Purpose |
|---|---|
| `forensic_vision/trufor_wrapper.py` | State-of-the-art TruFor image tampering & forgery detection |
| `forensic_vision/metadata_analyzer.py` | EXIF and PDF metadata inspection for manipulation artifacts |
| `ocr_nlp/document_ocr.py` | Extracts text and named entities (PAN, Names, Dates) |
| `ocr_nlp/math_reconciler.py` | Validates that line-item financial amounts sum correctly |
| `ocr_nlp/benford_checker.py` | Verifies financial figures against Benford's Law |
| `behavioral_twin/behavior_analyzer.py` | Detects anomalous user behavior based on mouse/keyboard telemetry |
| `trust_engine/score_fusion.py` | Intelligent weighted fusion of all module scores → final risk level |
| `llm_reporter/ollama_reporter.py` | Generates natural-language fraud narratives using local Llama 3.2 |
| `pipeline.py` | Multi-threaded coordinator that executes the above modules in parallel |

---

## Key Features Added Recently

- **Local LLM Integration (Ollama):** The platform now uses `llama3.2:1b` running locally to generate human-readable fraud reports instantly without sending sensitive PII to external APIs.
- **Advanced Forensics:** Replaced legacy models with **TruFor**, a state-of-the-art pixel-level tampering detector that provides heatmaps of forged areas.
- **Enterprise UI Refactor:** The frontend has been completely redesigned with a modern, clean, bank-grade aesthetic, prioritizing the document viewer and ML analysis results.
- **Cross-Document Analysis:** Ability to select two documents side-by-side and cross-validate extracted entities (e.g., checking if the PAN on an ITR matches the PAN on an Aadhaar card).
- **Parallel Pipeline:** The backend ML engine now executes the heavy Forensic, OCR, and Behavioral scans in parallel threads, reducing analysis time significantly.
- **Robust Timeouts & Fallbacks:** Graceful handling of slow CPUs. If the LLM is busy or models take too long, the system seamlessly falls back to template-based reporting without crashing.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.11 |
| Node.js | 20 LTS |
| Ollama | Latest (requires `llama3.2:1b` model) |

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/404prateek/Dhanrakshak.git
cd Dhanrakshak
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Set up your environment variables if necessary
```

### 3. Backend & ML Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies (requires PyTorch)
pip install -r ../requirements_ml.txt
pip install -r requirements.txt

# Seed the local SQLite database
python seed_db.py
python create_admin.py

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API docs available at `http://localhost:8000/docs`

### 4. Ollama LLM Setup (Required for AI Reports)

In a separate terminal, pull and start the local Llama model:
```bash
ollama pull llama3.2:1b
ollama run llama3.2:1b
```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`

---

## Security & Architecture Notes

- **Offline ML Processing:** All machine learning models, including the LLM, run locally. **No sensitive financial documents are sent to cloud providers.**
- **Module Cleanup:** Deprecated and stubbed modules (like legacy Neo4j, empty cybersecurity folders, and unused mock services) have been aggressively purged to keep the codebase clean and production-ready.
- **JWT Auth:** API endpoints are protected by JWT tokens. Use the `create_admin.py` script to generate your first login credentials.

---

## License

Private — all rights reserved.
