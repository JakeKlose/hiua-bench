# Outline — Hallucination-Induced Unauthorized Action (HIUA) Benchmark Paper

Working outline. Each claim-bearing bullet ends with `[citation_key]` from `_citations.json` or `[ANALYSIS]` for King's own claims.

## North star (one sentence)

Target the conditional rate `P(forbidden action | hallucination ∧ explicit prohibition was salient)` for tool-using LLM agents, and demonstrate that no current benchmark isolates this conditional rate from confounded constructs (lucid violation, jailbreak compliance, generic harmfulness).

## Contribution claim (revised after lit scan)

1. **Construct identification.** Define HIUA formally and decompose it from the four near-but-distinct constructs that current benchmarks confound it with: (a) malicious-user compliance (AgentHarm, RoboPAIR), (b) indirect-prompt-injection vulnerability (InjecAgent, AgentDojo), (c) hazardous-instruction refusal (SafeAgentBench, AGENTSAFE), (d) lucid constraint violation (DriftBench, AgentIF, HSP). `[ANALYSIS]`
2. **Validity audit.** Apply Messick's six aspects (content, substantive, structural, generalizability, external, consequential) to nine prior instruments. Show that the substantive aspect — the cognitive-process claim that hallucination caused the violation — is essentially undefended in the literature. `[ANALYSIS]`
3. **Design sketch.** Propose HIUA-Bench: 3 hallucination sub-types × 3 prohibition-salience levels × 4 task domains, with simulator-verifiable outcomes, post-hoc recall probes, and a G-study reliability plan computing Phi/Ep² across persons × items × raters × occasions × paraphrases. `[ANALYSIS]`

---

## Section 1 — Abstract

(Write last; ~200 words. Lede: a passing score on existing agent-safety benchmarks is poor evidence that an agent will not take a hallucination-induced forbidden action in deployment, because no extant benchmark isolates that conditional pathway. Set up the Messick audit and the HIUA design.)

## Section 2 — Introduction

- **The consequential-validity hook.** The dominant case for agent-safety evaluation is a transfer argument: scores on digital-tool sandboxes predict embodied/lethal-system behavior. This argument is rarely defended. `[m2m2025, kane2013, ANALYSIS]`
- **The motivating example.** RoboPAIR achieved ~100% attack success eliciting physical harmful actions from three robot platforms via jailbreak `[robopair2024]`. ARMOR 2025 finds that civilian safety metrics underestimate military-relevant gaps, with two failure modes — hallucinating rules and refusing lawful requests `[armor2026]`. The Anthropic agentic misalignment study found Claude Opus 4 blackmailed in 96% of relevant red-team scenarios; multiple frontier models blackmailed at 79-96% `[anthropicagentic2025]`. Different mechanisms, same blast radius.
- **The construct confound.** DriftBench shows KBV (knows-but-violates) rates of 8-99% across models, meaning most constraint violations are not hallucinations of the constraint `[driftbench2026]`. SafeAgentBench shows embodied agents refuse hazardous tasks only 5% of the time `[safeagentbench2024]`. AgentHarm shows leading LLMs comply with malicious agent requests without any jailbreak `[agentharm2024]`. These are different failure modes, but they are all reported under the umbrella of "agent safety."
- **Contribution.** This paper does three things: (i) defines HIUA as a separable construct with anti-construct, (ii) audits nine prior instruments against Messick's six validity aspects, (iii) proposes HIUA-Bench, a design that isolates the hallucination → forbidden-action pathway with G-study reliability accounting and a published nomological-network prediction.
- **Why now.** The push to deploy agents in irreversible-action settings (lethal, financial, infrastructural) is moving faster than the measurement vocabulary `[armor2026, robopair2024, anthropicagentic2025]`. A benchmark that conflates lucid violation with hallucination-induced violation will mis-license deployment in exactly the cases where the cost of being wrong is highest. `[ANALYSIS]`

## Section 3 — Construct definition

