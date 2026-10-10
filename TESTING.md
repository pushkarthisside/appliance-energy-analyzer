# TESTING.md — Verification plan

This file defines **how** Appliance Energy Analyzer is verified. It never states expected numbers for things that depend on experiments; it defines the measurement and where the result is recorded.

Behaviour under test is defined in [ARCHITECTURE.md](ARCHITECTURE.md). Requirements acceptance criteria and traceability are maintained in [TASKS.md](TASKS.md) §14.

---

## 1. Five different kinds of claim

These must never be mixed. Passing one says nothing about the others.

| Kind | Question it answers | Evidence | Where recorded |
|---|---|---|---|
| **Software correctness** | Does the code do what the spec says? | Unit, contract, integration, API, failure tests (§3–§7) | CI / local `pytest` output |
| **Model performance** | How well does NILM estimate each appliance on unseen data from the same house? | Evaluation procedure (§8) | `artifacts/evaluation/evaluation.json` |
| **Anomaly-detection performance** | Does the flag fire on an injected increase and stay quiet on normal weeks? | Downstream check (§8.5) | `evaluation.json` → `downstream_check` |
| **Simulated demonstration behaviour** | Does the demo scenario produce the intended story? | TS-I-02, TS-E2E | Test output; rehearsal notes |
| **Real-world environmental impact** | Did any household actually save energy or emissions? | **Not measured in this project.** | Stated as a limitation everywhere |

The `problem_week` flag passing TS-I-02 proves the pipeline works on a scenario we built. It is not evidence of real-world detection performance.

---

## 2. How to run

```bash
# backend tests (from repo root)
cd backend && .venv/bin/pytest -q

# contract tests against the committed artifacts
cd backend && NILM_CACHE_DIR=../artifacts .venv/bin/pytest -q tests/test_contracts.py

# frontend type check and build
cd frontend && npm run typecheck && npm run build

# evaluation (Teammate A; needs the dataset in ml/data)
PYTHONPATH=backend python ml/evaluate.py --data ml/data --artifacts artifacts
```

Test files live in `backend/tests/`. Small fixtures live in `backend/tests/fixtures/`.

---

## 3. Unit tests (software correctness)

| ID | Module | What it checks |
|---|---|---|
| TS-U-01 | `ingest/preprocess` | Resampling to 1-minute means; gaps ≤ 5 min interpolated; gaps > 5 min stay NaN; no extrapolation at the edges |
| TS-U-02 | `ingest/preprocess` | Naive timestamps read as IST; aware timestamps converted; duplicates dropped; whole-week window counted back from the last complete local day; W0 coverage below 0.8 → `insufficient_history`; < 3 weeks → `insufficient_history` |
| TS-U-03 | `analytics/energy` | Constant 1000 W for a full week → 168 kWh; same signal with 15% NaN still → 168 kWh (coverage-normalised); ON-hours and avg ON power on a synthetic square wave; daily kWh null below 50% coverage |
| TS-U-04 | `analytics/anomaly` | Baseline = median of valid W1…W4; < 2 valid baseline weeks → `insufficient_history` |
| TS-U-05 | `analytics/anomaly` | Flag true just above `baseline × (1+T)` and false just below; false when excess < `min_excess_kwh_week`; `T` uses the floor when error is small and `2e` when large; baseline 0 case; `change_pct` null when baseline is 0 |
| TS-U-06 | `analytics/anomaly` | Driver selection for longer-time, higher-power, tie (→ longer time), zero baseline hours, null power |
| TS-U-07 | `analytics/cost` | Effective cost from amount/units and from cost_per_kwh; both given → amount/units wins; invalid bills rejected; cost = kWh × rate |
| TS-U-08 | `analytics/recommend` | Savings low/mid/high per ARCH §10.7 including the `max(0, …)` floor; CO₂ null when factor null |
| TS-U-09 | `analytics/recommend` | Ranking by ₹ mid then `change_pct`; `_default` action used for an unknown appliance; ranks start at 1 |
| TS-U-10 | all | No forbidden word (ARCH §10.11) in `actions.json`, `driver_text` constants, or alert text, case-insensitive |
| TS-U-11 | `nilm/postprocess` | Clipping; proportional scaling when Σ > aggregate; `Σ + other == aggregate` at every valid minute; NaN minutes stay NaN |
| TS-U-12 | `nilm/registry` | `no_go` entries skipped; an entry with a missing model file goes to `appliances_failed`; invalid ids rejected; `other` cannot be an id |

