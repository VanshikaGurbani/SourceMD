# Labelled claim set

`answers.jsonl`: one short AI-style answer per line with its gold claims.

- Labels are relative to the ingested corpus (see docs/UPGRADE_PLAN.md).
- `SUPPORTED` / `CONTRADICTED` claims carry a gold evidence quote (`doc`, `page`, `quote`) that `python -m backend.eval.validate` checks against the cached PDFs. `CONTRADICTED` claims are minimal edits of a real guideline statement.
- `UNSUPPORTED` claims are on-topic statements the corpus does not address (checked by keyword absence and reviewable via `python -m backend.eval.review`).
- `split` is fixed per answer (`dev` for iteration, `test` for reported numbers).
- Note: the file `NICE-CG181-Cardiovascular-Risk.pdf` is actually NICE NG238, which replaced CG181 in 2023; claims cite the doc by its repo name.
