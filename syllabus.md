# CS321M — AI Measurement Science (Spring 2026)

> Snapshot of the course Google Doc, captured May 1, 2026.
> Live source: https://docs.google.com/document/d/1sE6VC7BZ0QK9gF8zD2904CJy-GRebW0dg3p0oi4jGEs/edit

**MW 11:30 AM–12:50 PM, CoDa B60 · cs321m.stanford.edu**

Instructors / staff: Sanmi Koyejo, Sang Truong, Mike Hardy, Anka Reuel, Colin Sullivan, Alyssa Unell, Nicole Chiou, Yegor Denisov-Blanch, Natalie Dullerud.

Contact: Ed forum for questions; cs321m-spr2526-staff@lists.stanford.edu for personal matters.

---

## Description

AI measurement science provides frameworks and methodologies for evaluating, benchmarking, and understanding AI systems. As AI systems are deployed into high-stakes domains, rigorous measurement is increasingly important. Current approaches are often ad hoc, lacking theoretical grounding, and disconnected from real-world use cases — producing a measurement crisis of benchmark saturation, inconsistent methodology, and unreliable claims about capability. The course develops AI measurement science through three connected themes:

- **Measurement as Predictive Modeling** — probabilistic models of evaluation data (item-wise and pairwise response models, latent variable models), modeling benchmark response matrices, scaling laws, and sample-efficient measurement.
- **Measurement Validity and Reliability** — validity theory applied to AI evaluation (content, criterion, construct, external, consequential), operationalizing constructs, and reliability analysis including noise models and sources of measurement error.
- **Design, Governance, and Applications** — benchmark and instrument design, synthetic and adversarial evaluation, incentive-aware leaderboard design, and governance/policy considerations.

Graduate-level. Counts toward the CS MS "Learning and Modeling" breadth requirement (MSCS area B; note this in the GIN program-sheet notes box).

**Prerequisites:** Machine Learning (CS 221/229/230/224N), Probability & Statistics (CS 109 or equivalent), Linear Algebra & Calculus (MATH 51, CME 100), Python proficiency.

---

## Schedule

Friday discussion & tutorial sessions are optional.

| Date | # | Topic | Inst. | Event | Materials |
|---|---|---|---|---|---|
| Mar 30 | 1 | Introduction & Foundations — taxonomy, history, MCQ/preference/agentic data landscape | K1 | | Lec 1 slides; Chapter 1 |
| **Arc 1: Measurement as Predictive Modeling** | | | | | |
| Apr 1 | 2 | Probabilistic Models I (item-wise, pairwise; Rasch, 2PL, 3PL, factor models, Bradley-Terry) | K2 | | Lec 2 slides; Chapter 2 |
| Apr 3 | | Tutorial: data and predictive modeling | T1 | | Discussion 1 notebook |
| Apr 6 | 3 | Probabilistic Models II — inference (EM, MLE, Bayesian); AUC, ECE | | | Lec 3 slides; Chapter 3 |
| Apr 8 | 4 | Probabilistic Models III — sparse, low-rank, deep methods; cold-start; amortized | K3 | | Lec 4 slides; Chapter 3 |
| Apr 10 | | Tutorial: learning algorithms and metrics | S1 | | Discussion 2 notebook |
| Apr 13 | 5 | Sample-Efficient Measurement & Active Learning | K4 | Attendance policy begins; quiz guidance released | Lec 5 slides; Chapter 4 |
| Apr 15 | 6 | Scaling Laws | K5 | | Lec 6 slides |
| Apr 17 | | Tutorial: sample-efficient measurement | S2 | | Discussion 3 notebook |
| **Arc 2: Measurement Reliability and Validity** | | | | | |
| Apr 20 | 7 | Reliability I — signal/noise, Generalizability Theory, uncertainty (LLM-as-judge) | H1 | | Lec 7 slides; Reliability notes; Ch. 5 |
| Apr 22 | 8 | Reliability II — diagnostic tools, random effects, decision studies (agentic measurement) | H2 | Quiz 1; Predictive Evaluation Competition starts | Lec 8 slides; Reliability notes; Predictive Evaluation Handbook |
| Apr 24 | | Tutorial: reliability | S3 | | Discussion 4 notebook |
| Apr 27 | 9 | High-noise contexts — downstream tasks & intended impacts (noisy human annotations, edtech) | H3 | | Lec 9 slides; Reliability notes |
| Apr 29 | 10 | Validity | R1 | Validity HW released | Lec 10 slides; Chapter 6; Validity Homework |
| May 1 | | Tutorial: measurement validity | K6 | | Discussion 5 slides + notebook |
| May 4 | 11 | Design against noise — model evaluation, instrument construction & revision | H4 | Quiz 2 | Lec 11 slides; Reliability notes |
| **Arc 3: Design, Governance, Applications, Frontier** | | | | | |
| May 6 | 12 | The AI Evaluation Ecosystem | R2 | Validity HW Phase 1 due | Ecosystem notes |
| May 8 | | Tutorial: predictive evaluation competition | D1 | Validity HW debate (Phase 2) opens | |
| May 11 | 13 | Synthetic Data, Red-teaming & Adversarial Evaluation | K7 | Pre-analysis plan due | |
| May 13 | 14 | (Tentative) Evaluations in AI Governance | R3 | | |
| May 18 | 15 | Guest: Serena Wang — Information & Mechanism Design Against Gaming | KTHR | Validity HW Phase 2 due | |
| May 20 | 16 | Guest: Wale Salaudeen — Validity, Causality, Distribution Shift | KTHR | Quiz 3; HW post-debate grading due | |
| May 22 | | Tutorial: mechanism design and red teaming | K8 | Competition due | |
| May 25 | | Memorial Day — no class | | | |
| May 27 | 17 | Guest: Berivan Isik (Google DeepMind) | KTHR | Project due | |
| May 29 | | No tutorial | | Showcase selection released | |
| Jun 1 | 18 | Guest: Daniel Johnson (Transluce) | KTHR | | |
| Jun 3 | 19 | Summary and review; optional HAI Showcase (4 pm, HAI lobby) | K9 | Attendance period ends | |

