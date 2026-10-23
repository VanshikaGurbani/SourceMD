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
   - Flagged-claim rate % (share of claims the model did not call SUPPORTED)
   - Source Coverage %
   - Per-claim verdicts with rationale and citations
   - Corrected, source-backed answer with clickable sources
   - Follow-up chat grounded in retrieved context
```

---

## Features

- **Claim-level fact-checking** â€” answers are broken into atomic claims, each verified independently
- **Real guideline citations** â€” evidence sourced from NICE NG28, NICE NG136, NICE CG181, and AHA 2025 CPR with page numbers
- **Live web augmentation** â€” Tavily searches trusted medical domains (NIH, WHO, NICE, AHA, PubMed) when the local corpus lacks relevant content, shown with a live web badge
- **Trust score** â€” 0-100 aggregate metric weighted by claim verdicts and confidence
- **Flagged-claim rate and Source Coverage** â€” two descriptive metrics computed directly from pipeline output. The flagged-claim rate is the share of claims the model itself labelled UNSUPPORTED or CONTRADICTED; it is **not** a measured hallucination rate or an accuracy figure (see [Evaluation](#evaluation) for measured accuracy)
- **Corrected answer** â€” a rewritten, source-grounded version of the original AI answer with clickable citations
- **Follow-up chat** â€” multi-turn Q&A grounded in retrieved guideline passages, persisted per evaluation
- **Evaluation history sidebar** â€” ChatGPT-style sidebar grouped by date, with rename and delete
- **Anonymous persistence** â€” evaluations saved to PostgreSQL without requiring an account; history lives in the browser, shareable by URL
- **Light/dark theme** â€” persisted to localStorage
- **Responsive** â€” works on mobile and desktop

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq `openai/gpt-oss-120b` (primary; set `GROQ_MODEL` to change) with optional Anthropic failover (`LLM_FAILOVER=true`) |
| Agent framework | LangGraph `StateGraph` â€” 3-node linear pipeline |
| Embeddings | `all-MiniLM-L6-v2` (384-dim) served via FastEmbed (ONNX, CPU) |
| Vector store | ChromaDB over HTTP, cosine similarity, ~844 guideline chunks |
| Web search | Tavily API (trusted medical domains only) |
| Backend | FastAPI, SQLAlchemy 2.0, PostgreSQL |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| Infrastructure | Render (backend + ChromaDB), Neon (PostgreSQL), Vercel (frontend) |

---

## Project Structure

```
sourcemd/
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ main.py                   FastAPI app, CORS, router mounts
â”‚   â”œâ”€â”€ config.py                 Pydantic settings from env vars
â”‚   â”œâ”€â”€ api/routes/
â”‚   â”‚   â”œâ”€â”€ evaluate.py           POST /evaluate
â”‚   â”‚   â”œâ”€â”€ history.py            GET /history/{id}
â”‚   â”‚   â””â”€â”€ followup.py           POST /follow-up
â”‚   â”œâ”€â”€ agents/
â”‚   â”‚   â”œâ”€â”€ graph.py              LangGraph StateGraph wiring
â”‚   â”‚   â”œâ”€â”€ state.py              PipelineState, ScoredClaim TypedDicts
â”‚   â”‚   â”œâ”€â”€ llm.py                Groq/Anthropic client with JSON extractor
â”‚   â”‚   â”œâ”€â”€ embeddings.py         FastEmbed (ONNX) singleton
â”‚   â”‚   â”œâ”€â”€ chroma_client.py      ChromaDB HTTP client with cold-start retry
â”‚   â”‚   â”œâ”€â”€ quality_metrics.py    Flagged-claim rate and source coverage metrics
â”‚   â”‚   â””â”€â”€ nodes/
â”‚   â”‚       â”œâ”€â”€ claim_extractor.py
â”‚   â”‚       â”œâ”€â”€ retriever.py      ChromaDB + Tavily augmentation
â”‚   â”‚       â””â”€â”€ scorer.py         Verdict scoring, trust score, correction prompt
â”‚   â”œâ”€â”€ ingestion/
â”‚   â”‚   â”œâ”€â”€ sources.py            Guideline registry (name, url, tag)
â”‚   â”‚   â”œâ”€â”€ ingest.py             Download, chunk, embed, upsert pipeline
â”‚   â”‚   â””â”€â”€ cache/                PDF files committed to repo
â”‚   â”œâ”€â”€ db/
â”‚   â”‚   â”œâ”€â”€ base.py               SQLAlchemy engine and session
â”‚   â”‚   â””â”€â”€ models.py             Evaluation, Claim
â”‚   â””â”€â”€ schemas/                  Pydantic v2 request and response models
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ api/                  Axios client and typed endpoint wrappers
â”‚   â”‚   â”œâ”€â”€ context/              ThemeContext (light/dark)
â”‚   â”‚   â”œâ”€â”€ components/
â”‚   â”‚   â”‚   â”œâ”€â”€ EvalSidebar.tsx   History sidebar with rename and delete
â”‚   â”‚   â”‚   â”œâ”€â”€ TrustGauge.tsx    Recharts radial gauge
â”‚   â”‚   â”‚   â”œâ”€â”€ ClaimRow.tsx      Expandable claim card with sources
â”‚   â”‚   â”‚   â””â”€â”€ VerdictChip.tsx   SUPPORTED / UNSUPPORTED / CONTRADICTED badge
â”‚   â”‚   â””â”€â”€ pages/
â”‚   â”‚       â”œâ”€â”€ EvaluatePage.tsx
â”‚   â”‚       â”œâ”€â”€ ResultsPage.tsx   Full trust report with follow-up chat
â”‚   â”‚       â””â”€â”€ HistoryPage.tsx
â”‚   â””â”€â”€ tailwind.config.js
â””â”€â”€ docker-compose.yml
```

---

## Deployment

The live app runs entirely on free tiers:

| Piece | Host | Notes |
|---|---|---|
| Frontend | Vercel | Set `VITE_API_URL` to the backend URL. `frontend/vercel.json` rewrites all routes to `index.html`. |
| Backend | Render (Docker web service) | Dockerfile path `./backend/Dockerfile`, build context `.` (repo root), port 8080. |
| Vector store | Render (ChromaDB image) | Reached over HTTPS, so set `CHROMA_PORT=443`. |
| Database | Neon (serverless PostgreSQL) | Tables are created on startup, so no migration step is needed. |

Backend environment variables: `DATABASE_URL` (Neon connection string with `sslmode=require`), `CHROMA_HOST`, `CHROMA_PORT`, `FRONTEND_ORIGIN`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `JWT_SECRET`.

Notes:
- Ingestion is too memory-hungry for a 512 MB instance. Run it locally in the compose backend container with `CHROMA_HOST` and `CHROMA_PORT` overridden to point at the remote ChromaDB.
- Free Render services sleep after 15 minutes idle. The first request afterwards can take 30 to 60 seconds, and the backend retries its ChromaDB connection with backoff while the service wakes.

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
curl -X POST https://sourcemd-backend.onrender.com/evaluate \
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

## Memory footprint (ONNX vs PyTorch embeddings)

`scripts/bench_memory.py` loads `all-MiniLM-L6-v2` in a fresh subprocess, embeds 64 sentences, and reports the process's peak resident memory. Median of 5 runs after a warm-up (raw data in `docs/bench/`):

| Embedding stack | Linux container, Python 3.11 (peak RSS) | Windows 11 (peak RSS) |
|---|---|---|
| `sentence-transformers` + PyTorch 2.14 (CPU) | 526 MB | 498 MB |
| FastEmbed 0.3.6 + ONNX Runtime 1.31 | 247 MB | 220 MB |
| Reduction | **53%** | 56% |

The Linux run (Docker `python:3.11-slim` on WSL2, both stacks on the same Python) is the closer proxy for Render. Limitations: it covers import + model load + one batch, not the whole FastAPI process, and it is not Render's own container. The figure "45%" that appeared in earlier project descriptions was not produced by anything in this repo; the measured figure is about 53%.

Reproduce: `python scripts/bench_memory.py --python-torch <py with sentence-transformers> --python-onnx <py with fastembed>`.
---|---|
| `sentence-transformers` 5.1.1 + PyTorch 2.14 (CPU) | 498 |
| FastEmbed 0.3.6 + ONNX Runtime 1.31 | 220 |

That is a **56% reduction** for the embedding stage. Limitations: measured on Windows 11 (torch under Python 3.13, FastEmbed under Python 3.11), not on the Render Linux container; it covers import + model load + one batch, not the whole FastAPI process. The figure "45%" that appeared in earlier project descriptions was not produced by anything in this repo.

Reproduce: `python scripts/bench_memory.py --python-torch <py with sentence-transformers> --python-onnx <py with fastembed>`.

---

## Evaluation

Design and label definitions: [docs/UPGRADE_PLAN.md](docs/UPGRADE_PLAN.md). Full tables (confusion matrices, per-class scores, trust-score validity): [docs/EVAL_RESULTS.md](docs/EVAL_RESULTS.md). Everything is regenerated by `python -m backend.eval.run`; model outputs are replayed from `backend/eval/cache/calls.jsonl`, so reruns are free and deterministic.

**Setup.** 134 labelled claims in 48 short answers, labelled against the four ingested guidelines (`SUPPORTED` / `UNSUPPORTED` = corpus silent / `CONTRADICTED`). Split by answer into dev (iteration) and test (reported here: 20 answers, 57 claims). Gold claims are fed straight into retrieval + scoring, so this measures verification, not claim extraction. LLM: Groq `openai/gpt-oss-120b`.

**Verdict accuracy, test split** (95% bootstrap intervals in brackets):

| Configuration | Accuracy | Macro-F1 | CONTRADICTED recall | Trust-score AUROC |
|---|---|---|---|---|
| LLM only, no retrieval | 0.61 [0.49, 0.74] | 0.52 | 0.82 | 0.85 [0.59, 1.00] |
| Corpus, dense top-3 (production) | 0.83 [0.74, 0.91] | 0.81 | 0.76 | 0.98 [0.89, 1.00] |
| Corpus + Tavily web (production behaviour) | 0.81 [0.70, 0.90] | 0.80 | 0.76 | 0.98 [0.89, 1.00] |
| Corpus, hybrid BM25 + dense | 0.84 [0.74, 0.93] | 0.82 | 0.59 | 0.97 [0.86, 1.00] |

What this supports: retrieval over the guideline corpus clearly beats the bare LLM (0.83 vs 0.61, intervals do not overlap), and the 0-100 trust score ranks fully-supported answers above flawed ones well (AUROC 0.98 over 20 test answers). What it does not support: web augmentation and hybrid retrieval are not distinguishable from plain dense retrieval on verdict accuracy, and hybrid lowers recall on CONTRADICTED claims (7 of 17 called UNSUPPORTED instead), so **hybrid stays off by default**. The web path fired for only 1 of 57 claims, so that comparison says little.

**Citations** (corpus configs): the quote the model cites literally appears in the passage it cites for 97% of committed verdicts; 83% [0.69, 0.94] cite a passage that also contains the gold evidence.

**Retrieval alone** (no LLM; share of claims with gold evidence whose gold sentence is in the top-3 chunks; n=103 across dev + test): dense 0.78 [0.70, 0.85], BM25 0.88 [0.82, 0.94], hybrid 0.92 [0.86, 0.97], hybrid + cross-encoder rerank 0.91 [0.85, 0.96]. Hybrid finds the right passage more often but did not turn that into better verdicts here; the reranker added nothing and is eval-only. Hybrid is available behind `HYBRID_RETRIEVAL=true`.

**Limitations (read before quoting any number).**
- Small test set (57 claims, 20 answers): intervals are wide and gaps of a few points are noise.
- **No human reviewed the labels.** The claims were drafted by Claude from the corpus text, then cross-checked by four independent blind re-labelling runs by Claude (134/134 agreement) and mechanical quote verification. Same model family, so shared blind spots are possible, and the claims are cleaner than real LLM output, so absolute accuracy is probably optimistic.
- Labels are relative to the corpus, not to medical truth: the no-retrieval baseline is penalised when it says SUPPORTED for true statements the corpus does not contain.
- Retrieval claims were written from the gold sentences, which favours lexical retrieval.
- The deployed model before this work (`llama-3.3-70b-versatile`) is no longer served by Groq; these numbers are for the current default.
## Testing and CI

- `pytest` (90 offline tests, no API keys, no network): JSON extraction, claim-extraction fallbacks, verdict parsing, trust-score aggregation, quality metrics, the call cache, citation check, eval metrics and dataset integrity, and the API routes (in-memory SQLite, pipeline faked). LLM responses used by the tests are canned fixtures keyed by the real request hash (`backend/tests/fixtures/`), not recordings of a live model.
- `ruff check .`, `mypy`, and the frontend `npm run build` (tsc + vite) run in GitHub Actions (`.github/workflows/ci.yml`).

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
