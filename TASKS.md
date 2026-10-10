# TASKS.md — Appliance Energy Analyzer

## 1. Purpose and Rules

This file defines implementation order, ownership, dependencies, and completion criteria.

**Technical authority:** `ARCHITECTURE.md` is frozen and authoritative. Do not redefine its API contracts, schemas, preprocessing, formulas, evaluation criteria, provenance rules, or AWS topology here.

### Priorities

- **P0:** Required for a reliable submission.
- **P1:** Implement only after the P0 application works end to end.
- **P2:** Optional work after P0 is complete.

### Status tracking

Use these statuses:

- `NOT_STARTED`
- `IN_PROGRESS`
- `BLOCKED`
- `DONE`

Do not mark tasks `DONE` without verifying their completion criteria. No task is assumed complete merely because it is documented.

### Team ownership

- **ML/data owner:** Data audit, split logic, preprocessing, model training and evaluation, synthetic traces, analytics, sample generation, and parity tests.
- **Cloud/app owner:** AWS setup, FastAPI integration, artifact storage, React frontend, deployment, health checks, and demo preparation.

Both teammates review shared contracts and end-to-end integration.

## 2. Binding Execution Order

Follow this order from `ARCHITECTURE.md` §20.6:

1. Build the smallest end-to-end application path.
2. Implement and verify the deterministic synthetic fallback independently of real-model evaluation.
3. Implement the shared data-processing and evaluation pipeline; freeze GO/NO-GO criteria before examining results.
4. Evaluate real models against the frozen criteria and record actual results.
5. Integrate only models that pass; complete the core results experience and evidence display.
6. Add optional SNS alerts or polish only after the P0 fallback and results experience work. Enable SNS only after the complete notification path is configured and tested.

**Critical rule:** Real-model training must never block the working fallback demo.

## 3. Phase 0 — Repository and Contracts

**Priority:** P0

**Owners:** Both

- [ ] **T-001 — Inspect repository and current implementation**
  - Inspect the existing source tree, dependencies, tests, and Git status.
  - Identify which required components already exist and which are missing.
  - Do not assume any task or test is complete based on documentation alone.

- [ ] **T-002 — Establish project structure and development environment**
  - Follow the repository layout in `ARCHITECTURE.md` §3.1.
  - Configure Python and frontend dependencies.
  - Ensure secrets, local environments, and restricted data are excluded from Git.
  - Verify the documented test commands work or record the blocker.

- [ ] **T-003 — Verify implementation contracts**
  - Review `ARCHITECTURE.md`, `PROJECT.md`, `TASKS.md` (§14 requirements matrix), and the current implementation.
  - Resolve any conflict that would affect implementation before proceeding.
  - Keep the API and frontend types consistent with the frozen schemas.

**Completion gate:** Repository structure is understood, the team knows the current implementation state, and blocking contract conflicts are identified.

## 4. Phase 1 — Deterministic Analytics and Synthetic Fallback

**Priority:** P0

**Owner:** ML/data owner

This phase must produce a usable fallback without depending on a passing real appliance model.

- [ ] **T-101 — Audit the available iAWE data**
  - Implement or verify `ml/data_audit.py`.
  - Record actual date ranges, sampling intervals, aggregate coverage, and available appliance sub-meter data.
  - Write `evaluation/data_audit.json`.
  - Do not assume specific recording dates, coverage, or usable appliances.

- [ ] **T-102 — Implement chronological split logic**
  - Implement or verify `ml/split.py` against `ARCHITECTURE.md` §12.2.
  - Apply the frozen gap, coverage, contiguous-span, and minimum-training-data rules.
  - Support `independent_test`, `development_only`, and `none`.
  - Never manufacture a valid split by shifting, padding, or reusing data.

- [ ] **T-103 — Freeze and verify GO/NO-GO criteria**
  - Commit `ml/go_criteria.json` using the criteria in `ARCHITECTURE.md` §12.3.
  - Freeze and record the criteria before inspecting final evaluation results; do not tune thresholds afterward to obtain a pass.
  - Verify that undefined required metrics fail the relevant criterion and are recorded as `null`, not zero.
  - Status 2026-10-10: `ml/go_criteria.json` committed and frozen before any result. The executable gate in `ml/evaluate.py` is not implemented yet.

- [x] **T-104 — Implement shared preprocessing**
  - Implement or verify the minute grid, timestamp handling, invalid-value handling, and coverage rules.
  - Do not interpolate or impute missing minutes.
  - Ensure training, evaluation, and serving use the same preprocessing implementation.

- [x] **T-105 — Implement postprocessing**
  - Clip real-model estimates to the valid aggregate signal.
  - Apply proportional scaling when estimates exceed the available signal.
  - Calculate the non-negative residual category `other`.
  - Preserve missing values for each appliance's own statistics.

