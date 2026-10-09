# REQUIREMENTS.md — Acceptance criteria

Every requirement here has an ID, a priority, and a check that a person or a test can perform. The behaviour itself is defined in [ARCHITECTURE.md](ARCHITECTURE.md); tasks are in [TASKS.md](TASKS.md); tests are in [TESTING.md](TESTING.md). The traceability table in §8 links all three.

**Priorities**

- **P0** — required for submission. The project is not done until every P0 passes.
- **P1** — polish. Build only after checkpoint C4 (live end-to-end) passes.
- **P2** — optional. Build only if P0 and P1 are stable.

---

## 1. Functional requirements

| ID | Pri | Requirement | Acceptance criterion |
|---|---|---|---|
| FR-01 | P0 | User can load a sample scenario (`normal`, `problem_week`) | Clicking each sample button returns a complete `AnalysisResponse` (ARCH §6.5) and renders all four tabs, on the public URL |
| FR-02 | P0 | User enters bill amount (₹) and units (kWh), or a ₹/kWh value; system derives effective cost per kWh | The form shows the live ₹/kWh; invalid input shows a message and sends nothing; the API returns 400 `bad_bill` for an invalid bill; sample default bills are labelled illustrative |
| FR-03 | P1 | User can upload an aggregate CSV (ARCH §7.5) | A valid 21–35-day file returns a complete analysis; each invalid case in ARCH §6.9 returns its code and a one-sentence message shown in the UI |
| FR-04 | P0 | "Where your money goes": per appliance kWh, estimated cost contribution, share %, largest consumer, plus `other` | Values match ARCH §10.1–10.3; Σ appliance kWh + other kWh = total kWh within 0.1%; label reads "Estimated cost contribution" |
| FR-05 | P1 | Daily drill-down per appliance | Clicking an appliance shows its `daily_kwh` chart; null days appear as gaps |
| FR-06 | P0 | "See the AI work": aggregate and estimated appliance signals for the current week | The stacked chart renders all series in `signals` (672 points each) with a legend |
| FR-07 | P0 | Model evaluation panel | Shows, per GO appliance, the example-window overlay (aggregate, predicted, actual), the weekly predicted vs actual chart, the metrics table vs naive baseline, and the downstream-check line, all read from `/api/evaluation`; the label "Model evaluation on data not used in training" is visible; no confidence scores appear anywhere |
| FR-08 | P0 | "What changed": each appliance vs its baseline, status, likely driver, explanations | Statuses follow ARCH §10.4–10.6; flagged rows show `driver_text` and explanations; no forbidden word (ARCH §10.11) appears |
| FR-09 | P0 | "What to fix first": ranked issues with one action and possible ₹/kWh/CO₂ per month as ranges | Cards are ordered by ₹ mid value; each shows issue, likely driver, explanations, action, three ranges; the label "Possible savings if use returns to its normal level" is on every card; CO₂ is hidden if the factor is not configured |
| FR-10 | P0 | Empty state | With no issues, Tab 4 shows exactly "No unusual use found." |
| FR-11 | P0 | Overuse alert email | When an analysis has issues and `send_alert` is true, one email arrives at the subscribed inbox with the content of ARCH §10.10; the UI shows the alert status |
| FR-12 | P0 | Methodology drawer | Lists the three data types (ARCH §5), the simulated-scenario description, the CO₂ source, NO-GO appliances with reasons, and the limitations of PROJECT.md §7 |
| FR-13 | P0 | Appliance set is driven by `registry.json` | Changing an entry's `status` between `go` and `no_go` and restarting changes the dashboard with no code change |
| FR-14 | P0 | Health endpoint | `/api/health` reports loaded/failed appliances, `samples_ready`, `s3_synced`, per ARCH §6.9 |
| FR-15 | P0 | Wording rules | Automated test finds no forbidden word in backend strings or `actions.json` |
| FR-16 | P0 | Only GO appliances are shown as estimated loads | The dashboard lists exactly the appliances with `status: "go"` that loaded; NO-GO appliances appear only in the methodology drawer |

## 2. Non-functional requirements

