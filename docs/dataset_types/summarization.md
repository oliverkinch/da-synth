# Dataset Type: Summarization

## Definition

`{document, summary}` pairs. Both fields are synthesised by the LLM: the seed text is used as topical inspiration to generate a natural Danish document, which is then summarised in a second LLM call. Neither field is copied from the seed. Seed rows exceeding `max_seed_chars` are skipped so the full generated document fits the prompt window and the summary genuinely covers the whole text.

## Quality Criteria

A high-quality summarization record satisfies all of the following:

- **Faithfulness**: the summary contains no information not present in the document. It does not hallucinate details or draw on external knowledge.
- **Coverage**: the summary captures the main point(s) of the document, not just the opening sentences.
- **Compression**: the summary is meaningfully shorter than the document. A summary that reproduces 80% of the source text is not a summary.
- **Coherence**: the summary reads as a self-contained text. It does not reference "the text above" or use pronouns without clear antecedents.
- **Danish fluency**: both document and summary are written in natural, idiomatic Danish with appropriate register.
- **Document naturalness**: the document reads as text originally written in Danish, not as translated or calqued prose.

## Known Pitfalls

- **Opening-sentence bias**: the summary covers only the first paragraph and ignores the rest of the document.
- **Faithfulness violation**: the summary introduces information not present in the document — common when the model draws on training knowledge rather than the document content.
- **Over-long summaries**: the model produces a near-full paraphrase rather than a genuine compression.
- **Calqued document**: the generated document reads as translated EU or academic prose rather than naturally written Danish.
- **Coherence break**: the summary refers to "ovenstående tekst" or uses "han/hun" without a clear antecedent.

---

## Golden Examples

---

### Example 1 — Factual article, prose summary

```json
{
  "document": "Grønland er verdens største ø med et areal på cirka 2,166 millioner kvadratkilometer, hvoraf omkring 80 procent er dækket af indlandsisen. Øen er en del af Kongeriget Danmark, men har siden 1979 haft hjemmestyre og siden 2009 selvstyre, hvilket betyder, at Grønland selv bestemmer over en lang række indenrigspolitiske områder. Befolkningen tæller godt 56.000 mennesker, og hovedstaden hedder Nuuk. Grønlands økonomi er i høj grad afhængig af fiskeri, særligt rejer og hellefisk, samt af bloktilskud fra den danske stat. Turisme og udvinding af naturressourcer som olie, gas og mineraler betragtes som vigtige vækstområder for fremtiden.",
  "summary": "Grønland er verdens største ø og en del af Kongeriget Danmark med vidtgående selvstyre siden 2009. Øens økonomi hviler primært på fiskeri og dansk bloktilskud, mens turisme og råstofudvinding ses som fremtidige vækstmotorer."
}
```

**Why this is a good record**: the summary is faithful (no invented details), covers the full document (geography, political status, economy, future prospects), and compresses it to roughly a third of the length. It reads as a self-contained text with no reference to "ovenstående tekst".

---

### Example 2 — Research finding, tight compression

```json
{
  "document": "Søvnmangel er et udbredt problem i den moderne verden og har en række dokumenterede konsekvenser for helbredet. Forskning viser, at voksne der sover under seks timer pr. nat over længere tid, har markant forhøjet risiko for hjerte-kar-sygdomme, type 2-diabetes og overvægt. Koncentrationsevnen falder allerede efter én nat med utilstrækkelig søvn, og reaktionstiden forringes på niveau med let beruselse. På det psykiske plan øger kronisk søvnmangel risikoen for angst og depression betydeligt. Søvnforskere anbefaler, at voksne sover syv til ni timer pr. nat, og at man opretholder faste sengetider også i weekenderne for at stabilisere kroppens døgnrytme.",
  "summary": "Kronisk søvnmangel øger risikoen for hjerte-kar-sygdomme, diabetes, overvægt, angst og depression og svækker koncentrationsevnen markant allerede efter én nat. Søvnforskere anbefaler syv til ni timers søvn pr. nat med faste sengetider."
}
```

**Why this is a good record**: covers all main points from the document (cardiovascular risk, diabetes/obesity, cognitive impairment, mental health, recommendations) and compresses faithfully into two sentences. No padding.

---

### Example 3 — Institutional topic, tight compression

```json
{
  "document": "Den danske model for arbejdsmarkedsrelationer bygger på tre søjler: organiserede arbejdsgivere, stærke fagforeninger og en tradition for kollektive overenskomster uden statslig indblanding. Systemet adskiller sig fra de fleste andre landes arbejdsmarkeder ved, at løn og arbejdsvilkår primært fastsættes gennem forhandlinger mellem arbejdsmarkedets parter frem for ved lovgivning. Til gengæld er der politisk opbakning til en fleksibel arbejdsmarkedslovgivning kombineret med generøse dagpengesatser — det såkaldte flexicurity-system.",
  "summary": "Den danske arbejdsmarkedsmodel hviler på trepartsforhandlinger uden statslig indblanding og kombinerer fleksibel ansættelseslovgivning med generøse dagpenge — det såkaldte flexicurity-system."
}
```

**Why this is a good record**: one sentence capturing the two defining features (negotiated model, flexicurity). No content outside the document, no padding.
