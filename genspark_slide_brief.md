# Genspark Brief: CS321M Showcase Slide Deck

## What I need

Build a **6-slide presentation** (title slide + 5 content slides) for a **5-minute talk** at the Stanford CS321M Showcase on June 3, 2026. The talk will be followed by 3 minutes of Q&A from a panel of four judges (academic, civil society, venture capital, infrastructure).

Title slide is for staging only; the five content slides each support roughly 60 seconds of speaking.

## Audience and venue

- **Venue:** CoDa E160, Stanford, in front of approximately 30 students and faculty plus four panel judges
- **Judges:** Emma Brunskill (Stanford CS, statistics-heavy), Eileen Donahoe (governance and human rights), James da Costa (a16z, agentic-AI investing), Charles Frye (Modal, developer relations)
- **Tone:** Academic but accessible. Closer to a NeurIPS oral presentation than an industry pitch. No marketing language. Statistical literacy is assumed; deep ML expertise is not.

## Aesthetic constraints

- **Format:** 16:9 widescreen, PowerPoint-compatible (.pptx)
- **Color palette:** Stanford Cardinal Red (#8C1515) for accents and headers; charcoal (#2E2D29) for body text; warm off-white (#F4F4F4) background. Use sparingly — this is a serious academic context, not a marketing deck.
- **Typography:** Headers in Georgia or a serif of similar weight; body in Calibri or a clean sans-serif. Large body text — minimum 24pt for any text the audience needs to read.
- **Style:** Stanford-academic. Heavy on white space. No icons or stock illustration. Tables use booktabs-style horizontal rules (no vertical lines, no fills). Charts use a restrained two- or three-color palette.
- **No emojis. No clip art. No drop shadows. No gradient fills.**

## Authors

Jake Klosowski (jfkx@stanford.edu) and Michelle Campeau (campeau@stanford.edu)

## Paper title

A Validity Audit of Hallucination-Induced Unauthorized Action in LLM Agents

---

## Slide-by-slide content

### Slide 1 — Title slide (5 seconds; staging only)

- **Title:** A Validity Audit of Hallucination-Induced Unauthorized Action in LLM Agents
- **Authors:** Jake Klosowski and Michelle Campeau
- **Affiliation line:** Stanford University · CS321M: AI Measurement Science · June 3, 2026
- **Visual:** Clean. Stanford block-S in cardinal red, top-right corner, small. Otherwise text-only on warm off-white.

---

### Slide 2 — The carving problem (60 seconds; opening hook)

**Header:** Existing benchmarks are not carving the agent-safety landscape at the joints that matter.

**Body content (three short rows, NOT bullet points — use a clean three-column table):**

| Source | Finding | What it measures |
|---|---|---|
| RoboPAIR (2024) | ~100% attack success on 3 commercial robot platforms | Adversarial jailbreak under explicit attack |
| ARMOR (2025) | 21 commercial LLMs fail military-doctrine grounding | Doctrine mismatch under genuine prompts |
| Anthropic (June 2025) | Claude Opus 4 blackmails in 96% of relevant scenarios | Goal protection under shutdown threat |

**Bottom line (one sentence, larger text, cardinal red):** Three different mechanisms with overlapping blast radius. The field is using their scores interchangeably to license deployment in irreversible-action settings.

---

### Slide 3 — Construct: HIUA and its anti-constructs (60 seconds)

**Header:** Hallucination-Induced Unauthorized Action (HIUA)

**Left column (60% width) — formal definition box:**

HIUA(M, D) = P(forbidden action | hallucination ∧ salient prohibition)

*The rate at which an agent, having hallucinated, then crosses an explicit prohibition it could otherwise restate verbatim.*

**Right column (40% width) — what HIUA is NOT (four short items, vertical list):**

- **Lucid violation (KBV).** Knew the rule, broke it anyway. (DriftBench: 8–99% across models.)
- **Jailbreak compliance.** Adversary instructed the harmful action. (AgentHarm, RoboPAIR.)
- **Over-refusal.** Refused a permitted action. (OR-Bench.)
- **Policy-invisible violation.** Policy facts absent from context. (PhantomPolicy.)

**Footer (small, italic):** A measurement that cannot partition these four neighbors from HIUA is measuring a confounded construct.

---

### Slide 4 — The audit: nine instruments, six aspects (60 seconds)

**Header:** Validity audit against Messick's six aspects.

**Body content — a compact table with the C / P / U coding from Table 1 of the paper:**

| Instrument | Content | Substantive | Structural | Generalizability | External | Consequential |
|---|---|---|---|---|---|---|
| AgentHarm | P | U | U | P | U | P |
| AgentDojo | P | U | U | U | U | U |
| RoboPAIR | P | U | U | U | U | P |
| ToolEmu | U | U | U | U | U | U |
| R-Judge | U | U | P | U | U | U |
| Agent-SafetyBench | P | U | U | U | U | U |
| DriftBench | U | P | P | U | U | P |
| SafeAgentBench | P | U | U | U | U | U |
| HEAL | P | P | U | U | U | U |

**Legend (small, bottom-left):** C = covered · P = partial · U = unaddressed

**Key takeaway (bottom, cardinal red, one sentence):** The substantive aspect — the cognitive-process claim that hallucination *caused* the violation — is essentially undefended in the surveyed corpus.

---

### Slide 5 — HIUA-Bench: design + pilot result (75 seconds; the headline empirical slide)

**Header:** HIUA-Bench: a 3 × 3 × 4 factorial design with a recall-probe partition.

**Layout: two-column.**

**Left column — Design (40% width):**

- **3 sub-types** × **3 salience levels** × **4 domains** = 36 base items
- 4 paraphrases × 3 seeds = 432 trials per model
- Three measurements per trial: outcome (simulator-verified), hallucination (3-judge ensemble on chain-of-thought), recall (probe in fresh context)
- Generalizability Theory: report Φ and Eρ² across persons × items × raters × occasions

**Right column — Pilot empirical result (60% width):**

Header line: **Pilot: 144 trials, 6 open-weights models on Groq**

A simple table showing the salience contrast (this IS the headline finding — make it visually prominent):

| Salience | n | Violation rate |
|---|---|---|
| **High** (prohibition at top of system prompt) | 84 | **1.2%** |
| **Low** (prohibition mid-prompt) | 60 | **23.3%** |

Below the table, one line of text, larger and in cardinal red:

**Prohibition salience: a 19× difference in violation rate.**

Below that, smaller text, two lines:

- Partition is empirically realizable: 11 HIUA-candidate vs. 4 KBV trials (the 2×4×2 cell structure produces non-trivial occupancy in both)
- Single-seed pilot; κ = 0.419 on the most-reliable judge pair; per-model rates lack standard errors

---

### Slide 6 — What this licenses, and what it does not (60 seconds; closing)

**Header:** Smaller and on-construct beats larger and confounded when the cost is irreversible.

**Body — three short paragraphs, NOT bullet points (or three short cards if Genspark renders cards well):**

**What HIUA-Bench supports.** Scores from a properly-measured HIUA benchmark can license the claim that an agent will not, above rate α, hallucinate authorization, state, or tool effect and execute a forbidden action in distribution D. Different mechanisms imply different interventions: faithfulness work for hallucinated authorization, perception-grounding for hallucinated state, instruction-following for lucid violation.

**What it does not support.** Broader safety claims, narrower safety claims, and transfer claims from digital sandbox to physical or lethal deployment. The pilot is digital-only. The military framing motivates the consequential argument; the empirical commitment is to tabletop simulators.

**The consequential-aspect recommendation.** Gated release with AgentHarm-style harm-score controls, no public leaderboard, accompanied by a developer-signed deployment-claim audit. Make consequential validity an explicit object of test-developer responsibility, rather than a side effect of how the score is used in the marketplace.

**Bottom-of-slide line (small, italic):** Repo: github.com/[anonymized]/hiua-bench · Paper available on request

---

## Pacing notes for the speaker (do not put these on the slides; include as speaker notes only)

- **Slide 2 — 60s.** Open with the three empirical anchors. Pause after each row.
- **Slide 3 — 60s.** Read the formal definition once, slowly. Spend most of the time on the four anti-constructs, since that decomposition is what makes the audit possible.
- **Slide 4 — 60s.** Do not read the table cell-by-cell. Point at the Substantive column and the Consequential column. Say: "the substantive aspect is unaddressed almost everywhere; the consequential aspect is only partially considered in four instruments."
- **Slide 5 — 75s.** This is the empirical headline. Spend 30 seconds on the design and 45 on the salience finding. The 1.2% vs. 23.3% number should be the last thing the audience sees before Q&A starts.
- **Slide 6 — 60s.** End on the consequential recommendation. Do not end on "thank you." End on "make consequential validity an explicit object of test-developer responsibility."

## Things to NOT include on the slides

- No agenda or roadmap slide. Five minutes is too short.
- No "about the authors" content.
- No literature-review slide separate from Slide 4 — the audit IS the literature review.
- No detailed per-model rates from Table 3 in the paper. The salience finding is sharper than the per-model finding for a 5-minute talk.
- No equations beyond the single HIUA conditional rate on Slide 3.
- No references slide. Citations belong in the paper, not in a 5-minute deck.

## Speaker-notes content

For each slide, populate the speaker-notes field with a verbatim script of approximately the right length for the slide's time allotment. Use clear declarative prose. No bullet points in the notes.

## Final delivery format

- **.pptx file**, 16:9
- **Speaker notes populated** for each slide
- **Slide master should use** the Stanford palette and fonts described above
- **All tables should use horizontal rules only**, no fills, no vertical lines (booktabs style)
