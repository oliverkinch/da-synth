# Style Wiki: Summarization

## Definition

The model is given a text passage and asked to produce a shorter version that captures the essential information. The passage is provided in the user message; the summary appears in the assistant response. The request style, response format, and expected length vary — the model must infer appropriate scope and depth from context.

## Quality Criteria

A high-quality summarization sample satisfies all of the following:

- **Faithfulness**: the summary contains no information not present in the source text. It does not hallucinate details, fill gaps, or draw on external knowledge.
- **Coverage**: the summary captures the main point(s) of the source, not just the opening sentences.
- **Compression**: the summary is meaningfully shorter than the source. A summary that reproduces 80% of the source text is not a summary.
- **Coherence**: the summary reads as a self-contained text. It does not reference "the text above" or use pronouns without clear antecedents.
- **Danish fluency**: the summary is written in natural, idiomatic Danish. EU documents may warrant more formal register; academic texts a measured neutral register; Wikipedia a plain accessible register.
- **Format compliance**: if the user specifies a format (prose, bullet points, number of sentences), the assistant follows it exactly.

## Known Pitfalls

- **Opening-sentence bias**: the model summarizes only the first paragraph and ignores the rest of the document.
- **Translation artifacts**: the model produces subtly translated/calqued phrasing rather than natural Danish, especially on EU or academic source texts.
- **Over-long summaries**: the model produces a near-full paraphrase rather than a genuine compression.
- **Format drift**: when asked for bullet points, the model produces a prose paragraph with bullet markers; or vice versa.
- **Leaking source boilerplate**: EU documents contain header metadata (dates, journal references, CELEX IDs) that should not appear in the summary.

---

## Golden Examples

---

### Example 1 — EU legislation (EUR-Lex), prose summary, formal request

**Source**: `oliverkinch/eur-lex-sum`, CELEX 12007L/TXT (Lissabontraktaten)

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Herunder følger teksten til Lissabontraktaten, som ændrer traktaten om Den Europæiske Union og traktaten om oprettelse af Det Europæiske Fællesskab. Kan du give mig et klart og kortfattet resumé af, hvad traktaten handler om, og hvad dens vigtigste ændringer er?\n\n---\n\nLISSABONTRAKTATEN\nOM ÆNDRING AF TRAKTATEN OM DEN EUROPÆISKE UNION OG TRAKTATEN OM OPRETTELSE AF DET EUROPÆISKE FÆLLESSKAB\n\nHANS MAJESTÆT BELGIERNES KONGE, REPUBLIKEN BULGARIAS PRÆSIDENT [...]\n\nSom ønsker at fuldføre den proces, der blev indledt med Amsterdam- og Nicetraktaterne med henblik på at styrke EU's effektivitet og demokratiske legitimitet samt forbedre sammenhængen i Unionens optræden udadtil [...]\n\nArtikel 1 – Ændringer i traktaten om Den Europæiske Union\n[...]\nUnionen afløser og efterfølger Det Europæiske Fællesskab.\n[tekst forkortet]"
    },
    {
      "role": "assistant",
      "content": "Lissabontraktaten, som trådte i kraft den 1. december 2009, er en reformtraktat, der ændrer de to grundlæggende EU-traktater uden at erstatte dem med en egentlig forfatning.\n\nDe vigtigste ændringer er: EU overtager Det Europæiske Fællesskabs retslige personlighed og bliver dermed et selvstændigt retssubjekt. Der indføres en fast formand for Det Europæiske Råd med en embedsperiode på to et halvt år, og posten som Unionens højtstående repræsentant for udenrigsanliggender og sikkerhedspolitik styrkes. Europa-Parlamentets beføjelser udvides markant, og den fælles beslutningsprocedure — nu kaldt den almindelige lovgivningsprocedure — bliver standardproceduren på de fleste politikområder. Desuden fastslår traktaten borgernes ret til at indgive et borgerinitiativ, og den giver for første gang medlemsstaterne en formel ret til at udtræde af Unionen."
    }
  ]
}
```

**Why this is a good sample**: the summary is faithful (no invented details), covers the whole document's main points (not just the preamble), uses appropriate formal register, and is compressed to a fraction of the source length. It does not reproduce header metadata.

---

### Example 2 — Academic article (tidsskrift.dk / dynaword), bullet-point key claims

**Source**: `danish-foundation-models/danish-dynaword`, subset `tidsskrift`, representative sports psychology article

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Du er en hjælpsom assistent. Svar altid på dansk."
    },
    {
      "role": "user",
      "content": "Jeg har fundet denne artikel fra Dansk Sportsmedicinsk Tidsskrift og vil gerne have de vigtigste pointer fremhævet som punkter. Kan du hjælpe?\n\n---\n\n**Stress og genopladning under træningslejre og konkurrencer**\nKristoffer Henriksen, Astrid Becker-Larsen & Carsten Hvid Larsen\nInstitut for Idræt og Biomekanik, Syddansk Universitet\n\nResumé: I dette studie undersøgte vi de danske U20-ishockeylandsholds oplevelser af stress og genopladning under en VM-forberedelseslejr. Data blev indsamlet via spørgeskemaet REST-Q-Sport samt semistrukturerede interviews med otte spillere og to trænere.\n\nResultaterne viste, at spillerne generelt oplevede et moderat stressniveau under lejren, men at individuelle forskelle var markante. De primære stressorer var konkurrenceangst, uklare rolleforventninger fra trænerens side samt social isolation fra familie og venner. Genopladningsstrategier der viste sig mest effektive var aktiv restitution, sociale aktiviteter med holdkammerater og strukturerede rutiner for søvn.\n\nStudiet peger på, at trænere med fordel kan arbejde eksplicit med psykologisk tryghed i truppen og sikre, at spillernes roller kommunikeres tydeligt inden og under lejren. Forfatterne anbefaler desuden, at elitesportsorganisationer integrerer viden om stresshåndtering i deres træneruddannelser.\n[tekst forkortet]"
    },
    {
      "role": "assistant",
      "content": "Her er artiklens vigtigste pointer:\n\n- **Formål**: Studiet undersøger stressoplevelser og genopladningsstrategier hos det danske U20-ishockeylandshold under en VM-forberedelseslejr.\n- **Metode**: Kombineret kvantitativ (REST-Q-Sport spørgeskema) og kvalitativ tilgang (interviews med 8 spillere og 2 trænere).\n- **Stressorer**: De hyppigste stresskilder var konkurrenceangst, uklare rolleforventninger og social isolation fra familie og venner.\n- **Effektiv genopladning**: Aktiv restitution, samvær med holdkammerater og faste søvnrutiner viste sig som de mest virksomme strategier.\n- **Praktiske anbefalinger**: Trænere bør kommunikere roller tydeligt og arbejde bevidst med psykologisk tryghed; stresshåndtering bør indgå i træneruddannelser."
    }
  ]
}
```