- [x] **T-106 — Implement deterministic analytics**
  - Implement or verify weekly statistics, baseline calculations, unusual-usage flags, drivers, cost attribution, possible-savings ranges, and issue ranking.
  - Follow the exact formulas and constants in `ARCHITECTURE.md` §9.
  - Ensure `insufficient_data` produces no verdict, driver, issue, or savings.
  - Ensure `other` is never flagged or assigned a driver or savings.

- [x] **T-107 — Implement synthetic appliance traces**
  - Implement or verify `ml/synthetic/generate.py` and the scenario YAML configuration.
  - Use fixed seeds and deterministic generation.
  - Ensure regeneration produces byte-identical traces.
  - Generate at least one synthetic appliance for the simulated scenario.

- [x] **T-108 — Implement synthetic background fallback**
  - Implement or verify the deterministic background generator for the fully synthetic fallback.
  - Record the generator, configuration hash, and seed in the manifest.
  - Treat background load as unitemized aggregate load, not as a monitored appliance.
  - Never run real-model inference on a fully synthetic aggregate.

- [ ] **T-109 — Generate sample bundles**
  - Implement or verify `ml/make_samples.py`.
  - Generate `typical_period` only when at least one real appliance model passes the frozen criteria (`go`) and a valid real-model sample can be built.
  - Generate `simulated_scenario` using a valid held-out validation/test base plus synthetic traces when available; otherwise use the fully synthetic fallback.
  - Record actual provenance, dates, hashes, scenario configuration, and expected synthetic status.
  - Never use training days as the sample base.
  - Upload the fallback artifact set to S3 when ready.
  - Status 2026-10-10: `simulated_scenario` (fully synthetic fallback) built by `ml/build_fallback.py`; `typical_period` not built (no `go` model). Not yet uploaded to S3.

**Phase completion gate:**

- Data audit and split outputs reflect the actual dataset.
- Deterministic analytics follow the frozen formulas.
- Synthetic generation is reproducible.
- The simulated scenario produces the expected status.
- The sample manifest and provenance are valid.
- The fallback artifacts exist and are ready for integration.

## 5. Phase 2 — API and Frontend on the Fallback

**Priority:** P0

**Owner:** Cloud/app owner

Start with the synthetic fallback. Do not wait for model training.

- [x] **T-201 — Implement API schemas and errors**
  - Implement or verify `backend/app/schemas.py` and `backend/app/errors.py`.
  - Match the frozen request, response, and error contracts.
  - Ensure unavailable values are represented as `null` where specified.

- [x] **T-202 — Implement artifact storage and startup**
  - Implement or verify S3 synchronization and local cache handling.
  - Validate artifacts before swapping the cache into service.
  - Support the documented fallback when S3 synchronization fails.
  - Load real models only when their registry status is `go`.
  - Allow synthetic-trace entries with status `demo` without loading a model.
  - Precompute valid samples and expose their availability accurately.

- [x] **T-203 — Implement the FastAPI endpoints**
  - Implement or verify:
    - `GET /api/health`
    - `GET /api/config`
    - `POST /api/analyze/sample`
    - `GET /api/evaluation`
  - Implement the upload endpoint only as P1 and keep it disabled by default.
  - Follow the response schemas and error codes in `ARCHITECTURE.md` §11.

- [x] **T-204 — Implement the analysis pipeline**
  - Connect sample loading, aggregate preprocessing, trace adapters, real-model adapters, postprocessing, and analytics.
  - Apply bill inputs to the cached bill-independent results.
  - Keep analysis results in memory only for the request; do not add persistent result storage.
  - Surface unavailable appliances and warnings accurately.

- [ ] **T-205 — Build the frontend structure**
  - Use the approved React, Vite, Tailwind, and Recharts stack.
  - Implement the start panel, summary bar, four tabs, and methodology drawer.
  - Mirror the backend response schemas in `frontend/src/types.ts`.
  - Keep analytics in the backend; the browser only renders API results.

- [ ] **T-206 — Implement honest scenario and provenance disclosures**
  - Display sample descriptions and simulated-scenario disclosures.
  - Distinguish real-model estimates from synthetic demonstration results using the approved wording.
  - Show the evidence-level statement from the evaluation artifact.
  - Mark savings as illustrative when required.
  - Hide emissions unless the complete verified configuration exists.

- [ ] **T-207 — Complete the fallback user journey**
  - Analyze the available sample with bill inputs.
  - Display appliance cost breakdowns, comparisons, flags, recommendations, and possible savings.
  - Show the evaluation panel and methodology.
  - Handle unavailable samples, insufficient data, and API failures explicitly.

**Phase completion gate:** The frontend and API complete the simulated fallback workflow locally, using real generated artifacts rather than fabricated frontend-only results.

## 6. Phase 3 — AWS Deployment and Backup Demo

**Priority:** P0

**Owner:** Cloud/app owner

- [ ] **T-301 — Configure AWS resources**
  - Use the frozen architecture's Mumbai region, private S3 bucket, SNS topic if needed, EC2 instance, and IAM instance role.
  - Apply least-privilege permissions.
  - Keep the EC2 role read-only for S3 artifacts and scoped to the intended SNS topic.
  - Verify security group rules and expected costs before provisioning.

