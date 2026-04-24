# SourceMD

**SourceMD** is an AI-powered medical fact-checker that evaluates whether an AI-generated answer is grounded in real clinical guidelines or hallucinated. Paste any medical question and an AI-generated answer — SourceMD extracts every factual claim, retrieves evidence from authoritative guideline PDFs (NICE, AHA), scores each claim as **SUPPORTED / UNSUPPORTED / CONTRADICTED**, and returns a trust score with a corrected, source-backed rewrite.

Built as a full-stack portfolio project demonstrating RAG pipelines, LangGraph agent orchestration, vector search, and production-shaped web application architecture.

---

## How It Works

```
User submits question + AI answer
          │
          ▼
┌─────────────────────────────────────────────────────┐
│                  LangGraph Pipeline                  │
│                                                      │
│  1. Claim Extractor                                  │
│     └── LLM extracts atomic factual claims          │
│                                                      │
│  2. Retriever                                        │
│     ├── Embeds each claim (all-MiniLM-L6-v2)        │
│     ├── Queries ChromaDB (cosine similarity)        │
│     └── Augments with Tavily live web search        │
│         when corpus similarity < 0.35               │
│                                                      │
│  3. Scorer                                           │
│     ├── LLM scores each claim vs. passages          │
│     ├── Aggregates trust score (0–100)              │
│     ├── Synthesizes corrected answer                │
│     └── Generates follow-up questions               │
└─────────────────────────────────────────────────────┘
          │
          ▼
   Trust Report
   ├── Trust score (0–100)
   ├── Hallucination Rate %
   ├── Source Coverage %
   ├── Per-claim verdicts with rationale + citations
   ├── Corrected, source-backed answer
   └── Follow-up chat (grounded in retrieved context)
```

---

## Features

- **Claim-level fact-checking** — answers are broken into atomic claims, each verified independently
- **Real guideline citations** — evidence sourced from NICE NG28, NICE NG136, NICE CG181, AHA 2025 CPR with page numbers
- **Live web augmentation** — Tavily searches trusted medical domains (NIH, WHO, NICE, AHA, PubMed) when the local corpus lacks relevant content
- **Trust score** — 0–100 aggregate metric weighted by claim verdicts and confidence
- **Hallucination Rate & Source Coverage** — two additional metrics computed directly from pipeline output
- **Corrected answer** — a rewritten, source-grounded version of the original AI answer
- **Follow-up chat** — multi-turn Q&A grounded in the retrieved guideline passages, persisted per evaluation
- **ChatGPT-style sidebar** — evaluation history grouped by date, rename/delete per chat, light/dark theme
- **JWT authentication** — register, login, evaluations linked to user accounts
- **Public evaluate endpoint** — `/evaluate` works without auth; results stored anonymously

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Groq `llama-3.3-70b-versatile` (free tier) · Anthropic Claude fallback |
| **Agent framework** | LangGraph `StateGraph` — 3-node linear pipeline |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs locally) |
| **Vector store** | ChromaDB (HTTP, cosine similarity, ~2000 guideline chunks) |
| **Web search** | Tavily API (trusted medical domains only) |
| **Backend** | FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL · python-jose JWT |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind CSS · Recharts |
| **Infrastructure** | Docker Compose (4 services) |

---

## Project Structure

