# Overleaf upload instructions

Three files, drop them into a fresh Overleaf project:

- `paper_long.tex` — the CS321M term paper (~9,200 words, ~15–20 pages compiled)
- `paper_workshop.tex` — the workshop submission (~3,000 words, ~8 pages compiled)
- `references.bib` — shared bibliography, used by both papers

## To compile in Overleaf

1. Create a new blank Overleaf project (or upload to an existing one)
2. Drag all three files in
3. In Menu → Settings, set **Compiler** to **pdfLaTeX**
4. In Menu → Settings, set **Main document** to whichever paper you want to compile (default is `paper_long.tex`)
5. Hit Recompile. Overleaf runs LaTeX twice automatically; bibliography appears after the second pass.

If you see `Citation 'foo' undefined` warnings on the first compile, ignore them — they resolve on the second run.

## To switch which paper compiles

Either set the Main Document in Settings, or delete the one you don't want.

## To add your own LaTeX preamble

If your CS321M coursework expects a specific class file (e.g., `cs321m.cls`), drop it in and change the `\documentclass` line at the top of the .tex file. The rest of the body should work unchanged.

## If the venue (NeurIPS SafeGenAI, etc.) has its own style file

For `paper_workshop.tex`, replace the preamble block (everything between `\documentclass` and `\title`) with the venue's preamble. The body content is venue-agnostic.

## Known cosmetics

- Tables and figures: none included. If you want comparison tables (e.g., the benchmarks-by-Messick-aspect matrix), add them where they fit naturally in §4 (long) or §3 (workshop).
- Math notation uses standard `amsmath` — should render on any LaTeX install.
- Citation style is `plain` — change to `acm`, `apa`, `ieeetr`, or whatever your venue prefers in the `\bibliographystyle{...}` line near the end.

## What you should fact-check before submitting

The bibliography contains a mix of `verified_via: fetch` (we read the abstract) and `verified_via: search` (we confirmed the paper exists and matched the topic via search snippets, but didn't fetch the full abstract). For the workshop submission, spot-check the search-only entries by clicking through the URLs in `references.bib` and confirming the title/year are correct.

The Anthropic Agentic Misalignment citation is an industry research post, not peer-reviewed. Acceptable for the CS321M term paper; for a workshop submission, either swap for a peer-reviewed source or scope the claim so it doesn't depend on that one citation.

The paper's non-existence claim ("no published benchmark isolates this construct") is load-bearing. Before submission, run a focused search of NeurIPS 2025 and ICLR 2026 proceedings for any new instrument with the HIUA shape — a single counter-example would force a reframe.
