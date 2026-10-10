# Appliance Energy Analyzer — Architecture (Frozen)

| | |
|---|---|
| **Status** | Frozen design baseline. Implementation must follow it. |
| **Authority** | This is the single authoritative technical specification. Other documents may summarize or link to it but must not redefine anything defined here. Any earlier architecture document (including the retired PDF) has no authority. |
| **Scope of claims** | This file specifies a design. Nothing in it states that code, models, AWS resources, emails, or tests exist or have been run. Every number in a JSON example is **illustrative**. Measured results exist only in `evaluation/evaluation.json`, produced by the offline evaluation scripts. |

---

## 1. Product definition

**Appliance Energy Analyzer** analyzes a household's aggregate (main-meter) electricity signal and:

1. estimates energy use per monitored appliance;
2. attributes approximate cost to each appliance;
3. compares each appliance's current week with its own recent weeks and flags *unusual use*;
4. names a plausible usage driver (longer operating time vs higher power while on) when the data supports one;
5. recommends an action with a *possible savings* range.

```
aggregate signal → appliance estimates → energy/cost attribution → baseline comparison
  → unusual-use flag → likely driver → recommendation → possible savings
```

NILM (non-intrusive load monitoring) is the technical method, not the product name.

### 1.1 What the product may and may not say

| May say | Must never say |
|---|---|
| "Estimated" energy and cost per appliance | That an appliance is faulty, broken, or wasting energy |
| "Unusual use" / "estimated increase" relative to the preceding two weeks | That weather or occupancy did not cause a change |
| "Possible savings if use returns to its recent level" | That savings were achieved, or that emissions were reduced |
| That model estimates for a GO appliance were checked on held-out weeks of the same household, at the evidence level stated in `evaluation.json` (§13.1) | That the models work for other homes |
| That a scenario is simulated, when it is | That synthetic traces are model predictions |

### 1.2 Real and synthetic demonstrations

Two kinds of appliance share one pipeline and one dashboard (full rules in §5, §10, §13):

- **Real-model appliance** (`provenance: real_model`): a CPU ONNX model trained and evaluated offline on real recordings (iAWE). It runs in production only if its registry status is `go`.
- **Synthetic-trace appliance** (`provenance: synthetic_trace`): a deterministic, documented, pre-generated per-minute trace. It has no model, is never evaluated as a model, and never contributes to any real-model metric.

The deterministic analytics (§9) are identical for both. The product can demonstrate its full insight workflow with no passing real model (§20.3).

---

## 2. Frozen decisions, runtime outcomes, future work

### 2.1 Frozen design decisions (implementation must follow)

| Topic | Decision |
|---|---|
| Stack | React + Vite frontend served by one FastAPI app on one EC2 instance; S3 (artifacts); IAM instance role; SNS (optional alert email); CPU ONNX Runtime; offline training/evaluation. No database, LLM, queue, container orchestration, Lambda, API Gateway, SageMaker endpoint, or auth. |
| Analysis window | Fixed **21 days** = three consecutive 7-day blocks of whole local days (§7.1). One current week, two baseline weeks. No flexible windows. |
| Time zone | `Asia/Kolkata` for all day/week boundaries. |
| Interval | 1-minute grid (60 s). |
| Results | No analysis results are stored. Sample pipeline outputs are cached in memory at startup; `analysis_id` is a correlation id only. |
| P0 data scope | Precomputed sample bundles only. **CSV upload is P1 and disabled by default** (§11.4, §17.3). |
| Alerts | Synchronous SNS publish with a short timeout; failure never fails an analysis (§16). |
| Transport | HTTP only on port 80 for the demo; limitations documented in §17.3. |
| Evaluation | Chronological split, naive baseline, pre-frozen GO/NO-GO criteria (§12.3), measured results only. |
| Emissions | Hidden unless a complete, verified `config/emissions.json` exists (§9.9). |

### 2.2 Runtime / evaluation outcomes (determined by data, never assumed)

Which appliances reach `go`; every metric; the evidence level (`independent_test`, `development_only`, `none`); per-appliance `energy_uncertainty_pct` and `min_excess_kwh_week`; scenario-check results; measured inference latency; AWS/email behavior on the day.

### 2.3 Future extensions (out of MVP)

HTTPS, persistent results, user accounts, more appliances, other households, weather adjustment, measured-savings tracking, CloudWatch metrics. None may be required by P0.

### 2.4 Audit findings and architectural baseline changes

#### Problems identified and resolved

| # | Problem | Severity | Resolution |
|---|---|---|---|
| A1 | Demo samples were 35 days, but the held-out test period of a ~73-day dataset is only about 3 weeks; samples would include training data. | Critical (honesty) | Samples use only the held-out test period, 3 whole weeks (D-011). |
| A2 | Problem-week injection was fixed at +25%, but flag threshold is `max(25%, 2 × error)`. With error > 12.5%, demo moment fails silently. | Critical (demo) | Injection size derived from T after evaluation (D-014). |
| A3 | Threshold error measured over whole test period where weekly errors cancel, while flag compares one week. | High (correctness) | Use median weekly energy error (D-012). |
| A4 | Savings range `mid × (1 ± e)` applied relative error to excess, understating uncertainty. | Medium (correctness) | Absolute uncertainty `e × kWh_W0` (D-013). |
| A5 | Evaluation showed one example day without weekly energy or flag verification evidence. | High (judging) | Weekly chart, downstream check, rule-selected window (D-017). |
| A6 | No gap between train and test windows; window could straddle both. | Medium (leakage) | Gap ≥ window/2 (D-016). |
| A7 | Caddy and sslip.io HTTPS added unnecessary points of failure. | Medium (feasibility) | FastAPI serves frontend on port 80; HTTPS is P2 (D-004). |
| A8 | Result persistence existed only for a link in the email alert. | Low | Email is self-contained; no persistence (D-019). |
| A9 | Teammate B owned AWS, API, frontend, and deployment while Teammate A owned only ML. | High (schedule) | Teammate A also owns preprocessing, energy, anomaly, and pipeline (D-020). |
| A10 | Default typed bill (₹4,200 / 500 kWh) mismatched sample consumption. | Medium (demo) | Default bill derived from sample kWh, labelled illustrative (D-023). |
| A11 | CO₂ factor implied without official source. | Medium (honesty) | Sourced from CEA database; nullable and hidden until configured (D-024). |
| A12 | Node 20 reached end-of-life in 2026. | Low | Node 22 LTS (D-027). |

#### Baseline evolution

| ID | Area | Initial Design | Current Approved Contract | Decision |
|---|---|---|---|---|
| C-01 | Hosting | Caddy reverse proxy + sslip.io HTTPS | Uvicorn on port 80 serves API and static build; HTTPS P2 | D-004 |
| C-02 | API | `GET /api/analysis/{id}`, `results/` in S3 | Removed; transient in-memory analyses only | D-019 |
| C-03 | Samples | 35 days ("normal_month") | Canonical IDs are `typical_period` (available only with a passing real model) and `simulated_scenario` (synthetic demonstration fallback). Historical IDs `normal` and `problem_week` are retired terminology. | D-011 |
| C-04 | Contract fields | `kwh_28d`, `cost_28d_inr`, `total_kwh_28d` | `kwh_period`, `cost_period_inr`, `total_kwh_period` | D-011 |
| C-05 | Error metric | `energy_error_pct` (whole test period) | `weekly_energy_error_pct` (median weekly) in registry | D-012 |
| C-06 | Savings range | `mid × (1 ± e)` | `mid ± e × kWh_W0` | D-013 |
| C-07 | Evaluation injection size | Fixed +25% | After a `go` decision, apply the fixed §12.6 rule `extra_kwh_week = (T + 0.15) × K_val`; record the injection and result without retuning. This does not change frozen GO/NO-GO criteria. | D-014 |
| C-08 | Evaluation contract | Metrics + one window | Records `weekly[]`, scenario checks, deterministic example selection, `code_version`, and the §6.6 split gap dates/counts | D-017 |
| C-09 | Split | Train/test | Chronological train/validation/test where available, with a full excluded local day between adjacent splits and no model windows crossing split boundaries (§12.2) | D-016 |
| C-10 | Alerts | Cooldown per 10 min, link in email | Retired wording: one email per analysis. Current contract: an eligible analysis may trigger one self-contained email when enabled and configured, subject to per-sample/source cooldown; `send_alert` is a request, not a delivery guarantee. | D-019 |
| C-11 | Ownership | ML owns `nilm/`, `analytics/` | A: preprocess, nilm, energy, anomaly, pipeline. B: api, schemas, storage, alerts, validate, cost, recommend, frontend, AWS | D-020 |
| C-12 | Weekly energy | Sum of valid minutes | Mean of valid minutes × 168 h (coverage-normalised) | D-021 |
| C-13 | Analysis window | Last 35 days | Fixed 21 consecutive local days: two baseline weeks and one current week (§7.1) | D-021 |
| C-14 | Bill default | Typed values | Derived from sample kWh × illustrative rate | D-023 |
| C-15 | CO₂ | Factor assumed present | Nullable; hidden when not configured | D-024 |
| C-16 | Repo artifacts | Not specified | `artifacts/` mirrors S3 (JSON committed, binaries ignored) | D-025 |
| C-17 | Priorities | Backup video P1, HTTPS P1 | Backup video P0, HTTPS P2 | D-026 |
| C-18 | Node | 20 | 22 LTS | D-027 |
| C-19 | `RuleStepDetector` | Fallback, unevaluated | Must pass same offline evaluation to be used | D-009 |
| C-20 | Frontend language | JavaScript | TypeScript mirroring schemas | D-028 |

### 2.5 Architecture Decision Record (ADR)