- [ ] **T-302 — Configure the application service**
  - Build the frontend on the developer machine.
  - Deploy the backend and frontend build to the approved paths.
  - Configure the systemd service and environment variables as documented.
  - Keep one Uvicorn worker for the in-memory cache and alert cooldown.

- [ ] **T-303 — Deploy the fallback application**
  - Deploy the working fallback before relying on real-model results.
  - Verify startup, S3 synchronization, artifact validation, sample precomputation, and health status.
  - Confirm the deployed sample-analysis flow works.

- [ ] **T-304 — Record a backup demo**
  - Record the working deployed fallback.
  - Capture screenshots of the primary workflow and evaluation disclosures.
  - Verify the backup shows the actual implementation and clearly labels simulated outputs.

**Phase completion gate:** A working fallback is deployed and a usable backup demo exists before the team depends on the outcome of model training.

## 7. Phase 4 — Real Appliance Model Evaluation

**Priority:** P0 for the evaluation requirement; model candidates are data-dependent.

**Owner:** ML/data owner

This phase begins once the deterministic pipeline and fallback artifacts are available. It runs in parallel with frontend and deployment work.

- [ ] **T-401 — Select candidate appliances from audited data**
  - Use `ml/candidates.json` and the actual dataset audit.
  - Attempt only appliance classes with usable sub-metered data.

- [ ] **T-402 — Train candidate models**
  - Follow the shared preprocessing and split contracts.
  - Keep training and model-selection decisions within the permitted training/validation data.
  - Do not begin training if doing so would block the fallback pipeline.

- [ ] **T-403 — Export ONNX models**
  - Implement or verify the approved adapter contract and ONNX export.
  - Use the frozen sequence-to-point window and normalization rules.
  - Verify the CPU inference path.
  - Status 2026-10-10: `app/nilm/adapters/onnx_seq2point.py` implemented and tested; no real model exported yet. A synthetic-data prototype exists (ARCH §12.9), not served.

- [ ] **T-404 — Evaluate each candidate**
  - Run the frozen evaluation gate.
  - Compare model results against the naive baseline.
  - Record all required metrics, failed criteria, split boundaries, and evidence level.
  - Do not change thresholds to obtain a passing result.
  - Run the final evaluation according to the frozen execution plan.

- [ ] **T-405 — Export the registry and evaluation artifacts**
  - Generate `evaluation/evaluation.json` and the registry using the approved scripts.
  - Set real-model statuses from actual evaluation output.
  - Keep failed candidates as `no_go`; do not manually promote them.
  - Record uncertainty and minimum-excess parameters from the approved validation calculations.

- [ ] **T-406 — Verify scenario checks and evaluation isolation**
  - Run the prescribed scenario check for each GO appliance.
  - Record missed detections honestly.
  - Ensure synthetic traces never enter real-model metrics.
  - Confirm the unmodified-window check is reported.

**Phase completion gate:** Every attempted candidate has an evidence-backed decision, or is left as `candidate` if it could not be evaluated. The application remains usable regardless of the result.

## 8. Phase 5 — Integration and Release Verification

**Priority:** P0

**Owners:** Both

- [ ] **T-501 — Integrate passing real models**
  - Add only models whose frozen evaluation decision is `go`.
  - Upload the registry, model artifacts, sample bundles, and evaluation output.
  - Preserve the fallback artifact set so it can be restored.
  - Restart the service and verify runtime model loading.

- [ ] **T-502 — Verify real and synthetic provenance**
  - Check that real-model outputs and synthetic-trace outputs are correctly identified.
  - Confirm fully synthetic bundles never invoke real-model inference.
  - Confirm synthetic outputs do not contribute to real-model metrics or emissions claims.

- [ ] **T-503 — Run backend and contract tests**
  - Run the relevant checks listed in §13 and the architecture test expectations.
  - Verify preprocessing, postprocessing, analytics boundaries, wording, registry validation, splits, GO/NO-GO handling, samples, and API contracts.

- [ ] **T-504 — Verify training/serving parity**
  - Run the parity test on the fixed input.
  - Investigate failures rather than weakening the tolerance or bypassing the test.

- [ ] **T-505 — Run end-to-end checks on the deployed application**
  - Check health, configuration, available samples, analysis, evaluation, and error behavior.
  - Confirm the frontend build and API work together on the same origin.
  - Confirm that a failed optional service does not break analysis.

- [ ] **T-506 — Configure optional SNS alerts or keep them disabled**
  - Enable SNS only if the complete path can be tested before the demo.
  - Configure the topic and confirmed email subscription, then verify the end-to-end application notification path, message wording, cooldown, and on-screen status.
  - Otherwise keep alerts disabled and omit email from the demo.
  - Status 2026-10-10: `app/alerts.py` implemented (cooldown, 3 s timeout, failure never breaks analysis) and tested with a fake SNS client; real SNS not configured, alerts stay disabled.