| ID | Pri | Requirement | Acceptance criterion |
|---|---|---|---|
| NFR-01 | P0 | Sample analysis is fast | Server time for `/api/analyze/sample` p50 ≤ 1 s over 20 calls (TS-PERF-02) |
| NFR-02 | P0 | Startup completes | `/api/health` reaches `samples_ready: true` within 5 minutes of `systemctl start` (TS-PERF-01) |
| NFR-03 | P1 | Upload analysis completes | A 35-day 1-minute file finishes in ≤ 30 s on the chosen instance (TS-PERF-03) |
| NFR-04 | P0 | Memory headroom | After startup, available memory ≥ 25% of instance RAM (TS-PERF-04) |
| NFR-05 | P0 | Determinism | Two identical sample requests return identical numbers (except `analysis_id`) (TS-I-03) |
| NFR-06 | P0 | No credentials in the repository | No AWS keys or secrets in git history; checked before submission (T-708) |
| NFR-07 | P0 | Single origin | Frontend and API are served by the same host and port; CORS disabled in production (TS-A-05) |
| NFR-08 | P0 | Graceful degradation | Failures of ARCH §14 behave as specified (TS-F-01…06) |
| NFR-09 | P0 | Recovers from crash | Killing the process restarts it automatically (TS-F-05) |
| NFR-10 | P0 | Cost control | An AWS budget alert exists before any resource is created (T-004) |
| NFR-11 | P0 | Honest numbers | Every metric in the README and UI is traceable to `evaluation.json` or a computed response; none is typed by hand (T-703) |
| NFR-12 | P0 | Readable on a projector | Every screen is usable at 1280×720 with no horizontal scroll; chart labels ≥ 12 px (TS-E2E-01) |

## 3. Data requirements

| ID | Pri | Requirement |
|---|---|---|
| DR-01 | P0 | Real training/evaluation data is iAWE, prepared to a 1-minute aligned grid by the shared preprocessing (ARCH §8, §11.1) |
| DR-02 | P0 | Train and test are chronological with a gap ≥ window/2; the test period has ≥ 3 valid weeks (gate G1) |
| DR-03 | P0 | Both samples are built only from the held-out test period (3 whole weeks) |
| DR-04 | P0 | `problem_week` is the only simulated data; its modification is recorded in `scenario.json` and described in the methodology drawer |
| DR-05 | P0 | Uploaded files follow ARCH §7.5; raw uploads are deleted by S3 lifecycle after 7 days (P1) |
| DR-06 | P0 | Dataset files and model binaries are never committed to git |

## 4. API requirements

| ID | Pri | Requirement |
|---|---|---|
| API-01 | P0 | Endpoints, request and response shapes exactly as ARCH §6; Pydantic models are the implementation |
| API-02 | P0 | Every error uses `ErrorResponse` with the codes and HTTP statuses of ARCH §6.9 |
| API-03 | P0 | Mock fixtures in `frontend/src/mocks/` validate against the Pydantic models (TS-C-01) |
| API-04 | P0 | Non-`/api` paths return the frontend; unknown `/api/*` paths return JSON 404 |

## 5. AWS requirements

| ID | Pri | Requirement |
|---|---|---|
| AWS-01 | P0 | All resources in ap-south-1; a budget alert exists |
| AWS-02 | P0 | One private S3 bucket, Block Public Access on, SSE-S3, layout of ARCH §12.1 |
| AWS-03 | P0 | EC2 accesses S3/SNS only through an instance role with the least-privilege policy of DEPLOYMENT.md §3 |
| AWS-04 | P0 | One SNS topic with one confirmed email subscription |
| AWS-05 | P0 | Security group: 80 open, 22 restricted to the team's IP, nothing else |
| AWS-06 | P0 | Teammate A uploads artifacts with a separate IAM user limited to the artifact prefixes |

## 6. Model evaluation requirements

| ID | Pri | Requirement |
|---|---|---|
| ML-01 | P0 | Every candidate appliance is evaluated on held-out test data with the metrics of ARCH §11.3, for the model and the naive baseline |
| ML-02 | P0 | Weekly predicted vs actual kWh is reported for every valid test week |
| ML-03 | P0 | The downstream check (ARCH §11.5) is run for every candidate; its note states the small sample size |
| ML-04 | P0 | The example window is selected by the rule in ARCH §11.6 |
| ML-05 | P0 | Each candidate gets a recorded GO or NO-GO with a reason (ARCH §11.4), in `evaluation.json` and DECISIONS.md |
| ML-06 | P0 | At least one appliance is GO. If none is, the team stops feature work and reassesses (TASKS.md cut rules) |
| ML-07 | P0 | Backend inference matches the training-side reference within 1 W (TS-P-02) |
| ML-08 | P1 | AC rule baseline included in evaluation |