---

## Learning outcomes

**Core (must-have)**
1. **Predictive measurement modeling** — model evaluation data using IRT, Bradley-Terry, factor models, scaling laws; predict unobserved outcomes; estimate latent capabilities.
2. **Reliability and validity analysis** — analyze sources of measurement noise (annotation, benchmark artifacts, model stochasticity); assess reliability/validity using established frameworks.
3. **Evaluation design** — design protocols including task construction, sampling, robustness.

**Important (should-have)**
4. **Critical consumption of measurement models** — interpret/critique assumptions, limitations, failure modes.
5. **Practical reliability analysis** — implement diagnostics, uncertainty estimation, noise analysis.
6. **Measurement ecosystem awareness** — how benchmarks/leaderboards shape developer incentives and governance.

**Stretch (mostly via project)**
7. **Research contribution** — develop novel measurement approaches or identify open problems.

---

## Assessment

Total = 120% (100% = full score).

| Component | Weight | Notes |
|---|---|---|
| Project | 40% | Pre-analysis plan May 11; final June 3 |
| Predictive Evaluation Competition | 25% | Starts Apr 22 |
| Validity assignment | 15% | Released Apr 29 |
| In-class quizzes (×3) | 40% | 15 min each, closed-book, ~13⅓% each |

Each student has **3 late days** total across all assignments. Regrade requests go through Gradescope within 3 days.

### Project deliverables (Gradescope, PDF)
1. **Pre-analysis plan** (30%) — May 11. Everything except experiments. NeurIPS 2025 format, 3–4 pages excluding references.
2. **Final manuscript** (60%) — May 27. Max 8 pages excluding references, NeurIPS 2025 format.
3. **Code** (10%) — June 3. README, docs, requirements.txt, reproducibility scripts.

Groups of up to **three people**. Topics: any AI Measurement Science direction (IRT extensions, latent capability estimation, sparse evaluation prediction, scaling-law analyses, LLM-as-judge reliability, GTheory pipelines, annotation noise, ranking uncertainty, construct validity audits, contamination detection, active learning for items, synthetic/adversarial benchmarks, agentic evaluation, etc.).

### Quiz topic guide

**Quiz 1** — benchmark misleadingness, basic IRT models (Rasch, 2/3PL, BT, Elo) and their assumptions, parameter interpretation, item characteristic/information curves, EM intuition, out-of-benchmark prediction with factor/IRT.

**Quiz 2** — Generalizability Theory in AI benchmarks, Phi/Ep², Cronbach's α and alternatives, CTT vs. agreement/IRR metrics, conditional reliability vs. IRT properties, validity types and applications, scaling law properties, content of L6–L10.

**Quiz 3** — TBD.

---

## Grading philosophy

Mastery is assessed in ways augmented but not replaced by AI; the course aims to build theoretical understanding, critical analysis, implementation, and deployment skills.

---

## AI policy

Students under stress should reach out (instructors and Stanford support) rather than relying on chatbots as a shortcut. Anthropic-style chatbots are not used by the staff for grading but may be used to provide feedback on submissions.

For coding assignments, AI-in-IDE is allowed; you must submit your own solution and own the result.

For the project, generative AI use is allowed but requires three disclosures (each ~150 words, missing any costs 10% of the course grade):
- **Integrity statement** — how you identified and addressed plagiarism, attribution, bias, inaccuracies.
- **Reflection** — how/why you used AI, impact on learning, future use.
- **Impact statement** — social/ethical/environmental impacts, misuse risks, mitigations, attribution, ethics.

---

## Logistics

**Computing.** Google Cloud sponsors compute credits (request form deadline: April 8 AOE). Free Google Colab is available. Recommendation: debug on CPU, switch to GPU for full-scale runs.

**Office hours.**
- Sullivan — Wed, CoDa B50, 1–2 pm in person
- Unell — Mon, Gates 315, 1–2 pm in person
- Chiou — Tue, Zoom, 1–2 pm
- Dullerud — Fri, Huang basement, 1–2 pm (from Apr 10); Zoom from May 15
- Koyejo — Mon, CoDa B60, 12:50–1:30 (from Apr 13)
- Hardy / Denisov-Blanch / Truong / Reuel — by appointment

