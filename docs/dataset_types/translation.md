# Dataset Type: Translation

## Definition

`{da, en}` pairs. Both fields are synthesised by the LLM: the seed text is used as topical inspiration to generate a natural Danish passage, which is then translated to English in a second LLM call. Neither field is copied from the seed. The primary translation direction is DA→EN (the `da` field is generated first), keeping the Danish side authoritative.

## Quality Criteria

A high-quality translation record satisfies all of the following:

- **Semantic fidelity**: every meaning present in the Danish text is present in the English translation. Nothing is added, omitted, or distorted.
- **Register preservation**: the English translation matches the register of the Danish original — formal stays formal, conversational stays conversational.
- **Naturalness**: the English reads as text originally written in English, not as a word-for-word rendering of Danish. Calqued syntax is a defect.
- **Terminology consistency**: domain-specific terms are translated using established English equivalents, not ad-hoc renderings.
- **Document naturalness (DA side)**: the Danish text reads as naturally written Danish, not as translated EU or institutional prose.
- **No explanatory additions**: the translation does not add commentary, footnotes, or clarifications.

## Known Pitfalls

- **Calquing**: preserving Danish syntactic structure in English, especially nominal chains or verb-final constructions.
- **Register drift**: the Danish source is informal but the English translation becomes formal, or vice versa.
- **False friends**: Danish "eventuelt" → English "eventually" (wrong; should be "possibly"). These are frequent failure modes in DA→EN.
- **Dropped or merged sentences**: the model silently omits a sentence or merges two, especially in longer passages.
- **Stilted DA side**: the generated Danish document reads as translated institutional prose rather than natural Danish.

---

## Golden Examples

---

### Example 1 — Factual prose, neutral register

```json
{
  "da": "Vindenergi spiller en stadig større rolle i Danmarks energiforsyning. I 2023 dækkede vindmøller over 55 procent af landets elforbrug, hvilket placerer Danmark blandt de lande i verden med den højeste andel af vindkraft i elproduktionen. Den store udbredelse skyldes dels gunstige geografiske forhold med lange kyststrækninger og høj gennemsnitlig vindhastighed, dels en langsigtet politisk satsning på vedvarende energi siden 1970'erne.",
  "en": "Wind energy plays an increasingly important role in Denmark's energy supply. In 2023, wind turbines covered more than 55 percent of the country's electricity consumption, placing Denmark among the world's leading nations in terms of wind power's share of electricity generation. This high penetration is due partly to favourable geographic conditions — long coastlines and high average wind speeds — and partly to a long-term political commitment to renewable energy dating back to the 1970s."
}
```

**Why this is a good record**: semantic fidelity is exact (all figures and causal factors preserved), register matches (neutral informational prose), "gunstige geografiske forhold" is rendered as "favourable geographic conditions" rather than calqued, and the Danish side reads as naturally written Danish.

---

### Example 2 — Institutional topic, formal register

```json
{
  "da": "Den Europæiske Centralbank har til opgave at opretholde prisstabilitet i euroområdet. Banken definerer prisstabilitet som en inflation tæt på, men under, to procent på mellemlang sigt, og anvender pengepolitiske instrumenter som renteændringer og opkøbsprogrammer til at nå dette mål. ECB er uafhængig af nationale regeringer og EU-institutioner og må ikke finansiere offentlige underskud.",
  "en": "The European Central Bank is mandated to maintain price stability in the euro area. The bank defines price stability as inflation close to, but below, two percent over the medium term, and uses monetary policy instruments such as interest rate adjustments and asset purchase programmes to achieve this objective. The ECB is independent of national governments and EU institutions and may not finance public deficits."
}
```

**Why this is a good record**: formal register is preserved throughout, established institutional terminology is used correctly ("pengepolitiske instrumenter" → "monetary policy instruments", "opkøbsprogrammer" → "asset purchase programmes"), and nothing is added or omitted.

---

### Example 3 — Conversational register

```json
{
  "da": "Jeg har faktisk aldrig forstået, hvorfor folk er så begejstrede for at stå op tidligt. Ja, man får lidt ekstra stille tid om morgenen, men til gengæld er man træt hele dagen. Jeg fungerer meget bedre om aftenen, når alle andre er gået i seng.",
  "en": "I've honestly never understood why people are so enthusiastic about getting up early. Sure, you get a bit of extra quiet time in the morning, but then you're tired for the rest of the day. I work much better in the evening, when everyone else has gone to bed."
}
```

**Why this is a good record**: casual register is preserved end-to-end ("faktisk" → "honestly", "ja" → "sure"), the translation reads as natural spoken English rather than a formal rendering, and no content is added or changed.
