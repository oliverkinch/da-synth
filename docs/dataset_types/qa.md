# Dataset Type: Question Answering (QA)

## Definition

`{question, answer}` pairs. The question is a naturally-phrased Danish query; the answer is a direct, accurate response from general knowledge. Seed text is used at generation time to identify a general-knowledge fact and produce a naturalistic question, but neither the source text nor the fact itself appears in the output record. The answer must be answerable by a well-trained language model without access to any source document.

## Quality Criteria

A high-quality QA record satisfies all of the following:

- **Answer correctness**: the answer is factually correct and directly addresses the question asked.
- **Genuine open question**: the question is one the user is asking because they do not know the answer — not a confirmation or a rhetorical check.
- **No question leakage**: the question does not contain or paraphrase the answer. The answer must not be deducible from reading the question alone.
- **Question naturalness**: the question reads as something a person would actually ask, not as a cloze or fill-in-the-blank rewritten as a question.
- **Answer concision**: the answer gives what was asked for and stops. It does not pad with caveats or restate the question.
- **Danish fluency**: both question and answer are in natural, idiomatic Danish.

## Known Pitfalls

- **Confirmation questions**: the most common failure mode with casual phrasing. "Var det ikke Linda Blair, der spillede i Eksorcisten?" — the user is not asking because they don't know; they're asking for confirmation. This trains confirmation behaviour, not knowledge recall. The question must be genuinely open.
- **Question leakage**: the generated question contains the answer as a substring or close paraphrase. Check that the question cannot be answered by reading the question alone.
- **Context dependency**: the question only makes sense with the seed source text present ("hvad er den vigtigste pointe i teksten?"). The judge rejects these.
- **Trivial questions**: "Hvad er X?" where X is the topic of the seed text — too easy, trains nothing useful.
- **Answer padding**: the model restates the question before answering ("Det er et godt spørgsmål. Svaret på dit spørgsmål om...").
- **AI phrasing**: questions like "hvad er det mest bemærkelsesværdige ved X?" signal generation artefacts, not natural queries.

---

## Golden Examples

---

### Example 1 — Open-domain factual, Danish civic knowledge

```json
{
  "question": "Hvor mange medlemmer har Folketinget, og hvordan fordeler mandaterne sig geografisk?",
  "answer": "Folketinget har 179 medlemmer i alt. De 175 vælges i Danmark, mens Grønland og Færøerne hver bidrager med 2 mandater."
}
```

**Why this is a good record**: the question is genuinely open — the user does not supply the answer. It targets a specific numerical fact that cannot be deduced from the question itself. The answer is compact and addresses both parts without padding.

---

### Example 2 — Casual phrasing, geography

```json
{
  "question": "Hej, jeg sad lige og kiggede på nogle gamle kort over amerikanske jernbaner og undrede mig: hvilken strækning er egentlig den mest travle i USA, hvis man ser på antal passagerer?",
  "answer": "Det er Northeast Corridor, der løber langs østkysten fra Washington D.C. til Boston, som er den travleste jernbanestrækning i USA målt på passagertal."
}
```

**Why this is a good record**: the context-setting preamble ("jeg sad og kiggede på kort") is realistic and does not contain the answer. The question is open: the user does not know which corridor it is. Compare with the bad version: "var det ikke Northeast Corridor, der er den travleste?" — that is a confirmation question.

---

### Example 3 — Direct factual, Danish history

```json
{
  "question": "Hvornår fik kvinder stemmeret i Danmark?",
  "answer": "Kvinder fik stemmeret i Danmark ved grundlovsændringen i 1915."
}
```

**Why this is a good record**: terse and direct. The question is genuinely open and the answer is a single fact with no padding.

---

### Example 4 — Casual phrasing with task framing

```json
{
  "question": "Jeg sidder med en opgave og undrer mig – hvad hedder den halvø, der udgør den kontinentale del af Danmark?",
  "answer": "Den halvø hedder Jylland."
}
```

**Why this is a good record**: the casual framing ("sidder med en opgave") is natural; the answer is the single word the question is asking for — no padding.

---

### Example 5 — Multi-part factual

```json
{
  "question": "Hvad er det kemiske symbol for guld, og hvad stammer det fra?",
  "answer": "Symbolet er Au, som stammer fra det latinske ord 'aurum', der betyder guld."
}
```

**Why this is a good record**: the question has two parts and the answer addresses both concisely — no restatement of the question, no trailing caveats.
