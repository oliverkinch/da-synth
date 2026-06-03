# Coding conventions

Always pass arguments by name at call sites — `f(x=x)` not `f(x)`. Applies to all functions defined in this codebase. External library calls (e.g. `random.choice`, `asyncio.gather`) are exempt.

Use `git mv` instead of `mv` when moving tracked files.

# Design decisions

**Never hardcode limits that belong in config.** Text length caps, sample counts, token budgets — these must live in `DatasetConfig` (or equivalent) and be applied once in `render_seed_text` / the pipeline. Do not re-slice or re-cap inside generator methods.

**Always generate output fields, even when the seed dataset contains ready-made targets.** For example, `eur-lex` contains parallel DA/EN translations and `eur-lex-sum` contains official summaries — use them as input only. This keeps register consistent and the distribution uniform across seed sources.
