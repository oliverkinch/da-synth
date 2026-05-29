# Style Wiki: Question Answering (QA)

## Definition

The model is asked a question and produces a direct, accurate answer. QA covers two distinct sub-types:

- **Grounded QA**: a source passage is provided in the user message; the answer must be derived solely from that passage.
- **Open-domain QA**: no passage is provided; the model answers from knowledge.

Both sub-types appear in this dataset. The generation pipeline primarily produces grounded QA (seed text → generate question → generate answer), but open-domain questions are also generated using Wikipedia article content as the knowledge source without requiring the user to paste the article.

## Quality Criteria

A high-quality QA sample satisfies all of the following:

- **Answer correctness**: the answer is factually correct and directly addresses the question asked.
- **Groundedness** (for grounded QA): the answer contains no information beyond what is in the provided passage. The model does not supplement with external knowledge.
- **No question leakage**: the question does not contain or paraphrase the answer. "Hvad hedder den asteroide der blev opdaget af LINEAR-projektet den 11. september 1999 og midlertidigt navngivet 1999 RQ36?" is a leaking question — the answer is embedded in the question itself.
- **Question naturalness**: the question reads as something a person would actually ask, not as a cloze or fill-in-the-blank rewritten as a question.
- **Answer concision**: the answer gives what was asked for and stops. It does not reproduce large chunks of the source passage, pad with caveats, or answer a different question.
- **Danish fluency**: both question and answer are in natural, idiomatic Danish.

## Known Pitfalls

- **Question leakage**: the most common failure mode. The generated question contains the answer as a substring or close paraphrase. Check that the question cannot be answered by reading the question alone.
- **Trivial questions**: "Hvad handler teksten om?" — answerable without reading the passage, trains nothing useful.
- **Answer padding**: the model restates the question before answering ("Det er et godt spørgsmål. Svaret på dit spørgsmål om...").
- **Out-of-passage answers** (grounded QA): the model draws on world knowledge to supplement a thin passage instead of staying within the source.
- **Multi-question conflation**: the user asks one thing but the assistant answers a slightly different question.

---

## Golden Examples

---

### Example 1 — Wikipedia, open-domain factual QA

**Source**: `oliverkinch/danish_wikipedia`, article "'Ndrangheta"

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Hvad er 'ndrine, og hvilken rolle spiller de i 'Ndranghetaen?"
    },
    {
      "role": "assistant",
      "content": "'Ndrine (ental: 'ndrina) er de familieklaner, som 'Ndrangheta er struktureret omkring. Hver 'ndrina opererer relativt selvstændigt og kontrollerer typisk et bestemt geografisk område, men de koordinerer overordnet via et fælles råd. Den tætte familiebinding er en af hovedårsagerne til, at organisationen har vist sig meget svær at optrævle for myndighederne."
    }
  ]
}
```

**Why this is a good sample**: the question asks about a specific concept ('ndrine) that requires knowing the article — it cannot be answered from the question alone. The answer is precise, structured, and adds the explanatory consequence (how it affects law enforcement) without departing from what the source establishes.

---

### Example 2 — EUR-Lex, grounded QA with source passage

**Source**: `oliverkinch/eur-lex`, Lissabontraktaten (CELEX 12007L/TXT)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Du er en hjælpsom assistent. Svar altid på dansk, og basér dine svar udelukkende på den tekst, brugeren præsenterer."
    },
    {
      "role": "user",
      "content": "Læs venligst følgende uddrag fra Lissabontraktaten og besvar spørgsmålet nedenfor.\n\n---\n\nArtikel 1\n[...]\nUnionen afløser og efterfølger Det Europæiske Fællesskab.\n\nArtikel 9 F\nRådet vælger sin formand med kvalificeret flertal for en periode på to et halvt år, der kan fornyes én gang. I tilfælde af inhabilitet eller grov forseelse kan Det Europæiske Råd afsætte formanden ved kvalificeret flertal.\n[tekst forkortet]\n\n---\n\nHvordan vælges formanden for Det Europæiske Råd ifølge traktaten, og hvad er embedsperiodens varighed?"
    },
    {
      "role": "assistant",
      "content": "Ifølge traktaten vælges formanden for Det Europæiske Råd med kvalificeret flertal blandt rådets medlemmer. Embedsperioden er på to et halvt år og kan fornyes én gang, dvs. en formand kan maksimalt sidde i fem år. Rådet kan afsætte formanden ved kvalificeret flertal, hvis der er tale om inhabilitet eller grov forseelse."
    }
  ]
}
```

**Why this is a good sample**: the answer is fully grounded in the provided passage — no external knowledge is used. It correctly handles a two-part question (election procedure + term length) and adds the logical corollary (maximum total term) without departing from the source.

---

### Example 3 — Academic text (dynaword/tidsskrift), grounded QA, multi-sentence answer

**Source**: `danish-foundation-models/danish-dynaword`, subset `tidsskrift`, sports psychology article

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Baseret på nedenstående uddrag: hvilke genopladningsstrategier fandt forskerne mest effektive for U20-ishockeyspillerne?\n\n---\n\nResultaterne viste, at spillerne generelt oplevede et moderat stressniveau under lejren, men at individuelle forskelle var markante. De primære stressorer var konkurrenceangst, uklare rolleforventninger fra trænerens side samt social isolation fra familie og venner. Genopladningsstrategier der viste sig mest effektive var aktiv restitution, sociale aktiviteter med holdkammerater og strukturerede rutiner for søvn."
    },
    {
      "role": "assistant",
      "content": "Ifølge studiet var de mest effektive genopladningsstrategier aktiv restitution, sociale aktiviteter med holdkammerater samt strukturerede søvnrutiner."
    }
  ]
}
```

**Why this is a good sample**: the answer is a direct, single-sentence response to a specific question — no padding, no re-statement of the question, no information from outside the passage. The brevity is appropriate because the question is narrow and the passage gives a clear, enumerable answer.