**Why this is a good sample**: bullets are genuinely informative (not just headers), each point is substantiated by the source, the summary distinguishes method from findings from recommendations — a real intellectual compression rather than a reformatted copy.

---

### Example 3 — Wikipedia article, length-constrained prose summary

**Source**: `oliverkinch/danish_wikipedia`, article "'Ndrangheta"

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Kan du opsummere følgende Wikipedia-artikel i præcis tre sætninger?\n\n---\n\n# 'Ndrangheta\n\n'Ndrangheta (også kaldet Onorata Società) er en italiensk kriminel organisation, der er hjemmehørende i Calabrien. Europol anslog i 2013, at 'Ndrangheta er en af de mest truende netværk af organiseret kriminalitet i Europa. Organisationen er i dag involveret globalt i kriminalitet, der omfatter narkohandel, menneskehandel, afpresning og hvidvaskning af penge. Dens struktur er opbygget omkring familieklaner kaldet 'ndrine, som opererer relativt selvstændigt, men koordinerer via et overordnet råd. Organisationens rødder går tilbage til det 19. århundrede i det sydlige Italien, og den har siden udvidet sin aktivitet til store dele af Europa, Nord- og Sydamerika samt Australien. Trods adskillige italienske politioperationer har organisationen vist sig meget svær at optrævle på grund af den tætte familiebinding og tavshedsnormen omerta."
    },
    {
      "role": "assistant",
      "content": "'Ndrangheta er en italiensk mafiaorganisation fra Calabrien, der af Europol betragtes som et af Europas mest farlige kriminelle netværk. Organisationen opererer globalt med aktiviteter som narkohandel, menneskehandel og hvidvaskning og er struktureret omkring familieklaner kaldet 'ndrine, der koordineres via et fælles råd. På trods af gentagne politioperationer har den tætte familiebinding og tavshedskulturen omerta gjort organisationen særdeles svær at optrævle."
    }
  ]
}
```

**Why this is a good sample**: exactly three sentences as requested, each covers a distinct dimension (identity/scale, operations/structure, resilience), no information outside the source text, natural Danish without calquing from the source phrasing.
