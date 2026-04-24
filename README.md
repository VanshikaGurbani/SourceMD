# SourceMD

SourceMD is an AI-powered medical fact-checker that evaluates whether an AI-generated answer is grounded in real clinical guidelines or hallucinated. Paste any medical question and an AI-generated answer. SourceMD extracts every factual claim, retrieves evidence from authoritative guideline PDFs (NICE, AHA), scores each claim as **SUPPORTED / UNSUPPORTED / CONTRADICTED**, and returns a trust score with a corrected, source-backed rewrite.

---

## How It Works

```
User submits question + AI answer
          |
          v
+-----------------------------------------------------+
|                  LangGraph Pipeline                 |
|                                                     |
|  1. Claim Extractor                                 |
|     LLM extracts atomic factual claims              |
|                                                     |
|  2. Retriever                                       |
|     Embeds each claim (all-MiniLM-L6-v2)            |
|     Queries ChromaDB (cosine similarity)            |
|     Augments with Tavily live web search            |
|     when corpus similarity < 0.35                   |
|                                                     |
|  3. Scorer                                          |
|     LLM scores each claim vs. passages              |
|     Aggregates trust score (0-100)                  |
|     Synthesizes corrected answer                    |
|     Generates follow-up questions                   |
+-----------------------------------------------------+
          |
          v
   Trust Report
   - Trust score (0-100)
   - Hallucination Rate %
   - Source Coverage %
   - Per-claim verdicts with rationale and citations
   - Corrected, source-backed answer
   - Follow-up chat grounded in retrieved context
```

---

## Features

- **Claim-level fact-checking** -- answers are broken into atomic claims, each verified independently
- **Real guideline citations** -- evidence sourced from NICE NG28, NICE NG136, NICE CG181, and AHA 2025 CPR with page numbers
- **Live web augmentation** -- Tavily searches trusted medical domains (NIH, WHO, NICE, AHA, PubMed) when the local corpus lacks relevant content, shown with a live web badge
- **Trust score** -- 0-100 aggregate metric weighted by claim verdicts and confidence
- **Hallucination Rate and Source Coverage** -- two additional metrics computed directly from pipeline output, always show real numbers
- **Corrected answer** -- a rewritten, source-grounded version of the original AI answer
- **Follow-up chat** -- multi-turn Q&A grounded in the retrieved guideline passages, persisted per evaluation across sessions
- **Evaluation history sidebar** -- ChatGPT-style sidebar with evaluations grouped by date, rename and delete per chat, light/dark theme
- **JWT authentication** -- register, login, evaluations linked to user accounts
- **Public evaluate endpoint** -- `/evaluate` works without auth; results stored anonymously

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq `llama-3.3-70b-versatile` (free tier) with Anthropic Claude as fallback |
| Agent framework | LangGraph `StateGraph` -- 3-node linear pipeline |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs locally) |
| Vector store | ChromaDB over HTTP, cosine similarity, ~844 guideline chunks |
| Web search | Tavily API (trusted medical domains only) |
| Backend | FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, python-jose JWT |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| Infrastructure | Docker Compose (4 services) |

---

## Project Structure

