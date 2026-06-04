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
- **Before diagnosing a "new" issue, check the Pipeline knowledge section.** If the issue is listed under "What's already fixed", it is a regression and the first question is: was the fix accidentally reverted?

## Pipeline knowledge

### Known failure modes

- **Latin-script foreign words in generated documents** (both configs): The model embeds English, German, Swedish, and French-influenced words into generated documents despite an explicit prohibition in `_DOCUMENT_PROMPT`. Observed vocabulary: "beyond", "swiftly", "successfully", "unfair", "already", "such", "piece", "initially", "tight", "active", "deployeres", "security", "social_balance", "committement", "corner", "Positive" (German-capitalized), "betalingsverkehrret" (corrupted German compound), "across", "av" (Swedish/Norwegian), "bereits", "financielle". EUR-LEX generates 10–14 contaminated documents per 20-sample run; nordjylland generates 4. Generation-level prohibition in `_DOCUMENT_PROMPT` has been in place since iteration 3 but has not reduced contamination rates. Judge correctly rejects the vast majority. Status: **persistent** — no generation-level fix found.
- **Judge inconsistency on retry when document is contaminated**: The judge sometimes passes a retry pair (new summary + same contaminated document) that it correctly rejected on first pass. This happens because seeing a clean summary distracts attention away from the still-contaminated document. Observed: "av" (line 22) and "across" (line 51) in EUR-LEX iteration 3. **Fix applied in iteration 4**: added two rejection examples that explicitly show clean summary + contaminated document = still reject. Status: **addressed** — examples added, validation pending.
- **Calque / word-choice failures in nordjylland documents**: Generator occasionally uses Danish words in English semantic roles (e.g. "rygning" as a calque for "backing"/"opbakning"). Judge catches these correctly under the "oversat eller kalket prosa" criterion; retries recover. Status: **open**.

### What's already fixed

- **`max_seed_chars` discarding instead of truncating** (`config.py`): `render_seed_text` was returning `None` for any document longer than `max_seed_chars`, silently starving eur-lex-sum (99.9% of its docs exceeded 4000 chars). Fixed to truncate instead of discard.
- **Non-Latin character leakage** (both configs): The Qwen model leaks CJK (Chinese), Cyrillic (Russian), and Arabic characters into generated Danish text. Fixed with `_NON_LATIN_RE = re.compile(r"[Ѐ-ӿ؀-ۿ　-ヿ一-鿿]")` applied pre-judge on both documents and summaries in `summarization.py`. The regex covers: Cyrillic U+0400–U+04FF, Arabic U+0600–U+06FF, CJK Symbols+Kana U+3000–U+30FF, CJK Unified U+4E00–U+9FFF.
- **Retry prompt not enforcing Danish** (`_RETRY_SUMMARY_PROMPT`): Retry summaries were repeating foreign words present in the (already-problematic) document. Added "udelukkende på korrekt dansk" to the retry prompt.
- **Summary prompt not enforcing Danish** (`_SUMMARY_PROMPT`): First-pass summaries contained English words ("compromise", "occupy", "alongside"). Added "og udelukkende" → "kortfattet og udelukkende på dansk". Result: nordjylland retry recovery went from 17% to 100%.
- **Judge criterion wording for foreign text**: Original criterion said "ikke-latinske tegn" which technically excluded Latin-script foreign words. Expanded to: "ikke-dansk tekst: ikke-latinske tegn (fx kinesiske, russiske, arabiske) eller fremmedsprogede ord der ikke er etablerede lånord i dansk".
- **Retry yield 0% due to document-level failures**: When the non-Latin filter was applied only to summaries (not documents), retries were triggered for document quality failures — a retry of the summary can never fix a broken document. Moving the document regex check before summary generation means retries only occur for genuine summary issues; retry recovery improved to 50–100%.
- **Judge missing English business vocabulary** (eur-lex): Judge passed documents containing "alarming", "rigorous", "successfully", "unfair". Fixed by creating `assets/summarization_judge_rejection_examples.jsonl` with 4 examples and loading them in `_build_judge_prompt` analogously to `qa.py`.
- **Document prompt lacking explicit vocabulary constraint**: `_DOCUMENT_PROMPT` only said "ikke som en oversættelse eller omskrivning" — did not explicitly prohibit English/German/French words. Added "Brug udelukkende korrekte danske ord — ingen engelske, tyske eller franske ord." (iteration 3). Note: this instruction did not measurably reduce contamination rates (14 rejections in iter 3 vs. 4 in iter 2 for EUR-LEX).
- **Judge missing retry false acceptances of document-level contamination**: Judge accepted pairs on retry where the document still contained foreign words ("av", "across") but the summary was clean. Fixed by adding two rejection examples that show clean summary + contaminated document = still reject (iteration 4).

### Dataset notes

- **eur-lex-sum** (`oliverkinch/eur-lex-sum`): EU legislative documents. Median raw length ~59k chars, truncated to 4000 chars for seed. Legal/formal register; generated documents frequently embed English technical vocabulary and occasionally Swedish/German words. Contamination rate is high: iteration 3 had 14/20 first-pass rejections (36% retry recovery for summary-level issues; 0% for doc-level). Retry recovery only works for summary-level failures; doc-level failures always fail retry.
- **nordjylland-news** (`alexandrainst/nordjylland-news-summarization`): Danish regional news articles. Raw articles ~1500–1900 chars; well within `max_seed_chars: 4000`. Colloquial register. Contamination pattern: common English idioms embedded mid-sentence ("such ildsjæle", "piece historien sammen", "initially var lunkne", "tight samarbejde"). ~4 contaminated documents per 20-sample run; 0% retry recovery when all rejections are doc-level.

### Judge calibration notes

- Overall well-calibrated. No false rejections observed across iterations 1–4.
- **EUR-LEX iteration 2 false acceptances** (fixed): Judge passed two documents with "successfully" and "unfair". Fixed by adding rejection examples.
- **EUR-LEX iteration 3 false acceptances** (fixed in iter 4): Judge passed two retry pairs where documents still had "av" and "across". Fixed by adding rejection examples that explicitly show clean summary + contaminated document = still reject.
- The judge's "opening-sentence bias" criterion fires correctly — summaries that only paraphrase the first paragraph are correctly rejected.
- The judge does not over-penalise compression: moderately short summaries that cover the full document pass reliably.
- EUR-LEX retry recovery at 0% (iteration 2) and 0% for doc-level failures is expected and correct — retries cannot fix a contaminated document. Only summary-level failures recover on retry (typically 3–5 such cases per 20-sample EUR-LEX run).
