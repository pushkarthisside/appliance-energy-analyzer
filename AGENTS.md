# AGENTS.md — Rules for coding agents (Antigravity and others)

You are implementing an **approved plan**. Do not redesign it. When something in the plan seems wrong, stop and report it; do not quietly build something different.

## 1. Before you write code

1. Read the task in [TASKS.md](TASKS.md) you were given, including its dependencies and **Done when** line.
2. Read the sections of [ARCHITECTURE.md](ARCHITECTURE.md) that the task touches. ARCHITECTURE.md is the single source of truth for contracts, schemas, rules and paths.
3. Check [DECISIONS.md](DECISIONS.md) for any decision affecting the task, and §4 for unresolved items. Never implement an unresolved item as if it were decided.
4. If the task depends on an unfinished task, say so and stop.

## 2. Contracts you must not change on your own

- API endpoints and JSON shapes (ARCH §6), including field names and error codes.
- Artifact schemas: `registry.json`, `settings.json`, `actions.json`, `scenario.json`, `evaluation.json` (ARCH §6.8, §7).
- The model I/O contract (ARCH §9.1) and preprocessing rules (ARCH §8).
- Analytics formulas and wording (ARCH §10).
- File and folder paths (README §Repository layout).

A contract change requires: both teammates agree → a new `D-xxx` entry in DECISIONS.md → ARCHITECTURE.md updated → `schemas.py`, `types.ts`, mocks and tests updated in the **same** commit.

## 3. Architecture boundaries

- Do **not** add: databases, queues, Lambda, API Gateway, containers, Kubernetes, Caddy/Nginx, auth systems, LLMs, chatbots, agent frameworks, new AWS services, or new frontend frameworks/state libraries.
- Do **not** hard-code appliance ids or names anywhere except tests and `actions.json`. Read them from the registry/config.
- Preprocessing exists once, in `backend/app/ingest/preprocess.py`. Training and evaluation code imports it. Never copy it.
- Analytics are deterministic Python/NumPy. No randomness at request time.

## 4. Priorities

Work on P0 tasks first, in TASKS.md order. Do not start P1 before checkpoint C4, or P2 before C5. If asked for a P1/P2 feature early, say what P0 work is still open.

## 5. Honesty rules (non-negotiable)

- **Never fabricate** metrics, evaluation results, savings, CO₂ factors, dataset facts or test results. If a number is not produced by code from real data, do not write it.
- Mock fixtures are allowed only in `frontend/src/mocks/` and `backend/tests/fixtures/`, and must never be shown as results.
- Never present the `problem_week` scenario as real household data.
- Never show an appliance as supported unless its registry status is `go`.
- User-facing text must not contain: fault, faulty, broken, waste, wasted, cause, guaranteed. Use "likely driver" and "possible savings if use returns to its normal level".
- No confidence scores anywhere.

## 6. Testing

- Add or update the tests named in the task (IDs in [TESTING.md](TESTING.md)) in the same change.
- Run before reporting done:
  - backend: `cd backend && .venv/bin/pytest -q`
  - frontend: `cd frontend && npm run typecheck && npm run build`
- Report results exactly as they came out. If a test fails, say which one and why. Never weaken, skip or delete a test to make it pass without stating that you did and why.

## 7. Secrets and data

- Never commit AWS keys, `.env` files, the dataset, `*.onnx` or sample CSVs.
- The server uses the IAM instance role; do not add credential code.
- Do not log uploaded file contents.

## 8. When you finish a task

1. Tick the checkbox in TASKS.md only if **Done when** is verifiably true.
2. If you made a decision the docs did not cover, add a `D-xxx` entry to DECISIONS.md (status **Proposed** unless the team confirmed it).
3. If you resolved an unresolved item, fill in its Resolution line with evidence.
4. Summarise: what changed, which tests ran and their results, anything left undone or uncertain.

## 9. When you are blocked or think the plan is wrong

Stop, describe the problem, propose at most two options with their trade-offs, and wait for a human decision. Do not work around the plan.