- **Formal definition.** HIUA is the propensity `P(a ∈ A_forbidden | h ∧ s)` where `h` is a hallucination event (intermediate generation unfaithful to input/world), `s` is the salience condition (prohibition was present, parseable, and within the agent's effective context), and `a ∈ A_forbidden` is the executed action belonging to the prohibited set. `[ANALYSIS]`
- **Sub-constructs.** Map to the agent-hallucination taxonomy `[halluagentsurvey2025]`:
  - **Authorization hallucination** — agent fabricates an exception/override/higher-priority instruction. (Reasoning-stage hallucination.)
  - **State hallucination** — agent fabricates a world state in which the action is no longer in `A_forbidden`. (Perception-stage hallucination.)
  - **Tool hallucination** — agent fabricates a tool's behavior such that calling it produces `a` without the agent representing the call as `a`. (Execution-stage hallucination.)
- **Anti-construct.** HIUA explicitly excludes: (i) lucid violation (KBV — the rule was recalled and violated anyway) `[driftbench2026]`, (ii) jailbreak compliance under adversarial user/data instructions `[agentharm2024, robopair2024, injecagent2024]`, (iii) over-refusal of legitimate tasks `[orbench2024]`, (iv) under-coverage of policy due to invisible policy `[phantompolicy2026]`. `[ANALYSIS]`
- **Why this decomposition matters for validity.** A measurement that does not partition `h` from `¬h` cannot make causal claims about hallucination as the mechanism. Borsboom's causal account of validity requires that variations in the attribute (hallucination propensity) produce variations in the measurement outcome (violation rate) `[borsboom2004]`. Without manipulation of `h`, only a correlation between observed hallucination markers and observed violations is licensed — and the literature does not even report that consistently. `[ANALYSIS]`

## Section 4 — Related work, organized by what each instrument measures

(Anti-pattern: list-by-paper. Organize by *implicit construct*.)

### 4.1 Malicious-user-instruction compliance
- AgentHarm: 110 malicious tasks, 11 categories, 440 with augmentations; leading models comply without jailbreaking `[agentharm2024]`
- AgentDojo: 97 realistic tasks, 629 security cases; GPT-4o benign utility 69% → 45% under prompt-injection attack; 53.1% success on "Important message" canonical attack `[agentdojo2024]`
- InjecAgent: 1,054 cases, 17 user tools + 62 attacker tools; ReAct GPT-4 vulnerable 24%, doubled with hacking-prompt reinforcement `[injecagent2024]`
- RoboPAIR: ~100% attack success eliciting physical harmful actions on three robot platforms `[robopair2024]`
- **Synthesis claim:** These instruments measure the *complement* of HIUA — the user (or third-party content) is the adversary, the agent is not hallucinating, the agent is being maliciously instructed. The agent's compliance rate is a different conditional distribution. `[ANALYSIS]`

### 4.2 Outcome-aggregated agent safety
- ToolEmu: 36 toolkits / 144 cases; safest LM agent still fails 23.9% per automatic evaluator, 68.8% per human `[toolemu2024]`
- R-Judge: 569 records, 27 scenarios, 5 application categories, 10 risk types; meta-evaluation of LLM judges, GPT-4o 74.42% `[rjudge2024]`
- Agent-SafetyBench: 349 environments, 2,000 test cases, 8 risk categories, 10 failure modes; 16 LLM agents evaluated, none above 60% safety score `[agentsafetybench2024]`
- **Synthesis claim:** These report a single aggregated failure rate. The KBV literature (8-99% across models on DriftBench) implies that aggregating across hallucinated and lucid violations averages over a 90-percentage-point swing — a single accuracy number is uninterpretable as a model property. `[driftbench2026, ANALYSIS]`

### 4.3 Lucid constraint adherence
- DriftBench: KBV 8-99%; models accurately restate constraints they simultaneously violate; structured checkpointing partial fix `[driftbench2026]`
- AgentIF: 707 instructions, avg 11.9 constraints, three constraint types; best model < 30% perfect adherence `[agentif2025]`
- Hierarchical Safety Principles: lightweight probe; "cost of compliance" + "illusion of compliance" `[hsp2025]`
- Instruction Hierarchy training: system > developer > user > data prioritization as a *fix* for the gap these benchmarks expose `[instructionhierarchy2024]`
- **Synthesis claim:** The lucid-violation literature has converged on the finding that constraint recall and constraint adherence are dissociable. This is the *cleanest* operationalization of what HIUA is *not*: a model that recalls the rule and breaks it is not exhibiting hallucination-induced violation. `[ANALYSIS]`

### 4.4 Embodied safety
- SafeAgentBench: 750 tasks, 10 hazard categories, simulator-grounded; best baseline 69% safe-task success, 5% hazardous-task rejection `[safeagentbench2024]`
- AGENTSAFE: 45 adversarial scenarios, 1,350 hazardous tasks, 9,900 instructions across VLM agents; multi-level diagnosis of perception/planning/execution `[agentsafe2025]`
- HEAL: probing set induces hallucination rates up to 40× higher; models cannot reliably reject infeasible tasks; hallucinations persist under feedback `[heal2025]`
- **Synthesis claim:** The embodied literature comes closest to HIUA because (a) infeasible-task probing induces state-hallucinations and (b) outcomes are simulator-verifiable. HEAL in particular constructs the manipulation that the digital-agent literature lacks. But none of these benchmarks measure the joint distribution of `(hallucination event, forbidden action)` — they measure hallucination presence and refusal rate as separate, unconditioned quantities. `[ANALYSIS]`

### 4.5 Hallucination measurement
- HalluLens: extrinsic vs. intrinsic hallucination; dynamically generated test set; closes leakage `[hallulens2025]`
- LLM-agent hallucination survey: 5-type taxonomy by workflow stage; 18 triggering causes `[halluagentsurvey2025]`
- **Synthesis claim:** Hallucination is now measured but never cross-linked to action consequence. The taxonomy maturity in this literature is the asset HIUA-Bench should borrow. `[ANALYSIS]`

### 4.6 Validity and benchmarking-of-benchmarks
- Measurement-to-Meaning: validity-centered framework for AI evaluation; scope of claims must match strength of measurement `[m2m2025]`
- Nomological-networks-required argument: nomological account is most suitable for LLM capability research `[nomologicalnetworks2026]`
- BetterBench: 25 benchmarks assessed; large quality differences; most don't report statistical significance `[betterbench2024]`
- "Can We Trust AI Benchmarks?": meta-review of ~100 studies; names construct validity, misaligned incentives, gaming `[canwetrust2025]`
- AI and the Everything Benchmark: critique of "general" benchmarks as abstractions `[raji2021]`
- "What will it take to fix benchmarking": four-criterion bar that most NLU benchmarks fail `[bowmandahl2021]`
- Lost in Benchmarks: 41,871 items across 11 benchmarks; widespread saturation and contamination `[lostinbench2025]`
- Liao & Xiao: argue for situated evaluation closing the socio-technical gap `[liaoxiao2023]`
- Jacobs & Wallach: measurement modeling as fairness frame; content and consequential validity as load-bearing `[jacobswallach2021]`

## Section 5 — Validity audit (Messick's six aspects)

(Central contribution. One subsection per aspect; each subsection audits ≥3 prior instruments and states explicitly where each falls short.)

### 5.1 Content aspect — does the test span the construct?
- HIUA construct = `P(forbidden | hallucination ∧ salient prohibition)`.
- **SafeAgentBench:** 10 hazard categories simulator-grounded `[safeagentbench2024]`. Content covers hazardous instructions but does not factorial-cross hazardous-instruction × hallucination-trigger; the construct it covers is "hazard refusal under direct adversarial instruction," not HIUA. `[ANALYSIS]`
- **AgentHarm:** 11 harm categories `[agentharm2024]`. The user is the adversary by construction; no items where the agent confabulates authorization or state to take a non-instructed harmful action.
- **InjecAgent / AgentDojo:** content is third-party-injected adversarial instructions `[injecagent2024, agentdojo2024]`. Same coverage gap: the agent has been instructed to do the harmful thing, just by an untrusted source.
- **HEAL:** has the right manipulation (scene-task inconsistency to induce state hallucination) but the dependent variable is plan-correctness, not crossing a prohibition `[heal2025]`. A content extension of HEAL with explicit prohibitions would be the closest existing instrument.
- **Consequence:** prevailing benchmarks cover the malicious-instruction half of agent safety thickly and the hallucinated-authorization half almost not at all. Content validity for HIUA is essentially zero across the surveyed corpus. `[ANALYSIS]`

### 5.2 Substantive aspect — does the response process match the theorized cognition?
- Strongest claim of the paper: this is where the literature is weakest.
- Substantive validity requires evidence that the cognitive process generating the response matches the theorized process `[messick1989, standards2014]`. For HIUA, the theorized process is "hallucination → action." No surveyed benchmark instruments this.
- **Toolemu / Agent-SafetyBench:** outcome scoring only; "why" is unrecoverable from the data `[toolemu2024, agentsafetybench2024]`.
- **R-Judge:** measures whether a *judge* LLM can identify the safety issue post-hoc `[rjudge2024]`. This is judge-cognition, not actor-cognition.
- **DriftBench:** the closest existing analogue — adds a recall probe to separate KBV from genuine forgetting `[driftbench2026]`. Critically, this probe partitions hallucination-of-rule from lucid violation, but not hallucination-of-authorization or hallucination-of-state from lucid violation. The 2×2 (recall × violation) is one factor short of the 2×2×2 (recall × hallucination-type × violation) HIUA requires.
- **HEAL:** has the manipulation (induced hallucination) but reports planning failures, not prohibition crossing `[heal2025]`.
- **Implication:** any HIUA-claim made from existing data is a post-hoc attribution. The paper should require that future benchmarks include (i) a manipulation of `h`, (ii) a measurement of `h` in trace data, (iii) a recall probe to rule out lucid violation. `[ANALYSIS]`

### 5.3 Structural aspect — internal structure and reliability
- Almost no agent-safety benchmark reports G-Theory variance decomposition. Single accuracy / refusal-rate numbers dominate.
- **AgentIF:** reports per-constraint-type breakdowns; no variance components `[agentif2025]`.
- **ToolEmu:** reports separately for `agent` and `evaluator` (human vs. LM judge) — 23.9% vs. 68.8% gap is in effect a one-facet partial-G-study revealing that rater variance is large `[toolemu2024]`. They do not report it as such.
- **DriftBench:** 8-99% KBV variance across persons (models) is exactly the kind of dispersion that should be partitioned into σ²(person), σ²(item), σ²(occasion), σ²(rater) `[driftbench2026, gtheoryage2025]`. If item variance dominates, a benchmark reporting a single rate is mostly measuring item difficulty.
- **Lost in Benchmarks / PSN-IRT:** demonstrates IRT-style item-level analysis is feasible on existing benchmarks; finds widespread saturation and contamination `[lostinbench2025]`. The same method applied to agent-safety benchmarks would likely reveal that most items are too easy or too contaminated for current frontier models.
- **Implication:** propose Phi/Ep² coefficients and per-item 2PL discrimination as a minimum reporting standard. Use D-studies to specify the items × occasions needed for Phi ≥ 0.80. `[ANALYSIS, gtheoryage2025]`

### 5.4 Generalizability aspect — across persons, items, occasions, settings
- The load-bearing assumption: a benchmark in a digital sandbox predicts behavior in an embodied/lethal setting.
- **Cross-domain transfer.** No published cross-walk exists between AgentHarm (digital, malicious-instruction) and SafeAgentBench (embodied, hazardous-instruction) on the same models. The transfer is assumed, not measured. `[ANALYSIS]`
- **Irreversibility gap.** A 5% violation rate that is acceptable for a chatbot is catastrophic for a drone `[robopair2024, armor2026]`. Generalizability across stakes is part of the construct, not a downstream policy decision. `[ANALYSIS]`
- **Occasion variance.** Prompt seeds, temperature, paraphrase, and tool-description rewording all matter. The Anthropic agentic-misalignment study reports 79-96% blackmail rates across models on the same scenario, but the within-model variance across seeds is reported sparsely `[anthropicagentic2025]`.
- **Implication for HIUA:** generalizability evidence must include both within-domain occasion-facet variance and cross-domain transfer correlation, with the irreversibility-stakes gradient explicit. `[ANALYSIS]`

### 5.5 External aspect — what does the score correlate with?
- The nomological-network requirement: a valid construct lives in a web of expected relationships with other measured constructs `[cronbachmeehl1955, nomologicalnetworks2026, m2m2025]`.
- **Predictions HIUA should make:**
  - Positive correlation with HalluLens hallucination rate (same underlying generative process) `[hallulens2025]`
  - Weakly positive correlation with AgentHarm compliance (different but adjacent failure mode) `[agentharm2024]`
  - Zero or inverse correlation with general capability (MMLU, GPQA) above a threshold (more capable models hallucinate less per token but may be deployed in higher-stakes settings) `[ANALYSIS]`
  - Positive correlation with deceptive-strategic behavior measures (Park et al. taxonomy) — both reflect breakdown of faithful intermediate generation `[deceptionsurvey2024]`
- No surveyed benchmark reports the full pattern.
- Anthropic's agentic misalignment work `[anthropicagentic2025]` is the closest external-validity datapoint: blackmail rates were elevated under shutdown-threat conditions across model families. But the prediction was made post-hoc, not as a pre-registered nomological hypothesis.
- **Implication:** the field should publish predicted correlation patterns before running new instruments. `[ANALYSIS]`

### 5.6 Consequential aspect — the leaderboard problem
- Messick's most underused aspect. Score uses must be evaluated for their consequences `[kane2013, jacobswallach2021]`.
- **Three predictable consequences if HIUA-style benchmarks gain leaderboard status:**
  1. **Surface compliance gaming.** Models train to refuse anything resembling a benchmark trigger, hurting helpfulness (the over-refusal pattern OR-Bench documents at scale across 32 LLMs and 8 families) `[orbench2024]`. This is Goodhart's law in the validity register: when a refusal rate becomes the target, refusal stops indicating safety `[canwetrust2025]`.
  2. **Policy-as-prompt theater.** Developers add longer system prompts that pass benchmarks but get stripped under token-budget pressure in production — exactly the "policy-invisible violation" PhantomPolicy is built around `[phantompolicy2026]`.
  3. **False assurance for high-stakes deployment.** A passing digital-sandbox score is cited to justify embodied/lethal deployment despite no demonstrated transfer. RoboPAIR + SafeAgentBench `[robopair2024, safeagentbench2024]` empirically show this transfer is missing.
- The instruction-hierarchy training response `[instructionhierarchy2024]` and consistency-training approaches partially mitigate (1) but introduce their own consequential risks around lawful-instruction refusal (the second ARMOR failure mode `[armor2026]`).
- **Recommendation (gated release):** HIUA-Bench should be released with the AgentHarm-style "harm-score gating" `[agentharm2024, inspectevals2024]` — not as a public leaderboard but as a controlled-access benchmark with a published nomological prediction. This treats the benchmark as a test of *both* the model and the developer's deployment claim. `[ANALYSIS]`

## Section 6 — Proposed design (HIUA-Bench)

### 6.1 Item structure
- Each item is a tuple `⟨environment, prohibition, hallucination-trigger, ground-truth state, action space⟩`.
- 3 hallucination sub-types (auth / state / tool) × 3 prohibition-salience levels (early-system / mid-system / tool-docstring) × 4 domains (file ops, communication, financial, embodied) = 36 base items.
- 4 paraphrases per item × 3 temperature seeds = 12 occasions per base item. Total 432 trials per model.
- Items implemented as Inspect Evals tasks where possible to inherit AgentHarm infrastructure `[inspectevals2024]`.
- Embodied items implemented in AI2-THOR or a HEAL-derived scene `[heal2025, safeagentbench2024]`.

### 6.2 Scoring — three measurements per trial
- **Outcome:** simulator ground truth. Binary "was a forbidden action executed?" Bypasses LLM-judge variance for the primary measure.
- **Hallucination:** rubric-coded from chain-of-thought trace; LLM-judge with 3-judge ensemble and human spot-check. Per-trial label of which sub-type of hallucination occurred, if any.
- **Recall probe:** post-action, prompt the model to restate the prohibition. Captures the KBV dimension `[driftbench2026]`. Trials are partitioned into the 2×2 of `{hallucination yes/no}` × `{recall yes/no}`; the HIUA estimate is the bottom-right cell `{hallucination yes, recall yes}`.

### 6.3 Reliability plan (G-study)
- Facets: persons (models) × items (36 base) × raters (3 LM-judges + 1 human spot) × occasions (4 paraphrase × 3 seed) × prohibition-salience.
- Report σ² decomposition; Phi (absolute) and Ep² (relative); D-study for `Phi ≥ 0.80`.
- IRT 2PL discrimination per item to flag uninformative items; bin items by difficulty so frontier-model ceilings are avoided `[lostinbench2025]`.

### 6.4 Validity argument by Messick aspect (pre-registered)
- Content: factorial coverage justified against the agent-hallucination taxonomy `[halluagentsurvey2025]`.
- Substantive: chain-of-thought + recall probe interleaved with action instruments the hypothesized cognitive process.
- Structural: Phi/Ep² + IRT 2PL parameters per item.
- Generalizability: cross-domain (digital → embodied) reported as correlation, with explicit irreversibility-stakes annotation per domain.
- External: pre-register correlations with HalluLens `[hallulens2025]`, AgentHarm `[agentharm2024]`, MMLU. Pre-registered prediction: positive with HalluLens, weakly positive with AgentHarm, zero/inverse with MMLU above threshold.
- Consequential: published only with gated access; no public leaderboard; release accompanied by a per-model deployment-claim audit.

## Section 7 — Discussion

- **What can a validity audit actually decide?** It cannot decide a model's safety; it can decide which deployment claims a benchmark licenses `[m2m2025]`. The HIUA contribution is a tighter license on the claim "this agent will not hallucinate its way into a forbidden action," not a broader one.
- **The counter-argument: pragmatic benchmarking.** Imperfect measurements still provide useful feedback during iterative development, especially when claims are scoped narrowly `[m2m2025]`. We agree with this for capability benchmarks. For agent-safety benchmarks used to justify deployment in irreversible-action settings, the asymmetry of error cost flips this argument: false negatives are catastrophic. `[ANALYSIS]`
- **Why not just measure outcomes and ignore mechanism?** Because the same outcome rate can be produced by (a) lucid violation (a fix would target instruction-following), (b) hallucinated authorization (a fix would target faithful intermediate generation), (c) hallucinated state (a fix would target perception grounding). Three different interventions, indistinguishable from outcome data alone. `[ANALYSIS]`
- **The deception/sycophancy adjacency.** Strategic deception `[deceptionsurvey2024]` and sycophancy `[sharmasycophancy2023]` are related but distinct constructs: deceptive models generate unfaithful traces *deliberately*, sycophantic models generate them under user pressure, HIUA-hallucinating models generate them without either intent or pressure. HIUA-Bench should be designed to discriminate among these — items with vs. without user pressure, with vs. without an obvious reward for the violation.
- **Transfer from digital to embodied.** SafeAgentBench's 5% rejection rate and HEAL's 40× hallucination-rate inflation under scene-task inconsistency `[safeagentbench2024, heal2025]` are the strongest empirical anchors for arguing the construct is real in embodied settings. The digital-to-embodied transfer assumption is the most important thing for HIUA-Bench to instrument, not assume.

## Section 8 — Limitations

- Single-author / one-quarter scope means HIUA-Bench is a design proposal; empirical validation is future work.
- Reliance on chain-of-thought traces as evidence of cognition is itself a substantive assumption — chain-of-thought may be a post-hoc rationalization rather than a faithful trace.
- The proposed nomological-network correlations are predictions, not established facts.
- The military/lethal motivation is rhetorically load-bearing but the proposed items live in tabletop simulators, not actual weapons systems.

## Section 9 — Conclusion

A short restatement: existing instruments answer different questions than the one that matters for deployment in irreversible-action settings. HIUA-Bench is a design that answers the right question, at the cost of being smaller and slower than the leaderboard-friendly instruments it would join. The validity argument is that smaller-and-slower-but-on-construct beats larger-and-faster-but-confounded for the use case in question.

## References
(Generated from `_citations.json`.)
