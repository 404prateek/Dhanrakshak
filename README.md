# DhanRakshak — AI-Powered Fraud Detection Platform

DhanRakshak is a real-time document forgery and behavioral anomaly detection system designed for financial institutions and insurance underwriters. It combines forensic vision, NLP-based document extraction, behavioral biometrics, and graph-based entity analysis into a unified trust score.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React + TypeScript)       │
│  DocumentUpload · RiskDashboard · BehaviorTracker        │
└───────────────────────┬─────────────────────────────────┘
                        │ REST + WebSocket
┌───────────────────────▼─────────────────────────────────┐
│                   Backend (FastAPI)                      │
│  /document · /session · /risk · /health                  │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼───────┐
│  ML Engine  │ │ PostgreSQL │ │   Neo4j    │
│  (Python)   │ │  (async)   │ │  (graph)   │
└─────────────┘ └────────────┘ └────────────┘
```

### ML Engine Modules

| Module | Purpose |
|---|---|
| `forensic_vision/ela_detector` | Error Level Analysis — detects tampered image regions |
| `forensic_vision/forgery_classifier` | EfficientNet-B0 binary forgery classifier |
| `forensic_vision/signature_verifier` | Siamese network for signature comparison |
| `ocr_nlp/layoutlm_extractor` | LayoutLMv3 document entity extraction (name, DOB, property ID) |
| `ocr_nlp/ner_pipeline` | spaCy NER for structured field extraction |
| `behavioral_twin/feature_extractor` | Computes feature vector from browser events |
| `behavioral_twin/isolation_forest` | Isolation Forest anomaly scoring |
| `behavioral_twin/panic_detector` | Rule-based duress / panic detection |
| `trust_engine/score_fusion` | Weighted fusion of all module scores → final risk level |
| `trust_engine/shap_explainer` | SHAP-based human-readable explanations |

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.11 |
| Node.js | 20 LTS |
| Docker + Docker Compose | 24 |
| Tesseract OCR | 5.x |
| PostgreSQL | 15 |
| Neo4j | 5 |

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
# Edit .env and fill in all required values (see .env.example for keys)
```

### 3. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Download spaCy English model
python -m spacy download en_core_web_sm

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`

### 5. Run with Docker (recommended)

```bash
docker compose -f infra/docker-compose.yml up --build
```

Services started:
- **backend** → `http://localhost:8000`
- **frontend** → `http://localhost:5173`
- **PostgreSQL** → `localhost:5432`
- **Neo4j** → `http://localhost:7474` (browser UI)
- **Redis** → `localhost:6379`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Description |
|---|---|
| `POSTGRES_URL` | Async PostgreSQL connection string |
| `NEO4J_URI` | Neo4j bolt URI |
| `NEO4J_USER` | Neo4j username |
| `NEO4J_PASS` | Neo4j password |
| `JWT_SECRET_KEY` | Secret key for JWT token signing |
| `JWT_ALGORITHM` | JWT algorithm (default: `HS256`) |
| `JWT_EXPIRE_MINUTES` | Token expiry in minutes (default: `60`) |
| `TRUST_WEIGHT_DOC_FORENSIC` | Weight for forensic score (default: `0.45`) |
| `TRUST_WEIGHT_BEHAVIORAL` | Weight for behavioral score (default: `0.35`) |
| `TRUST_WEIGHT_GRAPH_ANOMALY` | Weight for graph anomaly score (default: `0.20`) |
| `RISK_THRESHOLD_HIGH` | Score above which risk is HIGH (default: `0.65`) |
| `RISK_THRESHOLD_MEDIUM` | Score above which risk is MEDIUM (default: `0.35`) |
| `DHANRAKSHAK_IF_CONTAMINATION` | Isolation Forest contamination rate (default: `auto`) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/document/upload` | Upload document image for forensic analysis |
| `POST` | `/session/ingest` | Submit behavioral feature vector |
| `GET` | `/risk/{session_id}` | Retrieve final risk score and audit trail |
| `GET` | `/health` | Health check |

---

## Project Structure

```
Dhanrakshak/
├── backend/               FastAPI app, routers, services, models, DB
├── ml_engine/             All ML modules (forensic, NLP, behavioral, trust)
│   ├── forensic_vision/
│   ├── ocr_nlp/
│   ├── behavioral_twin/
│   ├── trust_engine/
│   └── training/          Training scripts, datasets/, checkpoints/
├── frontend/              React + TypeScript UI
│   └── src/
│       ├── components/
│       ├── services/      API client, BehaviorCollector, WebSocket
│       └── types/
├── cybersecurity/         JWT auth, AES encryption, audit log, rate limiter
├── infra/                 Docker Compose, Dockerfiles, nginx config
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Training Custom Models

```bash
# Train forgery classifier (EfficientNet-B0)
python ml_engine/training/train_forensic.py

# Train behavioral anomaly models (Isolation Forest + LSTM)
python ml_engine/training/train_behavioral.py
```

Place training datasets in `ml_engine/training/datasets/`.  
Saved model weights go to `ml_engine/training/checkpoints/`.  
Both directories are git-ignored.

---

## Security Notes

- Raw browser events are **never sent to the server** — only computed feature vectors leave the client (`BehaviorCollector` privacy-first design).
- All document uploads are hashed and AES-encrypted before storage (`cybersecurity/encryption.py`).
- Every risk decision is written to an immutable audit log (`cybersecurity/audit_trail.py`).
- API endpoints are protected by JWT with role-based access control (`cybersecurity/api_auth.py`).
- Model weights are loaded with `weights_only=True` to prevent arbitrary pickle execution.

---

## License

Private — all rights reserved.
