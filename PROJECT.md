# PROJECT.md — Appliance Energy Analyzer

## 1. Product Overview

**Project name:** Appliance Energy Analyzer

**Description:** An electricity usage diagnostic tool that estimates appliance-level consumption from whole-house electricity measurements, identifies unusual usage patterns, and recommends practical actions.

**Hackathon:** Environmental Hacks × AWS Bharat Builds  
**Team:** Inglorious Momos — two students.

This file defines the product scope. Technical contracts and implementation details belong in `ARCHITECTURE.md`.

The product direction is frozen unless feasibility, correctness, reliability, or implementation constraints require a change. Technical and architecture decisions are recorded in `ARCHITECTURE.md` §2.

## 2. Problem

A household's electricity meter reports total consumption but does not directly show which appliances contribute to that consumption or explain unusual changes.

Monitoring individual appliances separately can require additional meters or smart plugs.

The Appliance Energy Analyzer explores whether a single whole-house electricity signal can provide useful appliance-level estimates and actionable insights without requiring a separate sensor for every appliance.

## 3. Target User and Input

**Primary target:** Indian households with whole-house electricity measurements recorded at approximately one-minute intervals or faster.

**Required input:** Timestamped aggregate electricity measurements with sufficient valid data for the defined weekly comparisons.

A monthly electricity bill alone is insufficient for appliance-level analysis.

The MVP uses prepared sample scenarios. CSV upload is a P1 feature and must not delay the working P0 flow.

Small-business use is future work, not a validated market for this MVP (Decision D-001).

## 4. Core Product Workflow

The product converts an aggregate electricity signal into an understandable diagnostic workflow:

**Aggregate signal → appliance estimates → cost breakdown → baseline comparison → unusual-usage flag → recommendation → possible savings**

1. **Choose a scenario:** Select normal weeks or the simulated problem week.
2. **Estimate appliance usage:** Use the supported NILM models or the approved precomputed sample results.
3. **Understand consumption:** Show estimated energy consumption and approximate cost contribution for supported appliances.
4. **Compare usage:** Compare the selected period against the defined baseline.
5. **Identify unusual changes:** Flag eligible deviations and explain the likely driver only when supported by the analysis.
6. **Recommend an action:** Present practical actions from deterministic recommendation rules.
7. **Notify the user:** Demonstrate the configured email alert when an eligible issue is flagged.

Clearly distinguish aggregate measurements, model estimates, calculated values, and simulated scenarios.

## 5. MVP Features and Priorities

| Feature | Priority | Requirement |
|---|---|---|
| Prepared sample scenarios | P0 | Normal and simulated problem scenarios work end to end |
| Bill and tariff input | P0 | Cost calculations use the configured effective rate |
| Appliance cost breakdown | P0 | Show estimates only for supported appliances |
| Model evaluation | P0 | Display actual evaluation results and methodology |
| Baseline comparison | P0 | Identify eligible unusual changes using approved rules |
| Recommendations | P0 | Use deterministic rules and explain possible actions |
| Email alerts | P0 | Test the configured notification flow |
| CSV upload | P1 | Implement only after the P0 flow works |
| Additional interface polish | P2 | Only after required functionality is reliable |

Detailed acceptance criteria and implementation tracking are maintained in `TASKS.md`. Verification procedures belong in `TESTING.md`.

## 6. Appliance Support

Candidate appliances include air conditioning, refrigeration, and washing machines. These are candidates, not confirmed capabilities.

An appliance may be presented as supported only when:

- Its recorded evaluation decision is `go`.
- Its required model is available and successfully loaded.
- The implementation follows the support rules in `ARCHITECTURE.md`.

Never invent appliance-level results for unsupported appliances. If no appliance passes the evaluation gate, report the blocker honestly and obtain an explicit team decision before changing the approach. Synthetic-trace appliances are restricted to the P0 fallback demo (`demo` status in registry) and must never be represented as real-model predictions.

## 7. Analytics and Environmental Impact

NILM is the machine-learning component. Cost calculations, baseline comparisons, unusual-usage detection, and recommendations use the deterministic logic defined in `ARCHITECTURE.md`.

The product may present:

- Estimated appliance-level energy consumption.
- Approximate electricity cost contributions.
- Changes relative to the defined baseline.
- Possible actions associated with unusual usage.
- Possible savings and avoided emissions, only when their calculations and required inputs are supported.

These values are estimates, not guarantees.

The `problem_week` scenario is simulated. It must be labelled as simulated wherever users might otherwise mistake it for a real household event.

Do not claim measured household savings, measured emissions reductions, or proven real-world environmental impact without supporting evidence.

## 8. AI and AWS

### AI/ML

NILM estimates appliance-level consumption from aggregate electricity measurements. It is the core ML capability of the product.

Do not introduce an LLM, chatbot, or agent framework into calculations or recommendations (Decision D-018). AI must serve a real product requirement, not merely increase the apparent complexity.

### AWS

Follow the approved architecture in `ARCHITECTURE.md`:

- **Amazon EC2:** Hosts the application.
- **Amazon S3:** Stores configured artifacts and sample data.
- **Amazon SNS:** Supports email notifications.
- **AWS IAM:** Controls access to AWS resources.

Do not introduce additional AWS services without a concrete requirement and an explicit team decision.

