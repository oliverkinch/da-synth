# Style Wiki: Grounded Instruction Following

## Definition

The user provides a source text passage and gives an instruction that requires reading and responding to that specific text. The passage is always present in the user message. The instruction type is diverse — explanation, definition, comparison, analysis, simplification, specific questions about the text — but explicitly excludes summarization (→ `summarization` style) and translation (→ `translation` style).

This style trains the model to act as a reader's assistant: take whatever text a user pastes in, understand it, and respond to whatever they ask about it.

## Quality Criteria

A high-quality grounded sample satisfies all of the following:

- **Groundedness**: the response contains no information not present in the source text. The model does not supplement with external knowledge.
- **Instruction fit**: the response directly addresses the specific instruction given — not the whole text in general. An instruction asking about one concept gets an answer about that concept, not a tour of the entire passage.
- **Not a summary**: the response is not a compression of the source text. It does not reproduce the main points in order. It responds to a specific angle the user asked about.
- **Not a translation**: the source and response are in the same language (Danish).
- **Naturalness of instruction**: the user message reads as something a real person would write after encountering a text they wanted help with.
- **Danish fluency**: the response is written in natural, idiomatic Danish appropriate to the register of the source (formal for legal text, plain for news, measured for academic text).
- **No source reproduction**: the response does not quote large chunks of the source text back at the user.

## Known Pitfalls

- **Disguised summarization**: the generated instruction is "Hvad er de vigtigste punkter i denne tekst?" — which elicits a summary. The instruction must target something specific, not the whole text.
- **Translation leak**: the generated instruction asks the user to translate. Caught by excluding translation-type instructions at generation time.
- **External knowledge**: the model draws on world knowledge to supplement a thin passage. For legal and academic text especially, the response must stay within the source.
- **Generic instructions**: "Kan du forklare denne tekst?" without specifying what aspect. The instruction should be concrete enough that a different text would require a different answer.
- **Source text too short**: a one-sentence passage produces trivial grounded samples. Seed rows should be filtered for minimum length before generation.

---

## Golden Examples

---

### Example 1 — Legal text (retsinformationdk), definitional/comparative instruction

**Source**: `danish-foundation-models/danish-dynaword`, subset `retsinformationdk`, Databeskyttelsesloven § 6

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Jeg forsøger at forstå følgende paragraf fra Databeskyttelsesloven. Hvad er egentlig forskellen på de seks behandlingsgrundlag, og hvornår ville man bruge hvert af dem?\n\n---\n\n§ 6. Behandling af personoplysninger er kun lovlig, hvis mindst ét af følgende grundlag er opfyldt:\n\n1) Den registrerede har givet samtykke til behandling af sine personoplysninger til et eller flere specifikke formål.\n\n2) Behandling er nødvendig af hensyn til opfyldelse af en kontrakt, som den registrerede er part i, eller af hensyn til gennemførelse af foranstaltninger, der træffes på den registreredes anmodning forud for indgåelse af en kontrakt.\n\n3) Behandling er nødvendig for at overholde en retlig forpligtelse, som den dataansvarlige er underlagt.\n\n4) Behandling er nødvendig for at beskytte den registreredes eller en anden fysisk persons vitale interesser.\n\n5) Behandling er nødvendig af hensyn til udførelse af en opgave i samfundets interesse eller som henhører under offentlig myndighedsudøvelse, som den dataansvarlige har fået pålagt.\n\n6) Behandling er nødvendig for, at den dataansvarlige eller en tredjemand kan forfølge en legitim interesse, medmindre den registreredes interesser eller grundlæggende rettigheder og frihedsrettigheder går forud herfor."
    },
    {
      "role": "assistant",
      "content": "Paragraffen opstiller seks mulige juridiske hjemler — hvoraf mindst én skal være opfyldt, for at behandling af personoplysninger er lovlig. De adskiller sig primært på, hvem der bestemmer, og hvad formålet er:\n\n**1. Samtykke** — du har aktivt sagt ja. Bruges typisk, når der ikke er et andet klart grundlag: nyhedsbreve, markedsføringscookies, frivillige spørgeskemaer.\n\n**2. Kontrakt** — behandlingen er nødvendig for at opfylde en aftale med dig. En netbutik behandler din adresse for at levere din ordre; en arbejdsgiver behandler dit kontonummer for at udbetale løn.\n\n**3. Retlig forpligtelse** — en lov eller bekendtgørelse kræver det. En arbejdsgiver skal indberette løn til Skat; en bank skal opbevare transaktionsdata af hvidvaskningsårsager.\n\n**4. Vitale interesser** — et egentligt nødstilfælde, typisk liv og helbred. En læge, der behandler en bevidstløs patient, kan fx tilgå journaloplysninger uden samtykke.\n\n**5. Samfundsopgave eller myndighed** — offentlige myndigheder, der løser lovbestemte opgaver: en kommune, der behandler data for at udbetale ydelser; en skole, der fører karakterregister.\n\n**6. Legitim interesse** — den bredeste og mest skønsprægede hjemmel. Organisationen har en saglig interesse (fx intern IT-sikkerhedsovervågning), men den skal afvejes konkret mod den registreredes rettigheder. Bruges ikke af offentlige myndigheder i myndighedsudøvelse."
    }
  ]
}
```

**Why this is a good sample**: the instruction asks for *differentiation and contextualisation* — not compression. The answer maps each of the six grounds to a concrete use case, which is explanatory work, not summarisation. All examples stay within what the provision establishes; no external legal knowledge is added. The response would look different for a different paragraph, which confirms it is genuinely instruction-specific.
