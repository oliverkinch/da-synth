# danish-foundation-models/danish-dynaword

HuggingFace: `danish-foundation-models/danish-dynaword`

46 subsets, 5.66M rows, 6.83B tokens (Llama 3 tokenizer). All subsets share a uniform schema: `id`, `text`, `source`, `added`, `created`, `token_count`. All configs use `text_column: text`.

---

## Excluded subsets

These subsets are excluded from generation entirely.

| Subset | Reason |
|---|---|
| `adl` | Historical Danish literature - archaic language |
| `grundtvig` | Historical religious/philosophical texts |
| `enevaeldens_nyheder` | Historical newspapers (1660–1849), OCR quality |
| `relig` | Religious texts |
| `kb_historical_letters` | Historical letters (1500s–1900s) |
| `gutenberg` | Project Gutenberg - mostly translated works, archaic |
| `jvj` | Johannes V. Jensen - early 20th-century prose |
| `memo` | Modern Breakthrough novels (1870–1899) - archaic |
| `hvadvilduhelst` | "Would you rather" questions - too short/trivial |
| `spont` | Spontaneous conversational speech - wrong register |
| `synne` | Sønderjysk dialect content |
| `historical-danish-handwriting` | Parish/council minutes (1841–1939) - OCR, archaic |
| `cellar` | EU legal documents - already covered by `oliverkinch/eur-lex` |

Subsets not selected (evaluated but cut):

| Subset | Reason |
|---|---|
| `wikipedia` | Already covered by `oliverkinch/danish_wikipedia` (better, deduplicated) |
| `eur-lex-sum-da` | Already covered by `oliverkinch/eur-lex-sum` |
| `ep` | Europarl - overlaps with EUR-Lex content |
| `municipality_meetings` | Very procedural committee minutes - low instruction diversity |
| `kb_administrative_publication` | 845M tokens of mixed administrative content - quality too variable |
| `hest` | Horse enthusiast forum - niche/informal, low training value |
| `ai-aktindsigt` | Municipality website copy - variable quality, low information density |
| `opensubtitles` | Dialogue/subtitle format - not suited to QA or summarization seeds |
| `dannet` | Danish WordNet - structured lexical resource, not prose |
| `depbank` | Universal Dependencies treebank - too small, structured |
| `botxt` | Bornholmsk dialect dictionary |
| `wiki-comments` | Wikipedia talk page comments - too short, informal |
| `ncc_parliament` | Norwegian parliament proceedings in Danish - off-target |
| `ncc_maalfrid` | Norwegian institutional content in Danish - off-target |
| `ncc_newspaper` | 5.4k OCR'd newspaper pages - low volume, noisy |
| `nota` | Read-aloud text - too small (446 rows) |
| `naat` | Danish speeches archive - too small (129 rows) |
| `wikibooks` | Danish Wikibooks - too small (1.7k rows) |
| `wikisource` | Danish Wikisource - too small (3k rows) |
| `wiki-comments` | Wikipedia comments - too short, informal |
| `miljoeportalen` | 2.1M rows of environment portal pages - noisy web content |
| `danske-taler` | Danish speeches - too small (2.9k rows) |

---

## Selected subsets

| Subset | Rows | Tokens | Styles | Content |
|---|---|---|---|---|
| `tidsskrift-dk` | 4.1k | 50M | grounded, summarization | Open-access academic articles |
| `retsinformationdk` | 101k | 818M | grounded, summarization | Official Danish law and regulations |
| `domsdatabasen` | 8.5k | 86M | grounded, summarization | Court judgments |
| `ft` | 1.3k | 114M | grounded | Folketing (parliament) debates |
| `nordjyllandnews` | 75.2k | 38M | grounded, summarization | TV2 Nord news articles |
| `tv2r` | 49.1k | 22M | grounded, summarization | TV2 newswire (2010–2019) |
| `health_hoofdstaden` | 24k | 27M | grounded | Capital Region healthcare guidelines |
| `retspraksis` | 4.4k | 56M | grounded, summarization | Danish case law |
| `skat` | 14.7k | 122M | grounded | Danish Tax Authority content |
| `fm-udgivelser` | 443 | 50M | grounded, summarization | Ministry of Finance publications |
| `ncc_books` | 4.9M | 532M | grounded, summarization | OCR'd Danish books |

### Style assignment rationale

**grounded only** (`ft`, `health_hoofdstaden`, `skat`): content that is better suited to targeted explanation and Q&A than to compression. Folketing debate transcripts, healthcare guidelines, and tax authority content are instructional or argumentative in structure - summarisation is less natural than asking what something means or what a provision requires.

**grounded + summarization** (all others): substantive prose documents where both styles produce useful samples. Academic articles, legal texts, news articles, and court judgments all have enough information density for meaningful compression as well as targeted instruction following.

**No open-domain QA**: dynaword subsets are not used as seeds for the open-domain `qa` style. Open-domain QA seeds should come from sources whose content is well-represented in model training data (Wikipedia). Legal provisions, case law, and regional news articles are not reliably in the model's knowledge, so generating open-domain questions from them risks producing samples with hallucinated answers.
