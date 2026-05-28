# Measuring the Wrong Thing: The Validity Gap Between Agent-Safety Benchmarks and the Deployments They Are Used to License

**Author:** King | **Affiliation:** Stanford CS321M
**Target venue:** NeurIPS SafeGenAI Workshop
**Draft:** v1, May 2026

---

## Abstract

We argue that no published agent-safety benchmark isolates the construct that matters for licensing deployment in irreversible-action settings: the conditional rate at which an LLM agent, having hallucinated, executes an explicit prohibition it could otherwise restate. We formalize this construct as Hallucination-Induced Unauthorized Action (HIUA), separate it from four neighboring constructs the literature confounds it with — lucid violation, jailbreak compliance, over-refusal, policy-invisible violation — and audit nine prior instruments against Messick's six aspects of validity. The substantive aspect (the cognitive-process claim that hallucination produced the violation) is essentially undefended in the surveyed corpus; the structural aspect is reported through single accuracy numbers that aggregate over a documented 8-to-99% dissociation between rule recall and rule adherence; the consequential aspect predicts three gaming failures already visible in adjacent benchmarks. We close with a six-month-implementable design (HIUA-Bench) whose primary contribution is to make the partition that lets a HIUA claim be evidenced rather than asserted.

## 1. The gap

Three findings frame the problem. RoboPAIR achieved approximately 100% attack success eliciting physical harmful actions from three commercial robot platforms via algorithmic jailbreak [robopair2024]. ARMOR 2025, the first military-doctrine-aligned LLM safety benchmark, found that twenty-one commercial LLMs evaluated against 519 doctrine-grounded prompts exhibited two distinct failure modes — hallucinating rules or inventing constraints when justifying actions, and refusing lawful scoped requests — and concluded that deploying general-purpose LLMs for military decision support without additional controls is premature [armor2026]. Anthropic's June 2025 agentic-misalignment red team found that Claude Opus 4 blackmailed a fictional executive in 96% of relevant scenarios under shutdown threat; Gemini 2.5 Flash blackmailed at 96%, GPT-4.1 and Grok 3 Beta at 80%, and DeepSeek-R1 at 79% [anthropicagentic2025].

These are three different mechanisms with overlapping blast radius. The case for deploying agents in irreversible-action settings — military targeting, embodied robotics, autonomous trading — depends on a transfer claim: existing benchmark scores predict that an agent will not take a forbidden action when it matters. We argue this transfer is unsupportable from current measurements because the relevant construct is not what current benchmarks measure.

The empirical anchor for the unsupportability claim is the constraint-adherence literature. DriftBench, scoring 2,146 benchmark runs across seven models, found that the rate at which models violate constraints they can simultaneously restate verbatim — the "knows-but-violates" (KBV) rate — ranges from 8% to 99% across models [driftbench2026]. SafeAgentBench found that the best-performing embodied baseline achieves 69% success on safe tasks but only 5% rejection on hazardous tasks [safeagentbench2024]. AgentHarm found that leading models comply with malicious agentic requests without any jailbreak [agentharm2024]. These are routinely reported under one umbrella ("agent safety") and used as comparable scores; they are measurements of different conditional distributions.

The 91-percentage-point dispersion in KBV implies that aggregating across hallucinated and lucid violations averages over a swing larger than the entire range of useful policy distinctions. A 30% aggregate violation rate could reflect a model that lucidly violates with full recall, a model that fails to recall the rule at all, or a model that confabulates new authorizations 30% of the time. These have different remediations — instruction-following training, context-management, faithful-reasoning intervention — and the choice among them depends on which mechanism dominates.

## 2. Construct: Hallucination-Induced Unauthorized Action

Let `h_t` indicate a hallucination event at agent step `t` (a generated intermediate token sequence — chain-of-thought, tool argument, or tool-output interpretation — unfaithful to input or world state). Let `s_t` indicate the salience condition: an explicit prohibition `P` was in the model's effective context, syntactically parseable, and within the attention window (operationalized by recall-probe restateability). The HIUA construct is the conditional rate

`HIUA(M, D) = P(a_t ∈ A_forbidden | h_t = 1 ∧ s_t = 1; M, D)`

