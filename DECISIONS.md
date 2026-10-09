# DECISIONS.md — Architecture decision record

This file records **why** NILMTrace is built the way it is, what changed from the original architecture document, and what is still unresolved.

- Confirmed decisions are marked **Accepted**.
- Decisions that depend on an experiment are marked **Proposed — pending validation**, with the task that validates them.
- The technical definitions themselves live in [ARCHITECTURE.md](ARCHITECTURE.md).

To add a decision: append a new `D-xxx` entry, never edit history silently. To resolve an unresolved item: fill in its "Resolution" line with the date, the result and the evidence (file or commit).

---

## 1. Architecture audit summary

The original document, *NILM Energy Diagnostic — MVP Architecture* (archived in `docs/archive/`), was audited before these docs were written.

**Overall:** the shape is right and buildable by two people. One FastAPI process on one EC2 instance, S3 for artifacts, a registry file that decides the appliance set, precomputed samples, deterministic analytics, no database. The product loop maps cleanly to modules and screens.

**Problems found and fixed in this documentation set:**

| # | Problem | Severity | Fix |
|---|---|---|---|
| A1 | Demo samples were 35 days, but the held-out test period of a ~73-day dataset is only about 3 weeks. The samples would include **training data**, inflating results. | Critical (honesty) | Samples use only the held-out test period, 3 whole weeks (D-011) |
| A2 | The problem-week injection was fixed at +25%, but the flag threshold is `max(25%, 2 × error)`. With any error above 12.5%, the central demo moment would fail silently. | Critical (demo) | Injection size derived from T after evaluation (D-014) |
| A3 | The error that set the threshold was measured over the whole test period, where weekly errors cancel. The flag compares **one week**. | High (correctness) | Use the median weekly energy error (D-012) |
| A4 | Savings range `mid × (1 ± e)` applied a relative appliance error to the excess, which understates uncertainty. | Medium (correctness) | Absolute uncertainty `e × kWh_W0` (D-013) |
| A5 | F3 showed one example day, open to "you picked the best day", and no evidence about weekly energy or flag correctness. | High (judging) | Weekly chart, downstream check, rule-selected window (D-017) |
| A6 | No gap between train and test windows: a window could straddle both. | Medium (leakage) | Gap ≥ window/2 (D-016) |
| A7 | Caddy and sslip.io HTTPS added a tool and a failure point that judges do not value. | Medium (feasibility) | FastAPI serves the frontend on port 80; HTTPS is P2 (D-004) |
| A8 | Result persistence and `GET /api/analysis/{id}` existed only for a link in the email. | Low | Cut; email is self-contained (D-019) |
| A9 | Teammate B owned AWS, API, all frontend tabs and deployment; Teammate A owned only ML. Unbalanced. | High (schedule) | A also owns preprocessing, energy, anomaly and the pipeline (D-020) |
| A10 | A typed default bill (₹4,200 / 500 kWh) would not match the sample household's real consumption, making the breakdown look wrong. | Medium (demo) | Default bill derived from the sample's own kWh, labelled illustrative (D-023) |
| A11 | A CO₂ factor value was implied but never sourced. | Medium (honesty) | Factor is `null` until filled from the CEA database with its version; UI hides CO₂ while `null` (D-024) |
| A12 | Node 20 is past end-of-life by October 2026. | Low | Node 22 LTS (D-027) |

**What a skeptical judge will challenge, and the prepared answer:**

| Challenge | Answer the project can honestly give |
|---|---|
| "One house. Will it work in mine?" | Not proven. The model is evaluated on unseen weeks of the same house. We show weekly error and the downstream check; more houses is the next step. |
| "You picked the best example." | The example day is chosen by a stated rule; weekly results for every test week are shown. |
| "Beating a mean-share split is trivial." | It is the minimum bar; we report the numbers either way. (Optional P1: a fixed-wattage rule baseline for the AC.) |
| "Isn't the problem week fake?" | Yes, it is a labelled simulated scenario. The flag is computed from the model's estimate of the modified aggregate, not from the injected ground truth. |
| "Who has 1-minute data?" | One clip-on sensor at the main panel, instead of one meter per appliance. Monthly bill readings are not enough. |
| "Why only these appliances?" | Only appliances that passed GO/NO-GO are shown; failed ones are listed with reasons in the methodology drawer. |

