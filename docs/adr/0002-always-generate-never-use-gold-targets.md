# ADR 0002 — Always generate target text; never use gold targets from seed datasets

**Status**: Accepted

## Context

Several seed datasets contain ready-made target text alongside their source:

- `oliverkinch/eur-lex` — real DA/EN parallel pairs from EU institutions
- `oliverkinch/eur-lex-sum` — official EU document summaries

The temptation is to use these directly: skip the LLM call, take the gold text as the target field. For translation specifically, one might also keep the seed source text as the `da` field and only generate the `en` side.

## Decision

Always generate the target text with the LLM. Use seed data as input only, never as output.

## Rationale

EU parallel text and official summaries are authoritative but often unnatural. EU legislative language is heavily influenced by French drafting conventions and frequently calqued into Danish and English. A model trained on this text learns stilted register. LLM-generated text, steered by quality criteria, produces output that reads as naturally written Danish or English — which is the goal of a language model training dataset.

Consistent generation also keeps the data distribution uniform across seed sources: a model trained on the dataset does not need to learn two different registers (gold-official vs. generated-natural) depending on which source the record came from.

## Alternatives considered

**Use gold targets directly** — zero LLM cost, authoritative accuracy. Rejected because naturalness matters more than provenance for language model training data.

**Use gold source, generate target** (translation only) — keep the seed DA text as-is, generate EN. Rejected because EU Danish prose is stilted; synthesising the DA side too produces more natural output on both sides.

**Use gold as a fallback** — generate when no gold exists, use gold when it does. Rejected because it produces a mixed distribution and adds branching complexity.

## Consequences

- Every record in the dataset is LLM-generated, including records seeded from datasets that already contain target text.
- The gold target columns in `eur-lex` and `eur-lex-sum` are used as a quality reference (for human review and judge prompts), not as output.
- Slightly higher LLM cost for datasets where gold was available.
