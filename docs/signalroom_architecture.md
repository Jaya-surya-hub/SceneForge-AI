# IncuBrix Signal Room — Architecture & Design Document

> **Tagline:** *Every signal has a source. Every decision has proof.*  
> **Platform:** IncuBrix Signal Room — The Evidence-First Search & AI Visibility Intelligence Engine  
> **Assessment Track:** IncuBrix 2027 Graduate Hiring Growth Engineer Assessment (Option 3: AEO, SEO & GEO Visibility Engine)

---

## 1. Executive Summary & Vision

IncuBrix Signal Room is an assessment-grade, production-oriented growth intelligence engine. Unlike conventional SEO dashboards that display unverified keyword ranks or aggregate numbers without context, Signal Room is built upon a fundamental tenet: **Auditability**.

Every visibility score, brand mention, competitive displacement, and technical fix recorded by Signal Room is anchored to an immutable, cryptographically verifiable artifact stored in the **Proof Ledger**.

### Core Tenets
1. **No Fake Evidence:** No simulated rankings, fake assistant responses, or manufactured data.
2. **Deterministic Reproducibility:** Reviewers can replay any query via CLI (`signalroom replay Q-047 --market US`) and verify the historical ledger against live responses.
3. **Multi-Model Intelligence:** Variance-aware tracking across Google Search and four leading AI engines (ChatGPT Search, Claude 3.5 Sonnet, Gemini 1.5 Pro, Perplexity Sonar).
4. **Claim Guard:** Unverified product claims are structurally blocked from being published.

---

## 2. Signature Capabilities & System Modules

```
                    ┌────────────────────────────────────────────────────────┐
                    │               IncuBrix Signal Room Core                │
                    └────────────────────────────────────────────────────────┘
                                                 │
         ┌───────────────────┬───────────────────┼───────────────────┬───────────────────┐
         ▼                   ▼                   ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Question Atlas  │ │  Proof Ledger   │ │ Live Replay Lab │ │   Fix Court     │ │ Content Foundry │
│  (100+ Creator  │ │  (Append-Only   │ │(CLI & UI Replay │ │ (20 Validated   │ │  & Claim Guard  │
│    Queries)     │ │ SHA-256 Chained)│ │  Variance Delta)│ │ Technical Fixes)│ │  (Truth Sheet)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
         │                   │                   │                   │                   │
         └───────────────────┴───────────────────┼───────────────────┴───────────────────┘
                                                 │
                                                 ▼
                                    ┌─────────────────────────┐
                                    │ Citation Gravity Engine │
                                    │  & Weekly Briefings     │
                                    └─────────────────────────┘
```

### 2.1 Proof Ledger
An append-only, tamper-evident cryptographic evidence ledger. Each record registers:
- `id`: Unique evidence identifier (`EV-YYYYMMDD-XXX`)
- `question_id`: Link to originating Question in Question Atlas
- `run_id`: Execution run identifier
- `provider` & `collection_method`: Official API or permitted manual capture fixture
- `timestamp`: UTC ISO-8601 timestamp
- `market`, `location`, `language`: Geolocation context (US, UK, IN)
- `artifact_path`: Relative filesystem or object storage path to the raw response / screenshot
- `sha256_hash`: SHA-256 digest of the artifact file
- `prev_ledger_hash`: Hash of the preceding ledger record (Genesis: `0` * 64)
- `current_ledger_hash`: SHA-256 digest of record contents concatenated with `prev_ledger_hash`
- `execution_status`, `runtime_ms`, `cost_usd`

Historical evidence is **never overwritten**. Any attempt to alter historical records breaks the hash chain and is flagged immediately by `/api/v1/evidence/verify`.

### 2.2 Live Replay Lab
Reviewers can rerun queries at any time:
```bash
signalroom replay Q-047 --market US
```
- Fetches the original question and its recorded provider configuration.
- Executes fresh observations where permitted.
- Appends a new observation to the Proof Ledger without modifying the original baseline.
- Generates a side-by-side comparison report calculating rank drift, brand mention shifts, and citation status changes.

### 2.3 Question Atlas
Maintains 100+ genuine creator queries mapped across:
- **Journey Stages:** Make, Repurpose, Edit, Caption, Publish, Grow
- **Search Intents:** Informational, Comparison, Commercial Investigation
- **Verifiable Sources:** Google Autocomplete, People Also Ask (PAA), Reddit Creator subreddits, Keyword Planner. Every query contains its source URL.

