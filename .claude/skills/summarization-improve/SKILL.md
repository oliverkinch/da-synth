---
name: summarization-improve
description: Iterative summarization pipeline improvement loop. Generates ~20 samples, reviews judge verdicts, proposes concrete changes (prompt edits, filter thresholds, temperatures), applies them, and repeats. Use when the user wants to tune the summarization generation pipeline.
---

## Goal

Build a high-quality Danish summarization dataset. Every accepted sample will end up in the dataset, so the primary question at every step is: **are the accepted document–summary pairs actually good?** Reviewing rejections is secondary — it matters only insofar as the judge may be throwing away good pairs or letting bad ones through.

The pipeline now uses **real source documents** — only the summary is synthesised. A good pair satisfies all of:
- **Faithfulness**: the summary introduces no information absent from the document
- **Coverage**: the summary captures the main point(s) of the document, not just the opening sentences
- **Compression**: the summary is meaningfully shorter than the document (rough target: under 40% of document length)
- **Coherence**: the summary is self-contained — no "ovenstående tekst" references, no pronouns without clear antecedents
- **Danish fluency**: the summary is written in natural, idiomatic Danish (the document may contain some English words or noise — that is fine and expected for real-world source texts)

**Prefer prompt simplification over accumulated rules.** If you find yourself adding a fifth special-case constraint to a prompt, step back and ask whether a cleaner rewrite of the core instruction handles all cases. A prompt that grows one rule per iteration becomes fragile and hard to reason about.

**Always evaluate all seed datasets together.** The prompts and judge in `summarization.py` are shared across all configs. Tuning against only one dataset risks overfitting — a change that fixes a nordjylland pattern may break eur-lex, and vice versa. Every iteration must generate from all configs in parallel and diagnose the pooled verdicts before proposing any change.

You are running an iterative summarization pipeline improvement loop. Follow these steps precisely.

## Step 1 — parse arguments

The user may pass arguments in any order, e.g. `/summarization-improve --n-samples 30`.

- **Config paths** — any arguments that end in `.yaml`. Default: **all YAML files in `configs/summarization/`** (run `ls configs/summarization/*.yaml` to enumerate them).
- **`--n-samples N`** — how many accepted samples to generate per config. Default: `20`.

Derive per-config output paths from each config's stem, e.g. for `nordjylland_news.yaml`:
- samples: `debug/summarization/nordjylland_news.jsonl`
- verdicts: `debug/summarization/nordjylland_news_verdicts.jsonl`

Create the output directory: `mkdir -p debug/summarization`.

## Step 2 — generate samples

Run all configs **in parallel** (multiple Bash tool calls in a single message):

```
synth-da generate --config <config> --n-samples <n_samples> --output <samples_path>
```

Wait for all to complete before proceeding. Each run writes its own verdicts file automatically.

## Step 3 — read and analyse

Read **all** verdict files in full. Also read `src/synth_da/styles/summarization.py` to understand the current prompts, temperatures, and judge criteria.

For every rejected pair (verdict: false) across all configs, make your own independent judgement **before** reading the judge's reason. Ask: is this actually a bad pair — does the summary introduce facts not in the document, does it only cover the opening, is it too long, does it self-reference? Then compare your judgement with the judge's reason.

Apply the same critical eye to accepted pairs (verdict: true) across all configs: are any of them actually bad?

## Step 4 — diagnose

Pool findings from all configs into three buckets:

1. **False rejections** — judge rejected a good pair. Note which config it came from, quote the pair, and explain why it is in fact valid.
2. **Correct rejections** — judge was right. Note the pattern (faithfulness violation, opening-sentence bias, over-long, coherence break, calqued document, etc.) and which config(s) show it.
3. **False acceptances** — judge passed a bad pair. Note which config it came from, quote the pair, and explain the problem.

Also note per-config retry yield: how many first-pass rejections recovered on retry? A high retry recovery rate means the judge is well-calibrated; a low rate means the underlying generation is the problem.

When patterns appear in only one config, ask whether the proposed fix would break or degrade the other configs. Only propose a change if it is neutral or beneficial across all datasets.

## Step 5 — propose changes

Match the lever to the direction of error:

**Judge too strict (false rejections):**
- Narrow an overly broad criterion in `_build_judge_prompt` in `src/synth_da/styles/summarization.py`

**Judge too lenient (false acceptances):**
- Tighten a criterion in `_build_judge_prompt`
- Add a rejection examples file `assets/summarization_judge_rejection_examples.jsonl` (format: `{"document": "...", "summary": "...", "reason": "..."}` with reason in Danish) and load it in `_build_judge_prompt` analogously to `qa.py`

**Generation quality problems (bad pairs before judging):**
- Edit `_SUMMARY_PROMPT` if summaries are unfaithful, biased toward opening sentences, over-long, or the original-summary anchor is causing paraphrase rather than genuine re-summarisation
- Edit `_RETRY_SUMMARY_PROMPT` if retries are not recovering well

**Filter-level problems:**
- Adjust `min_assistant_tokens` or `max_repetition_ratio` in the affected config YAML(s)

Show each proposed change as the exact text to add/edit/remove. Ask the user to confirm before applying.

## Step 6 — apply and iterate

Apply approved changes. Then ask:
> "Run another batch to validate the changes, or are you satisfied?"

