# Appliance Energy Analyzer ⚡

**Your bill tells you how much. We tell you why, and what to fix first.**

Appliance Energy Analyzer is a web application exploring how a household's aggregate electricity consumption can be used to estimate appliance-level energy and cost contributions, compare usage patterns, and identify potential energy-saving actions without installing a separate sensor on every appliance.

Built by **Inglorious Momos** for Environmental Hacks × AWS — Bharat Builds.

## The problem

Households usually receive one electricity bill showing total consumption and cost. That makes it difficult to understand which appliances contribute most to consumption or explain an unexpected increase in the bill. Individual smart plugs can help, but require additional hardware and installation.

## What the application does

- **Appliance-level analysis:** Presents estimated energy and cost contributions for an available scenario.
- **Usage comparisons:** Explores differences between a typical period and a demonstration scenario when the corresponding data and model are available.
- **Potential actions:** Presents practical recommendations based on the available analysis.
- **Evaluation transparency:** Exposes the distinction between evaluated real-model outputs and synthetic demonstration results.
- **Sample-based demonstration:** Runs a reproducible simulated scenario without requiring live household meter hardware.

The available functionality depends on the sample, data, and model status reported by the backend.

## How it works

1. The user opens the web dashboard and selects an available analysis sample.
2. The React frontend sends requests to the FastAPI backend.
3. The backend loads and validates application artifacts and sample data stored in Amazon S3.
4. The analysis pipeline processes the available inputs and produces the supported results.
5. The frontend presents the estimates, comparisons, and potential actions.

The application includes a synthetic fallback scenario for demonstration. Synthetic output must not be interpreted as a real appliance prediction or proof of successful real-model evaluation.

## Current demonstration status

The deployed demonstration uses synthetic appliance traces for:

- Air conditioner
- Water heater

The backend's registry also lists candidate real-model appliances, including an air conditioner, refrigerator, and washing machine. These candidates are **inactive in the deployed runtime** and should not be represented as validated working predictions.

The application has been deployed to Amazon EC2. The backend health endpoint returned HTTP 200 with `ready: true`, S3 synchronization succeeded, and the `simulated_scenario` sample reported `ready` during verification.

## Architecture

```text
User's browser
      |
      | HTTP
      v
Amazon EC2 — Ubuntu
  React + TypeScript frontend
      |
      v
  FastAPI + Uvicorn backend
      |
      +------> Amazon S3
      |        Sample datasets
      |        Registry and artifacts
      |        Configuration and evaluation evidence
      |
      +------> Python analysis pipeline
               NumPy / pandas
               ONNX Runtime dependency
```

### AWS services

| Service | Purpose |
|---|---|
| Amazon EC2 | Hosts the web application and API |
| Amazon S3 | Stores sample data and application artifacts |
| AWS IAM | Grants the EC2 instance role access to required S3 objects |
| Amazon SNS | Optional notification capability; disabled in the current deployment |

The deployed application uses an EC2 instance role for S3 access rather than embedding AWS credentials in the application configuration.

## Technology stack

**Frontend**
- React
- TypeScript
- Vite

**Backend and processing**
- Python
- FastAPI
- Uvicorn
- NumPy
- pandas
- ONNX Runtime
- boto3

**Infrastructure**
- Amazon EC2
- Amazon S3
- AWS IAM
- Optional Amazon SNS

## Data and limitations

- Real-model development uses the **iAWE dataset**, collected from one household in Delhi.
- Performance across other households has not been established.
- The current public demonstration relies on synthetic traces for its working appliance-level example.
- Candidate real-model appliances are inactive in the deployed runtime.
- Energy attribution, cost estimates, and potential savings depend on the quality of the available inputs and analysis.
- Recommendations are not guarantees of savings.
- No real-world electricity or emissions reductions have been measured.
- Optional notifications are disabled in the current deployment.

These limitations are intentional disclosures. The project distinguishes a functioning software demonstration from a validated real-world appliance-disaggregation system.

## Running locally

### Prerequisites

- Node.js and npm
- Python 3.12 or a compatible version
- Git

### 1. Clone the repository

```bash
git clone https://github.com/pushkarthisside/appliance-energy-analyzer.git
cd appliance-energy-analyzer
```

### 2. Start the backend

```bash
cd backend
python -m venv .venv
```

Activate the environment:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Linux/macOS**
```bash
source .venv/bin/activate
```

Install dependencies and start the API:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Start the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite.

> **Note:** The deployed environment is configured to load application artifacts from Amazon S3. A local run may require the appropriate environment configuration, AWS credentials or IAM access, and valid sample artifacts. Do not commit credentials or private configuration files.

## Verification

From the repository root, the frontend can be checked with:

```bash
cd frontend
npm run typecheck
npm run build
```

Backend tests can be run using pytest in the configured Python environment:

```bash
cd backend
python -m pytest
```

## Documentation

- [Product scope and requirements](PROJECT.md)
- [Architecture and operational behavior](ARCHITECTURE.md)
- [Implementation plan and acceptance criteria](TASKS.md)
- [Architecture decisions](DECISIONS.md)
- [Deployment instructions](DEPLOYMENT.md)
- [Coding-agent instructions](AGENTS.md)

## Team

**Inglorious Momos** — Environmental Hacks × AWS, Bharat Builds.

The project focuses on making household energy consumption more understandable and actionable while keeping model limitations and environmental-impact claims explicit.
