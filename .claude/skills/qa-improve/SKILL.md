---
name: qa-improve
description: Iterative QA pipeline improvement loop. Generates ~20 samples, reviews judge verdicts, proposes concrete changes (rejection examples, regex patterns, prompt edits), applies them, and repeats. Use when the user wants to tune the QA generation pipeline.
---

## Goal

Build a high-quality Danish QA dataset. Every accepted sample will end up in the dataset, so the primary question at every step is: **are the accepted pairs actually good?** Reviewing rejections is secondary — it matters only insofar as the judge may be throwing away good pairs or letting bad ones through.

A good pair is:
- Written in natural Danish
- Self-contained — a stranger can answer it without the source text
- Timeless — the answer won't be wrong in a year
- Precise — the answer directly and unambiguously answers the question
- Genuinely informative — not a trivial or biography-style fact
- Single-focus — asks exactly one thing (e.g. not "Hvor mange X, og hvordan er Y?")

**The goal is a generation prompt so good the judge is rarely needed.** The judge is a safety net, not the primary quality mechanism. When you see repeated rejections, the right fix is almost always to improve `_PROMPT` or `_RETRY_PROMPT` so the generator stops producing those pairs in the first place — not to add more judge examples. Reach for the judge only for things the generator structurally cannot know, like whether an answer will still be true next year.

**A successful judge guides the retry to succeed.** When the judge rejects a pair, its reason is the *only* input the retry prompt gets. A good rejection reason is therefore specific and actionable: not just "tidsbundet" but "spørgsmålet refererer til 'i dag' — omformuler som historisk kendsgerning." If rejected pairs consistently fail the retry too, the judge reasons are probably too vague — fix the rejection examples to be more instructive, not stricter.

**Track the funnel at every iteration:**
- **Zero extraction** — model returned null for the article (generation prompt too restrictive, or genuinely barren)
- **First-pass accepted** — pairs the generator got right immediately
- **Retry accepted** — pairs the judge caught and the retry fixed (shows the judge reason was actionable)
- **Not accepted** — pairs neither pass could salvage (shows a structural generation problem or an unactionable judge reason)

A healthy pipeline has a high first-pass rate and, when rejections occur, a high retry success rate. A low retry success rate despite correct rejections means the judge reasons are not guiding the LLM effectively.

**Prefer simple, general improvements over accumulated guard rails.** If you find yourself wanting to add the fifth special case to a prompt, step back and ask whether a cleaner rewrite of the core instruction would handle all the cases at once. A prompt that grows one rule per iteration becomes fragile and hard to reason about.

You are running an iterative QA pipeline improvement loop. Follow these steps precisely.

## Step 1 — parse arguments

The user may pass arguments in any order, e.g. `/qa-improve configs/qa/danish_wikipedia.yaml --n-samples 100`.

- **Config path** — any argument that ends in `.yaml`. Default: `configs/qa/danish_wikipedia.yaml`.
- **`--n-samples N`** — how many accepted samples to generate. Default: `20`.

Derive output paths from the config stem, e.g. for `danish_wikipedia.yaml`:
- samples: `debug/qa/danish_wikipedia.jsonl`
- verdicts: `debug/qa/danish_wikipedia_verdicts.jsonl`

Create the `debug/qa/` directory if it does not exist: `mkdir -p debug/qa`.

## Step 2 — generate samples

Run:
```
synth-da generate --config <config> --n-samples <n-samples> --output <samples_path>
```

Wait for it to complete. The verdicts file (`<samples_stem>_verdicts.jsonl`) is written automatically.

## Step 3 — read and analyse

Read both files in full. Also read `assets/qa_rejection_examples.jsonl` and `src/synth_da/styles/qa.py` to understand the current judge prompt.

Count the zero-extraction records in the verdicts file — these have `"stage": "extraction"` and `"reason": "no_extraction"`. Note the `seed_text` snippets: are these genuinely fact-free articles, or articles with facts that the generation prompt is too restrictive to extract?

For every rejected pair (verdict: false), make your own independent judgement **before** reading the judge's reason. Ask: is this actually a bad QA pair — is it time-bound, does it require the source text, does it lack context for a stranger? Then compare your judgement with the judge's reason.

Apply the same critical eye to accepted pairs (verdict: true): are any of them actually bad?

## Step 4 — diagnose

Separate your findings into four buckets:

1. **Zero extraction** — model returned no pairs at all (`stage: "extraction"`). The current `_PROMPT` asks the generator to *always* attempt pairs and only return null for truly content-free articles. A high zero-extraction rate therefore indicates either genuinely barren articles (correct) or an overly restrictive `_PROMPT` (problem). Check the `seed_text` of zero-extraction records: are these articles that a human editor would also skip?
2. **False rejections** — judge rejected a good pair. Quote the pair and explain why it is in fact valid.
3. **Correct rejections** — judge was right. Note the pattern (time-bound, text-reference, missing context, etc.).
4. **False acceptances** — judge passed a bad pair. Quote the pair and explain the problem.

This tells you whether the judge is too strict, too lenient, or correctly calibrated — and whether the fix should loosen or tighten it.

## Step 5 — propose changes

For each problem, propose a concrete fix. Match the lever to the direction of error:

**Judge too strict (false rejections):**
- Remove or narrow an overly broad rejection example from `assets/qa_rejection_examples.jsonl`
- Clarify the judge prompt criteria in `_build_judge_prompt` to carve out the false rejection case

**Judge too lenient (false acceptances):**
- Add a rejection example to `assets/qa_rejection_examples.jsonl`

**Generation quality problems (bad pairs before judging, or zero extraction):**
- Edit `_PROMPT` or `_RETRY_PROMPT`
- Key constraints that belong in `_PROMPT` (not just the judge): self-containedness independent of other questions in the same batch ("Hvert spørgsmål skal kunne forstås og besvares uden kendskab til de andre spørgsmål i listen"), no text/article/film references, one question per fact, no compound questions
- If zero-extraction rate is high: the current `_PROMPT` has no skip list — check whether it has inadvertently become too restrictive in describing what kinds of facts are worth extracting. The generator should always try to produce its best 3 pairs; null is the last resort.
- The judge is the primary quality filter. The generator's job is to produce the best possible candidates; leave rejection to the judge. Avoid re-introducing skip lists into `_PROMPT` — they cause false zero-extractions for articles that do have extractable facts.

Show each proposed change as the exact text to add/remove/edit. Ask the user to confirm before applying.

## Step 6 — apply and iterate

Apply approved changes. Then ask:
> "Run another batch to validate the changes, or are you satisfied?"

If the user wants another round, clear the old output files and go back to Step 2.
If satisfied, summarise what changed across all iterations.

## Notes
- Never truncate your reading of the verdicts file — read every line.
- When proposing rejection examples, write them in the same JSON format as the existing file: `{"question": "...", "answer": "...", "reason": "..."}` with the reason in Danish.
- Be critical of accepted samples too — the goal is quality, not quantity.
- `language_check` should be `false` for QA configs — short answers are too brief for reliable Danish detection, and the judge enforces Danish implicitly.
- `max_tokens` for the judge is `len(pairs) * 200` — do not lower this; truncation causes silent false rejections with empty reasons.
- Low-value trivia (tracklist positions, running statistics, minor event logistics) should be addressed in the judge, not the generator — the current approach has no generator-side skip list. Add rejection examples for patterns the judge consistently misses.