- **D-001 — Target household scope:** Accepted. Indian residential households with 1-minute whole-house measurements. Small businesses deferred to future work. Trade-off: narrower market scope, complete evidential integrity.
- **D-002 — Python + FastAPI backend:** Accepted. Single language with training scripts removes train/serve mismatch risks. Teammate A can read and debug backend logic.
- **D-003 — Single FastAPI process on one EC2 instance:** Accepted. Stateless request pipeline, simplest operational debugging. Mitigated by backup video and laptop fallback (D-026).
- **D-004 — Port 80 HTTP serving; no Caddy reverse proxy:** Accepted. Same-origin serving eliminates CORS and mixed-content issues. HTTPS deferred to P2.
- **D-005 — No database:** Accepted. Analyses are ephemeral computations; artifacts are file-based keys in S3.
- **D-006 — Amazon S3 as single artifact store:** Accepted. Decoupled artifact sync without requiring SSH access for model deployment.
- **D-007 — Amazon SNS email notifications:** Accepted. One API call for alert distribution; failures degrade gracefully without blocking analysis.
- **D-008 — ONNX Runtime for inference:** Proposed — pending validation (T-403). Lightweight CPU inference without PyTorch server dependency. Fallback: TorchScript with PyTorch CPU.
- **D-009 — Sequence-to-point CNN per appliance:** Proposed — pending validation (T-402, T-404). Baseline NILM architecture trainable in Colab. Fallback: `RuleStepDetector` for AC if it passes evaluation.
- **D-010 — iAWE dataset for training and evaluation:** Accepted. Delhi residential dataset with sub-metered ACs, refrigerator, and washing machine.
- **D-011 — 3-week held-out test sample scope:** Accepted. Samples use only unseen test data, eliminating data-leakage criticism.
- **D-012 — Median weekly energy error drives threshold:** Accepted. Evaluates weekly variance directly rather than cancelling over long aggregate horizons.
- **D-013 — Absolute uncertainty for savings ranges:** Accepted. Formulas apply model uncertainty relative to base appliance energy, not relative to excess alone.
- **D-014 — Threshold-derived evaluation injection:** Accepted as a fixed post-GO scenario-check rule in §12.6. It does not change or tune the frozen GO/NO-GO criteria; a missed detection is recorded as observed.
- **D-015 — Heuristic flag rule:** Proposed — pending validation. `T = max(0.25, 2 × e)` plus minimum excess kWh prevents disaggregation noise from triggering flags.
- **D-016 — Chronological split with excluded-day gaps:** Accepted. The deterministic §12.2 split excludes a full local day between adjacent splits, and the window rule discards any model window that crosses a split boundary or touches a gap/unassigned day.
- **D-017 — Precomputed evaluation artifacts:** Accepted. Ground truth exists only offline; serving reads precomputed evaluation artifact `/api/evaluation`.
- **D-018 — Deterministic analytics without LLMs or agents:** Accepted. Explicit formulas and static action tables guarantee reproducible, audited outputs.
- **D-019 — Transient analyses and self-contained alert emails:** Accepted. Eliminates per-analysis persistence and result URL lookup endpoints.
- **D-020 — Team ownership division:** Accepted. Teammate A: ML, preprocessing, analytics, pipeline. Teammate B: API, schemas, storage, alerts, frontend, AWS.
- **D-021 — Whole-week analysis and coverage normalization:** Accepted. Fixed 21-day window (1 current, 2 baseline weeks) normalized by valid minute coverage.
- **D-022 — Banned terminology test:** Accepted. Automated tests enforce "likely driver" and prohibit words implying equipment failure or defect.
- **D-023 — Effective tariff calculation and illustrative default bill:** Accepted. Bill amount ÷ units yields approximate ₹/kWh rate; defaults derived from sample kWh.
- **D-024 — Nullable CEA CO₂ factor:** Accepted. Emission metrics are hidden unless a valid factor from CEA Baseline Database is configured.
- **D-025 — S3-mirrored repository `artifacts/` layout:** Accepted. Version-controlled JSON schemas in git; model binaries transferred via S3.
- **D-026 — Comprehensive demo resilience:** Accepted. P0 requires a backup video, local laptop fallback, and timed rehearsals; capture an alert screenshot only when optional SNS alerting is configured.
- **D-027 — Python 3.12, Node 22 LTS, Ubuntu 24.04 LTS:** Accepted. Current stable LTS environments for deployment and tooling.
- **D-028 — TypeScript React frontend:** Accepted. Strict compile-time validation against backend Pydantic models.
- **D-029 — Deterministic synthetic fallback demo:** Accepted. P0 fallback ensures the product insight workflow is fully demonstrable even if no candidate model passes the GO gate.

### 2.6 Unresolved decisions and experimental variables

| ID | Question | Needed by | Resolving Task | Owner | Resolution Status |
|---|---|---|---|---|---|
| U-01 | Which appliances achieve `go` status? | Integration (T-501) | T-404, T-405 (Gate G2) | A | Open — determined by offline evaluation results |
| U-02 | Exact train/gap/test dates; verification of ≥3 valid test weeks | Training (T-402) | T-101, T-102 (Gate G1) | A | Open — determined by dataset audit |
| U-03 | Final flag threshold parameters `T` and evaluation scenario-injection size | Samples (T-109) | T-106, T-107 | A | Open — pending approved evaluation metric outputs |
| U-04 | Frontend builder assignment | Phase 2 (T-205) | Phase 2 setup | B | Resolved — Teammate B with React/TypeScript |
| U-05 | Sequence-to-point model window length | Training (T-402) | T-402 | A | Proposed — 99 samples (99 minutes) |
| U-06 | Class aggregation: sum both AC channels or use primary AC? | Training (T-402) | T-101 | A | Open — depends on sub-meter completeness |
| U-07 | CO₂ factor value and CEA database version | Config (T-206) | T-206 | B | Open — pending config sourcing; hidden when null |
| U-08 | EC2 instance sizing confirmation | Deployment (T-301) | T-301, TS-PERF-04 | B | Proposed — `t3.medium` |
| U-09 | Illustrative ₹/kWh rate for sample default bills | Samples (T-109) | T-109 | Both | Open — illustrative rate to be cited |
| U-10 | ONNX Runtime export validation | Export (T-403) | T-403 | A | Proposed — pending PyTorch to ONNX export test |
| U-11 | Secondary synthetic appliance choice for `simulated_scenario` when needed | Samples (T-109) | T-107, Gate G2 | A | Open — choose from approved synthetic traces |

---

## 3. System topology and responsibilities

```
 Browser (React SPA)
      │ HTTP :80
      ▼
 ┌──────────────────────── EC2 instance (instance type = config) ───────────────────────┐
 │ systemd → uvicorn (1 worker) → FastAPI app                                           │
 │   StaticFiles(frontend/dist) │ /api routes │ pipeline.run()                          │
 │   startup: S3 sync → validate → load adapters → precompute samples → in-memory cache │
 │   local data cache: $AEA_DATA_DIR                                                    │
 └───────────────┬──────────────────────────────────────┬───────────────────────────────┘
                 │ s3:GetObject / ListBucket            │ sns:Publish
                 ▼                                      ▼
            Amazon S3 bucket                       Amazon SNS topic → email subscribers

 Offline (developer machines, never on EC2):
   data audit → split → train → export ONNX → evaluate → generate samples/synthetic traces
   → upload artifacts to S3 with developer credentials
```

| Component | Responsibility |
|---|---|
| React app | Start panel, summary bar, four tabs, methodology drawer. Renders only what the API returns. No analytics in the browser. |
| FastAPI app | Serve static files and API; sync/validate artifacts; run the pipeline; send alerts. |
| `app/nilm` | Preprocessing, adapters, postprocessing. **Shared by serving and by `ml/`** for train/serve parity. |
| `app/analytics` | Deterministic weekly stats, baseline, flags, drivers, cost, savings, ranking. |
| S3 | Durable source of artifacts (§6). Written only by developers. |
| SNS | Email delivery of alert text. |
| IAM role | Read-only S3 + publish to one SNS topic (§17.1). |

### 3.1 Repository layout

```
backend/app/
  main.py  config.py  schemas.py  errors.py
  api/routes.py
  pipeline.py                 # run_pipeline(bundle|upload) → PipelineResult (bill-independent)
  ingest/                     # csv parsing, minute grid, week validity
  nilm/                       # preprocess.py, postprocess.py, adapters/{onnx_seq2point,trace}.py, registry.py
  analytics/                  # constants.py, weekly.py, flags.py, drivers.py, savings.py, cost.py, rank.py, wording.py
  storage.py                  # S3 sync, local cache, atomic swap
  alerts.py
backend/tests/
frontend/                     # Vite + React + Tailwind + Recharts; src/types.ts mirrors schemas.py
ml/
  data_audit.py  split.py  train.py  export_onnx.py  evaluate.py  export_registry.py
  go_criteria.json            # frozen (§12.3)
  candidates.json             # appliance classes to attempt
  synthetic/{generate.py, generate_background.py, scenarios/*.yaml}
  make_samples.py
deploy/   aea.service  aea.env.example  deploy.sh
```

Ownership (two people): **ML owner** — `ml/`, `app/nilm`, `app/analytics`, `pipeline.py`, evaluation. **Cloud/app owner** — AWS setup, `main.py`, `api/`, `storage.py`, `alerts.py`, `frontend/`, `deploy/`.

---

## 4. Terminology (canonical)

| Term | Meaning |
|---|---|
| `current`, `baseline_1` (older), `baseline_2` (more recent) | The three 7-day weeks of the window, in that naming. |
| Monitored appliance | A registry appliance that runs for this analysis (status `go` or `demo`, loaded). |
| `other` | Residual category. Reserved id. Never flagged, never given a driver or savings. |
| Valid week | ≥ 80 % valid minutes (§7.3). |
| Effective rate | `bill_amount_inr ÷ bill_units_kwh` (§9.7). |
| Basis | `real_model`, `synthetic_trace`, or `simulated_scenario` (§13.2). |

Appliance ids match `^[a-z][a-z0-9_]{1,31}$`. Real appliances use the class name (e.g. `air_conditioner`); synthetic ones append `_sim` (e.g. `air_conditioner_sim`). `other` is reserved.

---

## 5. Registry and provenance model

One registry, `registry.json`, defines every appliance the system may run.

### 5.1 Enumerations

| Field | Values |
|---|---|
| `provenance` | `real_model`, `synthetic_trace` (API rows additionally use `residual` for `other`) |
| `status` (real_model) | `candidate` (not yet decided; **not run**), `go` (run), `no_go` (**not run**) |
| `status` (synthetic_trace) | `demo` (run only in bundles that list it) |
| `adapter` | `onnx_seq2point` (real_model only), `trace` (synthetic_trace only) |

Any other combination is a registry validation error (startup fails for that entry; see §15).

### 5.2 Schema

