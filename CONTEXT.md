# CONTEXT.md — Danish Synthetic Dataset Generator

## Coding Conventions

- **Explicit keyword arguments**: always pass arguments by name at call sites — `f(x=x)` not `f(x)`. Applies to calls to all functions defined in this codebase. External library calls (e.g. `random.choice`, `asyncio.gather`) are exempt.

---

## Purpose

A Python repository for generating high-quality synthetic Danish datasets. Active dataset types: QA (`{question, answer}` pairs), Summarization (`{document, summary}` pairs), and Translation (`{da, en}` pairs). Data is generated using the Alexandra Institute inference server via the OpenAI client.

---

## Glossary

**Record**
A single output row. Schema varies by dataset type — see Output Format. Each record carries metadata fields (`run_id`, `seed_dataset`, `seed_config`, and optionally `source_id`) regardless of type.

**Dataset Type**
A category of synthetic dataset, each with its own schema, generation pipeline, prompt template, quality criteria, and seed dataset configuration(s). Active dataset types: `qa`, `summarization`, `translation`.

**General Knowledge Fact**
A fact extracted from a seed document that a competent Danish speaker could plausibly encounter in mainstream media, school education, or everyday life — and that a language model is therefore likely to have learned reliably enough to answer correctly without the source text present. The `qa` dataset type exclusively targets general knowledge facts: seed text is used at generation time to identify eligible facts and produce naturalistic questions, but neither the source text nor the fact itself appears in the final record. Facts that are too domain-specific, too technical, or too obscure to pass this bar are discarded rather than used as generation seeds.

**Dataset Type Doc**
A per-type markdown document (`docs/dataset_types/<type>.md`). Contains: definition, quality criteria, known pitfalls, and golden example records. Used for human review and the `/dataset_review` skill — never injected into generation prompts.

**Quality Criteria**
A plain-text description of what makes a high-quality record for a given dataset type. Distinct from golden examples (which live only in the dataset type doc).

**Seed Dataset**
A HuggingFace dataset used as source material for generation. Each seed dataset has a YAML config that maps its columns to the fields expected by the dataset type's prompt template.

**Dataset Config**
A YAML file under `configs/<type>/` that specifies: seed dataset, column mapping (via `text_template` or explicit `source_column`/`target_column`), and sampling parameters.

**Persona**
A synthetic Danish person profile used to diversify question phrasing and register in QA generation. Sourced from `oliverkinch/danish-personas` (HuggingFace Hub, 5 000 personas). Derived from `nvidia/Nemotron-Personas-USA` by translating the persona text to Danish and replacing US geographic fields with Danish equivalents. Fields: `uuid`, `name`, `persona`, `age`, `sex`, `occupation`, `education_level`, `hobbies_and_interests`, `city`, `zipcode`, `country`. Personas are a **soft diversity signal** in the generation prompt — they do not appear in the output record. Only `age` + free-text `persona` description are passed (not occupation or city, which tend to be quoted verbatim).

**Dataset Type Doc Review / `/dataset_review`**
A skill that loads the dataset type doc and a sample of generated records, performs side-by-side comparison against the golden examples, and flags records that diverge from quality criteria.

---

## Inference Server

```
OPENAI_BASE_URL=https://inference.alexandra.dk/v1
OPENAI_MODEL_NAME=qwen3.5-397b
```

Client: `openai` Python package.

---

## Seed Datasets

### General Danish text (dynaword subsets)
- `danish-foundation-models/danish-dynaword` — see [`docs/datasets/dynaword.md`](docs/datasets/dynaword.md) for subset selection, exclusion rationale, and dataset type assignments.

### Wikipedia
- `oliverkinch/danish_wikipedia` — 300k Danish Wikipedia articles (CC BY-SA 4.0, 2026-03-01 dump). Replaces the dynaword wikipedia subset. Fields: `url`, `title`, `text`.

### EU Legislation
- `oliverkinch/eur-lex` — bilingual DA+EN EU legislative documents from CELLAR (CC BY 4.0). Used for translation and as general seed text. Replaces any separate "cellar" dataset. Fields: `celex`, `resource_type`, `url`, `title_en`, `title_da`, `text_en`, `text_da`, `text_source_en`, `text_source_da`, `chars_en`, `chars_da`.
- `oliverkinch/eur-lex-sum` — 1,605 bilingual EU document + official summary pairs (CC BY 4.0). Primary seed for summarization.

### Academic
- `oliverkinch/doab-da` — 4 open-access Danish book chapters (CC BY 4.0). Fields: `text`, `title`, `authors`, `doi`, `url`, `date`, `license`.
- `oliverkinch/danish-university-portals` — 94 Danish university research publications, CC BY 4.0. Fields: `text`, `university`, `url`.

### Statistics
- `oliverkinch/danmarks-statistik` — Statistics Denmark data (public domain / Danish government open data).

---

## Dataset Config Schema

```yaml
task: qa | summarization | translation
seed_dataset: <hf_dataset_id>
seed_subset: <subset_name>
seed_split: train
# Column mapping (all types):
text_template: "## {title}\n\n{text}"   # Python .format() over column names
# OR single column shorthand:
text_column: text
# Generation parameters:
n_samples: 1000
persona_sampling: true      # QA only; ignored for other dataset types
max_seed_chars: 4000        # Summarization only; seed rows exceeding this are skipped
```

