# SourceMD

**Live demo: [source-md.vercel.app](https://source-md.vercel.app)**

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
   - Corrected, source-backed answer with clickable sources
   - Follow-up chat grounded in retrieved context
```

---

## Features

- **Claim-level fact-checking** — answers are broken into atomic claims, each verified independently
- **Real guideline citations** — evidence sourced from NICE NG28, NICE NG136, NICE CG181, and AHA 2025 CPR with page numbers
- **Live web augmentation** — Tavily searches trusted medical domains (NIH, WHO, NICE, AHA, PubMed) when the local corpus lacks relevant content, shown with a live web badge
- **Trust score** — 0-100 aggregate metric weighted by claim verdicts and confidence
- **Hallucination Rate and Source Coverage** — two metrics computed directly from pipeline output
- **Corrected answer** — a rewritten, source-grounded version of the original AI answer with clickable citations
- **Follow-up chat** — multi-turn Q&A grounded in retrieved guideline passages, persisted per evaluation
- **Evaluation history sidebar** — ChatGPT-style sidebar grouped by date, with rename and delete
- **Anonymous persistence** — evaluations saved to PostgreSQL without requiring an account; history lives in the browser, shareable by URL
- **Light/dark theme** — persisted to localStorage
- **Responsive** — works on mobile and desktop

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq `llama-3.3-70b-versatile` (primary) with Anthropic Claude as fallback |
| Agent framework | LangGraph `StateGraph` — 3-node linear pipeline |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) |
| Vector store | ChromaDB over HTTP, cosine similarity, ~844 guideline chunks |
| Web search | Tavily API (trusted medical domains only) |
| Backend | FastAPI, SQLAlchemy 2.0, PostgreSQL |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| Infrastructure | Railway (backend + DB + ChromaDB), Vercel (frontend) |

---

## Project Structure

```
sourcemd/
├── backend/
│   ├── main.py                   FastAPI app, CORS, router mounts
│   ├── config.py                 Pydantic settings from env vars
│   ├── api/routes/
│   │   ├── evaluate.py           POST /evaluate
│   │   ├── history.py            GET /history/{id}
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
│   │   └── cache/                PDF files committed to repo
│   ├── db/
│   │   ├── base.py               SQLAlchemy engine and session
│   │   └── models.py             Evaluation, Claim
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
│   │       └── HistoryPage.tsx
│   └── tailwind.config.js
├── docker-compose.yml
└── railway.toml
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | none | Liveness probe |
| `POST` | `/evaluate` | none | Run trust pipeline `{question, ai_answer}` |
| `GET` | `/history/{id}` | none | Full evaluation report by ID |
| `POST` | `/follow-up` | none | Chat turn `{question, original_question, ai_answer, corrected_answer, claims}` |

### Example

```bash
curl -X POST https://sourcemd-production.up.railway.app/evaluate \
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

Out-of-corpus queries are handled by Tavily live web search against NIH, WHO, PubMed, Mayo Clinic, and other trusted domains.

---

## Local Development

Requires Docker Desktop, a [Groq API key](https://console.groq.com), and a [Tavily API key](https://app.tavily.com).

```bash
git clone https://github.com/VanshikaGurbani/SourceMD.git
cd SourceMD
cp backend/.env.example backend/.env
# Add GROQ_API_KEY and TAVILY_API_KEY to backend/.env

docker compose up --build
docker compose run --rm backend python -m backend.ingestion.ingest
# Open http://localhost:5173
```