**Completion gate:** The deployed application follows the frozen contracts, tests have been run and recorded, and any failures or limitations are explicitly documented.

## 9. Phase 6 — Demo and Submission

**Priority:** P0

**Owners:** Both

- [ ] **T-601 — Rehearse the two-to-three-minute demo**
  - Explain the household problem.
  - Show the typical sample only if it is available.
  - Show the actual evaluation evidence and any NO-GO results.
  - Demonstrate the simulated scenario and identify it as simulated.
  - Show the recommendation and possible-savings range.
  - Mention that savings and emissions reductions have not been measured.
  - Show the alert only if enabled and tested.

- [ ] **T-602 — Verify the backup**
  - Ensure the recording and screenshots reflect the deployed fallback.
  - Verify the backup is available if live AWS behavior fails during judging.

- [ ] **T-603 — Update public documentation**
  - Update `README.md` with the correct project name, verified architecture, setup steps, actual evaluation results, and limitations.
  - Do not insert illustrative architecture values as measured results.
  - Do not claim a deployment, test, notification, or metric that has not been verified.

- [ ] **T-604 — Final release check**
  - Confirm all P0 criteria are either satisfied or explicitly reported as failed.
  - Verify no secrets, restricted datasets, or unintended artifacts are committed.
  - Check Git status and review the final diff.

**Completion gate:** The team can demonstrate the product reliably, explain the evidence behind its outputs, and disclose the limitations without overstating the results.

## 10. P1 — Only After the P0 Release Gate

- [ ] **T-701 — Implement CSV upload**
  - Follow the frozen upload validation and error contracts.
  - Keep uploads disabled by default.
  - Never persist or log uploaded household data.
  - Do not use the public HTTP-only demo for private household data.

- [ ] **T-702 — Verify upload behavior**
  - Test malformed CSVs, missing columns, coarse intervals, invalid units, insufficient history, size limits, and disabled-route behavior.

Do not begin P1 work until the deployed P0 flow and backup demo are reliable.

## 11. P2 — Optional

Consider only if all required work is complete:

- Additional interface polish.
- Future HTTPS work.
- Persistent results, user accounts, or long-term history.
- More appliance classes or other households.
- Verified emissions display.
- Weather adjustment or measured-savings tracking.

These are not requirements for the current MVP.

## 12. Failure and Cut Rules

1. **No real model passes GO/NO-GO:** Keep the fallback. Report that no real-data appliance model has been validated. Do not delay delivery.
2. **Insufficient real data for a 21-day held-out base:** Use the fully synthetic fallback with explicit disclosure and no real-model inference.
3. **A candidate is not evaluated by the model-work cutoff:** Leave it `candidate`; do not claim support.
4. **SNS cannot be fully tested:** Disable alerts and omit email from the demo.
5. **AWS deployment fails:** Diagnose the issue, preserve a local working path, and retain verified backup materials. Do not claim successful deployment.
6. **A P0 task is blocked:** Identify the exact dependency and impact. Cut P1/P2 scope before weakening a frozen contract or test.
7. **Time is running out:** Prioritize the deterministic pipeline, working fallback, deployed demo, evaluation honesty, and backup.

## 13. Final Release Checklist

- [ ] The fallback scenario is generated reproducibly.
- [ ] The sample manifest and artifact hashes validate.
- [ ] Real-model evaluation results are generated from actual data, or explicitly state that no model was validated.
- [ ] Real and synthetic outputs remain isolated.
- [ ] API contracts and frontend types agree.
- [ ] The deployed fallback works.
- [ ] Relevant tests have been run and results recorded.
- [ ] SNS is tested or disabled.
- [ ] The backup demo is ready.
- [ ] `README.md` reports only verified results.
- [ ] No unsupported claims, secrets, or restricted artifacts are committed.

### Verification commands, expectations, and release gates

Run the relevant checks and record their actual outcomes; these commands and descriptions define expectations only and do not claim that checks have run:

```bash
(cd backend && .venv/bin/pytest -q)
(cd backend && NILM_CACHE_DIR=../artifacts .venv/bin/pytest -q tests/test_contracts.py)
(cd frontend && npm run typecheck && npm run build)
PYTHONPATH=backend python ml/evaluate.py --data ml/data --artifacts artifacts
```

The evaluation command requires the dataset in `ml/data`. Use small fixtures for software/integration verification when real artifacts are unavailable. Keep software correctness, real-model performance, evaluation-only scenario checks, synthetic demonstration behavior, and real-world impact claims distinct. Synthetic scenario success verifies the constructed demo workflow only; it does not establish model quality or real-world detection performance. No real-world environmental impact is measured.

The following test IDs are retained from the former verification plan; expected behavior follows `ARCHITECTURE.md`:

| IDs | Documentation-level expectation |
|---|---|
| TS-U-01…12 | Preprocessing resamples to one-minute means, leaves empty bins missing, and does not interpolate or impute; time-zone, validity/coverage, analytics, bill validation, wording, postprocessing, and registry checks follow ARCH contracts. Energy expectation includes 1000 W for a full valid week = 168 kWh, with coverage normalization for missing minutes. |
| TS-C-01…03 | Frontend mocks and committed artifact schemas validate against API/schema contracts; frontend types compile against mocks. |
| TS-P-01…02 | TS-P-01 compares PyTorch and ONNX on a held-out batch with `np.allclose(atol=1e-3)` in normalized units; TS-P-02 backend/training reference parity has max absolute difference < 1 W and blocks model integration on failure. |
| TS-I-01 | Each available sample returns a valid response with energy/cost reconciliation and expected series lengths. `typical_period` is conditional on a `go` real model. |
| TS-I-02 | `simulated_scenario` produces the manifest's expected synthetic status and is categorized only as simulated demonstration behavior. |
| TS-I-03…05 | Repeat sample requests are deterministic apart from `analysis_id`; registry `no_go` entries disappear from supported outputs; no issues yields the specified empty state. |
| TS-A-01 | `/api/config` exposes only currently available samples and supported appliances. |
| TS-A-02 | Unknown sample returns 404 `unknown_sample`; invalid bill returns 422 `invalid_bill`; omitted bill uses the illustrative sample default. |
| TS-A-03…05 | Evaluation artifact is returned unchanged; upload validation cases are P1; SPA/API routing and CORS follow ARCH. |
| TS-F-01…06 | Missing models, unavailable S3 with cache, optional SNS errors, pipeline errors, service recovery, and not-ready behavior follow ARCH failure contracts. |
| TS-E-01…06 | Record actual inventory and split outcome; use `independent_test` only when its approved data requirements hold, otherwise record `development_only` or `none` as appropriate. Record available metrics, weekly results, deterministic example selection, applicable GO-model scenario checks, and frozen GO/NO-GO outcomes. Freeze criteria before evaluation; undefined required metrics are `null`, fail their criteria, appear in `failed_criteria`, and yield `no_go`. Development-only results are not independent validation; unavailable test weeks do not block the synthetic fallback. |
| TS-PERF-01…04 | Record measured startup, sample latency, and memory against the existing targets. Upload throughput is P1 only. |
| TS-E2E-01…03 | Verify the public available-sample journey, laptop fallback, and two timed rehearsals. The P0 synthetic fallback remains independently demonstrable. |
| TS-E2E-04 | Verify end-to-end email delivery only when SNS alerting is enabled and configured; skip this check when intentionally disabled. |

Software-complete verification covers applicable unit, contract, parity, integration, API, and failure checks. Model claims require the actual evaluation record. Deployment checks apply only when deployment is attempted. Demo readiness requires the available-sample journey, laptop fallback, rehearsals, and backup recording; email delivery is conditional on SNS being enabled. Optional upload and email checks do not block the P0 release when disabled/not implemented.

## 14. Requirements Acceptance Criteria Matrix

### 14.1 Functional Requirements