If the user wants another round, delete all output files and go back to Step 2.
If satisfied, go to Step 7.

## Step 7 — update pipeline knowledge

After each session (whether one iteration or many), update the `## Pipeline knowledge` section of **this file** to reflect what was learned. This makes the next run smarter.

For each finding worth preserving, add or update an entry under the appropriate subsection:
- **Known failure modes** — patterns that cause bad generations or bad judge decisions; note which configs show them and whether they are fixed or still open.
- **What's already fixed** — changes already in the codebase; list them so they are never re-proposed.
- **Dataset notes** — quirks of individual seed datasets (typical length, language register, structural patterns) that should inform diagnosis.
- **Judge calibration notes** — observed false-rejection or false-acceptance tendencies; useful for knowing which direction to push when tuning.

Rules for updating:
- Write facts, not intentions. Record what you observed and what was done, not what you plan to do.
- Keep entries concise (1–3 lines each).
- If a known issue is resolved, move it from "Known failure modes" to "What's already fixed" rather than deleting it.
- Do not record ephemeral details (specific sample text, individual run statistics) — record patterns.

## Notes
- Never truncate your reading of any verdict file — read every line.
- When proposing rejection examples, write them in the format: `{"document": "...", "summary": "...", "reason": "..."}` with reason in Danish. The `document` field is kept for reference but only the `summary` and `reason` are shown to the judge.
- Be critical of accepted samples too — the goal is quality, not quantity.
- A high retry recovery rate (most first-pass rejections pass on retry) is a good sign. A low rate means fix the generation prompt, not the judge.
- When a pattern only appears in one config, explicitly note that before proposing a fix — the fix must survive across all configs.

## Pipeline knowledge

### Architecture (as of 2026-06-08)
- Real source documents are used directly — no synthetic document generation
- Only the summary is synthesised, conditioned on the real document + original summary as anchor
- Documents above `max_document_chars` are skipped (not truncated); nordjylland has no limit, EUR-LEX uses 800 000 chars
- Judge evaluates **summary quality only** — document noise (occasional English words, layout artefacts) is expected and acceptable
- Retry always attempted on judge rejection; skip only if reason is empty. Judge prompt now requires non-empty reason on rejection.
- Binary path is `.venv/bin/synth-da` (not `synth-da` in PATH)

### What's already fixed
- **EUR-LEX markdown formatting**: `da_summary` anchor caused model to produce `**bold headers**`. Fixed by adding "Skriv i løbende prosatekst — ingen overskrifter, ingen markdown-formatering" to both `_SUMMARY_PROMPT` and `_RETRY_SUMMARY_PROMPT`.
- **EUR-LEX external knowledge injection**: Model added future amendments, case law, precise dates not in document. Fixed by adding "Brug kun oplysninger der fremgår af det medfølgende dokument — tilføj ikke viden om EU-lovgivning, fremtidige ændringer, domme eller andre oplysninger fra din træning" to `_SUMMARY_PROMPT`.
- **Empty-reason retry guard**: Judge sometimes returned `{"verdict": false, "reason": ""}`, silently blocking retry. Fixed by adding "Ved afvisning er reason PÅKRÆVET — skriv altid en konkret begrundelse på 5–20 ord." to judge prompt output instruction.
- **Foreign-morphology rejection example**: Added example to `assets/summarization_judge_rejection_examples.jsonl` for "stands for" / "-ische" type errors (English/German morphology in otherwise Danish text).

### Known failure modes
- **Paraphrase of anchor**: if the model too closely copies the original summary anchor rather than re-summarising the document, the output adds little value. Watch for summaries nearly identical to the `summary_column` field.
- **Sports match hallucination (nordjylland)**: Live sports articles sometimes trigger faithfulness errors — model adds standings conclusions not stated in truncated documents. Both passes correctly reject these; this is a hard generation problem.
- **Date/number precision (EUR-LEX)**: Model sometimes computes or infers specific dates from vague time expressions in documents (e.g. "18 months after entry into force" → "januar 2015"). Judge correctly catches this. Retries reliably fix it.

### Dataset notes
- **nordjylland**: news articles, typically 800–2 500 chars. Original summaries are short (often 1–3 sentences). Documents are often truncated in the seed dataset — model must not hallucinate details from the missing portion.
- **EUR-LEX**: EU legal documents, 2 000–800 000 chars (after the skip filter). Original summaries can be multi-paragraph. Generated summaries should capture the legal purpose and key obligations. Paragraphs breaks in accepted summaries are fine for complex documents.

### Judge calibration notes
- Judge language sensitivity is well-calibrated: correctly catches "ermöglichte" (German), "causede" / "joinede" / "plight" (English), "rådmændene" (plural vs. singular), "Denpositive" (missing space), and hallucinated proper nouns.
- No false rejections observed across iters 3–4. Judge is not over-strict.
- Rejection examples file (`assets/summarization_judge_rejection_examples.jsonl`) has 3 entries: Norwegian word ("likestilling"), non-existent word ("Loiven"), English/German morphology in Danish ("stands for", "-ische").
- EUR-LEX retry recovery is routinely 100%; nordjylland ~80–90%. High retry recovery confirms judge calibration is good and generation is the bottleneck, not the judge.