---

## 2. Changes from the original architecture document

| ID | Area | Original | Now | Decision |
|---|---|---|---|---|
| C-01 | Hosting | Caddy reverse proxy + sslip.io HTTPS | Uvicorn on port 80 serves API and static build; HTTPS P2 | D-004 |
| C-02 | API | `GET /api/analysis/{id}`, `results/` in S3 | Removed (P2) | D-019 |
| C-03 | Samples | 35 days ("normal_month") | 3 weeks of held-out test data; ids `normal`, `problem_week` | D-011 |
| C-04 | Contract fields | `kwh_28d`, `cost_28d_inr`, `total_kwh_28d`, `estimated_cost_28d_inr` | `kwh_period`, `cost_period_inr`, `total_kwh_period`, `estimated_cost_period_inr`; `period.weeks_*`, `days_in_period` | D-011 |
| C-05 | Error metric | `energy_error_pct` (whole test period) | `weekly_energy_error_pct` (median weekly) in registry | D-012 |
| C-06 | Savings range | `mid × (1 ± e)` | `mid ± e × kWh_W0` | D-013 |
| C-07 | Scenario size | Fixed +25% | ≥ max(40, T + 15) percentage points, set after evaluation | D-014 |
| C-08 | Evaluation contract | Metrics + one window | Adds `weekly[]`, `downstream_check`, `selection_rule`, `test_on_events`, `code_version`, `gap_minutes` | D-017 |
| C-09 | Split | Train/test | Train/gap/test, gap ≥ window/2 | D-016 |
| C-10 | Alerts | Cooldown per 10 min, link in email | One email per analysis, `send_alert` flag, self-contained text | D-019 |
| C-11 | Ownership | ML owns `nilm/`, `analytics/` | A: preprocess, nilm, energy, anomaly, pipeline. B: api, schemas, storage, alerts, validate, cost, recommend, frontend, AWS | D-020 |
| C-12 | Weekly energy | Σ valid minutes | Mean of valid minutes × 168 h (coverage-normalised) | D-021 |
| C-13 | Analysis window | Last 35 days | Whole weeks, 3–5, counted back from the last complete local day | D-021 |
| C-14 | Bill default | Typed values | Derived from sample kWh × illustrative rate; `bill_is_illustrative` | D-023 |
| C-15 | CO₂ | Factor assumed present | Nullable; hidden when not configured | D-024 |
| C-16 | Repo artifacts | Not specified | `artifacts/` mirrors S3 (JSON committed, binaries ignored) | D-025 |
| C-17 | Priorities | Backup video P1, HTTPS P1 | Backup video P0, HTTPS P2 | D-026 |
| C-18 | Node | 20 | 22 LTS | D-027 |
| C-19 | `RuleStepDetector` | Fallback, unevaluated | Must pass the same evaluation to be used | D-009 |
| C-20 | Frontend language | JavaScript implied | TypeScript (types mirror the contract) | D-028 |

---

## 3. Decisions

### D-001 — Households are the validated user; small businesses are future work
**Status:** Accepted.
**Why:** The only suitable real dataset with Indian AC data (iAWE) is residential. Claims must match the evidence.
**Alternatives:** Small businesses (no suitable sub-metered public data); both (unsupported).
**Trade-off:** Smaller market story; much stronger honesty story.

### D-002 — Python + FastAPI backend, not Java Spring Boot
**Status:** Accepted.
**Why:** Training is Python. One language means preprocessing exists once and the evaluation script imports the backend code, removing the main train/serve mismatch risk. Teammate A can read and debug the backend.
**Alternatives:** Spring Boot + ONNX Runtime Java (works, but preprocessing and analytics would be duplicated in two languages).
**Trade-off:** Teammate B learns Python/FastAPI basics during the hackathon.

### D-003 — One FastAPI monolith on one EC2 instance
**Status:** Accepted.
**Why:** One request, one analysis, no shared state. Simplest thing that works and can be debugged live.
**Alternatives:** Lambda (ML package size, cold starts), App Runner/ECS (container pipeline), SageMaker endpoint (deployment overhead for a small CPU model).
**Trade-off:** Single point of failure; mitigated by D-026.