```json
{
  "registry_version": 1,
  "interval_seconds": 60,
  "appliances": [
    {
      "id": "air_conditioner", "name": "Air conditioner", "class": "air_conditioner",
      "provenance": "real_model", "status": "candidate",
      "adapter": "onnx_seq2point",
      "model": {
        "version": "v1", "path": "models/air_conditioner/v1/model.onnx", "window_minutes": 99,
        "norm": { "mains_mean": null, "mains_std": null, "app_mean": null, "app_std": null }
      },
      "on_threshold_w": null,
      "driver_analysis": true,
      "weather_sensitive": true,
      "energy_uncertainty_pct": null,
      "uncertainty_source": "validation_weeks",
      "min_excess_kwh_week": null,
      "action_id": "reduce_runtime",
      "evaluation_ref": "real.air_conditioner"
    },
    {
      "id": "air_conditioner_sim", "name": "Air conditioner", "class": "air_conditioner",
      "provenance": "synthetic_trace", "status": "demo",
      "adapter": "trace", "model": null,
      "on_threshold_w": 150.0,
      "driver_analysis": true,
      "weather_sensitive": true,
      "energy_uncertainty_pct": 15.0,
      "uncertainty_source": "declared",
      "min_excess_kwh_week": 1.0,
      "action_id": "reduce_runtime",
      "evaluation_ref": null
    }
  ]
}
```

Rules:

- `energy_uncertainty_pct` is the single field analytics reads. For `real_model` it is written by `ml/export_registry.py` from **validation weeks** (§12.4). For `synthetic_trace` it is a declared design parameter (default 15) and is **not** a measured error.
- `null` means unavailable. A `go` entry with any of `norm.*`, `on_threshold_w` (when `driver_analysis` is true), `energy_uncertainty_pct`, or `min_excess_kwh_week` equal to `null` is invalid and treated as `load_failed` (§15).
- `status` for real models is written only by `ml/export_registry.py` from `evaluation.json`; it is never edited by hand.
- A result never contains two monitored appliances with the same `class` (`make_samples.py` enforces this; §10.3).
- `driver_analysis: false` (e.g. cycling loads whose ON threshold is not meaningful) suppresses driver output.

---

## 6. Artifacts

### 6.1 S3 layout (single bucket, private)

```
registry.json
config/actions.json
config/emissions.json                         # optional
models/{appliance_id}/{version}/model.onnx    # real_model only
samples/{sample_id}/manifest.json
samples/{sample_id}/aggregate.csv
samples/{sample_id}/synthetic/{appliance_id}.csv
evaluation/evaluation.json
evaluation/data_audit.json
```

Developers write these with their own credentials. The EC2 role cannot write S3.

### 6.2 `aggregate.csv` and trace CSVs

Header `timestamp,power_w`; ISO-8601 timestamps with offset `+05:30`; exactly 30 240 rows (21 × 1440) at 1-minute spacing starting at local midnight; empty `power_w` means missing. Trace CSVs have the same shape.

### 6.3 Sample manifest

```json
{
  "schema_version": 1,
  "sample_id": "simulated_scenario",
  "title": "Simulated scenario",
  "description": "A real held-out household signal combined with documented simulated appliances. Simulated appliances change usage in the current week. If no valid real 21-day base exists, the manifest instead describes a fully synthetic aggregate and traces.",
  "simulated": true,
  "window": { "start": "2000-01-03T00:00:00+05:30", "days": 21 },
  "aggregate_origin": "real_base_plus_synthetic",
  "real_base": { "source": "iAWE", "split": "test", "start": "2000-01-03T00:00:00+05:30", "end": "2000-01-24T00:00:00+05:30" },
  "synthetic_background": null,
  "synthetic_appliances": [
    { "id": "air_conditioner_sim", "trace": "synthetic/air_conditioner_sim.csv",
      "generator": { "script": "ml/synthetic/generate.py", "config": "ml/synthetic/scenarios/simulated_scenario.yaml",
                     "config_sha256": "<hash>", "seed": 12345 },
      "expected_status": "unusual" }
  ],
  "composition": "For real_base_plus_synthetic: aggregate.csv = real_base + sum(synthetic appliance traces); real models receive aggregate minus synthetic traces. For fully_synthetic: aggregate.csv = synthetic background + sum(synthetic appliance traces); real-model inference is disabled.",
  "aggregate_sha256": "<hash>"
}
```

`aggregate_origin` is `real_base_plus_synthetic` or `fully_synthetic`. For `real_base_plus_synthetic`, `real_base` is required, its split is `test` or `validation` (never `train`), and `aggregate.csv = real_base + sum(synthetic appliance traces)`. For `fully_synthetic`, `real_base` is `null`; the manifest must include `synthetic_background` metadata (generator script, scenario config, config hash, seed), and `aggregate.csv = synthetic background + sum(synthetic appliance traces)`. The background represents unitemized load and is not an appliance estimate. No real-model inference is allowed on a fully synthetic bundle. `simulated` is `true` iff `synthetic_appliances` is non-empty or `aggregate_origin` is `fully_synthetic`. Dates above are illustrative placeholders; real manifests carry true recording dates (no timestamp shifting).

### 6.4 `config/actions.json`

```json
{
  "version": 1,
  "savings_label": "Possible savings if use returns to its recent level",
  "driver_texts": {
    "longer_operating_time": "The estimated increase is associated with longer operating time.",
    "higher_power_when_on": "The estimated increase is associated with higher power while running.",
    "unclear": "The estimates do not point to a single usage pattern."
  },
  "caveats": {
    "general": "Compared only with the preceding two weeks. Weather, occupancy and holidays are not adjusted for.",
    "weather_sensitive": "This appliance's use often varies with the weather, so a change can be seasonal."
  },
  "actions": {
    "reduce_runtime": "Review the schedule and use timers or switch it off when not needed."
  }
}
```

Wording constraint (unit-tested on this file and on all generated issue text): no match of the case-insensitive regex `\b(fault\w*|broken|wast\w*|caus\w*)\b`.

### 6.5 `config/emissions.json` (optional)

All fields required, otherwise treated as absent: `factor_kg_co2e_per_kwh` (number > 0), `source_name`, `source_url`, `edition`, `publication_year`, `geography`, `retrieved_on` (date), `verified_by`. **This document contains no factor value.**

### 6.6 `evaluation/evaluation.json`

Produced by `ml/evaluate.py` on every run, including when no usable split or candidate exists. In that case it records `evidence_level: "none"`, nullable split boundaries, an empty `real` object, and explicit reasons no model was evaluated; it must not fabricate metrics or dates. Served unchanged by `GET /api/evaluation`.

```json
{
  "schema_version": 1,
  "generated_at": "2000-01-01T00:00:00Z",
  "code_version": "<git sha>",
  "criteria_sha256": "<hash of ml/go_criteria.json>",
  "dataset": { "name": "iAWE", "audit_ref": "evaluation/data_audit.json" },
  "evidence_level": "independent_test",
  "no_evaluation_reason": null,
  "splits": {
    "gap_days": 1,
    "gap_dates": ["<date>", "<date>"],
    "train":      { "weeks": 0, "start": "<date>", "end": "<date>" },
    "validation": { "weeks": 0, "start": "<date>", "end": "<date>" },
    "test":       { "weeks": 3, "start": "<date>", "end": "<date>" }
  },
  "real": {
    "air_conditioner": {
      "decision": "go",
      "failed_criteria": [],
      "evaluated_on": "test",
      "n_weeks": 3,
      "model_version": "v1",
      "test_reused": false,
      "model": { "mae_w": 0.0, "weekly_energy_error_pct": { "median": 0.0, "worst": 0.0 }, "onoff_f1": 0.0, "coverage_pct": 0.0 },
      "naive": { "mae_w": 0.0, "weekly_energy_error_pct": { "median": 0.0, "worst": 0.0 }, "onoff_f1": 0.0 },
      "weekly": [ { "week_start": "<date>", "actual_kwh": 0.0, "model_kwh": 0.0, "naive_kwh": 0.0 } ],
      "example_day": { "date": "<date>", "rule": "median daily MAE", "t": [], "aggregate_w": [], "actual_w": [], "model_w": [] }
    }
  },
  "scenario_checks": [
    { "appliance_id": "air_conditioner", "evaluated_on": "test",
      "injection": { "extra_kwh_week": 0.0, "extra_minutes_per_day": 0, "power_w": 0.0, "start_local_time": "13:00", "capped": false },
      "current_week_status": "unusual", "detected": true }
  ],
  "unmodified_window_check": { "go_appliances_checked": 1, "unusual_flags": 0 },
  "synthetic": { "pipeline_checks": [ { "sample_id": "simulated_scenario", "appliance_id": "air_conditioner_sim", "expected_status": "unusual", "observed_status": "unusual" } ] }
}
```

All numeric zeros above are placeholders. Rules: `real` contains **only** `provenance: real_model` appliances, including `no_go` ones with `failed_criteria` listing reasons. `synthetic` never contains metrics about real appliances or accuracy-style metrics; it only records pipeline checks. `evidence_level` ∈ `independent_test`, `development_only`, `none` (§12.2). For `none`, `splits.train`, `splits.validation`, and `splits.test` are `null`, `gap_dates` is empty, `real` is `{}`, and the file includes a concise `no_evaluation_reason`. For other levels, unavailable split dates/counts are `null`, never fabricated. Missing numbers are `null`, never `0`.

### 6.7 Local cache

`$AEA_DATA_DIR/current/` mirrors the bucket layout. Startup downloads into `$AEA_DATA_DIR/staging/`, validates, then atomically renames to `current/` (previous `current/` kept as `previous/`). See §15.

---

## 7. Time, preprocessing, missing data

Implemented once in `app/nilm/preprocess.py` and `app/ingest/`; used by training, evaluation, and serving.

### 7.1 Window definition (defined only here)

- The analysis window is **21 consecutive local days** starting at local midnight: 30 240 one-minute slots.
- Weeks: `baseline_1` = days 1–7, `baseline_2` = days 8–14, `current` = days 15–21. Each is 10 080 slots.
- Samples: window start is fixed in the manifest.
- Uploads (P1): the window is the last 21 *complete* local days of the data, where a day is complete if the data extends to that day's last minute.

### 7.2 Minute grid

1. Parse timestamps (tz-aware ISO-8601; naive values are interpreted as `Asia/Kolkata`).
2. Convert `power_w` to float. Values `< 0`, `> 30 000`, or non-finite become missing.
3. Duplicate timestamps: mean. Resample to 1-minute **mean** (bins labelled by bin start). Empty bins stay missing. **No interpolation or imputation.**

### 7.3 Week validity

`coverage = valid_minutes / 10 080` after the grid is built. A week is valid iff `coverage ≥ 0.80`. Window coverage is the same ratio over 30 240 slots.

### 7.4 Scaling for missing minutes

For any block with `n_valid` valid minutes (energy series defined on valid minutes only):