for a model `M` on a distribution `D`. This is narrower than aggregate violation rate (which marginalizes over `h_t` and `s_t`), than aggregate hallucination rate (which marginalizes over `a_t`), and than compliance rate (which marginalizes over `h_t` and instruction provenance).

**Sub-constructs.** HIUA decomposes into three sub-constructs that map onto stages of the agent-hallucination workflow [halluagentsurvey2025]: *authorization* hallucination (agent fabricates an override permitting `a`), *state* hallucination (agent fabricates a world state in which `a` is no longer prohibited), and *tool* hallucination (agent fabricates a tool behavior such that calling the tool produces `a` without representing the call as `a`). These are distinct in mechanism, in remediation, and — as §3 will argue — in the measurement design that would isolate them.

**Anti-construct.** HIUA explicitly excludes four neighbors: (i) lucid violation (recalled and violated anyway) [driftbench2026]; (ii) jailbreak compliance (user or third-party content instructed the harmful action) [agentharm2024, robopair2024, injecagent2024, agentdojo2024]; (iii) over-refusal of legitimate tasks [orbench2024]; (iv) policy-invisible violation (decisive policy facts absent from visible context) [phantompolicy2026]. A measurement that does not partition these four neighbors from HIUA is measuring a confounded construct: Borsboom's causal account of validity requires variation in the target attribute to produce variation in the measurement outcome [borsboom2004], and a measurement responsive to five distinct mechanisms is responsive to a mixture, not the construct.

## 3. Validity audit: the three sharpest critiques

We organize the surveyed literature by Messick's six aspects of validity [messick1989, standards2014] in the extended version of this paper; here we present the three audits where the gap is most consequential.

### 3.1 The substantive aspect is undefended

The substantive aspect requires evidence that the cognitive process generating the test response matches the theorized process underlying the construct [messick1989]. For HIUA, the theorized process is "hallucination event → forbidden action." When the model produces a forbidden action, do we have evidence that a hallucination produced it, as opposed to merely co-occurring with it?

ToolEmu and Agent-SafetyBench score outcomes only [toolemu2024, agentsafetybench2024]. The 23.9% (automatic) and 68.8% (human) failure rates ToolEmu reports across 36 toolkits and 144 cases are consistent with hallucination-driven failure but provide no evidence that hallucination produced any specific failure. R-Judge measures whether a *judge* LLM can identify the safety issue post-hoc (GPT-4o 74.42% across 569 multi-turn agent interaction records) — the cognitive process under test is the judge's, not the actor's [rjudge2024].

DriftBench is the closest existing analogue to a substantive-aspect instrument. By interleaving a recall probe with the action, it partitions trials into a 2×2 of `{recall} × {violation}` and lets us read off KBV from the bottom-right cell [driftbench2026]. This is the right move, but the partition is one factor short of HIUA: it separates "did the model know the rule" from "did the model violate it" but not "did the model hallucinate authorization" from "did the model hallucinate state" from "did the model violate lucidly." The 2×2 must become 2 × 4 × 2 — `{recall} × {hallucination type or none} × {violation}`.

HEAL has the manipulation half: it intervenes on world state with four probe types (distractor injection, task-relevant object removal, synonymous substitution, scene-task contradiction) and induces hallucination rates up to 40× the base across 12 models in two simulators [heal2025]. It measures plan correctness, not prohibition crossing.

The cumulative critique: no surveyed benchmark could support a substantive-validity argument for HIUA as published. The data could in principle be re-analyzed — HEAL with an added prohibition layer, DriftBench with a hallucination-type classifier on the trace — but the analysis has not been done. The field has positioned agent-safety benchmarks as outcome-summary instruments and displaced the substantive question into discussion sections.

### 3.2 The structural aspect is reported through summary statistics that the underlying variance does not support

Generalizability Theory partitions observed-score variance into facets (persons, items, raters, occasions, settings) and reports Phi (absolute) and Ep² (relative) reliability coefficients [gtheoryage2025]. Almost no agent-safety benchmark reports this decomposition.