| ID | Pri | Requirement | Acceptance Criterion | Task Mappings | Test Mappings |
|---|---|---|---|---|---|
| FR-01 | P0 | User can load any available canonical sample (`typical_period`, `simulated_scenario`) | Each available sample returns complete `AnalysisResponse` (ARCH §6/§11) and renders its applicable results. `typical_period` is available only when a real model passes frozen criteria; `simulated_scenario` remains independently demonstrable as the disclosed synthetic fallback. | T-109, T-203, T-204, T-207, T-303, T-505 | TS-A-01, TS-I-01, TS-E2E-01 |
| FR-02 | P0 | Bill and tariff input derives effective ₹/kWh rate | Form displays live ₹/kWh; invalid input shows inline message and sends nothing; API returns 422 `invalid_bill` on invalid bill values; sample defaults labelled illustrative | T-201, T-207 | TS-U-07, TS-A-02 |
| FR-03 | P1 | User can upload aggregate CSV (ARCH §11.4) | Valid 21–35-day CSV returns complete analysis; invalid inputs return specified error code and one-sentence explanation | T-701, T-702 | TS-A-04, TS-PERF-03 |
| FR-04 | P0 | "Where your money goes" cost breakdown | Per-appliance kWh, estimated cost contribution, share %, largest consumer, plus `other`; Σ appliance kWh + other = total within 0.1%; label reads "Estimated cost contribution" | T-104, T-106, T-204, T-207 | TS-U-03, TS-I-01 |
| FR-05 | P1 | Daily drill-down per appliance | Clicking appliance displays its `daily_kwh` chart; days with <50% coverage appear as gaps | T-205, T-701 | TS-E2E-01 |
| FR-06 | P0 | "See the AI work" current-week signals | Stacked chart renders aggregate and estimated appliance series (672 points each at 15-min downsampling) with legend | T-204, T-205 | TS-I-01, TS-E2E-01 |
| FR-07 | P0 | Model evaluation panel | Shows actual evaluation evidence and limitations; for evaluated real models, shows per-GO example-window overlay, weekly chart, metrics vs naive baseline, and downstream check. If no real model passes, explicitly says no real-data appliance model was validated; never presents synthetic output as model evaluation. | T-203, T-205, T-405, T-505 | TS-C-02, TS-A-03, TS-E-02…05 |
| FR-08 | P0 | "What changed" baseline comparison | Statuses follow ARCH §9; flagged rows show `driver_text` and explanation; no forbidden words appear | T-106, T-204, T-207 | TS-U-04, TS-U-05, TS-U-06, TS-I-02 |
| FR-09 | P0 | "What to fix first" recommendations | Cards ordered by ₹ mid value; shows issue, likely driver, explanation, action, and three ranges using the approved possible-savings wording; CO₂ hidden if factor null | T-106, T-204, T-207 | TS-U-08, TS-U-09, TS-I-02 |
| FR-10 | P0 | Empty state handling | With no detected issues, recommendations tab displays exactly "No unusual use found." | T-205, T-207 | TS-I-05, TS-E2E-01 |
| FR-11 | Optional | SNS email alert | When alerting is enabled and configured, an eligible analysis may trigger a plain-text email if requested and per-sample/source cooldown permits; the UI reflects `sent`, `failed`, `disabled`, `no_issues`, or `cooldown`. Do not require delivery while alerts are disabled. | T-506 | TS-F-03; TS-E2E-04 only when SNS is enabled |
| FR-12 | P0 | Methodology drawer | Explains data types, simulated scenario description, CO₂ source, NO-GO appliances with reasons, and documented limitations | T-205, T-206 | TS-E2E-01 |
| FR-13 | P0 | Registry-driven appliance set | Changing entry status between `go` and `no_go` in `registry.json` and restarting updates dashboard without code modifications | T-202, T-405, T-501 | TS-U-12, TS-I-04 |
| FR-14 | P0 | Health endpoint | `/api/health` reports appliance runtime states, `samples_ready`, and `s3_sync` per ARCH §15.3 | T-201, T-203, T-505 | TS-A-01, TS-F-01 |
| FR-15 | P0 | Wording constraints | Automated test verifies absence of forbidden words (defect, broken, fault, waste, cause) across all backend constants, `actions.json`, and alerts | T-106, T-503 | TS-U-10 |
| FR-16 | P0 | Supported appliance display rules | Dashboard shows only appliances with registry status `go` that loaded successfully, plus synthetic traces with `demo` in sample manifests; NO-GO appliances appear only in methodology drawer | T-202, T-405, T-501, T-502 | TS-E-06, TS-I-04 |

### 14.2 Non-Functional Requirements

| ID | Pri | Requirement | Acceptance Criterion | Task Mappings | Test Mappings |
|---|---|---|---|---|---|
| NFR-01 | P0 | Sample analysis latency | Server response time for `/api/analyze/sample` p50 ≤ 1 s over 20 calls | T-204, T-505 | TS-PERF-02 |
| NFR-02 | P0 | Service startup time | `/api/health` reaches ready status within 5 minutes of service start | T-202, T-303, T-505 | TS-PERF-01 |
| NFR-03 | P1 | Upload analysis throughput | 35-day 1-minute CSV completes analysis in ≤ 30 s on chosen instance | T-701, T-702 | TS-PERF-03 |
| NFR-04 | P0 | Memory headroom | Available memory ≥ 25% of total instance RAM after startup | T-301, T-505 | TS-PERF-04 |
| NFR-05 | P0 | Computation determinism | Two identical sample requests return identical outputs (except correlation `analysis_id`) | T-106, T-204, T-503 | TS-I-03 |
| NFR-06 | P0 | Credential protection | Zero AWS secrets, access keys, or private keys committed to Git repository | T-002, T-604 | T-604 checklist |
| NFR-07 | P0 | Single origin architecture | React frontend and FastAPI API served on port 80 of same host; CORS disabled in production | T-203, T-205, T-505 | TS-A-05 |
| NFR-08 | P0 | Graceful degradation | Component failures (S3 sync, optional SNS, individual model load) degrade per ARCH §15.4 | T-202, T-204, T-505 | TS-F-01…06 |
| NFR-09 | P0 | Automatic crash recovery | Process restarts automatically upon failure via systemd unit | T-302, T-505 | TS-F-05 |
| NFR-10 | P0 | Cloud cost control | Active AWS monthly budget alert before provisioning any cloud resource | T-301 | T-301 DoD |
| NFR-11 | P0 | Honest metrics | Every metric displayed in README and UI is traceable to `evaluation.json` or computed responses | T-405, T-603 | T-603 DoD |
| NFR-12 | P0 | Responsive display | Interface fully legible at 1280×720 resolution without horizontal scroll; chart typography ≥ 12 px | T-205 | TS-E2E-01 |