## 7. Limitations that must be stated

These are product requirements: they must appear in the methodology drawer and the README.

1. Appliance figures are estimates from one aggregate signal; nothing is measured per appliance.
2. Models were trained and tested on one household over about 73 days. Accuracy in other homes is unknown.
3. Only appliances that passed GO/NO-GO are supported.
4. The input needs 1-minute (or faster) whole-house power data for at least 3 weeks. A monthly bill is not enough.
5. Effective cost per kWh is an approximation; cost contributions do not reproduce the bill.
6. Savings are possible savings if use returns to its normal level, not guaranteed.
7. A flag indicates unusual energy use, not a faulty appliance. Higher AC use can be due to hotter weather.
8. The problem week is a simulated scenario.
9. No real-world energy or emissions reduction has been measured.

## 8. Traceability (P0 and P1)

| Requirement | Tasks | Tests |
|---|---|---|
| FR-01 | T-113, T-204, T-403, T-504, T-505 | TS-A-01, TS-I-01, TS-E2E-01 |
| FR-02 | T-207, T-403 | TS-U-07, TS-A-02 |
| FR-03 (P1) | T-601, T-602 | TS-A-04, TS-PERF-03 |
| FR-04 | T-104, T-207, T-405 | TS-U-03, TS-I-01 |
| FR-05 (P1) | T-603 | TS-E2E-01 (manual item) |
| FR-06 | T-503, T-406 | TS-I-01 |
| FR-07 | T-112, T-406, T-505 | TS-C-02, TS-A-03, TS-E-02…05 |
| FR-08 | T-104, T-407 | TS-U-04, TS-U-05, TS-U-06, TS-I-02 |
| FR-09 | T-207, T-408 | TS-U-08, TS-U-09, TS-I-02 |
| FR-10 | T-408 | TS-I-05, TS-E2E-01 |
| FR-11 | T-304, T-506 | TS-F-03, TS-E2E-04 |
| FR-12 | T-208, T-409 | TS-E2E-01 |
| FR-13 | T-501, T-509 | TS-U-12, TS-I-04 |
| FR-14 | T-201, T-504 | TS-A-01, TS-F-01 |
| FR-15 | T-207, T-208 | TS-U-10 |
| FR-16 | T-111, T-409, T-505 | TS-E-06, TS-I-04 |
| NFR-01, 02, 04 | T-504, T-701 | TS-PERF-01, 02, 04 |
| NFR-03 (P1) | T-601, T-701 | TS-PERF-03 |
| NFR-05 | T-503 | TS-I-03 |
| NFR-06 | T-002, T-708 | T-708 checklist |
| NFR-07 | T-205 | TS-A-05 |
| NFR-08, 09 | T-206, T-209, T-504, T-702 | TS-F-01…06 |
| NFR-10 | T-004 | T-004 DoD |
| NFR-11 | T-703 | T-703 DoD |
| NFR-12 | T-401…T-409 | TS-E2E-01 |
| DR-01, DR-02 | T-101, T-102, T-103 | TS-U-01, TS-U-02, TS-E-01 |
| DR-03, DR-04 | T-113 | TS-C-02, TS-I-02 |
| DR-05 (P1) | T-301, T-601 | TS-A-04 |
| DR-06 | T-002 | T-708 checklist |
| API-01…04 | T-202, T-203, T-205, T-209 | TS-C-01, TS-A-01…05 |
| AWS-01…06 | T-004, T-301…T-306 | DEPLOYMENT.md §10 checks |
| ML-01…07 | T-104…T-112 | TS-E-01…06, TS-P-01, TS-P-02 |
| ML-08 (P1) | T-115 | TS-E-02 |

## 9. Definition of complete

The project is complete for submission when **all** of these hold:

1. Every P0 requirement above passes its acceptance criterion.
2. The release gates in [TESTING.md §11](TESTING.md#11-release-gates) pass.
3. Checkpoint C5 in [TASKS.md](TASKS.md) is reached: two timed rehearsals on the public URL, each ≤ 3:00.
4. The submission checklist (T-708) is fully ticked.