## 4. Contract tests

| ID | What it checks |
|---|---|
| TS-C-01 | Every file in `frontend/src/mocks/` parses with the Pydantic model for its endpoint |
| TS-C-02 | `artifacts/models/registry.json`, `config/settings.json`, `config/actions.json`, every `samples/*/scenario.json`, and `evaluation/evaluation.json` validate against ARCH §6.8 and §7; every GO appliance in the registry has an evaluation entry with `decision: "go"` |
| TS-C-03 | `npm run typecheck`: frontend types compile against the mocks |

## 5. Model parity tests

| ID | Owner | What it checks | Pass condition |
|---|---|---|---|
| TS-P-01 | A (in `export_onnx.py`) | PyTorch vs ONNX output on a held-out batch | `np.allclose(atol=1e-3)` in normalised units |
| TS-P-02 | Both (`test_parity.py`) | Backend adapter (with its own normalise/pad/window/denormalise) vs the training-side reference on one test day per GO model | max absolute difference < 1 W |

TS-P-02 failing is a release blocker: it means production does not run the model that was evaluated.

## 6. Integration tests (pipeline)

Run with `NILM_CACHE_DIR=../artifacts NILM_SYNC_ON_STARTUP=false` once real artifacts exist; before that, with small fixture artifacts in `tests/fixtures/`.

| ID | What it checks |
|---|---|
| TS-I-01 | `normal` sample → valid `AnalysisResponse`; Σ appliance kWh + other = total within 0.1%; Σ `share_pct` ≈ 100; `cost_period_inr = kwh_period × rate`; `signals` series length 672; `daily_kwh` length = days in period |
| TS-I-02 | `problem_week` sample → the modified appliance (scenario.json) is `flagged` and is issue rank 1. *Category: simulated demonstration behaviour.* |
| TS-I-03 | Same request twice → identical output except `analysis_id` |
| TS-I-04 | Fixture registry with one entry switched to `no_go` → that appliance disappears from `/api/config` and the analysis, with no code change |
| TS-I-05 | Fixture where no appliance exceeds its threshold → `issues == []` and `summary.possible_savings_inr_per_month == null` |

## 7. API and failure tests

Use FastAPI `TestClient`.

| ID | What it checks |
|---|---|
| TS-A-01 | `/api/health` always 200 with ARCH §6.9 fields; `/api/config` lists GO appliances (registry order, `other` last) and both samples |
| TS-A-02 | `/api/analyze/sample`: unknown id → 404 `unknown_sample`; bad bill → 400 `bad_bill`; omitted bill → sample default with `bill_is_illustrative: true`; `send_alert: false` → `alert.status == "not_requested"` |
| TS-A-03 | `/api/evaluation` returns the file content unchanged |
| TS-A-04 (P1) | Upload: each error code of ARCH §6.9 triggered by a crafted file (wrong header, bad timestamp, negative power, kW values, 5-min interval, 10 days, 21 MB); a valid 21-day file succeeds |
| TS-A-05 | `/` and `/some/route` return `index.html`; `/api/nope` returns JSON 404; no `Access-Control-Allow-Origin` header when `NILM_DEV_CORS=false` |
| TS-F-01 | Registry points to a missing model file → app starts, `status: "degraded"`, appliance in `appliances_failed`, analysis still works |
| TS-F-02 | S3 unreachable (bad bucket name) with a populated cache → app starts from cache, `s3_synced: false` |
| TS-F-03 | SNS client raises → analysis response still 200; error logged |
| TS-F-04 | Pipeline raises → 500 `internal` with `analysis_id`; traceback in log |
| TS-F-05 | On EC2: `sudo systemctl kill aea` → service back and healthy within 2 minutes |
| TS-F-06 | Request before startup completes → 503 `not_ready` |

