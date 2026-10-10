# AGENTS.md — Coding Agent Instructions

## Mission

Build a reliable, demonstrable Appliance Energy Analyzer MVP within the approved product scope and four-day plan. Make the smallest change that satisfies the task.

## Documentation authority

The repository's documentation structure is `AGENTS.md`, `PROJECT.md`, `ARCHITECTURE.md`, `TASKS.md`, and `README.md`. `ARCHITECTURE.md` is the sole technical source of truth. Follow its contracts, schemas, preprocessing, evaluation, provenance, AWS, and deployment requirements. Do not redesign the architecture without explicit authorization. If a required technical decision is missing or documents conflict, report the exact issue instead of guessing.

## Implementation rules

- Inspect the relevant source, tests, repository state, and `TASKS.md` before changing code. Documentation is not evidence that implementation or tests exist.
- Preserve API and artifact contracts; update relevant documentation and tests when an authorized change affects them.
- Real-model appliances may be shown only when their registry decision is `go` and their model loads. Synthetic-trace appliances may be shown only with registry decision `demo`, inclusion in the selected sample manifest, and valid trace data.
- Synthetic outputs are demonstrations, never real-model predictions or real-model evaluation results. The P0 synthetic fallback must work independently of real-model evaluation success.
- Do not bypass evaluation, provenance, or sample-manifest requirements to make an appliance appear supported.
- Never fabricate metrics, predictions, test results, deployment status, notification success, savings, or measured environmental impact. Label the synthetic scenario clearly; describe savings and emissions as estimates.
- Do not present an unusual-use flag as proof that an appliance is defective.

## Priorities and verification

- P0 is required for a reliable submission. Start with the working synthetic fallback. P1 follows the P0 end-to-end flow; P2 is optional.
- Follow task dependencies and release gates in `TASKS.md`. Add or update tests for changed behavior and run the relevant documented checks. Report only commands actually run and their results; never weaken tests to obtain a pass.
- Do not commit secrets, restricted data, or unapproved model/sample artifacts. Use the EC2 instance role for application AWS access; follow the read-only S3 permissions in `ARCHITECTURE.md`.
- Do not claim work is complete until acceptance criteria and relevant verification are satisfied. Review the final diff for unrelated changes and report incomplete checks or blockers.