### D-004 — Uvicorn serves frontend and API on port 80; no Caddy; HTTPS is P2
**Status:** Accepted.
**Why:** Same origin removes CORS and mixed content. One less tool to install and debug. Judges do not score TLS.
**Alternatives:** Caddy + sslip.io (original), Amplify + API (cross-origin, HTTPS-to-HTTP mixed content).
**Trade-off:** Browser shows "Not secure". Reopen this decision only if a venue or judging tool requires HTTPS.

### D-005 — No database
**Status:** Accepted.
**Why:** No accounts, no history, no queries. Every artifact is a file by key.
**Trade-off:** Results are not retrievable after the response.

### D-006 — S3 as the single artifact store
**Status:** Accepted.
**Why:** Teammate A ships models without SSH; the instance can be rebuilt from S3 + git.

### D-007 — Amazon SNS email alert (F6)
**Status:** Accepted.
**Why:** Real alert in one API call; meaningful but secondary AWS use.
**Alternatives:** SES (verified sender/recipients in sandbox).
**Trade-off:** Goes to topic subscribers, not per-user. Live delivery may lag; demo shows on-screen status plus a pre-captured screenshot as fallback.

### D-008 — ONNX Runtime for inference
**Status:** Proposed — pending validation (T-110).
**Why:** Small CPU runtime; no PyTorch or model code on the server.
**Fallback:** If export fails, load TorchScript with PyTorch CPU. Only `adapters.py` changes.

### D-009 — Sequence-to-point CNN, one model per appliance; rule-based fallback for AC
**Status:** Proposed — pending validation (gate G2, T-106/T-107).
**Why:** Well-studied NILM baseline, small, trainable in Colab within hours.
**Fallback:** `RuleStepDetector` for the AC, used only if it passes the same evaluation and GO/NO-GO.

### D-010 — iAWE as the real training/evaluation dataset
**Status:** Accepted (usability pending T-101).
**Why:** Indian household with ACs, fridge and washing machine sub-metered.
**Limitations:** One house, about 73 days. Water motor channel excluded (publisher reports it inaccurate).

### D-011 — Samples come only from the held-out test period; 3 whole weeks
**Status:** Accepted.
**Why:** Fixes audit A1. A demo built on training data inflates results and fails the question "is this unseen data?".
**Consequence:** Baseline for samples uses 2 weeks (the minimum). Field names changed to `*_period` (C-04).

### D-012 — Median weekly energy error drives the threshold and savings range
**Status:** Accepted.
**Why:** Fixes A3. The flag compares weekly energy, so the relevant error is weekly.
**Note:** Median rather than max, because with ~3 test weeks the max is one noisy number. The max is still reported in F3.

### D-013 — Savings range uses absolute uncertainty of the current-week estimate
**Status:** Accepted.
**Rule:** ARCHITECTURE.md §10.7.
**Why:** Fixes A4. Error is relative to the appliance's energy, not to the excess.

### D-014 — Problem-week injection size is derived from the threshold
**Status:** Proposed — pending validation (T-107, T-113).
**Rule:** `increase_pct = max(40, ceil(T × 100) + 15)`.
**Why:** Fixes A2. The injection must exceed the threshold by a margin, so the demo shows detection rather than a coin toss.
**Guardrail:** Never raise the injection repeatedly until it "just passes". If T is so large that the injection becomes unrealistic (judged at G2), the appliance is NO-GO for anomaly detection.

### D-015 — Flag rule is a heuristic: `T = max(0.25, 2 × e)` plus minimum excess kWh
**Status:** Proposed — pending validation (T-107). Parameters live in `settings.json` and the registry.
**Why:** Keeps model error alone from triggering most flags; minimum excess stops tiny loads producing large percentages.
**Wording:** "The threshold is set above measured model error to reduce false flags caused by disaggregation error." No guarantee is claimed.

### D-016 — Chronological split with a gap of at least half a window
**Status:** Accepted (exact dates pending T-103).
**Why:** Fixes A6 (window leakage across the boundary).

