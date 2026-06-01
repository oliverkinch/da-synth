# Style Guide: Question Answering (QA)

## Definition

Each sample is a `question`/`answer` pair. The question is a direct, open Danish question; the answer is a concise, self-contained fact. Seed text is used at generation time to identify a fact and produce a naturalistic question, but neither the source text nor any reference to it appears in the final sample.

## Quality Criteria

A high-quality QA sample satisfies all of the following:

- **Answer correctness**: the answer is factually correct and directly addresses the question asked.
- **Timelessness**: the answer does not depend on when it is read. Avoid facts that may change (current job titles, present-day locations, live statistics).
- **Self-contained answer**: the answer stands on its own without access to any source text. It must not contain phrases like "ifølge teksten" or "nævnt i artiklen".
- **No question leakage**: the question does not contain or paraphrase the answer. The answer must not be deducible from reading the question alone.
- **Question naturalness**: the question reads as something a person would actually ask, not as a cloze or fill-in-the-blank rewritten as a question.
- **Answer concision**: the answer gives what was asked for and stops. It does not pad with caveats or restate the question.
- **Danish fluency**: both question and answer are in natural, idiomatic Danish.

## Known Pitfalls

- **Time-bound answers**: "Hvad er X i dag?" or "Hvor arbejder X?" — the answer may be stale within months.
- **Source-dependent answers**: "Hvad nævner teksten som årsag til...?" — the answer is only meaningful alongside the source.
- **Birth facts**: "Hvor og hvornår blev X født?" — biographical trivia with low knowledge value.
- **Question leakage**: the generated question contains the answer as a substring or close paraphrase. Check that the question cannot be answered by reading the question alone.
- **Answer padding**: the answer restates the question before answering ("Det er et godt spørgsmål...").

---

## Golden Examples

---

### Example 1 — Historical fact

```json
{
  "question": "Hvilken hændelse den 3. februar 1825 ændrede Limfjorden fra en lukket fjord til et sund?",
  "answer": "En stormflod, der gennembrød Agger Tange."
}
```

**Why this is a good sample**: timeless historical fact, the answer is precise and fully self-contained, and the question cannot be answered without knowing the fact.

---

### Example 2 — Scientific definition

```json
{
  "question": "Hvad er definitionen på falske venner inden for sprogvidenskaben?",
  "answer": "Ordpar, der på to sprog eller dialekter minder om hinanden i udtale og/eller stavemåde, men har forskellig betydning."
}
```

**Why this is a good sample**: a stable definitional fact with a precise, compact answer. No time-sensitivity, no source reference.

---

### Example 3 — Danish history

```json
{
  "question": "Hvornår fik kvinder stemmeret i Danmark?",
  "answer": "Ved grundlovsændringen i 1915."
}
```

**Why this is a good sample**: terse and direct — the question is genuinely open and the answer is a single fact with no padding.

---

### Example 4 — Multi-part fact

```json
{
  "question": "Hvilke to klubber dannede overbygningen F.C. København?",
  "answer": "Kjøbenhavns Boldklub (KB) og Boldklubben 1903 (B 1903)."
}
```

**Why this is a good sample**: a specific factual question about Danish football history. The answer is timeless, enumerable, and self-contained.