```
kwh_block = mean_power_w(valid) × block_hours / 1000        # block_hours = 168 (week) or 504 (window)
on_hours_block = (on_minutes / n_valid) × block_hours
avg_on_power_w = mean(power_w over valid ON minutes)        # null if on_minutes == 0
```

ON means `power_w ≥ on_threshold_w`. Daily kWh uses the same rule with `block_hours = 24` and a day is `null` if its coverage is below 50 %.

---

## 8. Estimation adapters and postprocessing

### 8.1 Adapter contract

```
predict(mains_w: float64[T] with NaN) -> float64[T] with NaN
```

- **`onnx_seq2point`**: input windows of 99 minutes centered on each minute, normalized with the registry's training-only stats, batch size 2048, ONNX Runtime CPU provider. Output is de-normalized to watts. A minute is NaN if its window contains any NaN or extends beyond the series (first/last 49 minutes). No imputation.
- **`trace`**: loads `synthetic/{id}.csv` of the bundle, validated like §6.2. No inference.

### 8.2 Pipeline (bill-independent)

```
load bundle → build grid(aggregate) → synthetic = Σ trace adapters (known)
mains_for_models = max(aggregate − synthetic, 0)          # only when synthetic traces exist
estimates[a] = adapter_a.predict(mains_for_models)  for each real_model go appliance
postprocess (§8.3) → other
weekly stats (§9.1) → baseline/flags/drivers (§9.2–9.5)
```

Real models are given only the real component because they were not trained on synthetic loads; this is disclosed in the manifest (`composition`) and the methodology drawer. In bundles without synthetic traces `mains_for_models = aggregate`.

### 8.3 Postprocessing (identical in `ml/evaluate.py` and serving)

Per minute where `mains_for_models` is valid:

1. Clip each real estimate to `[0, mains_for_models]` (NaN estimates become 0 for the sum but remain missing for that appliance's own statistics).
2. If the sum of real estimates exceeds `mains_for_models`, scale all of them by `mains_for_models / sum`.
3. `other = mains_for_models − Σ real estimates` (≥ 0 by construction).

The displayed aggregate is `mains_for_models + Σ synthetic`. Minutes where `aggregate` is missing are missing for everything.

### 8.4 Implemented interface (code as of 2026-10-10)

| Step | Call | Behaviour |
|---|---|---|
| Load sample | `app.ingest.bundle.load_bundle(sample_dir) -> Bundle` | Validates manifest (§6.3), 1-minute CSV grid (§6.2) and `aggregate_sha256`; raises `BundleError` |
| Load registry | `app.nilm.registry.load_registry(path) -> Registry` | Unusable file raises `RegistryError` (`not_ready`); an invalid entry goes to `entry_errors` and never runs |
| Startup, per sample | `app.pipeline.run_pipeline(bundle, registry, evidence_level, real_adapters) -> PipelineResult` | Bill-independent; computed once and cached by `app.runtime.build_runtime` |
| Per request | `app.pipeline.apply_bill(result, bill_amount_inr, bill_units_kwh, actions, emissions=None, alert_status=None) -> AnalysisResponse` | Invalid bill raises `ValueError("invalid_bill")`, mapped to HTTP 422 |
| Real models | `app.nilm.adapters.onnx_seq2point.OnnxSeq2PointAdapter` | Loaded only for `go` entries; never invoked on a `fully_synthetic` bundle (callers may pass the same adapters to every sample) |

Local mode: with `AEA_S3_BUCKET` unset, startup reads `$AEA_DATA_DIR/current/`, or `$AEA_DATA_DIR` itself when it contains `registry.json` (for example `AEA_DATA_DIR=../artifacts` from `backend/`), and reports `s3_sync.state = failed_using_cache` (health `degraded`) because no sync ran. Unmatched `/api/*` paths return HTTP 404 with error code `not_found` (API-04). `generated_at` and `analysis_id` differ between otherwise identical responses (TS-I-03).

---

## 9. Analytics (single definition)

All in `app/analytics`, pure NumPy/Python, with constants in `analytics/constants.py`:

| Constant | Value |
|---|---|
| `WINDOW_DAYS` / `WEEK_DAYS` | 21 / 7 |
| `MIN_VALID_FRACTION` | 0.80 |
| `MIN_BASELINE_KWH_WEEK` | 0.5 |
| `FLAG_THRESHOLD_FLOOR` | 0.25 |
| `FLAG_ERROR_MULTIPLIER` | 2 |
| `MIN_EXCESS_FLOOR_KWH` | 1.0 |
| `DRIVER_MIN_RATIO` | 1.10 |
| `DAYS_PER_MONTH` | 30 |
| `SYNTHETIC_DEFAULT_UNCERTAINTY_PCT` | 15 |

### 9.1 Weekly statistics

For each monitored appliance and each of the three weeks (valid minutes of that appliance's series, §7.4): `kwh`, `on_hours`, `avg_on_power_w`. A week statistic is `null` if the week is invalid. `kwh_period` is the 21-day window kWh (§7.4). Appliance share: `share_pct = kwh_period / total_kwh_period × 100`, where the total is the displayed aggregate's window kWh; shares of monitored appliances plus `other` sum to 100 within rounding.

### 9.2 Status per monitored appliance

Evaluated in order; first match wins.

| Order | Condition | `status` | `status_reason` |
|---|---|---|---|
| 1 | `current` week invalid | `insufficient_data` | `current_week_invalid` |
| 2 | `baseline_1` or `baseline_2` invalid | `insufficient_data` | `baseline_week_invalid` |
| 3 | `baseline_kwh < MIN_BASELINE_KWH_WEEK` | `insufficient_data` | `baseline_too_small` |
| 4 | flag rule (§9.3) true | `unusual` | `null` |
| 5 | otherwise | `typical` | `null` |

`insufficient_data` never produces a verdict, percentage change, driver, issue, or savings (`change_pct` is `null`). `other` has no status (`null`).

### 9.3 Baseline and flag rule

```
baseline_kwh = median(kwh_baseline_1, kwh_baseline_2)         # equals their mean
e            = energy_uncertainty_pct / 100
T            = max(FLAG_THRESHOLD_FLOOR, FLAG_ERROR_MULTIPLIER × e)
excess_kwh   = kwh_current − baseline_kwh
unusual  ⇔  kwh_current > baseline_kwh × (1 + T)  AND  excess_kwh > min_excess_kwh_week
change_pct   = excess_kwh / baseline_kwh × 100
```

Limits: the baseline is two weeks; weather, season, occupancy, and holidays are not modelled. T is a design heuristic (an increase below about twice the typical weekly estimation error cannot be told apart from estimation error), not a statistical test.

### 9.4 Driver

Only if `unusual`, `driver_analysis` is true, `on_hours` and `avg_on_power_w` baselines (medians of the two baseline weeks) and current values are all non-null and the baselines are `> 0`:

```
r_time  = on_hours_current / median(on_hours_b1, on_hours_b2)
r_power = avg_on_power_current / median(avg_on_power_b1, avg_on_power_b2)
if r_time ≥ r_power and r_time  ≥ DRIVER_MIN_RATIO → longer_operating_time
elif r_power > r_time and r_power ≥ DRIVER_MIN_RATIO → higher_power_when_on
else → unclear
```

If any required input is missing: `driver = null`, `driver_text = null`. Driver text comes from `actions.json` and states an association only.

### 9.5 Savings (heuristic sensitivity range)

Only for `unusual` appliances:

```
mid_kwh_month  = excess_kwh × DAYS_PER_MONTH / WEEK_DAYS
low_kwh_month  = max(0, mid_kwh_month × (1 − e))
high_kwh_month = mid_kwh_month × (1 + e)
inr_*          = *_kwh_month × effective_rate_inr_per_kwh
```

This is a **heuristic sensitivity range, not a calibrated confidence interval.** It reflects only the appliance's estimation uncertainty `e`; it ignores baseline uncertainty, weather, behavior, and tariff slabs. It is *possible savings if use returned to the preceding weeks' level*, not a forecast and not a measured reduction. Values are computed unrounded and rounded at output (kWh 2 decimals, ₹ integer).

Illustrative example: `baseline 60, current 85, e = 0.15` → `T = max(0.25, 0.30) = 0.30`; `85 > 78` and `25 > min_excess` → unusual; `mid = 25×30/7 = 107.14 kWh`; `low 91.07`, `high 123.21`; at ₹8.40/kWh: ₹765 / ₹900 / ₹1,035 per month.

### 9.6 Ranking

Issues sorted by `savings.inr_per_month.mid` descending, ties by `change_pct` descending, then `appliance_id` ascending. `rank` starts at 1.

### 9.7 Cost attribution

```
effective_rate_inr_per_kwh = bill_amount_inr / bill_units_kwh
cost_period_inr(appliance) = kwh_period × effective_rate
estimated_cost_period_inr  = total_kwh_period × effective_rate
```

The effective rate is an *average* that spreads fixed charges and slab pricing over all units; marginal cost may differ. `estimated_cost_period_inr` is a 21-day estimate, not the bill. Bill inputs: finite, `> 0`, each `≤ 10 000 000`; otherwise `invalid_bill`. If the rate is `< 1` or `> 50` ₹/kWh a warning `bill_rate_unusual` is added (analysis continues).

### 9.8 Issue content

Each issue carries: driver text (if any); `caveats` = `[caveats.general]` plus `caveats.weather_sensitive` when the registry flag is true; the action text for `action_id`; the savings label from `actions.json`. Language is neutral; no malfunction diagnosis.

### 9.9 Emissions

- If `config/emissions.json` is complete, `emissions` (top level) holds the factor metadata and each non-illustrative issue's `savings.kg_co2e_per_month` is `{low, mid, high}` = kWh range × factor (kg CO₂e). Otherwise `emissions = null` and every `kg_co2e_per_month = null`, and the UI hides emissions.
- Issues with `savings.illustrative = true` always have `kg_co2e_per_month = null` (synthetic or simulated outputs never feed environmental claims).
- Values are *potential* avoided emissions, never measured reductions.

---

## 10. Samples and synthetic generation

### 10.1 Samples (P0)

| `sample_id` | Content | Simulated |
|---|---|---|
| `typical_period` | Real-data demonstration from a held-out aggregate; available only when a real appliance model has `go` under §12.3; real `go` models only | no |
| `simulated_scenario` | Prefer a real held-out base plus documented synthetic-trace appliances; if no valid 21-day base exists, use a fully synthetic background plus synthetic-trace appliances (§10.2–10.3) | yes |

A sample is `available: false` when it would contain no monitored appliance (e.g. `typical_period` when no model is `go`). Samples are built offline by `ml/make_samples.py` and uploaded to S3.

### 10.2 Real base selection and fallback

**Preferred path:** use a real base window of three valid consecutive weeks taken only from validation or test, never training. The window must be contained entirely within the named split and checked against `evaluation.json`; record the exact source dates without timestamp shifting.

**Mandatory fallback:** if no such 21-day validation/test window exists (including `development_only` with only two validation weeks, or evidence level `none`), generate a fully synthetic 21-day background plus deterministic synthetic appliance traces. Set `aggregate_origin: "fully_synthetic"`, `real_base: null`, include `synthetic_background` generator metadata, and state plainly in the manifest description that the aggregate and appliance traces are simulated. Do not pad, repeat, shift, or relabel real data to manufacture a 21-day window. Never use training days as a sample base. A fully synthetic bundle must not run real-model inference, contribute to real-model metrics, or support claims about household performance. `tests/test_samples.py` validates the appropriate branch and provenance.

### 10.3 Synthetic appliances and scenarios

- A synthetic appliance is generated by `ml/synthetic/generate.py` from a YAML scenario config with a fixed seed and written to committed trace CSVs. The config hash and seed are in the manifest. Regeneration must be byte-identical.
- For the fully synthetic fallback only, a separate deterministic background generator produces the unitemized aggregate load; record its script, config hash, and seed as `synthetic_background`. It is not registered as an appliance and is not included in appliance metrics.
- Per-appliance config: daily ON windows (start time, duration), `power_w` and `noise_std_w`, an optional weekday pattern, and an optional **current-week change**: `extra_minutes_per_day` (→ `longer_operating_time`) or `power_multiplier` (→ `higher_power_when_on`).
- Default P0 scenario: at least one and up to two synthetic appliances for classes with no `go` real model, e.g. `air_conditioner_sim` (longer operating time in the current week) and `water_heater_sim` (higher power while on in the current week). If every attempted class has a `go` model, choose a separate demonstration class not represented by a `go` model. A class with a `go` real model is never also simulated. `simulated_scenario` is invalid if it contains no synthetic appliance trace.
- The expected status of each synthetic appliance is stored in the manifest as `expected_status`; a unit test asserts the pipeline produces it. That test verifies code behavior on constructed data, **not** detection performance.
- Synthetic vs simulated: a *synthetic appliance* is a complete generated trace with known ground truth (`provenance: synthetic_trace`). A *simulated aggregate scenario* (the injection in §12.6) modifies a real aggregate and exists **only inside evaluation**; it is never shown as a UI sample.

---

## 11. API

Base path `/api`. JSON. All errors use:

```json
{ "error": { "code": "invalid_bill", "message": "bill_amount_inr must be greater than 0", "details": null } }
```

### 11.1 Error codes

| Code | HTTP | Meaning |
|---|---|---|
| `invalid_bill` | 422 | Bill missing, non-finite, `≤ 0`, or `> 10 000 000` |
| `unknown_sample` | 404 | `sample_id` not in manifest set |
| `sample_unavailable` | 503 | Sample failed startup precompute or has no monitored appliance |
| `not_ready` | 503 | Startup incomplete (§15) |
| `feature_disabled` | 404 | Upload route while `AEA_ENABLE_UPLOAD=false` |
| `bad_format` | 422 | CSV unparseable, wrong content type, or > 10 % invalid rows |
| `missing_columns` | 422 | `timestamp` or `power_w` absent |
| `too_large` | 413 | File > `AEA_MAX_UPLOAD_MB` |
| `interval_too_coarse` | 422 | Median sampling interval > 60 s |
| `invalid_units` | 422 | Peak power < 50 W (likely kW) |
| `insufficient_history` | 422 | Fewer than 21 complete days or window coverage < 80 % |
| `no_models_available` | 503 | Upload requested but no `go` model loaded |
| `evaluation_unavailable` | 404 | `evaluation.json` missing/invalid |
| `internal` | 500 | Unexpected error (no internals leaked) |

### 11.2 Endpoints

| Method | Path | Request | Success response | Errors |
|---|---|---|---|---|
| GET | `/api/health` | — | Health object (§15.3). HTTP 200 for `ok`/`degraded`, 503 for `not_ready` | — |
| GET | `/api/config` | — | Config object (§11.3) | `not_ready` |
| POST | `/api/analyze/sample` | `{ "sample_id": str, "bill": { "amount_inr": number, "units_kwh": number } }` | AnalysisResponse (§11.5) | `invalid_bill`, `unknown_sample`, `sample_unavailable`, `not_ready`, `internal` |
| POST | `/api/analyze/upload` (P1) | multipart: `file`, `bill_amount_inr`, `bill_units_kwh` | AnalysisResponse | `feature_disabled`, `invalid_bill`, `too_large`, `bad_format`, `missing_columns`, `interval_too_coarse`, `invalid_units`, `insufficient_history`, `no_models_available`, `not_ready`, `internal` |
| GET | `/api/evaluation` | — | Contents of `evaluation.json` (§6.6) | `evaluation_unavailable` |

Non-API paths serve the React build with SPA fallback to `index.html`.

### 11.3 Config object

```json
{
  "app_version": "0.1.0",
  "window_days": 21,
  "upload_enabled": false,
  "alerts_enabled": false,
  "max_upload_mb": 20,
  "evidence_level": "independent_test",
  "emissions_available": false,
  "samples": [
    { "id": "typical_period", "title": "Typical period", "description": "…", "simulated": false, "available": true },
    { "id": "simulated_scenario", "title": "Simulated scenario", "description": "…", "simulated": true, "available": true }
  ]
}
```

`evidence_level` is read from `evaluation.json` (`none` if absent).

### 11.4 Upload rules (P1, default off)

CSV with header `timestamp,power_w`; limits per §11.1. CSV upload is a P1 capability and disabled by default. The content is processed in memory, analyzed, and discarded; the application does not persist it to local disk or S3 and does not log its contents. Only `go` real models run; synthetic traces never apply. The response has `source.kind = "upload"` and `source.validated_domain = false`; the UI shows a notice that estimates for other homes are unverified. Uploads must not be used on the public HTTP demo for private data (§17.3).

### 11.5 AnalysisResponse (canonical; values illustrative; `appliances` and `signals` abridged)

```json
{
  "analysis_id": "an_3f9c1a2b",
  "generated_at": "2000-01-01T00:00:00Z",
  "source": {
    "kind": "sample", "sample_id": "simulated_scenario",
    "title": "Simulated scenario", "description": "…",
    "simulated": true, "simulated_appliance_ids": ["air_conditioner_sim"],
    "evidence_level": "independent_test", "validated_domain": true
  },
  "period": {
    "start": "2000-01-03T00:00:00+05:30", "end": "2000-01-24T00:00:00+05:30", "days": 21,
    "coverage_pct": 97.4,
    "weeks": {
      "baseline_1": { "start": "2000-01-03T00:00:00+05:30", "end": "2000-01-10T00:00:00+05:30", "valid": true, "coverage_pct": 98.1 },
      "baseline_2": { "start": "2000-01-10T00:00:00+05:30", "end": "2000-01-17T00:00:00+05:30", "valid": true, "coverage_pct": 97.0 },
      "current":    { "start": "2000-01-17T00:00:00+05:30", "end": "2000-01-24T00:00:00+05:30", "valid": true, "coverage_pct": 97.2 }
    }
  },
  "cost": { "bill_amount_inr": 4200, "bill_units_kwh": 500, "effective_rate_inr_per_kwh": 8.4 },
  "summary": {
    "total_kwh_period": 350.0, "estimated_cost_period_inr": 2940.0,
    "monitored_count": 1, "largest_monitored_appliance_id": "air_conditioner_sim", "issues_count": 1
  },
  "appliances": [
    { "id": "air_conditioner_sim", "name": "Air conditioner", "provenance": "synthetic_trace",
      "kwh_period": 205.0, "cost_period_inr": 1722.0, "share_pct": 58.57, "coverage_pct": 97.4,
      "weekly_kwh": { "baseline_1": 60.0, "baseline_2": 60.0, "current": 85.0 },
      "status": "unusual", "status_reason": null,
      "daily_kwh": [ { "date": "2000-01-03", "kwh": 8.6 } ] },
    { "id": "other", "name": "Other", "provenance": "residual",
      "kwh_period": 145.0, "cost_period_inr": 1218.0, "share_pct": 41.43, "coverage_pct": 97.4,
      "weekly_kwh": { "baseline_1": 48.0, "baseline_2": 49.0, "current": 48.0 },
      "status": null, "status_reason": null, "daily_kwh": [] }
  ],
  "issues": [
    { "rank": 1, "appliance_id": "air_conditioner_sim", "appliance_name": "Air conditioner",
      "basis": "synthetic_trace",
      "current_kwh": 85.0, "baseline_kwh": 60.0, "excess_kwh_week": 25.0,
      "change_pct": 41.7, "threshold_pct": 30.0,
      "driver": "longer_operating_time",
      "driver_text": "The estimated increase is associated with longer operating time.",
      "caveats": ["Compared only with the preceding two weeks. Weather, occupancy and holidays are not adjusted for.",
                  "This appliance's use often varies with the weather, so a change can be seasonal."],
      "recommendation": { "action_id": "reduce_runtime", "text": "Review the schedule and use timers or switch it off when not needed." },
      "savings": {
        "label": "Possible savings if use returns to its recent level",
        "illustrative": true,
        "kwh_per_month": { "low": 91.07, "mid": 107.14, "high": 123.21 },
        "inr_per_month": { "low": 765, "mid": 900, "high": 1035 },
        "kg_co2e_per_month": null
      } }
  ],
  "signals": { "window": "current_week", "start": "2000-01-17T00:00:00+05:30", "step_minutes": 15,
               "aggregate_w": [450.0], "by_appliance": { "air_conditioner_sim": [300.0], "other": [150.0] } },
  "emissions": null,
  "warnings": [],
  "alert": { "status": "sent" }
}
```

Field rules:

- `source.simulated` = any simulated appliance in the bundle. `source.evidence_level` is the evaluation evidence level for the real components (`null` for uploads); `validated_domain` is `true` only for samples.
- `issue.basis` ∈ `real_model` (real model on a non-simulated bundle), `synthetic_trace` (synthetic appliance), `simulated_scenario` (reserved for evaluation outputs; not emitted in P0 samples). `savings.illustrative` is `true` iff `basis ≠ real_model`.
- `weekly_kwh` values and `daily_kwh` entries are `null` where invalid; `status_reason` ∈ `current_week_invalid`, `baseline_week_invalid`, `baseline_too_small`, or `null`.
- `signals` covers the **current week** at 15-minute means (672 points; `null` for missing).
- `warnings` entries: `{ "code", "message" }`; codes: `bill_rate_unusual`, `appliance_unavailable` (a `go`/`demo` appliance failed to load; its energy is then in `other`).
- `alert.status` ∈ `sent`, `failed`, `disabled`, `no_issues`, `cooldown`.
- No field is duplicated under another name; `null` always means unavailable.

---

## 12. Evaluation methodology

Implemented by `ml/` scripts; uses `app/nilm` preprocessing, adapters, and postprocessing so training/evaluation and serving share code.

### 12.1 Data audit

`ml/data_audit.py` inspects the iAWE files actually present and writes `evaluation/data_audit.json`: actual date range, sampling intervals, per-appliance sub-meter availability, coverage per local day. For splitting (§12.2), a 7-day *span* is *usable* if its aggregate coverage is ≥ 80 %; per-appliance sub-meter coverage is enforced by GO criterion 6 (§12.3) and by discarding training windows whose target is missing. Candidate appliance classes (`ml/candidates.json`) are filtered to those with sub-metered data. Nothing about dates, counts, or appliances is assumed in advance.

### 12.2 Splits and evidence level

`ml/split.py` is the only place splits are computed; `train.py`, `evaluate.py`, and `make_samples.py` import it.

**Definitions.** Days are local calendar days (`Asia/Kolkata`). A *span* is 7 consecutive whole days; spans are evaluated at every start day (they are not anchored to the dataset's first day). A span is *usable* per §12.1. `latest_run(limit_day, n)` returns the run of `n` contiguous usable spans (7n consecutive days) whose last day is the latest day `≤ limit_day`, or nothing if no such run exists. `last_data_day` is the latest local day present in the dataset. Daily coverage is valid minutes ÷ 1 440.

**Algorithm (exact, deterministic):**

1. **Test.** `T = latest_run(last_data_day, 3)` (21 days, first day `d_T`). If none, go to step 5.
2. **Test gap.** Day `d_T − 1` is excluded from every split and from every model window. Days between the end of validation (step 3) and this gap day, if any, are unassigned and unused.
3. **Validation.** `V = latest_run(d_T − 2, 3)`; if none, `latest_run(d_T − 2, 2)` (first day `d_V`). If none, go to step 5.
4. **Validation gap and train.** Day `d_V − 1` is excluded. **Train** = every local day `≤ d_V − 2`; it must contain at least 28 days with daily aggregate coverage ≥ 80 %. If it does, the result is `independent_test`; otherwise go to step 5.
5. **Development-only fallback.** No test split. `V = latest_run(last_data_day, 3)`, or if none `latest_run(last_data_day, 2)`; day `d_V − 1` is excluded; train = every day `≤ d_V − 2` with the same ≥ 28-day requirement. If satisfied: `development_only`. Otherwise: `none` (no real model is trained for GO).

Resulting layout (chronological): `train … | gap day | validation (2–3 spans) | [unassigned days] | gap day | test (3 spans)`; there is at least one whole excluded day between adjacent splits. Validation and test consist of whole 7-day spans; train need not.

**Window rule.** A model input window (99 minutes) and its target minute belong to a split only if every one of those minutes lies on days of that split. Windows that touch a gap day, an unassigned day, or another split's days are discarded. Validation and test are evaluated on their own contiguous series, so their first and last 49 minutes are NaN (§8.1) and are not scored. `ml/split.py` returns each split's start/end and the excluded gap dates; `evaluation.json` records them (§6.6).

Other rules: no shuffling across time; preprocessing statistics, ON thresholds, hyperparameters, and early stopping use **train/validation only**.

`independent_test` means: test weeks were not used for training, model selection, threshold calibration, or scenario design, and each candidate model version was evaluated on them once. If any model is changed after test results were viewed, the affected appliance's entry gets `test_reused: true` and its evidence is reported as `development_only`; the file-level `evidence_level` becomes `development_only` if any GO appliance is affected. Even `independent_test` is one household and one time period; it supports only the claim "unseen weeks of the same household" (§13.1).

### 12.3 GO/NO-GO criteria (frozen now, before any result exists)

Stored in `ml/go_criteria.json`; `criteria_sha256` is recorded in `evaluation.json`. These are design parameters chosen without looking at results and **must not be changed after evaluation results exist**. Evaluation split = test (if `independent_test`) else validation. An appliance is `go` iff **all** hold:

| # | Criterion |
|---|---|
| 1 | Median weekly energy error ≤ 30 % and worst week ≤ 50 % |
| 2 | Model MAE ≤ 0.9 × naive MAE (at least 10 % better) |
| 3 | Model median weekly energy error ≤ naive median weekly energy error |
| 4 | If `driver_analysis` is true: model ON/OFF F1 > naive ON/OFF F1 |
| 5 | Median actual weekly energy in the evaluation weeks ≥ `MIN_BASELINE_KWH_WEEK` (0.5 kWh) |
| 6 | Every evaluation week has ≥ 80 % coverage; at least 3 weeks (test) or 2 weeks (development_only) |

Otherwise `no_go`. No_go candidates stay in `evaluation.json` with their metrics. Thresholds are never adjusted to make a candidate pass.

**Executable gate rules (`ml/evaluate.py`):**

- Every criterion is evaluated and recorded; none is skipped or replaced by a default. The only permitted non-evaluation is criterion 4 when `driver_analysis` is false (criterion not applicable).
- A metric a criterion requires (for the model **or** the naive baseline) is *undefined* if it cannot be computed or is not finite: no valid minutes; `Σactual = 0` (weekly energy error); `2TP + FP + FN = 0` (ON/OFF F1, with `F1 = 2TP / (2TP + FP + FN)`); an empty evaluation set; or fewer evaluation weeks than criterion 6 requires. Undefined metrics are stored as `null` in `evaluation.json` — never `0` — and **the criterion that needs them fails**, so the appliance is `no_go`.
- `failed_criteria` is a list of strings `"<criterion number>:<reason>"`, where reason is `threshold_not_met:<metric>` or `metric_undefined:<metric>` (e.g. `"4:metric_undefined:onoff_f1_naive"`, `"1:threshold_not_met:weekly_energy_error_worst"`). An appliance is `go` only if `failed_criteria` is empty.
- The same rule applies to the §12.4 validation-derived registry values: if `energy_uncertainty_pct` or `min_excess_kwh_week` cannot be computed, the appliance is `no_go` with reason `registry_input_undefined:<field>`.

### 12.4 Metrics

| Metric | Definition |
|---|---|
| MAE (W) | mean `|pred − actual|` over valid minutes |
| Weekly energy error (%) | `|Σpred − Σactual| / Σactual × 100` per week (weekly kWh per §7.4); median and worst reported |
| ON/OFF F1 | using `on_threshold_w` (from training sub-meter data) on predicted vs actual; only when `driver_analysis` |
| Naive baseline | `pred = aggregate × share`, `share = Σ appliance energy / Σ aggregate energy` over the training split (ratio of sums); all metrics reported for naive and model |
| Coverage | valid fraction per evaluation week |

`ml/export_registry.py` sets, from **validation weeks only** (computed before the final run): `energy_uncertainty_pct = worst validation-week weekly energy error`; `min_excess_kwh_week = max(1.0, worst validation-week absolute weekly energy error in kWh)`. In `development_only` mode the same weeks are used for GO and calibration; this is stated in `evidence_level`. If there are no validation weeks, the appliance cannot be `go`.

### 12.5 Example day

The evaluation day with the **median daily MAE** (lower median if even) is selected by this rule, never by hand, and stored with its series.

### 12.6 Scenario checks (kept separate from model accuracy)

For each `go` appliance, **run once**, after the GO decision, on the evaluation window:

1. Compute the injection by a fixed rule: `extra_kwh_week = (T + 0.15) × K_val`, where `T` comes from the registry and `K_val` is the median weekly *actual* energy of that appliance in validation weeks.
2. Add to the `current` week of the aggregate a constant load of the appliance's median training-ON power for `extra_minutes_per_day = extra_kwh_week × 1000 × 60 / (power_w × 7)` minutes per day starting at 13:00 local (cap 360; if capped, record `capped: true`).
3. Run the full pipeline; record `current_week_status` and `detected = (status == "unusual")`.
4. Also record the number of `unusual` flags in the **unmodified** window (`unmodified_window_check`).

The injection size rule and outputs are recorded and **never re-tuned** after seeing a result; a missed detection is reported as `detected: false`. These checks test pipeline mechanics on a modified real signal; they are not a real-world detection rate (one window; one household). They are never included in `real` metrics, and they do not decide GO/NO-GO.

### 12.7 Synthetic isolation

`ml/evaluate.py` refuses any appliance with `provenance: synthetic_trace` in the `real` section, and its tests assert that no synthetic id appears there and that no synthetic data touched any split. `synthetic.pipeline_checks` only records expected-vs-observed status for constructed bundles.

### 12.8 Evaluation tab content

Evidence-level statement; for each real appliance (GO and NO-GO): decision, failed criteria, model-vs-naive table, weekly predicted/actual/naive kWh chart, example-day overlay; scenario-check and unmodified-window callouts filled from the file; a line that simulated demonstration appliances are not evaluated against real data. If `real` is empty, the tab states that no real-data appliance model has been validated.

### 12.9 Synthetic-data prototype model (not served)

`ml/prototype_synthetic/train.py` trains a sequence-to-point network (scikit-learn `MLPRegressor`, exported to ONNX) for an air conditioner on randomized simulated households, and evaluates it on held-out simulated households through the serving adapter (§8.1) against the naive baseline. Results are written to `ml/prototype_synthetic/report.json`. The prototype has no registry entry, is never served, and its metrics never enter `evaluation.json`, the UI, or any accuracy claim (§13): it shows that the training, export and inference path works, not how a model performs in real homes. Real models still require the iAWE pipeline (§12.1-§12.6).

---

## 13. Provenance and claim rules

### 13.1 What the product may claim, by evidence level

| `evidence_level` | Allowed statement about real-model appliances |
|---|---|
| `independent_test` | "Estimates for [GO appliances] were evaluated on weeks of the same household that were not used for training, model selection or threshold setting." |
| `development_only` | "Estimates were checked on held-out weeks during development. This is not independent validation." |
| `none` / no GO appliance | "No real-data appliance model has been validated. This demonstration uses simulated scenarios." |

Never claimed: performance for other homes; detection rates; faults; achieved savings or emissions reductions.

### 13.2 Provenance propagation

| Stage | Carrier |
|---|---|
| Registry | `provenance`, `status` |
| Manifest | `simulated`, `synthetic_appliances`, `composition` |
| API | `appliances[].provenance`, `source.simulated`, `source.simulated_appliance_ids`, `issues[].basis`, `savings.illustrative` |
| Evaluation | `real` vs `synthetic` sections |
| Alert email | source line (§16) |
| UI | scenario description, methodology drawer, issue basis line |

### 13.3 UI disclosure without per-appliance badges

- Appliances appear in one consistent visual style; **no synthetic badge beside appliances in lists or charts**.
- The start panel shows the selected sample's `description` (which states plainly when it is simulated).
- A persistent **"Data & method"** link in the summary bar opens the methodology drawer, which lists every appliance with its source ("Model estimate from real household data, evaluated" / "Simulated demonstration trace") and the composition rule (§8.2).
- Each issue card shows a one-line *basis* ("Based on: model estimate" or "Based on: simulated demonstration data"); savings for illustrative issues read "Illustrative".
- Presentations and the README must state which parts are simulated (see §20.5).

### 13.4 Synthetic outputs and environmental claims

Synthetic and simulated outputs never enter real metrics (§12.7) and never produce emissions numbers (§9.9).

---

## 14. Frontend

Vite + React + Tailwind + Recharts; state in `App.jsx`/`App.tsx`; no router. `frontend/src/types.ts` mirrors `schemas.py`. Production build in `frontend/dist`, served by FastAPI `StaticFiles` (`AEA_FRONTEND_DIR`).

| Area | Content |
|---|---|
| Start panel | Sample buttons (only `available` samples), scenario description, bill form (amounts prefilled with illustrative defaults, editable), Analyze. Upload control only if `upload_enabled`. |
| Summary bar | Total kWh, estimated cost, largest monitored appliance, issue count, "Data & method" link. |
| Tab 1 — Where the money goes | Horizontal bars (kWh/₹ toggle), appliance rows with `typical`/`unusual`/`insufficient_data`, 21-day daily drill-down. `other` shown as "Other (not itemized)". |
| Tab 2 — How the estimates were checked | Current-week signal stack; Evaluation content per §12.8. |
| Tab 3 — What changed | Current vs baseline weeks per appliance; change %; driver text; caveats. `insufficient_data` appliances show a neutral "not enough data" row. |
| Tab 4 — What to fix first | Ranked issue cards (action, savings range with label, basis, caveats); emissions line only when present; alert status. |
| Methodology drawer | Window and baseline definition, flag rule and savings formula in plain language and their limits, evidence statement (§13.1), appliance sources, simulated-scenario disclosure, tariff limitation, emissions factor details if available. |

Errors from the API are displayed with their `message`. Loading and `not_ready` states are explicit.

---

## 15. Startup, caching, health, failure handling

### 15.1 Startup sequence

1. Download S3 artifacts to `$AEA_DATA_DIR/staging/` (list + get all keys under the layout in §6.1). On success, validate then atomically swap into `current/`.
2. If S3 sync fails: if `current/` exists, use it and report `s3_sync.state = failed_using_cache`; otherwise `failed_no_cache` → `not_ready`.
3. Validate `registry.json` (§5), `actions.json`, optional `emissions.json`. Invalid registry → `not_ready`. Invalid emissions file → treated as absent.
4. Load adapters: for each `go` real model, create an ONNX Runtime session; `demo` entries need no load. A failure marks that appliance `runtime_state = load_failed` (it is excluded; its energy falls into `other`).
5. Precompute every sample (§8.2 up to weekly stats) and keep the bill-independent result in memory. A failing sample is marked `failed`.
6. Ready when the registry is valid and at least one sample is `ready`.

### 15.2 Request behavior

`/api/analyze/sample` applies the bill (cost, savings in ₹, emissions if available), builds issues, publishes the alert (§16), and returns. There is no per-analysis storage. Sample analyses reuse cached pipeline results; target latency is under one second (a target, to be measured).

### 15.3 Health object

```json
{
  "status": "ok",
  "ready": true,
  "s3_sync": { "state": "ok", "at": "2000-01-01T00:00:00Z" },
  "registry_version": 1,
  "appliances": [ { "id": "air_conditioner", "provenance": "real_model", "registry_status": "go", "runtime_state": "loaded", "detail": null } ],
  "samples": [ { "id": "typical_period", "state": "ready", "detail": null } ],
  "alerts": { "enabled": false, "topic_configured": false },
  "upload_enabled": false
}
```

`runtime_state` ∈ `loaded`, `load_failed`, `inactive` (registry status not run). Overall: `ok` = all good; `degraded` = at least one `load_failed`, one failed sample, or `failed_using_cache` (serving continues, HTTP 200); `not_ready` = HTTP 503.

### 15.4 Failure rules

- Never return a partial analysis silently: any unavailable appliance adds the `appliance_unavailable` warning.
- If no model is `go`, the system remains ready (synthetic scenario only, §20.3).
- A `fully_synthetic` sample is invalid if any real-model adapter is invoked; reject the bundle during sample validation or precompute. A `real_base_plus_synthetic` sample may invoke only registry entries with `status: go`.
- Unhandled errors return `internal` without stack traces; details go to the application log (no uploaded data in logs).

---

## 16. Alerts (SNS, optional)

- Alerts are optional. Enable only after the SNS topic, email subscription, and end-to-end notification path have been configured and tested. Runtime enablement requires `AEA_ALERTS_ENABLED=true` and `AEA_SNS_TOPIC_ARN` to be set; subscriptions must be confirmed beforehand.
- An eligible analysis with non-empty `issues` may trigger an alert when requested, subject to a per-`sample_id`/source cooldown of `AEA_ALERT_COOLDOWN_SECONDS` (default 600). A `cooldown` result means delivery was suppressed by that cooldown; an email is not guaranteed for every analysis.
- Publish is synchronous with a 3-second timeout. Any exception sets `alert.status = "failed"` and never fails the analysis.
- Subject: `Appliance Energy Analyzer: unusual use estimated for N appliance(s)`. Plain-text body: source line (sample title; "Simulated demonstration scenario" when `source.simulated`), per issue: appliance, estimated change %, possible savings range (₹/month; marked "illustrative" when applicable), and the caveat line. No wording banned by §6.4.
- The on-screen alert status is the primary evidence during a demo; the email is supplementary.

---

## 17. AWS, configuration, security

### 17.1 Resources

One private S3 bucket, an optional SNS standard topic, one EC2 instance in `ap-south-1` with an instance profile. The instance type, resource names, and account ids are **configuration choices** (`t3.medium` is the planned default), not provisioned or tested facts. IMDSv2 required. Security group: inbound 80 from anywhere (demo), 22 from the team's IP addresses only; no other inbound.

IAM policy for the instance role:

| Service | Actions | Resource |
|---|---|---|
| S3 | `s3:ListBucket` | the bucket |
| S3 | `s3:GetObject` | `bucket/*` |
| SNS | `sns:Publish` | the topic ARN |

The EC2 role has read-only S3 access and no `s3:PutObject`, including for `uploads/*`. `sns:Publish` is granted only to the configured topic when alerting is used. AWS credentials are never stored in the repository or on the instance. Developers upload artifacts from their own machines using separate credentials limited to artifact prefixes (`models/`, `samples/`, `evaluation/`, and `config/`), with `s3:ListBucket` and only the required `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` object actions. Uploaded CSV content is processed in memory and is never persisted to local disk or S3; no S3 upload-prefix lifecycle rule is needed.

### 17.2 Environment variables (`/etc/aea/aea.env`, no secrets)

| Variable | Default | Meaning |
|---|---|---|
| `AEA_S3_BUCKET` | — (required) | Artifact bucket |
| `AEA_AWS_REGION` | `ap-south-1` | Region |
| `AEA_DATA_DIR` | `/opt/aea/data` | Local cache root |
| `AEA_FRONTEND_DIR` | `/srv/aea/frontend/dist` | Built SPA |
| `AEA_ALERTS_ENABLED` | `false` | Enable SNS alerts only after the topic, confirmed email subscription, and end-to-end notification path are configured and tested |
| `AEA_SNS_TOPIC_ARN` | — | Topic ARN |
| `AEA_ALERT_COOLDOWN_SECONDS` | `600` | Cooldown |
| `AEA_ENABLE_UPLOAD` | `false` | Enable upload route (P1) |
| `AEA_MAX_UPLOAD_MB` | `20` | Upload limit |
| `AEA_LOG_LEVEL` | `INFO` | Logging |

Analytics constants (§9) are in code, not environment.

### 17.3 Security limitations (documented, accepted for the demo)

- HTTP only; traffic is unencrypted. There is no authentication. The public demo therefore serves **precomputed samples only**; upload stays disabled, and private household data must not be uploaded over this deployment. HTTPS is a future extension.
- Uploaded data (P1) is processed in memory and discarded.
- Rate limiting is not implemented; the instance is single-purpose and disposable.

---

## 18. Deployment

Build the frontend on a developer machine (`npm ci && npm run build`); the instance needs no Node. `deploy/deploy.sh` copies `backend/` and `frontend/dist/` from the checked-out release with `rsync` over SSH and restarts the service. Do not use `git pull` on the instance as the deployment mechanism.

Paths: `/srv/aea/backend` (code, `.venv`), `/srv/aea/frontend/dist`, `/opt/aea/data` (cache), `/etc/aea/aea.env`.

```ini
# /etc/systemd/system/aea.service
[Unit]
Description=Appliance Energy Analyzer
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/srv/aea/backend
EnvironmentFile=/etc/aea/aea.env
ExecStart=/srv/aea/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 1
Restart=always
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```

One worker keeps the in-memory sample cache and alert cooldown consistent. Backend runtime dependencies: `fastapi`, `uvicorn`, `numpy`, `pandas`, `onnxruntime`, `boto3`, `pydantic`. Training dependencies (e.g. PyTorch) are offline only.

### 18.1 Provisioning and operations

Use region `ap-south-1`. Before provisioning, enable account MFA, configure a monthly cost budget alert, and check expected resource costs. The S3 bucket is private, has all Block Public Access settings enabled, and uses server-side encryption. It stores configured artifacts and samples; do not configure an upload-only lifecycle rule because uploads are never persisted. Keep any lifecycle rule for a separately approved artifact type only when that artifact's retention requirements call for it.

Create and harden the bucket with the AWS CLI (replace `<bucket>` with its unique name):

```bash
aws s3api create-bucket --bucket <bucket> --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-public-access-block --bucket <bucket> \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket <bucket> \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

Attach an EC2-trusted instance role. Its S3 permissions are limited to `s3:ListBucket` on the bucket and `s3:GetObject` on the configured artifact objects; it has no S3 write access. If SNS alerting is enabled, allow `sns:Publish` only to its configured topic. Developers upload artifact updates from their own machines using separate credentials scoped to the artifact prefixes (`models/`, `samples/`, `evaluation/`, and `config/`). Never store AWS credentials in Git or on the instance. Require IMDSv2. The security group allows TCP 80 for the public demo and TCP 22 only from team `/32` addresses.

Create and confirm the SNS email subscription only when enabling optional alerts. Test the end-to-end application notification path before setting `AEA_ALERTS_ENABLED=true`; otherwise leave the documented default `false`. The application environment file is `/etc/aea/aea.env`, root-owned and mode 644, and contains no secrets. The deployment example values are: `AEA_S3_BUCKET=<bucket>`, `AEA_AWS_REGION=ap-south-1`, `AEA_DATA_DIR=/opt/aea/data`, `AEA_FRONTEND_DIR=/srv/aea/frontend/dist`, `AEA_ALERTS_ENABLED=false`, `AEA_SNS_TOPIC_ARN=<topic-arn>` when configured, `AEA_ALERT_COOLDOWN_SECONDS=600`, `AEA_ENABLE_UPLOAD=false`, `AEA_MAX_UPLOAD_MB=20`, and `AEA_LOG_LEVEL=INFO`.

When enabling alerts, create the topic, subscribe the demo inbox, confirm its subscription, and test SNS publishing. Then test an eligible application analysis end to end before enabling alerts in the environment:

```bash
aws sns create-topic --name aea-alerts --region ap-south-1
aws sns subscribe --topic-arn <topic-arn> --protocol email --notification-endpoint <demo-email>
aws sns publish --topic-arn <topic-arn> --subject "Appliance Energy Analyzer test" --message "Test alert"
```

Provision Ubuntu Server 24.04 LTS x86_64, planned default `t3.medium` (confirm against the performance requirements), 20 GiB gp3 storage, and the instance role. Keep the SSH key outside the repository. Install Python 3.12 and Git; the service runs from `/srv/aea/backend` with its virtual environment, serves the frontend from `/srv/aea/frontend/dist`, and uses `/opt/aea/data` for the validated artifact cache. The systemd unit runs Uvicorn as `ubuntu` on port 80 with one worker and `CAP_NET_BIND_SERVICE`; enable and start `aea`, then verify `/api/health` locally and from a phone using mobile data. Inspect service state and logs with `systemctl status aea` and `journalctl -u aea`.

On the deployment machine, install the backend environment and build the frontend before deploying the checked-out release:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
cd .. && ./deploy/deploy.sh
curl -fsS http://<elastic-ip>/api/health
```

For code deployment, check out the intended release in the developer-side deployment clone and run `deploy/deploy.sh`; it transfers that checkout and restarts the service. To roll back, tag each known-good release (for example, `demo-ready-N`). In the deployment clone run `git checkout --detach demo-ready-N`, then run `./deploy/deploy.sh` from that checkout. The detached HEAD is expected: the script deploys the checked-out files and does not pull. After rollback, return to the existing working branch with `git switch main`. For artifact-only rollback, point the registry to the previous model version, sync artifacts, and restart the service. If recovery fails, use the prepared laptop fallback, then the backup video.

On the prepared laptop fallback, sync the configured artifact bucket into a local cache, build the frontend, install the documented backend environment, and run Uvicorn with `AEA_DATA_DIR` pointed at that cache, `AEA_FRONTEND_DIR` at the build, and `AEA_ALERTS_ENABLED=false`. State clearly that the demo is running locally. After judging, stop or terminate the instance and release the Elastic IP; remove no-longer-needed SNS resources and credentials according to the team's account cleanup procedure.

---

## 19. Testing requirements

| Test | Asserts |
|---|---|
| `test_preprocess` | Minute grid, invalid-value handling, no imputation, week validity at the 80 % boundary, scaling formulas (§7) |
| `test_postprocess` | Clip, proportional scaling, `other ≥ 0`, sum ≤ mains (§8.3) |
| `test_analytics` | Status order (§9.2), flag boundaries, zero/tiny baseline → `insufficient_data` with `change_pct = null`, driver edge cases (missing stats → `null`), savings and ranking formulas against the worked example, `other` never flagged |
| `test_wording` | Banned-word regex on `actions.json` and every generated string |
| `test_parity` | Training-time and serving predictions agree on a fixed input (max abs difference ≤ 1 W) |
| `test_samples` | 30 240 rows, 3 valid weeks, manifest hashes, `expected_status` matches pipeline output; real-base samples use validation/test only; fully synthetic fallback has `real_base: null`, background metadata, deterministic regeneration, explicit disclosure, and no real-model inference; `simulated_scenario` has at least one synthetic appliance trace |
| `test_synthetic_reproducible` | Regenerated traces are byte-identical |
| `test_splits` | On constructed coverage patterns: splits are disjoint and ordered train < validation < test; at least one whole excluded day separates adjacent splits and gap dates match `splits.gap_dates`; validation/test are whole 7-day spans; **no model window crosses a split boundary or touches a gap day**; fallback to `development_only` / `none` as in §12.2 |
| `test_go_gate` | Zero actual energy, undefined F1, missing weeks → criterion fails, `no_go`, metric stored as `null`, reason in `failed_criteria` (format §12.3); criterion 4 not applicable only when `driver_analysis` is false |
| `test_evaluation_isolation` | No synthetic id in `real`; criteria hash matches `go_criteria.json` |
| `test_api_contracts` | Every endpoint's success and error shapes; error codes in §11.1 |
| `test_registry` | Provenance/status/adapter combinations (§5.1); null-field rules |

Verification boundary: none of these have been run as of this document.

---

## 20. Scope, fallbacks, plan

### 20.1 P0 — minimum reliable submission

- Backend and frontend deployed on AWS (§17–18) with S3 sync and IAM role.
- Every sample that is available under §10 analyzed end to end; the `simulated_scenario` fallback remains available independently of real-model evaluation; shared analytics, cost attribution, and ranked issues with possible savings.
- Real-model inference only for appliances with `status: go`.
- Synthetic demonstration appliances via `trace` adapter.
- Four tabs, methodology drawer, evaluation panel generated from real `evaluation.json`.
- SNS alert **only if** it can be tested before the demo; otherwise `AEA_ALERTS_ENABLED=false` and the demo omits it.
- Backup demo materials: screen recording of the full walkthrough and screenshots.

### 20.2 P1

CSV upload (§11.4) with HTTPS or local-only use; additional drill-downs; alert cooldown tuning.

### 20.3 Fallback when no real model passes GO/NO-GO

The registry contains only `no_go`/`candidate` real entries plus synthetic ones. `typical_period` is unavailable. `simulated_scenario` uses a real held-out base signal (all real load in `other`) plus synthetic appliances when a valid 21-day validation/test base exists; otherwise it uses a fully synthetic background plus synthetic appliances. The latter is disclosed in the sample description, start panel, methodology drawer, Evaluation tab, and demo script. The UI states that no real-data appliance model has been validated. Delivery does not depend on any model passing.

### 20.4 P2

HTTPS, persistent storage, emissions display with a verified factor, measured-savings tracking, more appliances/homes, weather adjustment, CloudWatch.

### 20.5 Demo script (2–3 minutes)

1. Problem: one bill, one number.
2. `typical_period` (if available): estimated cost by appliance; state the evidence-level sentence from §13.1 exactly.
3. Evaluation tab: GO/NO-GO and model-vs-naive results as stored — including any NO-GO.
4. `simulated_scenario`: say it is simulated; show the change and driver, then the ranked action and "possible savings" range.
5. Alert badge/email if enabled; otherwise skip.
6. Close: estimates from one meter signal; savings are possible, not measured; real-data evaluation is limited to one household.

### 20.6 Execution order and four-day plan (two people)

**Binding order.** Training or model debugging must never block the working demo.

1. **Build the smallest end-to-end application path** using the prepared sample contract and deterministic analytics interfaces.
2. **Implement and verify the deterministic synthetic fallback** (`simulated_scenario`, no `go` model); generate and retain fallback artifacts. The fallback may use a valid held-out validation/test base or the fully synthetic background in §20.3.
3. **Implement the shared data-processing and evaluation pipeline**, including the data audit and exact split procedure (§12.1–12.2), and freeze the GO/NO-GO criteria before evaluation results are examined.
4. **Evaluate real models** against those frozen criteria and record actual metrics and decisions.
5. **Integrate only `go` models**, retaining the independently working fallback artifacts.
6. **Complete the core results experience and evidence display** and verify the available-sample flow.
7. **Add optional SNS alerts or polish** only after the P0 fallback and results experience work. Enable SNS only after its full path has been configured and tested.

**Freeze rule:** at the start of Day 4 no further model work begins; any candidate without a recorded evaluation decision stays `candidate` and the fallback in §20.3 applies without schedule impact.

| Day | ML owner | Cloud/app owner |
|---|---|---|
| 1 | Step 1: deterministic analytics interfaces and shared processing skeleton | Step 1: API/frontend skeleton, schemas/errors, and smallest end-to-end prepared-sample path |
| 2 | Step 2: deterministic synthetic traces, fallback bundle, and fallback verification; then Step 3 data audit/splits and frozen criteria | Step 2: complete fallback journey, deploy fallback, and record backup demo |
| 3 | Step 3: evaluation pipeline; Step 4: train/export/evaluate candidate models against frozen criteria | Step 6: complete core results experience and evidence display on available samples |
| 4 | Step 5: integrate only `go` models; parity and sample checks | Step 6 verification; Step 7: configure and test optional alerts or finish polish; rehearse and refresh backup recording |

---

## 21. Frozen versus flexible

| Frozen | Flexible |
|---|---|
| Stack and topology (§2.1, §3) | Instance type, resource names |
| 21-day window and formulas (§7, §9) | UI layout details |
| Registry/API/artifact schemas (§5, §6, §11) | Model architecture, as long as the adapter contract (§8.1) holds |
| GO/NO-GO criteria and split rules (§12) | Which appliance classes are attempted (`ml/candidates.json`) |
| Provenance and claim rules (§13) | Synthetic scenario contents within §10.3 |