### D-017 — F3 evaluation is precomputed and includes weekly results, the downstream check, and a rule-selected example window
**Status:** Accepted.
**Why:** Fixes A5. Ground truth exists only for the dataset; recomputing live adds failure risk with no benefit.

### D-018 — No LLM, chatbot or agent framework in the product
**Status:** Accepted.
**Why:** Every number must be deterministic and explainable. Actions come from a reviewed fixed table.

### D-019 — No result persistence; one self-contained email per analysis
**Status:** Accepted.
**Why:** Fixes A8. Simplifies storage and alerts. `send_alert` lets rehearsals avoid spamming the inbox.

### D-020 — Ownership split
**Status:** Accepted.
**Rule:** ARCHITECTURE.md §2 table.
**Why:** Fixes A9. The person who understands the data writes the rules that interpret it; B owns everything request-, cloud- and UI-facing.

### D-021 — Analysis window is whole weeks; weekly energy is coverage-normalised
**Status:** Accepted.
**Why:** Makes weeks comparable when data has gaps; avoids partial-week artefacts.

### D-022 — "Likely driver", never "cause"; banned-word test
**Status:** Accepted (frozen product rule).
**Rule:** ARCHITECTURE.md §10.6, §10.11.

### D-023 — Effective cost per kWh; illustrative default bill for samples
**Status:** Accepted. Rate value pending (U-09).
**Why:** Bills contain fixed charges, slabs and taxes, so amount ÷ units is an approximation; it is labelled as such. The sample's default bill is derived from its own consumption so the breakdown is internally consistent, and it is labelled illustrative.

### D-024 — CO₂ factor from the CEA CO2 Baseline Database; nullable
**Status:** Accepted. Value pending (U-07, T-208).
**Why:** A defensible, cited Indian grid factor. Until filled, CO₂ is hidden rather than estimated with an unsourced number.

### D-025 — `artifacts/` repo folder mirrors the S3 layout
**Status:** Accepted.
**Why:** JSON artifacts get code review in git; binaries travel through S3 only.

### D-026 — Demo resilience is P0
**Status:** Accepted.
**Includes:** recorded backup video, laptop fallback (`NILM_SYNC_ON_STARTUP=false`), pre-captured alert screenshot, two timed rehearsals on the public URL.

### D-027 — Python 3.12, Node 22 LTS, Ubuntu 24.04 LTS
**Status:** Accepted.
**Why:** Ubuntu 24.04 ships Python 3.12; Node 20 reached end-of-life in April 2026.

### D-028 — TypeScript frontend
**Status:** Accepted.
**Why:** `types.ts` mirrors the contract; the compiler catches contract drift (TS-C-03).

### D-029 — Synthetic appliances are P2
**Status:** Accepted.
**Rule:** Only after the real-data pipeline works end to end. A synthetic appliance must pass through a real trained model; it is never shown as validation.

---

## 4. Unresolved decisions

| ID | Question | Needed by | Resolved by | Owner | Resolution |
|---|---|---|---|---|---|
| U-01 | Which appliances are GO? | Integration (T-501) | T-106, T-107, T-109 (gate G2) | A | — |
| U-02 | Exact train / gap / test dates; are there ≥3 valid test weeks? | Training | T-101, T-103 (gate G1) | A | — |
| U-03 | Final `T` parameters and injection size | Samples (T-113) | T-107 | A | — |
| U-04 | Who builds the frontend? Default: Teammate B with Antigravity | Phase 4 | Team decision | Both | — |
| U-05 | Model window length (proposed 99 samples at 1 min) | Training | T-105 | A | — |
| U-06 | Sum both ACs into one class, or use the larger AC only? | Training | T-101 | A | — |
| U-07 | CO₂ factor value and database edition | C4 checkpoint | T-208 | B | — |
| U-08 | Instance size (proposed `t3.medium`) | Demo | T-701 | B | — |
| U-09 | Illustrative ₹/kWh rate for sample default bills, and its cited source | Samples | T-113 | Both | — |
| U-10 | Does ONNX export work for the trained model? | Integration | T-110 | A | — |
| U-11 | Which appliance drives `problem_week` if the AC is NO-GO? | Samples | G2 | A | — |
