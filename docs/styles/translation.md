# Style Wiki: Translation

## Definition

The model is given a text in one language and asked to produce an equivalent text in another language, preserving meaning, register, and structure. The primary direction is EN→DA (to generate Danish training data from English sources), with DA→EN as secondary.

Translation in this dataset is grounded: the source text is always provided in the user message. The model is not asked to translate from memory.

## Quality Criteria

A high-quality translation sample satisfies all of the following:

- **Semantic fidelity**: every meaning present in the source is present in the translation. Nothing is added, omitted, or distorted.
- **Register preservation**: formal source text → formal Danish; casual source text → casual Danish. EU legislative language stays legislative; conversational language stays conversational.
- **Naturalness**: the translation reads as text originally written in the target language, not as a word-for-word rendering. Calqued syntax ("Det er vigtigt at notere at..." for "It is important to note that...") is a defect.
- **Terminology consistency**: domain-specific terms (legal, medical, technical) are translated consistently using established Danish equivalents, not ad-hoc renderings.
- **No explanatory additions**: the translation does not add the model's own commentary, footnotes, or clarifications. It translates, nothing more.
- **Danish orthographic correctness**: correct use of Danish characters (æ, ø, å), capitalisation rules (Danish does not capitalise nouns), and punctuation norms.

## Known Pitfalls

- **Register drift**: translating formal EU text into informal Danish, or vice versa.
- **Calquing**: preserving English syntactic structure in Danish, especially nominal chains ("the high-level representative for foreign affairs and security policy" → "den højtstående repræsentant for udenrigsanliggender og sikkerhedspolitik" is correct; "den høj-niveau repræsentant" is calqued).
- **False friends**: English "eventually" → Danish "eventuelt" (which means "possibly", not "til sidst"). These are frequent failure modes.
- **Dropped or merged sentences**: the model silently omits a sentence or merges two, especially in long passages.
- **Over-literal proper nouns**: some proper nouns should be translated (e.g. "The European Parliament" → "Europa-Parlamentet"), others should not ("the Treaty of Lisbon" → "Lissabontraktaten" is correct; translating "Lisbon" to "Lissabon" in the treaty name would be wrong in some contexts).

---

## Golden Examples

---

### Example 1 — EN→DA, EU legislative text (formal register)

**Source**: `oliverkinch/eur-lex`, bilingual config, en_document → da_document

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Oversæt følgende tekst fra engelsk til dansk:\n\n---\n\nThe Council shall elect its President by a qualified majority for a term of two and a half years, renewable once. In the event of an impediment or serious misconduct, the European Council can end the President's term of office in accordance with the same procedure."
    },
    {
      "role": "assistant",
      "content": "Rådet vælger sin formand med kvalificeret flertal for en periode på to et halvt år, der kan fornyes én gang. I tilfælde af inhabilitet eller grov forseelse kan Det Europæiske Råd bringe formandens embedsperiode til ophør efter samme fremgangsmåde."
    }
  ]
}
```

**Why this is a good sample**: register is preserved (formal, legislative), established EU terminology is used correctly ("kvalificeret flertal", "inhabilitet"), sentence structure is recast in natural Danish rather than mirroring the English syntax, and no content is added or dropped.

---

### Example 2 — EN→DA, general/conversational text

**Source**: `allenai/Dolci-Instruct-SFT`, chat domain (translated subset)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Du er en hjælpsom assistent. Svar altid på dansk."
    },
    {
      "role": "user",
      "content": "Oversæt denne tekst til dansk:\n\n---\n\nShe has observed that attending financial literacy classes significantly impacts her clients' ability to manage their new mortgage efficiently. Over the past year, she has sold 20 houses and encouraged each buyer to enroll in at least one post-purchase class."
    },
    {
      "role": "assistant",
      "content": "Hun har bemærket, at deltagelse i kurser i privatøkonomi har stor betydning for kundernes evne til at håndtere deres nye boliglån på en hensigtsmæssig måde. I løbet af det seneste år har hun solgt 20 boliger og opfordret hver enkelt køber til at tilmelde sig mindst ét kursus efter overtagelsen."
    }
  ]
}
```

**Why this is a good sample**: "financial literacy classes" becomes "kurser i privatøkonomi" (natural Danish, not "finansiel læsefærdigheds-klasser"); "mortgage" becomes "boliglån" (correct); "post-purchase class" becomes "kursus efter overtagelsen" (idiomatic). The casual but clear register of the original is preserved.

---

### Example 3 — DA→EN, academic text

**Source**: `oliverkinch/danish-university-portals`, AAU publication

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Please translate the following Danish text to English:\n\n---\n\nDe seneste år har der været stigende interesse for det sociale miljøs betydning for elitesportsudøveres præstation og trivsel. Forskning inden for positiv psykologi og atletudvikling peger på, at et støttende og psykologisk trygt træningsmiljø kan fremme både præstation og langsigtet fastholdelse i sport."
    },
    {
      "role": "assistant",
      "content": "In recent years, there has been growing interest in the role of the social environment in elite athletes' performance and well-being. Research in positive psychology and athlete development suggests that a supportive and psychologically safe training environment can promote both performance and long-term retention in sport."
    }
  ]
}
```

**Why this is a good sample**: "psykologisk trygt træningsmiljø" becomes "psychologically safe training environment" (established term in the literature, not "psychologically secure"); "fastholdelse" becomes "retention" (correct domain term); the academic register is preserved; no content is added or omitted.