**Attendance (non-CGOE).** Required from Apr 13 through Jun 3. Penalties: 3rd unexcused absence → ½-grade; 5th → full grade; 8th → two grades; 10th → fail. Excused: religious, health, family emergency, or conference presentation. Submit attendance code as `ticket.txt` on Gradescope (duplicates void all involved). Codes must be submitted by end of week.

**Submissions.** Gradescope only — no email submissions; multiple uploads allowed (last before deadline counts).

---

## Resources & policies

**Access & accommodations.** Register with OAE (oae.stanford.edu); share your Academic Accommodation Letter early.

**Recording.** Lectures recorded via back-of-room cameras and posted to Canvas. Audience may be incidentally captured.

**Collaboration.** Study groups allowed; submit individually and list group members.

**Academic integrity.** Stanford Honor Code applies; cite all sources, attribute external code.

**Wellbeing.** CAPS (caps.stanford.edu); Vaden Health Center (vaden.stanford.edu).

---

## CGOE / HCP

- **No mandatory attendance** policy.
- **Coding/project submissions** identical to on-campus students.
- **Quizzes** administered by registered exam monitor; 24-hour window from on-campus quiz start; on-campus seating optional (email staff per quiz).
- **Office hours** include Zoom; assigned grader is your primary point of contact.

---

## Auditors

Admitted depending on capacity. Expectation: attend ≥60% of classes and engage with class activities.

---

## Reading list (highlights)

**L1.** Position: Evaluating Generative AI Systems Is a Social Science Measurement Challenge (arXiv:2502.00561). Plus: Measurement to Meaning — A Validity-Centered Framework (arXiv:2505.10573).

**L2.** Beyond Benchmarks: Evaluating Generalist Medical AI With Psychometrics (JMIR 2025). Plus: Chatbot Arena (arXiv:2403.04132).

**L3.** Reliable and Efficient Amortized Model-based Evaluation (arXiv:2503.13335). Plus: Birnbaum, Statistical Theories of Mental Test Scores.

**L4.** Nonlinear Sequential Designs for Logistic IRT Models (arXiv:0906.1859).

**L5.** Reliable and Efficient Amortized Model-based Evaluation; tinyBenchmarks (arXiv:2402.14992). Plus: On Speeding Up LM Evaluation (arXiv:2407.06172).

**L6.** Scaling Laws for Neural Language Models (arXiv:2001.08361). Plus: Training Compute-Optimal LLMs (arXiv:2203.15556); Item Response Scaling Laws (OpenReview pIfopX18D1).

**L7.** How Benchmark Prediction from Fewer Data Misses the Mark (arXiv:2506.07673); Coefficients and Indices in Generalizability Theory (CASMA); My Current Thoughts on Coefficient Alpha (Cronbach 2004). Plus: Alternative Annotator Test for LLM-as-a-Judge (ACL 2025); Confident Conclusions from Unconfident LLM Annotations (NAACL 2025); Design-based Supervised Learning (arXiv:2306.04746).

**L8.** Should I Use Fixed or Random Effects? (Cambridge PSRM). Plus: Fantastic Bugs in AI Benchmarks (arXiv:2511.16842); GDPval (arXiv:2510.04374).

**L9.** Knowledge without Wisdom: Misalignment between LLMs and Intended Impact (arXiv:2603.00883); The Fallacy of AI Functionality (arXiv:2206.09511). Plus: All that Glitters (NAACL Findings 2025); AI and the Everything in the Whole Wide World Benchmark (arXiv:2111.15366).

**L10.** Cronbach & Meehl, Construct Validity in Psychological Tests (1955). Plus: We Can't Understand AI Using Our Existing Vocabulary (arXiv:2502.07586).

**L11.** Measuring Data (arXiv:2212.05129). Plus: Correlated Errors in LLMs (arXiv:2506.07962); Yang on LLM Annotation; Keeping Humans in the Loop (arXiv:2409.09467); Training on the Test Task Confounds Evaluation and Emergence (arXiv:2407.07890); In Defense of Typing Monkeys (argmin.net).

**L13.** Comparison Requires Valid Measurement: Rethinking ASR Comparisons in AI Red Teaming (OpenReview d7hqAhLvWG).

**L15.** Do ImageNet Classifiers Generalize to ImageNet? (arXiv:1902.10811); ImageNot (arXiv:2404.02112). Plus: Benchmark Suites Instead of Leaderboards for Fairness; Do Better ImageNet Models Transfer Better? (arXiv:1805.08974).

**L16.** Paradigms of AI Evaluation (arXiv:2502.15620). Plus: Fairness through Difference Awareness (arXiv:2502.01926).

**L18.** Who Should Develop Which AI Evaluations? (Daniel Johnson). Plus: Anka Reuel civil society paper; Advancing Science- and Evidence-Based AI Policy (Science).

**L19.** Aggregated Individual Reporting for Post-Deployment Evaluation (arXiv:2506.18133).

---

*This file is a local snapshot. The Google Doc is the authoritative source — the syllabus is "subject to change during the quarter".*
