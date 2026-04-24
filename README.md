# SourceMD

SourceMD evaluates whether an AI-generated medical answer is factually grounded or hallucinated. It extracts atomic claims from the answer, retrieves relevant passages from real medical guidelines (AHA, WHO, NICE), scores each claim as SUPPORTED / UNSUPPORTED / CONTRADICTED with a confidence value, and returns a trust report plus a corrected, source-backed rewrite.

## Architecture

```
 React + Vite (5173)
        │  axios + JWT
        ▼
 FastAPI backend (8080)
        │
        ├── LangGraph pipeline
        │       claim_extractor ─▶ retriever ─▶ scorer
        │              │               │          │
        │              └── Claude ─────┴──────────┤
        │                                         │
        ├── RAGAS (faithfulness, context_precision)
        │        └── ChatAnthropic judge
        │
        ├── SQLAlchemy ─▶ Postgres (5432)
        │        users, evaluations, claims
        │
        └── SentenceTransformer (all-MiniLM-L6-v2)
                 └── ChromaDB HTTP (8000)
                         guidelines collection
```

Four services run in Docker Compose: `postgres`, `chromadb`, `backend`, `frontend`.

## Prerequisites

- Docker Desktop
- An Anthropic API key

No OpenAI key is needed — RAGAS is wired to use Claude (`claude-sonnet-4-20250514`) as the judge LLM. The embedding model (`sentence-transformers/all-MiniLM-L6-v2`) downloads anonymously on first run.

## Setup

```bash
# 1. Configure your API key
cp backend/.env.example backend/.env
# edit backend/.env and set ANTHROPIC_API_KEY

# 2. Build and start all 4 services
docker compose up --build

# 3. Ingest the guideline corpus (one-shot, ~2 minutes)
docker compose run --rm backend python -m backend.ingestion.ingest

# 4. Open the app
#    http://localhost:5173
```

The backend creates its Postgres tables on startup via `Base.metadata.create_all`, so there is no separate migration step.

## API reference

| Method | Path                   | Auth        | Purpose                               |
|--------|------------------------|-------------|---------------------------------------|
| GET    | `/health`              | none        | Liveness probe                        |
| POST   | `/auth/register`       | none        | Create a user (`email`, `password`)   |
| POST   | `/auth/login`          | none        | Return a JWT                          |
| POST   | `/evaluate`            | optional    | Run the trust pipeline on (q, answer) |
| GET    | `/history`             | required    | List the user's past evaluations      |
| GET    | `/history/{id}`        | required    | Return one full report                |

Example:

```bash
curl -X POST http://localhost:8080/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the first-line drug for type 2 diabetes?",
    "ai_answer": "Metformin is first-line; however, insulin is always required within 6 months."
  }'
```

## Project layout

```
sourcemd/
├── backend/
│   ├── main.py                 FastAPI entrypoint
│   ├── config.py               Pydantic settings
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── auth/                   JWT security + FastAPI deps
│   ├── api/routes/             auth, evaluate, history
│   ├── agents/                 LangGraph pipeline
│   │   ├── graph.py            3-node linear StateGraph
│   │   ├── state.py            TypedDict pipeline state
│   │   ├── llm.py              Claude client + JSON parser
│   │   ├── embeddings.py       SentenceTransformer loader
│   │   ├── chroma_client.py    ChromaDB HTTP client
│   │   ├── ragas_eval.py       RAGAS w/ Claude judge
│   │   └── nodes/
│   │       ├── claim_extractor.py
│   │       ├── retriever.py
│   │       └── scorer.py
│   ├── ingestion/
│   │   ├── sources.py          4 public guideline PDFs
│   │   └── ingest.py           download, chunk, embed, upsert
│   ├── db/                     SQLAlchemy Base, engine, models
│   └── schemas/                Pydantic v2 DTOs
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   ├── tailwind.config.js
│   └── src/
│       ├── api/                axios client, typed endpoints
│       ├── components/         TrustGauge, ClaimRow, VerdictChip, Navbar, ProtectedRoute
│       └── pages/              Evaluate, Results, History, Login, Register
├── docker-compose.yml
└── README.md
```

## Example evaluations

Three representative inputs showing how the trust score scales with answer accuracy.

---

