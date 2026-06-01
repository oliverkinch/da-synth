# ADR 0001 — Steer generation quality through few-shot examples, not negative rules

**Status**: Superseded — few-shot injection removed entirely; golden examples now live only in the style doc for human alignment. See conversation from 2026-06-01.

## Context

Early QA generation produced confirmation-seeking questions ("var det ikke Linda Blair, der spillede i Eksorcisten?"). The first fix added a negative pattern list to the generation prompt enumerating forbidden phrasings. This approach works for the specific patterns listed but has three failure modes:

1. **Accumulation** — every new failure mode adds another rule; prompts become noisy and hard to reason about.
2. **False precision** — listing `"var det ikke X?"` does not prevent `"er det ikke sandt at X?"` or adjacent forms the list missed.
3. **Overfitting** — the model avoids the listed strings but the underlying problem (confirming what the user already knows) is not addressed.

## Decision

Steer generation quality through a curated pool of few-shot examples injected into the generation prompt, not through negative pattern lists.

Concrete rules:
- Each style maintains a pool of golden examples under `assets/<style>_examples/`.
- One example is sampled randomly per generation call and injected into the prompt.
- Negative pattern lists ("IKKE X, IKKE Y") are not added to generation prompts.
- A single positive constraint is acceptable when it is a design requirement, not a workaround for observed behaviour (e.g. "spørgsmålet skal være ægte åbent" describes what we want; it is not a reaction to a specific failure mode).

## Alternatives considered

**Keep negative rules** — simple to add, but accumulates indefinitely and treats symptoms rather than causes.

**More golden examples in the prompt** — two or three examples steer more strongly but reduce output diversity. One example is enough to pattern-match good structure without over-constraining content.

## Consequences

- Prompts stay short and readable.
- Improving output quality means adding or replacing examples in `assets/`, not editing prompts.
- A failure mode that persists despite good examples signals a problem with the example pool or the fact extraction step, not the prompt rules.
