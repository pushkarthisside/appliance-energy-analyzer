import { useEffect, useState } from "react";

import type {
  AnalysisResponse,
  ApiErrorResponse,
  HealthResponse,
  SampleAnalysisRequest,
} from "./types";

const sampleTitles = {
  typical_period: "Typical period",
  simulated_scenario: "Simulated scenario",
} as const;

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState("");
  const [amountInr, setAmountInr] = useState("");
  const [unitsKwh, setUnitsKwh] = useState("");
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const availableSamples = health?.samples.filter((sample) => sample.state === "ready") ?? [];
  const selectedSample = availableSamples.find((sample) => sample.id === sampleId);
  const billAmount = Number(amountInr);
  const billUnits = Number(unitsKwh);
  const billIsValid =
    amountInr !== "" &&
    unitsKwh !== "" &&
    Number.isFinite(billAmount) &&
    Number.isFinite(billUnits) &&
    billAmount > 0 &&
    billUnits > 0 &&
    billAmount <= 10_000_000 &&
    billUnits <= 10_000_000;

  useEffect(() => {
    let active = true;

    fetch("/api/health")
      .then(async (response) => {
        const payload = (await response.json()) as HealthResponse;
        if (!response.ok && payload.status !== "not_ready") {
          throw new Error(`Health request failed (${response.status}).`);
        }
        if (active) setHealth(payload);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "The API could not be reached.",
          );
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!availableSamples.some((sample) => sample.id === sampleId)) {
      setSampleId(availableSamples[0]?.id ?? "");
    }
  }, [health, sampleId, availableSamples]);

  async function analyze(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSample || !billIsValid) return;

    const body: SampleAnalysisRequest = {
      sample_id: sampleId,
      bill: { amount_inr: billAmount, units_kwh: billUnits },
    };
    setSubmitting(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    try {
      const response = await fetch("/api/analyze/sample", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const apiError = payload as ApiErrorResponse;
        throw new Error(apiError.error?.message ?? `Analysis request failed (${response.status}).`);
      }
      setAnalysisResult(payload as AnalysisResponse);
    } catch (requestError: unknown) {
      setAnalysisError(
        requestError instanceof Error ? requestError.message : "The analysis request failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="status-card" aria-labelledby="page-title">
        <p className="eyebrow">Sample analysis</p>
        <h1 id="page-title">Appliance Energy Analyzer</h1>
        <p className="intro">
          Analyze a prepared electricity sample when its data and analysis pipeline are available.
        </p>

        <div className="status-row" aria-live="polite">
          <span
            className={`status-dot ${health?.ready ? "is-ready" : "is-waiting"}`}
            aria-hidden="true"
          />
          <span>Service status</span>
          <strong>{health?.status ?? (error ? "unavailable" : "checking")}</strong>
        </div>

        {health && (
          <p className="detail">
            {health.ready
              ? "Service is ready. Choose an available sample to continue."
              : "Analysis is not ready: sample artifacts and the analysis pipeline are not connected. No analysis results are being shown."}
          </p>
        )}
        {error && <p className="error-message">{error}</p>}

        <section className="samples" aria-labelledby="samples-title">
          <h2 id="samples-title">Prepared samples</h2>
          {health?.samples.length ? (
            <ul>
              {health.samples.map((sample) => (
                <li key={sample.id}>
                  <span>{sampleTitles[sample.id]}</span>
                  <strong>{sample.state === "ready" ? "Available" : "Unavailable"}</strong>
                  {sample.id === "simulated_scenario" && <small>Simulated demonstration</small>}
                  {sample.detail && <small>{sample.detail}</small>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="detail">Sample availability has not been reported by the API.</p>
          )}
        </section>

        <form className="analysis-form" onSubmit={analyze}>
          <label>
            Sample
            <select
              value={sampleId}
              onChange={(event) => setSampleId(event.target.value)}
              disabled={availableSamples.length === 0 || submitting}
            >
              <option value="">No available samples</option>
              {availableSamples.map((sample) => (
                <option value={sample.id} key={sample.id}>
                  {sampleTitles[sample.id]}
                </option>
              ))}
            </select>
          </label>
          <div className="bill-fields">
            <label>
              Bill amount (₹)
              <input
                type="number"
                min="0.01"
                max="10000000"
                step="0.01"
                value={amountInr}
                onChange={(event) => setAmountInr(event.target.value)}
                disabled={!selectedSample || submitting}
              />
            </label>
            <label>
              Bill units (kWh)
              <input
                type="number"
                min="0.01"
                max="10000000"
                step="0.01"
                value={unitsKwh}
                onChange={(event) => setUnitsKwh(event.target.value)}
                disabled={!selectedSample || submitting}
              />
            </label>
          </div>
          <button type="submit" disabled={!selectedSample || !billIsValid || submitting}>
            {submitting ? "Analyzing…" : "Analyze sample"}
          </button>
          {!selectedSample && (
            <p className="detail">Analysis becomes available when the API reports a ready sample.</p>
          )}
        </form>

        {analysisError && <p className="error-message" role="alert">{analysisError}</p>}
        {analysisResult !== null && (
          <pre className="analysis-result" aria-label="Analysis response">
            {JSON.stringify(analysisResult, null, 2)}
          </pre>
        )}
      </section>
    </main>
  );
}
