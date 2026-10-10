# AGENTS.md — Coding Agent Instructions

## 1. Mission

Build the **Appliance Energy Analyzer** hackathon MVP according to the approved product scope, architecture, requirements, and task plan.

Optimize for a reliable, demonstrable product. Do not optimize for complexity or feature count.

## 2. Read Before Implementing

Before starting a task, inspect:

1. `TASKS.md` — task, dependencies, priority, requirements acceptance criteria (§14), and completion criteria.
2. `ARCHITECTURE.md` — technical contracts, architecture decisions (§2.5), and implementation design.
3. `PROJECT.md` — product scope, decisions, and limitations.
4. `TESTING.md` — relevant tests and verification commands.
5. `DEPLOYMENT.md` — deployment and AWS configuration.
6. Existing source code, tests, and repository structure.

Do not assume that documentation describes the current implementation correctly. Inspect the code before modifying it.

## 3. Source-of-Truth Rules

The project maintains five canonical internal specification documents:

- `PROJECT.md` defines product scope, workflow, key decisions, and limitations.
- `ARCHITECTURE.md` defines technical contracts, APIs, schemas, calculations, and the Architecture Decision Record.
- `TASKS.md` defines implementation order, requirements acceptance criteria matrix, dependencies, and status.
- `TESTING.md` defines verification procedures, test commands, and release gates.
- `DEPLOYMENT.md` defines deployment and operational procedures.

Supporting documentation:
- `README.md` is public-facing landing page documentation.
- `AGENTS.md` defines coding-agent execution rules.

If documents conflict, do not silently choose one or invent a resolution. Report the exact conflict and wait for a decision when it affects correctness or implementation.

## 4. Architecture Boundaries

Follow the approved architecture in `ARCHITECTURE.md`.

The intended deployment consists of:

- One FastAPI application serving the frontend and API from the same origin on port 80.
- One EC2 instance hosting the application.
- Amazon S3 for configured artifacts and sample data.
- Amazon SNS for the configured email notification flow.
- AWS IAM for access control.
- NILM models for appliance-level consumption estimates.
- Deterministic Python logic for downstream calculations and recommendations.

Do not independently introduce:

- A database, message queue, Lambda, or API Gateway.
- Containers, Kubernetes, or additional services.
- A different frontend framework.
- An LLM, chatbot, or agent framework.
- New AWS services or infrastructure.

Any architecture change requires an explicit team decision recorded in `ARCHITECTURE.md` §2 and corresponding documentation updates.

## 5. Technical Correctness

- Reuse the approved preprocessing, model adapter, and analytics implementation.
- Keep training, evaluation, and inference behavior consistent with the architecture.
- Keep calculations deterministic where specified.
- Do not duplicate formulas or implement competing versions of the same logic.
- Follow the existing API schemas, artifact schemas, error contracts, and file paths.
- Validate external data and handle missing, malformed, or insufficient data explicitly.
- Real‑model appliances may be shown only when their registry entry has a `decision` of `go` **and** the model loads successfully at runtime.
- Synthetic‑trace appliances may be shown only when their registry entry has a `decision` of `demo`, the selected sample manifest lists the appliance, **and** the associated trace data is valid.
- Synthetic‑trace outputs must never be presented as real‑model predictions nor be included in real‑model evaluation metrics.
- Do not bypass the registry, provenance, or sample‑manifest contracts defined in `ARCHITECTURE.md`.
- Never bypass evaluation requirements to make an appliance appear supported.
- Do not change public interfaces or data contracts without updating the relevant documentation and tests.

## 6. Evidence and Honest Reporting

Never fabricate:

- Model metrics, evaluation results, or test outcomes.
- Appliance-level measurements or model predictions.
- Electricity savings, cost reductions, or emissions reductions.
- Dataset facts, deployment status, or notification success.

Distinguish clearly between:

- Measured aggregate electricity data.
- Model-estimated appliance consumption.
- Calculated costs and analytical outputs.
- Simulated scenarios.
- Actual evaluation results.

The `problem_week` scenario is simulated and must be labelled accordingly.

Savings and emissions figures are estimates, not guaranteed outcomes. Do not claim measured real-world impact without supporting evidence.

Follow the user-facing wording restrictions defined in `ARCHITECTURE.md`. Do not present an unusual-usage flag as proof that an appliance is defective.

## 7. Priority Discipline

- **P0:** Required for a reliable submission.
- **P1:** Implement only after the P0 end-to-end flow works.
- **P2:** Optional polish after required features are complete.

Follow the dependencies and release gates in `TASKS.md`.

Do not begin optional work while a required task or release gate is blocked. When time is limited, cut lower-priority features rather than weakening correctness.

## 8. Implementation and Testing

For each task:

1. Inspect the relevant code and existing tests.
2. Make the smallest change that satisfies the requirement.
3. Add or update tests for the behavior changed.
4. Run the relevant checks.
5. Inspect the final diff for unintended changes.
6. Update task status only after verification.

Use the verification commands documented in `TESTING.md`. The standard commands currently specified are:

**Backend**
```bash
cd backend
.venv/bin/pytest -q
```

**Frontend**
```bash
cd frontend
npm run typecheck && npm run build
```

Do not claim a command passed unless it was actually run and passed. Do not weaken, delete, or bypass tests merely to obtain a passing result.

If a test cannot run, report why and identify the remaining verification needed.

## 9. AWS, Credentials, and Data

- Use the EC2 instance role for application access to AWS services.
- Follow the least-privilege permissions and resource scope defined in `DEPLOYMENT.md`.
- Never commit AWS credentials, private keys, secret environment files, or other secrets.
- Do not commit restricted dataset files, model binaries, or sample CSVs unless explicitly approved.
- Do not log uploaded electricity data unnecessarily.
- Verify the AWS region and expected costs before creating resources.
- Do not claim a deployment or notification works without testing it.

## 10. Completion Criteria

A task is complete only when:

- Its documented acceptance criteria are met.
- Relevant tests have been run.
- Results and limitations are reported honestly.
- Documentation is updated if behavior or contracts changed.
- The final diff contains no unrelated changes.

In your completion summary, state:

- What changed.
- Which tests were run and their actual results.
- What remains incomplete.
- Any unresolved decisions or limitations.

## 11. When Blocked

Stop and report the blocker if:

- A required decision remains unresolved.
- The architecture and implementation contradict each other.
- The data or model does not meet the required evaluation gate.
- A task depends on an unavailable artifact or service.
- The proposed change would expand the approved scope.

Explain the issue, its impact, and at most two practical options. Do not silently invent requirements or make major architectural decisions on the team's behalf.