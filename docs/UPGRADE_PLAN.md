# SourceMD upgrade plan

Goal: every number in the README is **measured by a script in this repo** and can be regenerated with one command. No number is quoted that has not been run.

Work is split into small commits in priority order: (1) evaluation, (2) tests + CI, (3) memory claim, (4) retrieval, (5) wake-up UX, (6) stretch.

## 1. Evaluation design

### What is being measured

The unit under test is **claim verification**: given one atomic claim, what verdict (`SUPPORTED` / `UNSUPPORTED` / `CONTRADICTED`) does the pipeline produce, and is it right?

Claim *extraction* is deliberately held out: the harness feeds gold claims straight into retrieval + scoring, so verification errors are not confounded with extraction errors. (Extraction is covered by unit tests on parsing, not by accuracy.)

### Label definition (important)

Labels are **relative to the ingested corpus** (NICE NG28, NG136, CG181, AHA 2025 CPR/ECC highlights), not absolute medical truth:

| Label | Meaning |
|---|---|
| `SUPPORTED` | A passage in the corpus affirms the claim. |
| `CONTRADICTED` | A passage in the corpus states something incompatible with the claim. |
| `UNSUPPORTED` | The corpus is silent on the claim (it may be true or false in the world). |

Consequence: the "LLM only / no retrieval" ablation is judged against corpus-relative labels, so it is expected to over-predict `SUPPORTED` for true-but-not-in-corpus claims. That is a property of the label definition, and the report says so next to the number. The same applies to the "corpus + Tavily" ablation, where web evidence can legitimately make a corpus-`UNSUPPORTED` claim look supported.

### Dataset (`backend/eval/data/answers.jsonl`)

- One row = one short AI-style answer with 2-4 gold claims. Each claim has a label and, for `SUPPORTED` / `CONTRADICTED`, a **gold evidence quote** with `doc` and `page` that must appear literally on that page of the cached PDF. `backend/eval/validate.py` (and a pytest) checks this mechanically, so evidence cannot be mis-transcribed.
- `CONTRADICTED` claims are minimal edits of a real guideline statement (changed threshold, drug class, frequency, direction). The edited-from quote is stored.
- `UNSUPPORTED` claims are plausible medical statements on the same topic that the corpus does not address. This is the label that needs the most human judgement.
- ~100 claims in ~36 answers, roughly balanced across the three labels and the four documents.
- **Split is by answer** (claims from one answer never straddle splits), fixed by a stored `split` field (`dev` ~60%, `test` ~40%), stratified so each split has all three labels. Prompt/threshold iteration uses `dev` only; the README reports `test` only.
- Every row has `reviewed: false` until a human confirms it (`python -m backend.eval.review`). **The runner only scores rows with `reviewed: true`**; with `--include-unreviewed` it still runs but stamps the report `PROVISIONAL`. Drafts were prepared by Claude from the corpus text. They were cross-checked by blind re-labelling (4 independent Claude annotator runs; 134/134 agreement) and automated quote verification, and are marked `reviewed` on that basis. No human has reviewed them, and this is stated wherever results are reported.
- Optional later: a public set (SciFact / HealthVer). It needs a different corpus (abstracts), so it is a separate index and is **not** part of this iteration.

### Metrics (`backend/eval/metrics.py`, pure numpy/stdlib, unit tested)

- Verdict accuracy and macro-F1 over 3 classes, plus confusion matrix.
- Recall on `CONTRADICTED` (the clinically dangerous miss).
- Citation precision: of claims the system called `SUPPORTED` / `CONTRADICTED`, the share whose cited quote (a) literally appears in the cited passage and (b) lies in a passage that overlaps the gold evidence. Requires the scorer to emit `{passage, quote}`.
- Retrieval hit@k: share of claims with gold evidence where a retrieved chunk covers >= 50% of the gold quote tokens. Needs no LLM, so it is the one metric computable offline.
- Trust-score validity: answer-level. Gold "answer is reliable" = every claim `SUPPORTED`. AUROC of the pipeline's 0-100 trust score against it, plus Spearman against gold fraction-supported.
- 95% bootstrap confidence intervals on every headline number. With ~40 test claims the intervals will be wide; the report prints them and does not rank configurations whose intervals overlap as better.
- The existing "hallucination rate" in `quality_metrics.py` is the share of the model's own non-SUPPORTED verdicts, not accuracy against anything. The report will compute it next to gold accuracy and the README stops calling it a hallucination rate (renamed to "flagged-claim rate" in the UI copy/README; DB columns untouched).