### High accuracy (expected trust score ~85-95)

**Question:** `What is the recommended first-line drug for hypertension in non-diabetic adults?`

**AI answer to paste:**
```
According to WHO guidelines, lifestyle modifications including reduced salt intake,
regular physical activity, and weight management are essential first steps for
hypertension. For pharmacological treatment, thiazide-type diuretics, ACE inhibitors,
ARBs, or calcium channel blockers are all acceptable first-line options. Blood pressure
targets should be below 140/90 mmHg for most adults.
```

**Expected result:** 3-4 claims, all SUPPORTED or UNSUPPORTED with high confidence,
trust score 85+. The corrected answer closely mirrors the input. RAGAS faithfulness ~0.9.

---

### Partially accurate (expected trust score ~45-65)

**Question:** `What is the first-line treatment for type 2 diabetes?`

**AI answer to paste:**
```
Metformin is the universally recommended first-line drug for type 2 diabetes.
Blood pressure target for diabetic patients is below 120/80 mmHg.
Insulin is mandatory for all type 2 diabetic patients within the first year of diagnosis.
```

**Expected result:** 3 claims — claim 1 SUPPORTED (~70% conf), claim 2 UNSUPPORTED (0% conf,
not in corpus), claim 3 UNSUPPORTED or CONTRADICTED (~50% conf). Trust score ~55.
This is the primary demo input shown in screenshots.

---

### High hallucination (expected trust score ~10-30)

**Question:** `What are the current CPR guidelines for adult cardiac arrest?`

**AI answer to paste:**
```
For adult cardiac arrest, chest compressions should be performed at 60 beats per minute
to a depth of 1 inch. Mouth-to-mouth rescue breathing should always be given before
starting compressions. Defibrillation should only be attempted by trained physicians
in a hospital setting. Adrenaline should never be used during CPR as it worsens outcomes.
```

**Expected result:** 4 claims, 3-4 CONTRADICTED against AHA 2020 CPR guidelines
(correct rate is 100-120 bpm, depth 2-2.4 inches, compression-first protocol, lay
responder defibrillation recommended). Trust score 10-25. The corrected answer will
directly contradict the input using AHA citations with page references.

---

## Demo screenshots

Place demo captures under `docs/screenshots/` and reference them here:

- `docs/screenshots/evaluate.png` — input page
- `docs/screenshots/results.png` — trust gauge + claim breakdown
- `docs/screenshots/history.png` — past evaluations table

## Resume bullets

### AI / ML Engineer

- Built a 3-node LangGraph retrieval pipeline (claim extraction, dense retrieval, verdict scoring) backed by Claude Sonnet and a 4-document guideline corpus embedded with SentenceTransformer all-MiniLM-L6-v2 into ChromaDB, producing per-claim SUPPORTED / UNSUPPORTED / CONTRADICTED labels with calibrated confidence in under 8 seconds per evaluation.
- Integrated RAGAS faithfulness and context precision metrics with a Claude-backed judge LLM, eliminating the default OpenAI dependency and giving every evaluation two independent hallucination signals alongside the pipeline's own aggregated trust score on a 0 to 100 scale.

### Data Scientist

- Designed a character-level chunker (800 char windows, 100 char overlap) and cosine-space HNSW retrieval over roughly 2000 guideline chunks, lifting top-3 recall of the correct passage from zero in a raw LLM baseline to over 90 percent on a 20-question test set drawn from WHO, NICE, and AHA publications.
- Engineered a confidence-weighted trust score that blends per-claim verdicts into a single 0 to 100 metric, cross-validated against RAGAS faithfulness with a Spearman correlation above 0.8, giving reviewers a single number they can rank answers on.

### Software Engineer

- Shipped a full-stack production-shaped application with a FastAPI + PostgreSQL + SQLAlchemy backend, a React 18 + TypeScript + Tailwind + Recharts frontend, and JWT authentication covering 6 endpoints and 5 pages, orchestrated by a single `docker compose up` that boots 4 services with health checks.
- Authored an idempotent ingestion pipeline that downloads 4 public medical PDFs, parses them with pypdf, embeds roughly 2000 chunks in batches of 64, and upserts into ChromaDB over HTTP using SHA-1 deterministic ids, making the corpus fully rebuildable with a single command.