## 8. Model and anomaly evaluation procedure (Teammate A)

Implemented by `ml/evaluate.py`. Definitions: ARCH §12. Results are **recorded**, never asserted in advance.

| ID | Procedure | Recorded output |
|---|---|---|
| TS-E-01 | Data inventory and coverage; confirm ≥ 3 valid test weeks (gate G1) | `ml/reports/data_inventory.md`, `ml/reports/split.md`, `dataset` block of `evaluation.json` |
| TS-E-02 | For each candidate: `mae_w`, `total_energy_error_pct`, `weekly_energy_error_pct` (median, max), ON/OFF precision/recall/F1, for the model, the naive baseline and (P1) the AC rule baseline | `model`, `naive_baseline`, `rule_baseline` |
| TS-E-03 | Weekly predicted vs actual kWh for every valid test week | `weekly[]` |
| TS-E-04 | Example window chosen by the rule of ARCH §12.6; the script prints the candidate days and their MAE so the choice can be audited | `example_window.selection_rule` + log |
| TS-E-05 | Downstream check (ARCH §12.5): normal-run false flags and injected-run detection | `downstream_check` with its `note` |
| TS-E-06 | GO/NO-GO per ARCH §12.3 with a written reason; thresholds chosen after seeing results and recorded | `decision`, `decision_note`, ARCH §2.6 (U-01) / TASKS §15 (U-01) |

Rules:
- The evaluation run uses the same commit that is deployed (`code_version`).
- Re-running evaluation after changing a threshold is allowed; changing the injection size until the check "just passes" is not (D-014).
- With about 3 test weeks, report results as a sanity check on one household, not as statistical validation.

## 9. Performance tests (on the deployed instance)

| ID | Procedure | Target (from TASKS §14.2) |
|---|---|---|
| TS-PERF-01 | Time from `systemctl start` to `samples_ready: true` (poll `/api/health` every 5 s) | ≤ 5 min |
| TS-PERF-02 | 20 calls to `/api/analyze/sample` (`send_alert: false`), measure server time with `curl -w "%{time_total}"` from the instance | p50 ≤ 1 s |
| TS-PERF-03 (P1) | Upload a 35-day 1-minute file; measure total time | ≤ 30 s |
| TS-PERF-04 | `free -m` after startup | available ≥ 25% of RAM |

Record measured values in ARCHITECTURE.md §2.6 and TASKS.md §15 under U-08.

## 10. End-to-end demo tests

| ID | Procedure | Pass condition |
|---|---|---|
| TS-E2E-01 | On the public URL, from a phone hotspot (not the team's Wi-Fi), follow README §Demo exactly | Every step works; every FR-01, 02, 04, 06–10, 12 acceptance item is visibly met; screens readable at 1280×720 |
| TS-E2E-02 | Laptop fallback (DEPLOYMENT §11.2) with Wi-Fi off after setup | Same demo works except the email |
| TS-E2E-03 | Two timed rehearsals in a row, both speakers | Each ≤ 3:00, no unscripted waiting |
| TS-E2E-04 | `problem_week` with `send_alert: true` on the public URL | Email arrives at the demo inbox; time to arrival noted |

## 11. Release gates

| Gate | Must pass |
|---|---|
| **Software complete** | TS-U-01…12, TS-C-01…03, TS-P-02, TS-I-01…05, TS-A-01…03, TS-A-05, TS-F-01…06 |
| **Model claims allowed** | TS-E-01…06 recorded; every number in the README traceable to `evaluation.json` (TASKS T-603) |
| **Deployed** | TS-PERF-01, 02, 04 meet targets on the chosen instance |
| **Demo-ready (C5)** | TS-E2E-01, 02, 03, 04 pass; backup video recorded |

Only when all four gates pass may the team call the project complete.
