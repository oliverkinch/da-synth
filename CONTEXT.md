# CONTEXT.md — Danish Synthetic Instruction Data Generator

## Purpose

A Python repository for generating high-quality synthetic Danish instruction-finetuning data (supervised finetuning / SFT). All output is in **messages format** (OpenAI chat style). Data is generated using the Alexandra Institute inference server via the OpenAI client.

---

## Glossary

**Sample**
A single training example. Always in messages format:
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```
Optionally includes a system message as the first turn.

**Style**
A task category defining the type of instruction-following a sample trains. Each style has its own generation pipeline, prompt template, quality criteria, and seed dataset configuration(s). Active styles: `qa`, `summarization`, `translation`, `grounded`.

**General Knowledge Fact**
A fact extracted from a seed document that a competent Danish speaker could plausibly encounter in mainstream media, school education, or everyday life — and that a language model is therefore likely to have learned reliably enough to answer correctly without the source text present. The `qa` style exclusively targets general knowledge facts: seed text is used at generation time to identify eligible facts and produce naturalistic questions, but neither the source text nor the fact itself appears in the final sample. Facts that are too domain-specific, too technical, or too obscure to pass this bar are discarded rather than used as generation seeds.

**Style Doc**
A per-style markdown document (`docs/styles/<style>.md`). Contains: definition, quality criteria, known pitfalls, and golden example samples. Used for human review and the `/dataset_review` skill — never injected into generation prompts.

**Quality Criteria**
A plain-text description of what makes a high-quality sample for a given style. Stored in the style's YAML config and injected into generation prompts. Distinct from golden examples (which live only in the style doc).

**Seed Dataset**
A HuggingFace dataset used as source material for generation. Each seed dataset has a YAML config that maps its columns to the fields expected by the style's prompt template.

**Dataset Config**
A YAML file under `configs/<style>/` that specifies: seed dataset, column mapping (via `text_template` or explicit `source_column`/`target_column`), sampling parameters, and persona/system prompt rates.

**Persona**
A synthetic Danish person profile used to diversify question style and framing. Derived from `nvidia/Nemotron-Personas-USA` by translating the persona text to Danish and replacing US geographic fields with Danish equivalents (city, postal code). Personas are used as a soft diversity signal in the *generator prompt* (not as system prompts in the output sample). Stored as a preprocessed `personas.jsonl` asset.

**System Prompt Rate**
The fraction of generated samples that include a system prompt as the first message. Set per dataset config. Reflects the real-world mix of deployments with and without system prompts.

**Style Doc Review / `/dataset_review`**
A skill that loads the style doc for a given style and a sample of generated outputs, performs side-by-side comparison against the golden examples, and flags samples that diverge from quality criteria.

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
- `danish-foundation-models/danish-dynaword` — see [`docs/datasets/dynaword.md`](docs/datasets/dynaword.md) for subset selection, exclusion rationale, and style assignments.

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

### Translation source (English high-quality)
- `allenai/Dolci-Instruct-SFT` — 2.15M samples (ODC-BY 1.0, commercially usable). Already in messages format. Fields: `id`, `messages`, `source_dataset`, `domain`. Filter out `source_dataset` values containing "Precise IF" before translating (verifiable format constraints break on translation). The `domain` field (Math, Coding, Science, Safety, Other, Multilingual) allows targeted subset selection. The Aya subset (~100k, Apache 2.0) is multilingual — check for existing Danish samples before translating. Safety domain (WildGuardMix, WildJailbreak, CoCoNot) is particularly valuable as a source of Danish refusal training data.

---

## Dataset Config Schema

```yaml
task: qa | summarization | translation
seed_dataset: <hf_dataset_id>
seed_subset: <subset_name>
seed_split: train
# For single or merged columns:
text_template: "## {title}\n\n{text}"   # Python .format() over column names
# OR single column shorthand:
text_column: text
# For translation only:
source_column: en_document
target_column: da_document
direction: en->da
# Generation parameters:
n_samples: 1000
persona_sampling: true
system_prompt_rate: 0.6
```

`text_template` and `text_column` are mutually exclusive. Translation configs use `source_column`/`target_column` instead.

---

## Output Format

JSONL, one sample per line:
```json
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```
System message is omitted in samples where `system_prompt_rate` sampling excludes it.

---

## CLI

Built with `typer` + `rich` (progress display). Main commands:

```
uv run danish-sft generate --config configs/qa/danish_wikipedia.yaml [--concurrency 20] [--judge]
uv run danish-sft generate-personas
uv run danish-sft translate-nemotron --n 10000
```

---

## Output / HuggingFace Hub

- **Dataset repo**: `oliverkinch/danish-sft`
- **One subset per style**: `qa`, `summarization`, `translation`
- **Behavior on repeated runs**: append (never overwrite). Each sample includes a `run_id` metadata field for traceability.
- Each sample schema:
  ```json
  {
    "messages": [...],
    "run_id": "abc123",
    "style": "qa",
    "seed_dataset": "oliverkinch/danish_wikipedia",
    "seed_config": "configs/qa/danish_wikipedia.yaml",
    "source_id": "https://da.wikipedia.org/?curid=12345"
  }
  ```
  `source_id` is optional — only present when `source_id_column` is set in the dataset config.

---

## Generation Pipeline

- Async generation using `asyncio` + the OpenAI async client
- Concurrency controlled via `--concurrency` CLI flag (default: 20)
- Progress displayed with `rich` (overall samples + current batch)
- Each batch: sample seed rows → sample personas (if enabled) → render prompt → call LLM → apply filters → collect

---

## Quality Filtering

Applied post-generation, before pushing to Hub. All thresholds are configurable per style in the dataset config.

### Rule-based filters (always on)
1. **Language detection** — drop samples where the assistant response is not Danish (`lingua` library preferred over `langdetect` for accuracy).
2. **Length filter** — drop samples where the assistant response is below a minimum token count. Threshold varies by style (QA answers can be short; summaries should be substantial).
3. **Repetition filter** — drop samples with high n-gram repetition in the assistant response.

### LLM-as-judge (optional, `--judge` flag)
- Scores each sample 1–5 using an anchored rubric defined per style.
- Uses the same inference model (known limitation: self-serving bias, scores will cluster high). A different/stronger judge is preferable if available in future.
- Score and short reasoning are stored as metadata fields (`judge_score`, `judge_reasoning`) on each sample.
- Does **not** gate the push — all samples are pushed regardless of score. Score is used for post-hoc analysis and threshold setting.
- The `/dataset_review` skill plots the score distribution to help determine a cut-off.

### Known style-specific failure modes
- **QA**: question leakage — the generated question contains information from the answer. Flag in the QA style doc; consider a leakage-detection heuristic.
- **Grounded**: disguised summarization — the generated instruction asks for "the main points" or "an overview", producing a sample that belongs in the `summarization` style instead. Caught by steering the generation prompt away from compression instructions.
- **Grounded**: source text too short — a single sentence or very short passage produces trivial samples. Filter seed rows by minimum token count before generation.
- **General**: responses in English instead of Danish (caught by language filter).
- **General**: truncated or degenerate responses (caught by length + repetition filters).

---

## Style Doc Structure (`docs/styles/<style>.md`)

- **Definition** — what this style trains
- **Quality Criteria** — plain-text description of what makes a good sample
- **Known Pitfalls** — common failure modes observed in generated samples
- **Golden Examples** — 2–5 hand-curated samples in messages format

Style docs are maintained by humans and updated via the `/dataset_review` skill. They are **never injected into generation prompts** (to preserve diversity).

---

## Persona Generation

Personas are preprocessed from `nvidia/Nemotron-Personas-USA` (CC BY 4.0):
1. Sample a subset (~5–10k personas)
2. Translate the `persona` text field to Danish using the inference server
3. Replace `city`/`state`/`zipcode` with Danish equivalents (from a curated list of Danish cities and postal codes)
4. Output: `assets/personas.jsonl`

Personas are used as a **soft diversity signal** in generation prompts (option B): the generator is prompted to produce a question/task as if it came from a person with the given profile. Personas do not appear in the final training sample.
