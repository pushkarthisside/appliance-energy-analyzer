# Appliance Energy Analyzer

Appliance Energy Analyzer explores how a household's whole-house electricity signal can support appliance-level estimates, unusual-use comparisons, and practical recommendations without a separate sensor for each appliance.

## How it works

1. Choose an available sample: `typical_period` is available only when a real appliance model passes the frozen evaluation criteria; `simulated_scenario` is the explicitly disclosed synthetic demonstration fallback.
2. Review estimated appliance energy and cost contributions, comparisons, and possible actions.
3. Inspect the evaluation evidence and limitations. Synthetic demonstration output is not a real appliance prediction or evidence of successful real-model evaluation.
4. An eligible analysis may trigger an email when optional SNS alerting is enabled and configured, and the sample/source cooldown permits it.

## Planned technology

- Python, FastAPI, and ONNX Runtime
- React, TypeScript, and Vite
- AWS EC2, Amazon S3, optional Amazon SNS, and IAM

## Data and limitations

Real-model development uses the iAWE dataset from one household in Delhi; performance in other households has not been established. The synthetic fallback is simulated. Appliance values and possible savings are estimates, not guarantees; no real-world energy or emissions reductions have been measured.

**Status:** In active development. This README makes no claim that a model passed evaluation, deployment succeeded, or notifications were delivered.

## Documentation

- [Product scope](PROJECT.md)
- [Authoritative technical specification and operations](ARCHITECTURE.md)
- [Implementation plan, acceptance criteria, and release checks](TASKS.md)
- [Coding-agent instructions](AGENTS.md)