```
sourcemd/
├── backend/
│   ├── main.py                   FastAPI app, CORS, router mounts
│   ├── config.py                 Pydantic settings (env vars)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── auth/
│   │   ├── security.py           bcrypt hashing, JWT creation/decode
│   │   └── deps.py               FastAPI auth dependencies
│   ├── api/routes/
│   │   ├── auth.py               POST /auth/register, /auth/login
│   │   ├── evaluate.py           POST /evaluate
│   │   ├── history.py            GET|DELETE /history, GET /history/{id}
│   │   └── followup.py           POST /follow-up
│   ├── agents/
│   │   ├── graph.py              LangGraph StateGraph wiring
│   │   ├── state.py              PipelineState, ScoredClaim TypedDicts
│   │   ├── llm.py                Groq/Anthropic client + JSON extractor
│   │   ├── embeddings.py         SentenceTransformer singleton
│   │   ├── chroma_client.py      ChromaDB HTTP client
│   │   ├── ragas_eval.py         Hallucination rate + source coverage metrics
│   │   └── nodes/
│   │       ├── claim_extractor.py
│   │       ├── retriever.py      ChromaDB + Tavily augmentation
│   │       └── scorer.py         Verdict scoring, trust score, correction
│   ├── ingestion/
│   │   ├── sources.py            Guideline registry (name, url, tag)
│   │   ├── ingest.py             Download → chunk → embed → upsert
│   │   └── cache/                PDF files (committed to repo)
│   ├── db/
│   │   ├── base.py               SQLAlchemy engine + session
│   │   └── models.py             User, Evaluation, Claim, Verdict
│   └── schemas/                  Pydantic v2 request/response models
├── frontend/
│   ├── src/
│   │   ├── api/                  Axios client + typed endpoint wrappers
│   │   ├── context/              ThemeContext (light/dark)
│   │   ├── components/
│   │   │   ├── EvalSidebar.tsx   History sidebar with rename/delete
│   │   │   ├── TrustGauge.tsx    Recharts radial gauge
│   │   │   ├── ClaimRow.tsx      Expandable claim with sources
│   │   │   └── VerdictChip.tsx   SUPPORTED / UNSUPPORTED / CONTRADICTED
│   │   └── pages/
│   │       ├── EvaluatePage.tsx
│   │       ├── ResultsPage.tsx   Full trust report + follow-up chat
│   │       ├── HistoryPage.tsx
│   │       ├── LoginPage.tsx
│   │       └── RegisterPage.tsx
│   ├── Dockerfile
│   └── tailwind.config.js
├── docker-compose.yml
└── railway.toml
```

---