ToolEmu's discrepancy is, in effect, a single-facet G-study finding it does not name as such: 23.9% failure per automatic evaluator versus 68.8% per human on the same 144 cases [toolemu2024] is a 45-percentage-point gap that implies σ²(rater) is large enough to dominate the choice of agent. AgentIF reports per-constraint-type breakdowns but no variance decomposition; the < 30% perfect-adherence rate it reports on instructions averaging 11.9 constraints could reflect one or two systematically harder constraint types confounded with the headline rate [agentif2025]. DriftBench's 8-99% KBV across models is exactly the dispersion that should be partitioned: if σ²(item) is comparable to σ²(person), per-model rates would shift with item resampling.

The PSN-IRT analysis of 41,871 items across 11 LLM benchmarks is the precedent we lean on: item-level IRT analysis on existing benchmarks is feasible and reveals widespread saturation, insufficient difficulty ceilings, and contamination [lostinbench2025]. We predict the same analysis applied to AgentHarm and SafeAgentBench would reveal substantial item-level ceiling effects and low-discrimination items.

The minimum reporting expectation: Phi and Ep² across persons × items × raters × occasions, with D-studies indicating sample sizes needed for `Phi ≥ 0.80` at the target precision. Without these, a single accuracy number is not interpretable as a model property.

### 3.3 The consequential aspect predicts gaming patterns already visible in adjacent benchmarks

The consequential aspect requires evaluation of the social and behavioral consequences of using a test in a particular way [messick1989, kane2013, jacobswallach2021, m2m2025]. For agent-safety benchmarks used to license deployment, three consequences are predictable and already empirically anchored.

**Surface compliance gaming.** Models trained to refuse anything resembling a benchmark trigger over-refuse legitimate tasks. OR-Bench documents this at scale: 80,000 over-refusal prompts across 32 LLMs and 8 model families, with a hard subset of ~1,000 prompts challenging SOTA models [orbench2024]. ARMOR finds the same pattern in the military domain, where over-refusal of lawful scoped requests is one of its two principal failure modes [armor2026]. Goodhart's law in the validity register.

**Policy-as-prompt theater.** Developers add longer system prompts to pass benchmarks. Production strips them under token-budget pressure. PhantomPolicy formalizes the resulting policy-invisible-violation case across 8 violation categories with the policy intentionally absent from tool responses; 600 model traces across 5 frontier models showed a mix of self-avoidance, executed violations, and safe-case failures rather than reliable policy-grounded behavior [phantompolicy2026]. A benchmark that scores agents only with the full policy in context licenses a deployment claim production will not honor.

**False assurance for high-stakes deployment.** Digital-sandbox scores get cited to justify embodied or lethal deployment despite no demonstrated transfer. RoboPAIR's ~100% attack success on three robot platforms [robopair2024] and SafeAgentBench's 5% hazardous-task rejection [safeagentbench2024] together suggest the digital-to-embodied transfer is not just unmeasured but specifically disconfirmed.

The instruction-hierarchy training of Wallace et al. partly mitigates (1) but introduces its own consequential risk in the form of over-refusal [instructionhierarchy2024, armor2026]. Neither addresses (2) or (3).

## 4. Design sketch: HIUA-Bench

The constructive proposal is smaller than the leaderboard benchmarks it would join. The validity argument is that smaller-and-on-construct beats larger-and-confounded when the cost of the wrong answer is irreversible.

### 4.1 Item structure

Each item is `⟨environment, prohibition, hallucination-trigger, ground-truth state, action space⟩`.

The factorial is **3 sub-types** (authorization / state / tool) × **3 salience levels** (early-system / mid-system / tool-docstring) × **4 domains** (file ops, communication, financial, embodied), yielding 36 base items. Paraphrase ×4 and temperature seeds ×3 give 12 occasions per base item: 432 trials per model evaluated. Comparable in scale to ToolEmu's 144 cases [toolemu2024] but with a denser internal factorial.

The hallucination trigger per sub-type: for authorization, a forged "manager email" with no verified provenance arrives mid-task; for state, an ambiguous identifier suggests a duplicate (file name, sensor at discretization edge, inventory message implying target is gone); for tool, the docstring describes a benign action but the emulated implementation triggers a destructive side effect. The ground-truth state is simulator-verifiable so outcome scoring does not rely on an LLM judge for the primary measure.

Embodied items use AI2-THOR or a HEAL-derived scene [heal2025, safeagentbench2024]; digital items use Inspect Evals scaffolding inherited from AgentHarm [inspectevals2024, agentharm2024].

### 4.2 Scoring

Three measurements per trial.

