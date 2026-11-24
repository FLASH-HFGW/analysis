# FLASH documentation language and maintenance policy

**Effective 24 November 2026: all new or substantially revised FLASH repository documentation must be written entirely in English.**

This applies to:
- `docs/` Markdown guides, runbooks, technical notes and handovers
- README files, usage examples, and contributor instructions
- Python docstrings and explanatory source-code comments when added or revised
- Scientific reports, figure labels, tables and presentation slides
- Git commit messages and pull-request descriptions

**Conversations with the research team may continue in Italian.** User-provided scientific content is not to be silently translated or altered when quoted verbatim as a primary source.

Before editing an existing document, preserve its scientific content, numerical values, caveats, references and provenance. Translate or revise its natural-language text into English without changing technical meaning. Do not delete historical evidence to enforce language consistency. Older Italian-language documents remain a translation backlog until reviewed; the policy does not claim that all legacy files are already translated.

ROOT v3.1 documentation: [`docs/iq_root_v31.md`](iq_root_v31.md) is canonical. Additional short format notes should link there rather than duplicate its details.

**Codex handover:** At the start of a new task, read this policy and the active scientific context (`docs/ANALYSIS_CONTEXT.md` on the pilot branch). At each milestone, update lightweight English documentation alongside validated code/results, commit and push to the active branch, and report any uncommitted artifacts or unavailable tests.

Scientific claims must separate directly verified results, inferred explanations and untested hypotheses; preserve ADC versus RF reference planes and timing qualification. Do not add raw MIDAS, large ROOT files, secrets or large presentation binaries to Git when excluded by project policy.
