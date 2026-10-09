# PROJECT.md — Product specification

**NILMTrace** — *"Your bill tells you how much. We tell you why, and what to fix first."*

This file defines **what** the product is and is not. How it is built: [ARCHITECTURE.md](ARCHITECTURE.md). How it is accepted: [REQUIREMENTS.md](REQUIREMENTS.md).

The product direction is **frozen**. Only feasibility, correctness, reliability or implementation constraints may change it, and every such change is recorded in [DECISIONS.md](DECISIONS.md).

---

## 1. Problem

A household gets one electricity bill with one total. When the bill rises, the household cannot tell:

- which appliance used more electricity,
- whether that use is unusual,
- what to do about it first.

Finding out today means a separate meter or smart plug on every appliance. That costs money, takes installation work, and most households never do it. So people live with the higher bill or guess.

Unnecessary electricity use also has an environmental cost, because most of India's grid electricity is generated from fossil fuels.

## 2. Target user

- **Validated in this MVP:** Indian households with a whole-house power sensor that records at 1-minute intervals or faster (for example a clip-on sensor at the main panel).
- **Future, not validated:** small businesses with similar appliance types.

The MVP does not serve households that only have a monthly bill reading. That is a hard limitation of the method.

## 3. Value proposition

From **one aggregate meter signal**, NILMTrace:

1. estimates how much energy each supported appliance used,
2. converts that into an estimated cost contribution,
3. compares each appliance with its own normal week,
4. flags unusual use and states the likely driver,
5. recommends one action per issue, ranked by possible ₹ savings,
6. shows the possible ₹, kWh and CO₂ savings if use returns to normal,
7. sends an email alert when something is flagged.

The product loop:

**One aggregate meter → appliance estimation → cost attribution → baseline → anomaly → likely driver → action → possible savings**

Layers: NILM is the AI engine; anomaly detection is the intelligence layer; "What to fix first" is the product value; ₹/kWh/CO₂ is the measurable impact.

## 4. User journey (MVP)

1. Open the app. Choose **Normal weeks** or **Problem week**, or upload a CSV (P1).
2. Enter the bill amount and units from the electricity bill (a sample has an illustrative default).
3. **Where your money goes** — estimated kWh, cost contribution and share per appliance; the largest consumer is marked.
4. **See the AI work** — the total signal split into appliance estimates, and the model's evaluation on data it never saw in training.
5. **What changed** — each appliance against its normal week; flagged ones show the likely driver and possible explanations.
6. **What to fix first** — ranked cards with one action each and possible ₹/kWh/CO₂ per month; or "No unusual use found."
7. An alert email arrives when something is flagged.

## 5. Features

| ID | Feature | Priority | Notes |
|---|---|---|---|
| F1 | Load data and bill | P0 (samples), P1 (CSV upload) | Effective cost per kWh = bill amount ÷ bill units, an approximation |
| F2 | Where your money goes | P0 (drill-down P1) | "Estimated AC cost contribution: ₹X", never "Your AC caused ₹X" |
| F3 | See the AI work | P0 | Labelled "Model evaluation on data not used in training"; includes weekly results, a naive baseline comparison and the downstream check; no confidence scores |
| F4 | What changed | P0 | "The increase is primarily associated with longer operating time." Never "cause", "faulty" or "waste"; hotter weather is always a possible explanation for the AC |
| F5 | What to fix first | P0 | Only flagged issues, ranked by ₹; "Possible savings if use returns to its normal level" |
| F6 | Alert email | P0 | Supporting feature, not the headline |

**Supported appliances:** decided by evaluation, not by this document. Candidates are AC, refrigerator and washing machine (plus any other usable channel in the dataset). An appliance appears in the product only after a recorded GO decision. Appliances that fail are listed, with reasons, in the methodology drawer.

## 6. Non-goals (explicitly cut)

Chatbot; AI agent; LLM in any calculation or recommendation; energy-efficiency score; forecasting; smart-home integration; hardware or smart plugs; mobile app; long-term improvement tracking; user calibration; confidence scores; per-appliance claims for appliances without a GO decision; small-business validation; extra AWS services or a database without a concrete need.

Synthetic appliances are P2 only, and only if they pass through a real trained model and are never presented as validated.

## 7. Limitations (shown in the app and README)

1. Appliance figures are **estimates** from one aggregate signal.
2. Models are trained and evaluated on **one household** (iAWE, Delhi, about 73 days). Accuracy in other homes is unknown.
3. Only appliances with a GO decision are supported.
4. Input must be whole-house power at 1-minute intervals or faster, for at least 3 weeks.
5. Effective cost per kWh is an approximation; cost contributions do not reproduce the bill.
6. Savings are **possible** savings if use returns to its normal level, not guaranteed.
7. A flag means unusual energy use, not a faulty appliance. More AC use on hotter days is not waste.
8. The "Problem week" is a **simulated scenario** built from real held-out data.
9. **No real-world energy or emissions reduction has been measured.**

## 8. Environmental impact methodology

The environmental claim is a chain of estimates, each labelled:

1. **Excess energy (estimated):** current-week appliance energy above its baseline, from model estimates.
2. **Possible avoided energy (kWh/month):** excess × 30 ÷ 7, shown as a range that includes model error.
3. **Possible avoided emissions (kg CO₂/month):** possible avoided kWh × the Indian grid emission factor from the Central Electricity Authority's CO2 Baseline Database (edition cited in the app and DECISIONS.md).

What this is **not**: measured savings, measured emissions reductions, or a lifecycle assessment. Realising any saving requires the household to act, and real impact would need before/after measurement on real homes.

## 9. Success criteria for the MVP

| # | Criterion | How it is checked |
|---|---|---|
| S1 | At least one appliance passes GO on held-out real data and beats the naive baseline | `evaluation.json` (TESTING TS-E-06) |
| S2 | The downstream check detects an injected increase and is recorded honestly, with its small sample size | `evaluation.json` → `downstream_check` |
| S3 | The full loop runs on the public URL for both samples | TESTING TS-E2E-01 |
| S4 | The demo fits in 3 minutes, twice in a row | TESTING TS-E2E-03 |
| S5 | Every number in the UI and README is traceable to code output or `evaluation.json` | TASKS T-703 |
| S6 | Every limitation in §7 is visible in the app and README | REQUIREMENTS FR-12 |

## 10. What the MVP delivers vs future work

| Delivered (if S1–S6 pass) | Future work |
|---|---|
| NILM estimates for GO appliances, validated on unseen weeks of one household | Validation across many households |
| Cost contribution from an effective rate | Slab-aware tariff modelling |
| Weekly baseline anomaly flags with a likely driver | Weather-adjusted baselines |
| Ranked actions with possible ₹/kWh/CO₂ | Measuring actual savings after the user acts |
| Email alert to a demo inbox | Per-user accounts and alerts |
| Samples + CSV upload (P1) | Live meter streaming |
| Households | Small businesses (needs commercial sub-metered data) |