## Local Development

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- A free [Groq API key](https://console.groq.com) (primary LLM)
- A free [Tavily API key](https://app.tavily.com) (web search augmentation)

### 1. Clone and configure

```bash
git clone https://github.com/VanshikaGurbani/SourceMD.git
cd SourceMD
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in your keys:

```env
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
JWT_SECRET=any-long-random-string
```

### 2. Start all services

```bash
docker compose up --build
```

This starts 4 containers: `postgres`, `chromadb`, `backend` (port 8080), `frontend` (port 5173).  
Tables are created automatically on backend startup.

### 3. Ingest the guideline corpus

```bash
docker compose run --rm backend python -m backend.ingestion.ingest
```

Downloads and embeds ~844 chunks from 4 guideline PDFs into ChromaDB. Takes ~2 minutes on first run. Subsequent runs are idempotent.

### 4. Open the app

```
http://localhost:5173
```

Register an account, paste a question + AI answer, and run your first evaluation.

---

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | none | Liveness probe |
| `POST` | `/auth/register` | none | Create account `{email, password}` |
| `POST` | `/auth/login` | none | Returns `{access_token}` |
| `POST` | `/evaluate` | optional | Run trust pipeline `{question, ai_answer}` |
| `GET` | `/history` | required | List user's evaluations |
| `GET` | `/history/{id}` | required | Full evaluation report |
| `DELETE` | `/history/{id}` | required | Delete an evaluation |
| `POST` | `/follow-up` | none | Chat turn `{evaluation_id, question}` |

### Example — evaluate without auth

```bash
curl -X POST http://localhost:8080/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the first-line drug for type 2 diabetes?",
    "ai_answer": "Metformin is first-line. Insulin is mandatory within 6 months of diagnosis."
  }'
```

---

## Test Cases

Three inputs that demonstrate the full scoring range:

### High accuracy (trust score ~85–95)

**Q:** What are the recommended blood pressure targets for adults with hypertension?

**A:**
```
For adults under 80 with hypertension, the clinic blood pressure target is below
140/90 mmHg. For people with type 2 diabetes, the target is below 130/80 mmHg.
Lifestyle modifications including reduced salt intake and regular exercise are
essential alongside pharmacological treatment.
```

---

### Mixed accuracy (trust score ~40–60)

**Q:** What is the first-line treatment for type 2 diabetes?

**A:**
```
Metformin is the universally recommended first-line drug for type 2 diabetes.
Blood pressure target for diabetic patients is below 120/80 mmHg.
Insulin is mandatory for all type 2 diabetic patients within the first year of diagnosis.
```

Expected: claim 1 SUPPORTED, claim 2 CONTRADICTED (NICE says 140/90), claim 3 UNSUPPORTED.

---

### High hallucination (trust score ~10–25)

**Q:** What are the current CPR guidelines for adult cardiac arrest?

**A:**
```
For adult cardiac arrest, perform chest compressions at 60 beats per minute to a
depth of 1 inch. Mouth-to-mouth rescue breathing must be given before starting
compressions. Defibrillation should only be attempted by trained physicians.
Adrenaline should never be used during CPR.
```

Expected: 4 claims, 3–4 CONTRADICTED against AHA 2025 (correct rate 100–120 bpm, depth 2–2.4 inches, compression-first, lay responder AED).

---

## Deployment

### Railway (backend + databases) + Vercel (frontend)

#### Step 1 — Railway setup

1. Go to [railway.app](https://railway.app) → **New Project → Empty Project**
2. **Add PostgreSQL** → `+ New → Database → PostgreSQL`  
   Railway auto-injects `DATABASE_URL` into all services — do not set it manually.
3. **Add ChromaDB** → `+ New → Docker Image` → image: `chromadb/chroma:0.5.11`
   - Variables: `IS_PERSISTENT=TRUE`, `ANONYMIZED_TELEMETRY=FALSE`
   - Note the **internal hostname** Railway assigns (e.g. `chromadb.railway.internal`)
4. **Add backend** → `+ New → GitHub Repo` → select this repo
   - Settings → Build → Dockerfile path: `backend/Dockerfile` · Root directory: `/`
   - Add these environment variables:

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | your Groq key |
| `TAVILY_API_KEY` | your Tavily key |
| `JWT_SECRET` | any long random string |
| `CHROMA_HOST` | internal hostname from ChromaDB service above |
| `CHROMA_PORT` | `8000` |
| `FRONTEND_ORIGIN` | your Vercel URL (add after step below) |

5. After the backend deploys, open the **Railway shell** for the backend service and run:
   ```bash
   python -m backend.ingestion.ingest
   ```

#### Step 2 — Vercel setup (frontend)

1. Go to [vercel.com](https://vercel.com) → **New Project → Import Git Repository**
2. Select this repo
3. Configure:
   - **Framework preset**: Vite
   - **Root directory**: `frontend`
   - **Build command**: `npm run build`
   - **Output directory**: `dist`
4. Add environment variable:

| Variable | Value |
|---|---|
| `VITE_API_URL` | your Railway backend public URL |

5. Deploy. Copy the Vercel URL and paste it into `FRONTEND_ORIGIN` on Railway.

---

## Environment Variables Reference

### `backend/.env` (local dev)

```env
# LLM — at least one required
GROQ_API_KEY=gsk_...                    # free at console.groq.com
ANTHROPIC_API_KEY=sk-ant-...            # optional fallback

# Web search augmentation
TAVILY_API_KEY=tvly-...                 # free at app.tavily.com (1000/mo)

# Auth
JWT_SECRET=change-me-to-a-long-random-string
JWT_EXPIRE_MINUTES=1440

# Database (overridden by Docker Compose)
DATABASE_URL=postgresql+psycopg2://sourcemd:sourcemd_dev_password@postgres:5432/sourcemd

# ChromaDB (overridden by Docker Compose)
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# CORS
FRONTEND_ORIGIN=http://localhost:5173
```

Copy `backend/.env.example` as a starting point — it contains all keys with placeholder values.

---

## Resume Bullets

**AI / ML**
- Built a 3-node LangGraph RAG pipeline (claim extraction → dense retrieval → LLM verdict scoring) over 844 embedded guideline chunks, producing per-claim SUPPORTED / UNSUPPORTED / CONTRADICTED labels with calibrated confidence scores and an aggregated 0–100 trust metric in under 10 seconds per evaluation
- Designed a hybrid retrieval system combining ChromaDB cosine similarity search (all-MiniLM-L6-v2, 384-dim) with Tavily live web augmentation across 10 trusted medical domains, triggering web fallback when local corpus similarity drops below 0.35 to handle out-of-corpus queries gracefully

**Data Science**
- Engineered a trust scoring formula that applies fixed verdict penalties (SUPPORTED = confidence, UNSUPPORTED = 0.3, CONTRADICTED = 0.0) to prevent zero-confidence claims from silently inflating scores, and computed Hallucination Rate and Source Coverage as interpretable alternatives to RAGAS metrics
- Implemented character-level chunking (800-char windows, 100-char overlap) with SHA-1 deterministic IDs for idempotent ChromaDB upserts, enabling full corpus rebuild from 4 guideline PDFs in under 2 minutes

**Software Engineering**
- Shipped a production-shaped full-stack application with a FastAPI + PostgreSQL + SQLAlchemy 2.0 backend, React 18 + TypeScript + Tailwind + Recharts frontend, and JWT auth covering 8 endpoints, orchestrated by a single `docker compose up` across 4 services with health checks
- Built a ChatGPT-style evaluation history UI with persistent per-session follow-up chat (localStorage), inline rename/delete, light/dark theme toggle, and Tavily-sourced live web citations rendered with green badges alongside static guideline page references