### 2.4 Variance-Aware AI Visibility
Tracks AI assistant behavior across at least three repeated runs per question to measure:
- Brand mention rate
- Linked citation rate
- Competitor presence
- Run-level variance (e.g., &plusmn;3.5%)
- Failed and restricted observations

Providers are never averaged into a single arbitrary score without methodological justification.

### 2.5 Citation Gravity
Aggregates and ranks third-party URLs cited by AI engines and search overviews. Surfaces a prioritized 30-target citation acquisition plan with specific editorial angles.

### 2.6 Technical SEO Fix Court
Contains 20 prioritized, validated fixes for `incubrix.com`. Each entry includes:
- Problem diagnosis
- Supporting evidence artifact
- Ready-to-paste code snippet
- Validation tool & validation artifact

### 2.7 Content Foundry & Claim Guard
Produces 10 answer-first, publish-ready growth pages. Claim Guard audits all copy against the **IncuBrix Product Truth Sheet**:
- Claims matching product capabilities are verified.
- Unsupported or exaggerated claims are blocked from publish status.

### 2.8 Honesty Panel
The frontend includes a permanent Honesty Panel displaying:
- Operational limits
- Failed requests and timeouts
- API restrictions
- Manual vs automated observations
- Estimated vs actual API costs in USD

---

## 3. Technology Stack & Directory Structure

```
IncuBrix-SEAps3/
├── alembic_signalroom/            # Signal Room database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_signalroom_foundations.py
├── alembic_signalroom.ini         # Alembic configuration for Signal Room
├── docker/
│   ├── Dockerfile.signalroom.backend
│   └── Dockerfile.signalroom.frontend
├── docker-compose.signalroom.yml  # Container orchestration
├── docs/
│   └── signalroom_architecture.md # Architectural specifications
├── frontend/                      # React 18 + Vite + TypeScript + Tailwind
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── src/
│       ├── components/            # Header, Navigation, DemoBanner
│       ├── pages/                 # 10 dedicated navigation modules
│       ├── types.ts
│       └── App.tsx
├── scripts/
│   └── signalroom_cli.py          # Typer CLI script
├── signalroom.cmd                 # Windows CLI wrapper
├── signalroom.ps1                 # PowerShell CLI wrapper
├── src/signalroom/                # Python backend package
│   ├── api/                       # FastAPI routes, middleware, lifespan
│   ├── cli/                       # Typer CLI commands (info, health, replay, migrate)
│   ├── core/                      # Config, logging, exceptions
│   ├── db/                        # SQLAlchemy Base, session, engine
│   ├── models/                    # Project, Question, Run, EvidenceReference
│   ├── schemas/                   # Pydantic schemas
│   └── storage/                   # LocalArtifactStore, SHA-256 hasher
├── tests/signalroom/              # Pytest test suite (14 automated tests)
│   ├── conftest.py
│   ├── test_api_routes.py
│   ├── test_cli.py
│   ├── test_health.py
│   ├── test_models.py
│   └── test_storage.py
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore rules
├── pyproject.toml                 # Package & test configuration
├── PHASE_STATUS.md                # Phase-by-phase implementation tracker
└── SIGNALROOM_README.md           # Quickstart and operating guide
```

---

## 4. Cryptographic Proof Ledger Specification

```
[Genesis Hash: 0000000000000000000000000000000000000000000000000000000000000000]
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Record 1: EV-20261022-001                                                    │
│ Prev Hash: 0000000000000000000000000000000000000000000000000000000000000000   │
│ Artifact SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991...│
│ Current Hash: SHA256(prev_hash + question_id + run_id + provider + artifact) │
│            -> a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad... │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Record 2: EV-20261022-002                                                    │
│ Prev Hash: a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e │
│ Artifact SHA-256: ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b980778...│
│ Current Hash: SHA256(prev_hash + question_id + run_id + provider + artifact) │
│            -> 3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed5... │
└──────────────────────────────────────────────────────────────────────────────┘
```

The verify endpoint (`GET /api/v1/evidence/verify`) conducts a dual audit:
1. Validates that every stored artifact file on disk exists and has a byte-for-byte SHA-256 match.
2. Traverses the chain from Genesis to tip, verifying that `entry[i].prev_hash == entry[i-1].current_hash` and that each record's current hash matches the cryptographic formula.