## 9. Explicit Non-Goals

The MVP does not include:

- A chatbot, AI agent, or LLM-generated calculations (D-018).
- Individual appliance sensors, smart plugs, or custom hardware.
- Smart-home control or a mobile application.
- User accounts, persistent per-user history, or a production multi-household platform (D-005, D-019).
- Long-term forecasting or improvement tracking.
- Claims that an appliance is defective based only on an unusual-usage flag (D-022).
- Validated small-business monitoring (D-001).
- Additional databases, queues, microservices, or infrastructure outside the approved architecture (D-003, D-005).
- Claims of measured environmental impact based only on simulated scenarios.

- Synthetic appliance scenarios are part of the P0 fallback demo to ensure the product remains demonstrable even if no real appliance meets the GO criteria; they are required for a reliable demo.

## 10. Product Decisions and Skeptical Challenge Defenses

### Key Scope and Product Decisions

- **D-001 (Residential scope):** Indian households are the sole validated target because the iAWE dataset is residential. Small-business use remains future work.
- **D-018 (Deterministic intelligence):** No LLMs, conversational agents, or generative models. Recommendations are driven by deterministic rules and fixed action definitions.
- **D-022 (Honest wording):** The UI uses "likely driver", never "cause", and forbids defect-implying terminology.
- **D-023 (Approximate rate derivation):** Bill input calculates an effective rate (₹/kWh) labelled approximate; sample default bills are derived from sample consumption and labelled illustrative.
- **D-024 (Sourced emissions factor):** CO₂ factor is nullable and sourced from the CEA Baseline Database; emission reductions are hidden if not configured.
- **D-026 (Demo resilience):** Demo resilience is a P0 priority, requiring a backup video, laptop fallback mode, pre-captured alert screenshots, and timed rehearsals.
- **D-029 (Synthetic fallback):** Deterministic synthetic traces ensure the product insight loop is fully demonstrable even if no candidate model passes offline validation.

### Prepared Answers to Skeptical Inquiries

| Challenge | Prepared Honest Answer |
|---|---|
| "One house. Will it work in mine?" | Not proven. The model is evaluated on unseen weeks of the same house. We display weekly error and downstream check results; cross-household transfer is future work. |
| "You picked the best example." | The example window is selected by a deterministic frozen rule; weekly results for all test weeks are reported in the evaluation panel. |
| "Beating a mean-share split is trivial." | It is the defined minimum bar; actual numbers against the naive baseline are reported either way. |
| "Isn't the problem week fake?" | Yes, it is a transparently labelled simulated scenario. The anomaly flag is evaluated from the model's estimate on the modified aggregate, not from injected ground truth. |
| "Who has 1-minute data?" | One main-panel clamp meter instead of sub-metering every appliance. Monthly bill data alone is insufficient. |
| "Why only these appliances?" | Only appliances passing offline evaluation are supported; rejected candidates are listed with reasons in the methodology drawer. |

## 11. Limitations

The app and public documentation must disclose:

1. Appliance-level figures are estimates derived from an aggregate electricity signal.
2. Initial model development and evaluation use data from one household in the iAWE dataset from Delhi, covering approximately 73 days.
3. Performance on other households has not been established.
4. Only appliances that pass evaluation and runtime availability checks are supported.
5. The analysis requires suitable time-series data; a monthly bill alone is insufficient.
6. Effective electricity rates and cost contributions are approximate.
7. Possible savings depend on user actions and actual operating conditions.
8. The problem-week scenario is simulated.
9. Real-world energy and emissions reductions have not been measured.

## 12. MVP Success Criteria

The submission should meet the following criteria:

1. At least one appliance passes the documented evaluation gate on held-out real data and beats the defined naive baseline, or the synthetic fallback demo is clearly disclosed as the fallback.
2. The downstream check detects an injected increase and its results are reported with appropriate limitations.
3. The deployed application supports the required sample-analysis flow.
4. The normal and simulated problem scenarios are clearly distinguished.
5. The interface explains the estimates, comparisons, and recommended actions.
6. The notification flow is tested or cleanly disabled.
7. The core demo can be completed twice consecutively within approximately three minutes.
8. Every displayed model metric and evaluation result is traceable to actual output.
9. The limitations above are disclosed in the app and public documentation.

If a criterion fails, report the failure accurately rather than presenting the project as fully validated.

## 13. Documentation Responsibilities

The project maintains five canonical internal specification documents:

- `PROJECT.md` — product scope, workflow, key decisions, and limitations.
- `ARCHITECTURE.md` — technical architecture, frozen contracts, APIs, schemas, processing, calculations, and Architecture Decision Record.
- `TASKS.md` — implementation plan, priorities, requirements acceptance criteria matrix, dependencies, and task status.
- `TESTING.md` — verification plan, test procedures, commands, and release gates.
- `DEPLOYMENT.md` — AWS operational runbook, configuration, troubleshooting, and teardown.

Public and agent documentation:
- `README.md` — public GitHub landing page, verified summary, and repository guide.
- `AGENTS.md` — coding-agent rules, source-of-truth hierarchy, and execution constraints.

Avoid duplicating detailed technical contracts across documents. When requirements conflict, identify the conflict and resolve it explicitly before implementation.