`text_template` and `text_column` are mutually exclusive. All dataset types use the same column mapping — translation no longer has `source_column`, `target_column`, or `direction`.

---

## Output Format

All output is JSONL, one record per line. Schema varies by dataset type:

**QA**
```json
{"question": "Hvornår fik kvinder stemmeret i Danmark?", "answer": "Ved grundlovsændringen i 1915.", "run_id": "abc123", "source_id": "https://da.wikipedia.org/?curid=...", "seed_dataset": "oliverkinch/danish_wikipedia", "seed_config": "configs/qa/danish_wikipedia.yaml"}
```

**Summarization**
```json
{"document": "...", "summary": "...", "run_id": "abc123", "source_id": "...", "seed_dataset": "oliverkinch/eur-lex-sum", "seed_config": "configs/summarization/eur_lex_sum.yaml"}
```

**Translation**
```json
{"da": "...", "en": "...", "run_id": "abc123", "source_id": "...", "seed_dataset": "oliverkinch/eur-lex", "seed_config": "configs/translation/eur_lex.yaml"}
```

---

## CLI

Built with `typer` + `rich` (progress display). Main commands:

```
uv run danish-sft generate --config configs/qa/danish_wikipedia.yaml [--concurrency 20]
uv run danish-sft generate-personas
uv run danish-sft translate-nemotron --n 10000
```

---

## Output / HuggingFace Hub

- One HuggingFace repo per dataset type: `oliverkinch/danish-qa`, `oliverkinch/danish-summarization`, `oliverkinch/danish-translation`
- **Behavior on repeated runs**: append (never overwrite). Each record includes a `run_id` metadata field for traceability.
- Source-level deduplication: on each run the output file is scanned for existing `source_id` values; rows already present in the output are skipped before generation begins.
- `source_id` is optional — only present when `source_id_column` is set in the dataset config.

---

## Generation Pipeline

- Async generation using `asyncio` + the OpenAI async client
- Concurrency controlled via `--concurrency` CLI flag (default: 20)
- Progress displayed with `rich`
- Each batch: sample seed rows → render seed text → call LLM → apply rule-based filters (+ binary judge for QA) → write Record to output JSONL
- The LLM always generates output fields. Seed datasets that contain gold targets (e.g. `eur-lex` parallel pairs, `eur-lex-sum` summaries) are used as input only — see ADR 0002.
- **QA**: one LLM call — extracts a general-knowledge fact and generates question + answer.
- **Summarization**: two LLM calls — first generate a natural document from the seed text, then summarize it. Both `document` and `summary` fields are synthesised; neither is copied from the seed. Seed rows exceeding a configurable character limit are filtered before generation so the generated document fits the prompt window.
- **Translation**: two LLM calls — first generate a natural Danish passage inspired by the seed text, then translate it to English. Both `da` and `en` fields are synthesised; neither is copied from the seed.

---

## Quality Filtering

Applied post-generation, before pushing to Hub. All thresholds are configurable per dataset type in the dataset config.

### Rule-based filters (always on)
1. **Language detection** — drop records where the generated text is not Danish (`lingua` library).
2. **Length filter** — drop records below a minimum token count. Threshold varies by dataset type (QA answers can be short; summaries should be substantial).
3. **Repetition filter** — drop records with high n-gram repetition in the generated text.

### LLM-as-judge (always on for QA)
- Binary pass/fail — rejects records that do not clear the quality bar, rather than scoring them.
- For `qa`: rejects if (1) the question can only be answered with access to the source text, (2) the question contains or paraphrases the answer, (3) the question is confirmation-seeking or leading, (4) the question uses AI phrasing ("hvad er det mest kendte faktum om…").
- Uses the same inference model at temperature 0.

### Known dataset-type-specific failure modes
- **QA**: question leakage — the generated question contains information from the answer. Caught by the binary judge.
- **QA**: context dependency — the question only makes sense with the source text present. Caught by the binary judge.
- **Summarization**: opening-sentence bias — the model summarizes only the first paragraph and ignores the rest of the document.
- **Summarization**: faithfulness violation — the summary introduces information not present in the source.
- **Translation**: calquing — preserving English syntactic structure in Danish rather than recasting naturally.
- **Translation**: register drift — translating formal text into informal Danish or vice versa.
- **General**: output in English instead of Danish (caught by language filter).
- **General**: truncated or degenerate output (caught by length + repetition filters).

---

## Dataset Type Doc Structure (`docs/dataset_types/<type>.md`)

- **Definition** — what this dataset trains / what it is for
- **Quality Criteria** — plain-text description of what makes a good record
- **Known Pitfalls** — common failure modes observed in generated records
- **Golden Examples** — 2–5 hand-curated records in the type's native schema

Dataset type docs are maintained by humans and updated via the `/dataset_review` skill. They are **never injected into generation prompts** (to preserve diversity).

---

## Persona Generation

Personas are preprocessed from `nvidia/Nemotron-Personas-USA` (CC BY 4.0):
1. Sample a subset (~5–10k personas)
2. Translate the `persona` text field to Danish using the inference server
3. Replace `city`/`state`/`zipcode` with Danish equivalents (from a curated list of Danish cities and postal codes)
4. Output: `assets/personas.jsonl`

Personas are injected as a soft diversity signal into the QA generation prompt: the generator is prompted to phrase the question as if it came from a person with the given profile. Personas do not appear in the output record.
