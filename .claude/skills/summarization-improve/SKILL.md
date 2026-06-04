---
name: summarization-improve
description: Iterative summarization pipeline improvement loop. Generates ~20 samples, reviews judge verdicts, proposes concrete changes (prompt edits, filter thresholds, temperatures), applies them, and repeats. Use when the user wants to tune the summarization generation pipeline.
---

## Goal

Build a high-quality Danish summarization dataset. Every accepted sample will end up in the dataset, so the primary question at every step is: **are the accepted document–summary pairs actually good?** Reviewing rejections is secondary — it matters only insofar as the judge may be throwing away good pairs or letting bad ones through.

A good pair satisfies all of:
- **Faithfulness**: the summary introduces no information absent from the document
- **Coverage**: the summary captures the main point(s) of the document, not just the opening sentences
- **Compression**: the summary is meaningfully shorter than the document (rough target: under 40% of document length)
- **Coherence**: the summary is self-contained — no "ovenstående tekst" references, no pronouns without clear antecedents
- **Danish fluency**: both document and summary are written in natural, idiomatic Danish
- **Document naturalness**: the document reads as originally-written Danish, not as translated or calqued prose

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
- Edit `_DOCUMENT_PROMPT` if documents are calqued or unnatural
- Edit `_SUMMARY_PROMPT` if summaries are unfaithful, biased toward opening sentences, or over-long
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
- When proposing rejection examples, write them in the format: `{"document": "...", "summary": "...", "reason": "..."}` with reason in Danish.
- Be critical of accepted samples too — the goal is quality, not quantity.
- A high retry recovery rate (most first-pass rejections pass on retry) is a good sign. A low rate means fix the generation prompt, not the judge.
- When a pattern only appears in one config, explicitly note that before proposing a fix — the fix must survive across all configs.
