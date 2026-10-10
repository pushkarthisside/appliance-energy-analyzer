# Appliance Energy Analyzer

**Understand where your household electricity goes — and what to fix first.**

Appliance Energy Analyzer estimates appliance-level energy use from a single whole-house power signal (without using individual appliance sensors), flags unusual consumption, and recommends actions with possible savings.

## How it works

1. **Estimate:** Use NILM to estimate energy consumption for supported appliances.
2. **Compare:** Identify unusual weekly consumption against each appliance's baseline.
3. **Recommend:** Rank practical actions by possible cost and energy savings.
4. **Alert:** Send an email when unusual consumption is detected.

## Technology

- Python, FastAPI and ONNX Runtime
- React, TypeScript and Vite
- AWS EC2, Amazon S3, Amazon SNS and IAM

## Data and limitations

The MVP uses the iAWE dataset from one household in Delhi. Appliance readings are estimates, and performance in other households is unverified. The problem-week demo is simulated. Savings are estimates, not guarantees; no real-world energy or emissions reductions have been measured.

**Status:** In active development. Real-model evaluation results will be recorded following offline validation on held-out iAWE test data. A deterministic synthetic-trace scenario provides the P0 fallback for complete workflow demonstration.

## Documentation

The project maintains five canonical internal specification documents:

- [Product specification](PROJECT.md) — Scope, target user, workflow, key decisions, and limitations.
- [Architecture](ARCHITECTURE.md) — Authoritative technical design baseline, APIs, schemas, and Architecture Decision Record (ADR).
- [Implementation plan & Requirements](TASKS.md) — Implementation phases, task tracking, requirements acceptance criteria matrix, and traceability.
- [Testing plan](TESTING.md) — Verification plan, test suites, commands, and release gates.
- [Deployment manual](DEPLOYMENT.md) — AWS operational runbook, configuration, service unit, and teardown.

Coding agent instructions:
- [Agent instructions](AGENTS.md) — Execution rules, safety constraints, and boundaries.
