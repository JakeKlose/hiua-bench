# Self-review notes — v1

## Files produced

- `paper_long.md` — 9,188 words (target 8,000-11,000). Within range.
- `paper_workshop.md` — 3,020 words body (target ~4,500). Below target but tight; the workshop cut intentionally compresses §3 and §6 and drops §8 per the spec. Likely acceptable for a 6-page workshop format; if expanded to 8 pages, the strongest additions would be a richer §3 (sub-construct examples worked through) and a §4.5 (predicted nomological correlations).
- `_citations.json` — 40 verified sources.
- `_outline.md` — phase-2 outline.

## Citation audit

- Every `[citation_key]` in both manuscripts resolves to an entry in `_citations.json`. Verified by grep cross-check (see audit run at v1-phase5).
- 0 `[CITE NEEDED]` markers in either file.
- All 40 entries in `_citations.json` were verified in this session via either WebSearch (existence/topic) or WebFetch (numerical claims). 8 entries are `verified_via: "fetch"` (full abstract read); 32 are `verified_via: "search"` (abstract or canonical summary from search results plus arXiv canonical URL confirmation).

## Numerical claim audit and corrections applied

During self-review I re-verified the three most specific numerical claims by re-querying their sources. Three corrections were applied:

1. **DriftBench: "five of seven models above 50% KBV"** — this detail appeared in a search snippet but is NOT in the verified abstract. Removed from both papers; the 8-99% range is preserved (verified in the abstract).

2. **AgentDojo: "53.1% attack success on 'Important message'"** — initial draft included; on first re-verification this number wasn't in the abstract snippet I had. Re-verified via a second WebSearch that found the number reported in the AgentDojo paper's own materials and a published technical summary. Restored.

3. **Anthropic blackmail rates (Claude Opus 4 96%, Gemini 2.5 Flash 96%, GPT-4.1 80%, Grok 3 Beta 80%, DeepSeek-R1 79%)** — all verified via WebSearch of Anthropic's research page and corroborating press summaries. The cited source is Anthropic's June 2025 research post, which is not peer-reviewed; flagged as a non-academic source in `_citations.json`.

## Messick aspect coverage audit (long form)

All six aspects appear as named subsections in §5 with explicit instrument critique:
- 5.1 Content — audits SafeAgentBench, AgentHarm, InjecAgent/AgentDojo, HEAL
- 5.2 Substantive — audits ToolEmu/Agent-SafetyBench, R-Judge, DriftBench, HEAL
- 5.3 Structural — audits AgentIF, ToolEmu, DriftBench, PSN-IRT
- 5.4 Generalizability — audits AgentHarm × SafeAgentBench cross-walk gap, ARMOR, RoboPAIR, Anthropic agentic misalignment
- 5.5 External — predicts correlation patterns; audits agentic-misalignment as closest existing datapoint
- 5.6 Consequential — audits OR-Bench (gaming), PhantomPolicy (prompt theater), RoboPAIR×SafeAgentBench (false assurance)

## Anti-construct check

- §3.3 lists four anti-construct neighbors (lucid violation, jailbreak compliance, over-refusal, policy-invisible violation), each with citation support.
- Anti-construct recurs in §5.1 (content gap), §5.2 (DriftBench partition is one factor short), §5.6 (consequences of confounding).

## Strongest claims that need human verification

Three claims in the paper carry the most analytical weight; if any is wrong, the argument requires repair. Listed in descending order of risk-to-thesis:

1. **"No published benchmark *isolates* hallucination as the causal pathway to forbidden-action execution."** This is a non-existence claim, so it cannot be proven via WebSearch — only disproven by a counterexample. The paper would be substantially weakened if a 2025–2026 benchmark exists that I missed. The closest counterexample candidates I am aware of and considered: HEAL (measures hallucination + plan correctness in embodied agents but not prohibition crossing), DriftBench (measures KBV but partitions only one factor short of HIUA), PhantomPolicy (measures policy-invisible violation but explicitly excludes hallucination as a mechanism). King should run a targeted search of recent NeurIPS 2025 and ICLR 2026 papers with "hallucination" + "agent" + "instruction violation" or "forbidden action" before submitting.

2. **"DriftBench's 8-99% KBV variance partitions one factor short of what HIUA requires (2×2 vs. 2×2×2)."** This claim depends on a particular reading of DriftBench's design — that DriftBench's recall probe identifies *whether* the model recalls the rule but does not identify *which type of hallucination* (if any) occurred in the trace leading to the violation. The verified abstract supports this reading (the recall probe is described as a "restatement probe" testing "declarative recall"), but a careful reader who has run the benchmark may dispute it. King should read the DriftBench methods section before finalizing.

3. **"The 23.9% / 68.8% ToolEmu gap is best interpreted as a G-Theory σ²(rater) signal."** This is my analytical reframing of a finding the ToolEmu authors reported as a quality-of-emulator check. The reframing is defensible and (I argue) sharper, but the ToolEmu authors may have responded to this critique somewhere I have not located. Worth a single targeted search of the ToolEmu paper's own discussion section before finalizing.

## Minor issues to address before submission

- The workshop cut at 3,020 words is short of the 4,500-word target. If submitting to NeurIPS SafeGenAI workshop, fits the page count comfortably; if a more substantive version is wanted, the §3 sub-construct treatment and the §4.4 pre-registered nomological correlations are the easiest expansions.
- The §6.4 pre-registered external predictions list specific predicted correlation patterns. These predictions should be reviewed by a co-author or advisor before final submission; they are conjectural and a misprediction is recoverable but visible.
- The Anthropic agentic-misalignment work is cited but is an industry research post, not a peer-reviewed paper. If submitting to a venue with stricter citation norms, a 2025-2026 academic citation of similar findings would strengthen the use of this datapoint.
- The HEAL "dishwasher example" in §4.4 is paraphrased from a search-result summary. Confirmed the structural shape of the example via the paper's HTML render (linked in `_citations.json`), but King should double-check the verbatim example before quoting in submission.
- §6.4 says "above the 0.7 threshold" for MMLU — this threshold is a stipulation rather than a derived value. Either cite a precedent for the threshold or hedge to "above some saturation threshold."

## What was deliberately not included

- The agent-hallucination taxonomy survey [halluagentsurvey2025] reports a 5-type taxonomy in the memo's phrasing (reasoning/execution/perception/memorization/communication). The current verified search result describes the taxonomy as "brain/perception/action" stage-based. I used the stage-based phrasing because that's what the abstract supports. King may want to read the survey's table of contents and update if the 5-type phrasing matches a refined version of the taxonomy in the full paper.
- The ARMOR 2025 arXiv ID in the memo (2605.00245) and my search confirm it but the paper is dated April 30 2026 — that's a future date relative to the user's stated current date of 2026-05-17 (i.e., the paper is ~17 days old). I cited it but King should verify this is the intended paper.
- The DriftBench / PhantomPolicy / nomological-networks / "Measuring what Matters" papers all have 2026 arXiv IDs (2604.28031, 2604.12177, 2603.15121). These match the memo's listing and verify as real papers; flagged here for King's awareness that several core citations are very recent.

## Status

Phases 0-6 complete. Files at /Users/jfk/Documents/Claude/Projects/AI Measurement/paper_drafts/v1/.
