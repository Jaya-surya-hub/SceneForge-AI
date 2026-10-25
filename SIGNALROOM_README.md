# IncuBrix Signal Room — Quickstart & Operations Guide

> **The Evidence-First Search & AI Visibility Intelligence Engine**  
> *Every signal has a source. Every decision has proof.*

---

## 1. Prerequisites

- Python 3.11+
- Node.js 20+ & npm
- Docker & Docker Compose (optional for local dev, used for containerized deployment)

---

## 2. Quickstart

### 2.1 Backend Setup & Migration

```bash
# Set PYTHONPATH to include src
# In PowerShell:
$env:PYTHONPATH = "src"

# In Command Prompt:
set PYTHONPATH=src

# Run database migrations
.\signalroom.cmd migrate
# or in PowerShell:
.\signalroom.ps1 migrate
```

### 2.2 Verify CLI

```bash
# View CLI help
.\signalroom.cmd --help

# Check system health & database connection
.\signalroom.cmd health

# Display active runtime configuration
.\signalroom.cmd info

# Inspect live replay engine interface
.\signalroom.cmd replay Q-047 --market US
```

### 2.3 Start FastAPI Backend

```bash
# Start backend on http://127.0.0.1:8000
python -m uvicorn signalroom.api.app:app --port 8000 --reload
```

- Interactive API Docs (Swagger UI): `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/api/v1/health`

### 2.4 Start Frontend Application

The frontend is built with React 18, Vite, TypeScript, and Tailwind CSS using an editorial research laboratory design system.

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to explore all 10 core modules:
1. **Command Center** (`/`)
2. **Question Atlas** (`/questions`)
3. **Proof Ledger** (`/ledger`)
4. **Replay Lab** (`/replay`)
5. **Visibility Intelligence** (`/visibility`)
6. **Fix Court** (`/fixes`)
7. **Content Foundry & Claim Guard** (`/content`)
8. **Citation Gravity** (`/citations`)
9. **Weekly Reports** (`/reports`)
10. **Settings & Honesty Panel** (`/settings`)

---

## 3. Running Automated Tests

Run the Signal Room test suite:

```bash
$env:PYTHONPATH = "src"; python -m pytest tests/signalroom -v
```

All 14 unit and integration tests verify:
- Health endpoint schema and database/storage probes
- Foundational model persistence (Projects, Questions, Runs, EvidenceReferences)
- Cryptographic SHA-256 calculation and tamper-detection
- Full Typer CLI command execution (`--help`, `info`, `health`, `replay`)
- API endpoints (`/projects`, `/questions`, `/runs`, `/evidence/ledger`, `/evidence/verify`)

---

## 4. Docker Deployment

Validate configuration:
```bash
docker compose -f docker-compose.signalroom.yml config
```

Build and launch services (when Docker Desktop daemon is running):
```bash
docker compose -f docker-compose.signalroom.yml up --build
```

Services:
- `signalroom-backend`: FastAPI on port 8000
- `signalroom-frontend`: Nginx serving SPA on port 3000
- `signalroom_storage`: Persistent volume for SQLite DB and evidence artifacts

---

## 5. Architectural & Assessment Compliance Rules

- **Zero Synthetic Measurements:** No artificial rankings or generated model hallucinations are presented as real.
- **DEMO Labeling:** All illustrative fixtures in Phase 1 display explicit `DEMO` badges.
- **Preserved Existing Work:** All pre-existing workspace code (`sceneforge`) remains intact.