### 14.3 Data Requirements

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| DR-01 | P0 | Real training and evaluation uses iAWE, aligned to 1-minute grid by shared preprocessing | TS-U-01, TS-E-01 |
| DR-02 | P0 | Use the exact chronological split, full-day gap/exclusion, coverage, contiguous-span, minimum-training-data, and window-boundary rules in ARCH §12.2 | TS-U-02, TS-E-01 (record the data-supported evidence level; `development_only`/`none` do not block the synthetic fallback) |
| DR-03 | P0 | Real sample periods use only an approved held-out validation/test base; no training data. `typical_period` exists only when at least one real model passes frozen criteria. | TS-C-02, TS-I-01 |
| DR-04 | P0 | `simulated_scenario` is the disclosed synthetic demonstration fallback; its manifest and methodology identify provenance. Simulated aggregate injections used for offline evaluation are fixtures, not user-facing sample IDs. | TS-I-02, TS-E2E-01 |
| DR-05 | P1 | Uploaded CSV is processed in memory, not persisted to local disk or S3. | TS-A-04 |
| DR-06 | P0 | Raw dataset files, model binaries, and private data excluded from Git | T-604 checklist |

### 14.4 API Requirements

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| API-01 | P0 | Endpoints, request and response schemas strictly implement ARCH §6 and §11 via Pydantic | TS-C-01, TS-A-01…05 |
| API-02 | P0 | Error responses conform to `ErrorResponse` with designated HTTP status codes | TS-A-02, TS-A-04 |
| API-03 | P0 | Frontend mock fixtures in `frontend/src/mocks/` validate against Pydantic models | TS-C-01 |
| API-04 | P0 | Non-API routes serve frontend SPA; unmatched `/api/*` routes return JSON 404 | TS-A-05 |

### 14.5 AWS Requirements

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| AWS-01 | P0 | Resources provisioned in `ap-south-1` under an active budget alert | ARCH §18.1 |
| AWS-02 | P0 | Single private S3 bucket with Block Public Access, SSE-S3 encryption, and structured prefixes; no upload-storage lifecycle rule | ARCH §18.1 |
| AWS-03 | P0 | EC2 instance accesses AWS via IAM instance role (`s3:ListBucket`, `s3:GetObject`, optional topic-scoped `sns:Publish`) without S3 write permissions or on-instance credentials | ARCH §17.1, §18.1 |
| AWS-04 | Optional | SNS standard topic and confirmed email subscription when alerting is enabled and tested; no email requirement while disabled | ARCH §16, §18.1 |
| AWS-05 | P0 | Security group allows port 80 for the demo and port 22 only from team `/32` IPs, with no other inbound access | ARCH §18.1 |
| AWS-06 | P0 | Artifact uploads use separate developer credentials scoped to artifact prefixes | ARCH §18.1 |

### 14.6 Model Evaluation Requirements

| ID | Pri | Requirement | Verification |
|---|---|---|---|
| ML-01 | P0 | Candidate models evaluated on the ARCH-approved test split, or validation split in `development_only`, using required MAE, energy-error, coverage, and applicable F1 criteria vs the naive baseline | TS-E-02, Gate G2 |
| ML-02 | P0 | Weekly predicted vs actual kWh reported for all valid test weeks in evaluation artifact | TS-E-03 |
| ML-03 | P0 | Approved downstream anomaly check executed for each `go` model, with the small-sample limitation disclosed; record actual outcomes, including misses | TS-E-05 |
| ML-04 | P0 | Example demonstration window selected by deterministic rule (median error day) | TS-E-04 |
| ML-05 | P0 | Each candidate assigned recorded `go` or `no_go` decision with explicit written reason | TS-E-06, ARCH §2.6 |
| ML-06 | P0 | Real models shown only if passing evaluation; fallback synthetic demo ensures full workflow | T-109, T-501, ARCH §20.3 |
| ML-07 | P0 | Backend inference matches training-side reference within 1 W tolerance | TS-P-02 |
| ML-08 | P1 | AC rule-based baseline included in evaluation comparisons | TS-E-02 |

### 14.7 Disclosed Product Limitations

1. Appliance consumption values are disaggregated estimates from a single aggregate signal, not direct measurements.
2. Training and evaluation rely on a single household from the iAWE Delhi dataset covering ~73 days; generalization is unverified.
3. Only appliances meeting frozen GO/NO-GO criteria are supported as real models.
4. Input requires 1-minute (or faster) power time-series across multiple weeks; monthly bills alone cannot disaggregate.
5. Effective electricity rates (₹/kWh) are approximations; cost allocations do not reproduce utility bills.
6. Savings figures represent potential recovery if usage normalizes, not guaranteed outcomes.
7. Anomaly flags indicate unusual energy usage relative to baseline, not proof of defective equipment.
8. `simulated_scenario` is a simulated demonstration.
9. Real-world energy and emissions reductions have not been measured.