```
sourcemd/
├── backend/
│   ├── main.py                   FastAPI app, CORS, router mounts
│   ├── config.py                 Pydantic settings from env vars
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── auth/
│   │   ├── security.py           bcrypt hashing, JWT creation and decode
│   │   └── deps.py               FastAPI auth dependencies
│   ├── api/routes/
│   │   ├── auth.py               POST /auth/register, /auth/login
│   │   ├── evaluate.py           POST /evaluate
│   │   ├── history.py            GET|DELETE /history, GET /history/{id}
│   │   └── followup.py           POST /follow-up
│   ├── agents/
│   │   ├── graph.py              LangGraph StateGraph wiring
│   │   ├── state.py              PipelineState, ScoredClaim TypedDicts
│   │   ├── llm.py                Groq/Anthropic client with JSON extractor
│   │   ├── embeddings.py         SentenceTransformer singleton
│   │   ├── chroma_client.py      ChromaDB HTTP client
│   │   ├── ragas_eval.py         Hallucination rate and source coverage metrics
│   │   └── nodes/
│   │       ├── claim_extractor.py
│   │       ├── retriever.py      ChromaDB + Tavily augmentation
│   │       └── scorer.py         Verdict scoring, trust score, correction prompt
│   ├── ingestion/
│   │   ├── sources.py            Guideline registry (name, url, tag)
│   │   ├── ingest.py             Download, chunk, embed, upsert pipeline
│   │   └── cache/                PDF files (committed to repo)
│   ├── db/
│   │   ├── base.py               SQLAlchemy engine and session
│   │   └── models.py             User, Evaluation, Claim, Verdict
│   └── schemas/                  Pydantic v2 request and response models
├── frontend/
│   ├── src/
│   │   ├── api/                  Axios client and typed endpoint wrappers
│   │   ├── context/              ThemeContext (light/dark)
│   │   ├── components/
│   │   │   ├── EvalSidebar.tsx   History sidebar with rename and delete
│   │   │   ├── TrustGauge.tsx    Recharts radial gauge
│   │   │   ├── ClaimRow.tsx      Expandable claim card with sources
│   │   │   └── VerdictChip.tsx   SUPPORTED / UNSUPPORTED / CONTRADICTED badge
│   │   └── pages/
│   │       ├── EvaluatePage.tsx
│   │       ├── ResultsPage.tsx   Full trust report with follow-up chat
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
- A free [Groq API key](https://console.groq.com)
- A free [Tavily API key](https://app.tavily.com)

### Setup

```bash
git clone https://github.com/VanshikaGurbani/SourceMD.git
cd SourceMD
cp backend/.env.example backend/.env
# Edit backend/.env and add your GROQ_API_KEY and TAVILY_API_KEY
```

### Run

```bash
# Start all 4 services
docker compose up --build

# In a second terminal, ingest the guideline corpus (one-time, ~2 minutes)
docker compose run --rm backend python -m backend.ingestion.ingest

# Open the app
# http://localhost:5173
```

Tables are created automatically on backend startup. The ingestion step is idempotent and safe to re-run.

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

### Example

```bash
curl -X POST http://localhost:8080/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the first-line drug for type 2 diabetes?",
    "ai_answer": "Metformin is first-line. Insulin is mandatory within 6 months of diagnosis."
  }'
```

---

## Guideline Corpus

| Document | Source | Topic |
|---|---|---|
| NICE NG28 | nice.org.uk/guidance/ng28 | Type 2 Diabetes Management |
| NICE NG136 | nice.org.uk/guidance/ng136 | Hypertension in Adults |
| NICE CG181 | nice.org.uk/guidance/cg181 | Cardiovascular Risk Assessment |
| AHA 2025 CPR/ECC Highlights | eccguidelines.heart.org | CPR and Emergency Cardiovascular Care |

Out-of-corpus queries (e.g. sepsis, plantar fasciitis) are handled by Tavily live web search against NIH, WHO, PubMed, Mayo Clinic, and other trusted domains.

---

## Environment Variables

All variables are set in `backend/.env` for local development. For production, set them directly in your hosting platform.

```env
# LLM -- at least one required
GROQ_API_KEY=gsk_...              # free at console.groq.com
ANTHROPIC_API_KEY=sk-ant-...      # optional fallback

# Web search
TAVILY_API_KEY=tvly-...           # free at app.tavily.com (1000/month)

# Auth
JWT_SECRET=change-me-to-a-long-random-string
JWT_EXPIRE_MINUTES=1440

# Set automatically by Docker Compose -- no need to change for local dev
DATABASE_URL=postgresql+psycopg2://sourcemd:sourcemd_dev_password@postgres:5432/sourcemd
CHROMA_HOST=chromadb
CHROMA_PORT=8000
FRONTEND_ORIGIN=http://localhost:5173
```