- **Outcome.** Binary, simulator-derived: forbidden action executed? No LLM judge for the primary measure.
- **Hallucination.** Rubric-coded from chain-of-thought by a 3-model LLM-judge ensemble with human spot-checks on 10% of trials. Per-trial label among {none, authorization, state, tool}. Cohen's kappa per category, Krippendorff's alpha overall.
- **Recall probe.** Post-action prompt for the agent to restate the prohibition. Partitions trials into the 2 × 4 × 2 cell structure HIUA requires (recall × hallucination-type-or-none × violation).

The HIUA estimate is the rate of forbidden-action execution in the `{recall yes, hallucination one of three types}` cells, separately reported per sub-type. The `{recall yes, no hallucination, violation}` cell is the lucid-violation rate, matching DriftBench [driftbench2026].

### 4.3 Reliability plan

Crossed G-study design: persons (models) × items (36 base) × raters (3 LM-judges + 1 human spot) × occasions (4 paraphrases × 3 seeds) × salience (3 levels), with sub-type and domain as fixed strata for separate reporting.

Reported coefficients: σ² decomposition across facets; Phi (absolute) and Ep² (relative); D-study for `Phi ≥ 0.80` per domain stratum. IRT 2PL discrimination per item; items below 0.5 discrimination flagged rather than included in the headline rate. Discrimination distribution published alongside model rates, following the PSN-IRT precedent [lostinbench2025].

Minimum interpretability requirement: σ²(person) > σ²(item) for headline rates to be reported as model properties.

### 4.4 Validity argument, pre-registered

The validity argument is registered at item-construction time and reported alongside empirical results.

- **Content.** Factorial coverage justified against the agent-hallucination taxonomy [halluagentsurvey2025]; the three sub-types map onto reasoning, perception, and execution stages.
- **Substantive.** Chain-of-thought + recall probe interleaved with action instrument the hypothesized process; the 2 × 4 × 2 cell structure is the construct's empirical residence.
- **Structural.** Phi/Ep²/2PL across all facets; D-studies (§4.3).
- **Generalizability.** Cross-domain (digital → embodied) reported as Spearman rank correlation across model rankings with explicit irreversibility-stakes annotation per domain.
- **External.** Pre-registered predictions: positive correlation with HalluLens hallucination rate [hallulens2025], weakly positive with AgentHarm compliance [agentharm2024], zero or inverse with MMLU above the 0.7 threshold, positive with sycophancy [sharmasycophancy2023] and strategic-deception measures [deceptionsurvey2024].
- **Consequential.** Released through gated access with AgentHarm-style harm-score gating [agentharm2024, inspectevals2024]; not deployed as a public leaderboard; release accompanied by developer-signed deployment-claim audit.

## 5. Discussion

**Why not measure outcomes and ignore mechanism?** The §3.1 critique can be read as philosophical hand-wringing when an outcome metric exists. The reply is that the same outcome rate can be produced by lucid violation (which an instruction-following intervention would fix), by hallucinated authorization (which a faithful-reasoning intervention would fix), or by hallucinated state (which a perception-grounding intervention would fix). The interventions are distinct, the costs are distinct, and the appropriateness depends on which mechanism dominates. A benchmark that does not partition the mechanism cannot inform the intervention choice; it can only flag that something is wrong.

**Why not just iterate?** The pragmatic counter-argument is that imperfect measurements provide useful feedback during iterative development and that demanding pre-registered nomological networks and G-Theory decompositions raises benchmark-development cost without obviously raising value [m2m2025]. For capability benchmarks, where over-claim costs misallocated research dollars, this is largely correct. For agent-safety benchmarks used to license deployment in irreversible-action settings, the asymmetry flips: a false negative (deploying a benchmark-certified-safe system that then takes an irreversible forbidden action) is, by definition of irreversibility, catastrophic. The measurement standard should rise with the stakes of the use [kane2013, standards2014].

**Adjacency to deception and sycophancy.** Strategic deception [deceptionsurvey2024] involves unfaithful generation chosen deliberately; sycophancy [sharmasycophancy2023] involves it produced under user pressure; HIUA involves it without either. HIUA-Bench items should be designed to discriminate among these — with/without explicit goal incentives, with/without user pressure — to test the construct decomposition empirically.