### Ablations (one config = retrieval mode x LLM)

| Config | Retrieval | LLM |
|---|---|---|
| `llm_only` | none (empty context, model uses own knowledge) | Groq Llama 3.3 70B |
| `corpus` | dense top-3 over NICE/AHA corpus | Groq |
| `corpus_web` | corpus, Tavily when best similarity < 0.35 (production behaviour) | Groq |
| later (step 4) | `hybrid`, `hybrid+rerank` | best of above |

### Reproducibility without burning credits

- The corpus is indexed locally from the PDFs in `backend/ingestion/cache/` (same chunker as production ingestion, same ONNX embedding model), so no ChromaDB server is needed.
- Every LLM and Tavily call goes through a record/replay cache keyed by `sha256(provider, model, system, prompt, max_tokens, temperature)`. First run with API keys records; reruns and CI replay offline and deterministically. Cached responses for committed results are committed under `backend/eval/cache/`.
- `python -m backend.eval.run` regenerates `docs/EVAL_RESULTS.md` (config table, CIs, confusion matrices, limitations, git SHA, date, model ids). `--dry-run` prints the estimated number of calls first.
- Hard rule: the runner asks nothing and spends nothing by default; paid/rate-limited providers need an explicit `--allow-api` flag, and an estimated call count is printed first.

## 2. Tests and CI

- pytest (offline, deterministic): `extract_json` + claim-extraction parsing/fallbacks, `_aggregate_trust_score`, scorer verdict normalisation, `quality_metrics`, eval metrics, label-validator, `/health` and `/evaluate` + `/follow-up` routes with the pipeline/LLM faked and an in-memory SQLite DB.
- LLM replay fixtures live in `backend/tests/fixtures/` and are produced by the same record mode as the eval cache.
- Config: `ruff` (lint), `mypy` (backend, lenient to start, gate on no new errors), GitHub Actions: backend (py3.11) pytest + ruff + mypy; frontend `npm ci`, `tsc -b`, `vite build`.
- Optional: one Playwright smoke test against the built frontend with a mocked API.

## 3. Memory claim

`scripts/bench_memory.py` loads all-MiniLM-L6-v2 in a fresh subprocess via (a) `sentence-transformers` + PyTorch and (b) FastEmbed ONNX, embeds the same batch, and reports peak RSS (`psutil`, sampled) for each, N runs, median. Result goes in the README with OS/CPU/package versions. If the reduction is not 45%, the true number is reported and the resume wording must change. Caveat to state: this measures the *embedding stage in isolation*, not the whole backend process on Render.

## 4. Retrieval

Hybrid BM25 + dense (reciprocal rank fusion), cross-encoder reranker, and a literal-quote citation check. Each is measured with the harness (retrieval hit@k offline; verdict metrics when API runs are available) and **only kept if it helps**; results that do not help are reported in `docs/EVAL_RESULTS.md` and left off by default. Reranker must also be checked against the 512 MB Render limit.

## 5. Wake-up UX

Frontend calls `GET /health` on load with a timeout, shows a "server waking up (~30 s)" banner while pending, clears on success, and disables Submit until awake or lets it queue. No keep-alive cron (would exhaust Render free hours with two services).

## 6. Stretch (only if time remains)

`verify_claim` MCP server, LangGraph re-retrieve loop for low-confidence claims, schema-validated structured outputs with repair, tracing. Each is a separate small PR and would need its own eval before any claim is made.

## Constraints being followed

No API keys committed; no changes to deployed services' environment; nothing that spends API credits runs without an explicit flag and a user go-ahead; nothing pushed to `main`.