### 14.8 Traceability Matrix

| Requirement | Primary Implementing Tasks | Verifying Tests |
|---|---|---|
| FR-01 | T-109, T-203, T-204, T-207, T-303, T-505 | TS-A-01, TS-I-01, TS-E2E-01 |
| FR-02 | T-201, T-207 | TS-U-07, TS-A-02 |
| FR-03 (P1) | T-701, T-702 | TS-A-04, TS-PERF-03 |
| FR-04 | T-104, T-106, T-204, T-207 | TS-U-03, TS-I-01 |
| FR-05 (P1) | T-205, T-701 | TS-E2E-01 |
| FR-06 | T-204, T-205 | TS-I-01, TS-E2E-01 |
| FR-07 | T-203, T-205, T-405, T-505 | TS-C-02, TS-A-03, TS-E-02…05 |
| FR-08 | T-106, T-204, T-207 | TS-U-04, TS-U-05, TS-U-06, TS-I-02 |
| FR-09 | T-106, T-204, T-207 | TS-U-08, TS-U-09, TS-I-02 |
| FR-10 | T-205, T-207 | TS-I-05, TS-E2E-01 |
| FR-11 (optional) | T-506 | TS-F-03; TS-E2E-04 if SNS enabled |
| FR-12 | T-205, T-206 | TS-E2E-01 |
| FR-13 | T-202, T-405, T-501 | TS-U-12, TS-I-04 |
| FR-14 | T-201, T-203, T-505 | TS-A-01, TS-F-01 |
| FR-15 | T-106, T-503 | TS-U-10 |
| FR-16 | T-202, T-405, T-501, T-502 | TS-E-06, TS-I-04 |
| NFR-01, 02, 04 | T-202, T-204, T-301, T-303, T-505 | TS-PERF-01, 02, 04 |
| NFR-03 (P1) | T-701, T-702 | TS-PERF-03 |
| NFR-05 | T-106, T-204, T-503 | TS-I-03 |
| NFR-06 | T-002, T-604 | T-604 release check |
| NFR-07 | T-203, T-205, T-505 | TS-A-05 |
| NFR-08, 09 | T-202, T-302, T-505 | TS-F-01…06 |
| NFR-10 | T-301 | T-301 DoD |
| NFR-11 | T-405, T-603 | T-603 DoD |
| NFR-12 | T-205 | TS-E2E-01 |
| DR-01, DR-02 | T-101, T-102 | TS-U-01, TS-U-02, TS-E-01 |
| DR-03, DR-04 | T-107, T-109 | TS-C-02, TS-I-02 |
| DR-05 (P1) | T-701, T-702 | TS-A-04 |
| DR-06 | T-002, T-604 | T-604 release check |
| API-01…04 | T-201, T-202, T-203 | TS-C-01, TS-A-01…05 |
| AWS-01…06 | T-301, T-302, T-506 | ARCH §17–18.1 |
| ML-01…07 | T-103, T-402, T-403, T-404, T-405, T-504 | TS-E-01…06, TS-P-01, TS-P-02 |
| ML-08 (P1) | T-404 | TS-E-02 |

## 15. Unresolved Decisions and Experimental Variables Tracking

| Decision ID | Open Question | Dependency | Owner | Resolving Task | Current Status |
|---|---|---|---|---|---|
| U-01 | Which candidate appliances achieve `go` status? | Gate G2 | A | T-404, T-405 | Open — determined by offline evaluation results |
| U-02 | Exact split dates and whether `independent_test` requirements are met; otherwise record `development_only` or `none` | Evaluation evidence level | A | T-101, T-102 | Open — determined by dataset audit; unavailable test data does not block the synthetic fallback |
| U-03 | Final flag threshold `T` and evaluation scenario-injection parameters | Sample bundles | A | T-106, T-107, T-109 | Open — derived from approved evaluation outputs; GO/NO-GO criteria remain frozen |
| U-04 | Frontend builder assignment | Phase 2 | B | T-205 | Resolved — Teammate B with React/TypeScript |
| U-05 | Model window length (proposed 99 samples at 1 min) | Training | A | T-402 | Open — proposed 99-minute window |
| U-06 | Class aggregation: sum both AC channels or use primary AC? | Audit | A | T-101 | Open — depends on sub-meter completeness |
| U-07 | CO₂ factor value and CEA database version | Config | B | T-206 | Open — nullable, hidden until configured |
| U-08 | EC2 instance sizing confirmation | Deployment | B | T-301 | Proposed `t3.medium`, verified via TS-PERF-04 |
| U-09 | Illustrative ₹/kWh rate for sample default bills | Samples | Both | T-109 | Open — illustrative rate to be cited |
| U-10 | ONNX Runtime CPU export validation | Adapters | A | T-403 | Proposed — validated on held-out batch |
| U-11 | Secondary synthetic appliance choice for `simulated_scenario` when needed | Fallback demo | A | T-107, T-109 | Open — choose from approved synthetic traces |