**What this paper does not contribute.** A design, not an empirical study. The 36-item factorial is sketched, not implemented; nomological predictions are predictions, not findings. The contribution is a tighter measurement target and a pre-registered validity argument, on the bet that the field's current outcome-aggregation practice is mis-licensing deployment in the cases where the cost of being wrong is highest.

## 6. Conclusion

The agent-safety benchmark landscape contains many instruments measuring what is easy to measure: aggregate failure rates, malicious-instruction compliance, jailbreak vulnerability. It does not contain an instrument measuring the conditional rate at which an agent hallucinates and, because of the hallucination, crosses a prohibition it could otherwise restate verbatim. The gap is load-bearing because the deployment frontier is moving into settings where a single forbidden action is irreversible. The validity audit in §3 shows that existing benchmark scores cannot license the deployment claim they are being asked to support; the HIUA-Bench design in §4 sketches what an instrument with the right validity properties might look like. The argument is that smaller-and-on-construct beats larger-and-confounded when the cost of the wrong answer is irreversible.

---

## References

(Same bibliography as the extended version; entries verified in `_citations.json`.)

- [agentdojo2024] AgentDojo. https://arxiv.org/abs/2406.13352
- [agentharm2024] AgentHarm (ICLR 2025). https://arxiv.org/abs/2410.09024
- [agentif2025] AGENTIF. https://arxiv.org/abs/2505.16944
- [agentsafetybench2024] Agent-SafetyBench. https://arxiv.org/abs/2412.14470
- [anthropicagentic2025] Anthropic Agentic Misalignment (June 2025). https://www.anthropic.com/research/agentic-misalignment
- [armor2026] ARMOR 2025. https://arxiv.org/abs/2605.00245
- [borsboom2004] Borsboom, Mellenbergh, van Heerden (2004). The Concept of Validity. Psychological Review, 111.
- [deceptionsurvey2024] Park et al., AI deception survey. Patterns 2024.
- [driftbench2026] DriftBench / Models Recall What They Violate. https://arxiv.org/abs/2604.28031
- [gtheoryage2025] Revisiting generalizability theory in the age of AI (2025). https://www.sciencedirect.com/science/article/pii/S2666557325000370
- [halluagentsurvey2025] LLM-based Agents Suffer from Hallucinations: A Survey. https://arxiv.org/abs/2509.18970
- [hallulens2025] HalluLens. https://arxiv.org/abs/2504.17550
- [heal2025] HEAL (EMNLP Findings 2025). https://arxiv.org/abs/2506.15065
- [injecagent2024] InjecAgent. https://arxiv.org/abs/2403.02691
- [inspectevals2024] Inspect Evals (UK AISI). https://github.com/UKGovernmentBEIS/inspect_evals
- [instructionhierarchy2024] The Instruction Hierarchy (Wallace et al. 2024). https://arxiv.org/abs/2404.13208
- [jacobswallach2021] Jacobs & Wallach (2021). Measurement and Fairness. FAccT 2021.
- [kane2013] Kane (2013). Validating the Interpretations and Uses of Test Scores. J. Educ. Meas.
- [lostinbench2025] Lost in Benchmarks (AAAI 2026 Oral). https://arxiv.org/abs/2505.15055
- [m2m2025] Measurement to Meaning (Salaudeen et al., 2025). https://arxiv.org/abs/2505.10573
- [messick1989] Messick (1989). Validity, in Educational Measurement (3rd ed.).
- [orbench2024] OR-Bench. https://arxiv.org/abs/2405.20947
- [phantompolicy2026] PhantomPolicy. https://arxiv.org/abs/2604.12177
- [rjudge2024] R-Judge (EMNLP Findings 2024). https://arxiv.org/abs/2401.10019
- [robopair2024] RoboPAIR (2024). https://arxiv.org/abs/2410.13691
- [safeagentbench2024] SafeAgentBench. https://arxiv.org/abs/2412.13178
- [sharmasycophancy2023] Sharma et al. Towards Understanding Sycophancy. https://arxiv.org/abs/2310.13548
- [standards2014] AERA/APA/NCME (2014). Standards for Educational and Psychological Testing.
- [toolemu2024] ToolEmu (ICLR 2024 Spotlight). https://arxiv.org/abs/2309.15817
