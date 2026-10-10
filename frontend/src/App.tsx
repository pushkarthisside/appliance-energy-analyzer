import { useEffect, useState } from "react";

import type { HealthResponse } from "./types";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <main className="page-shell">
      <section className="status-card" aria-labelledby="page-title">
        <p className="eyebrow">P0 application scaffold</p>
        <h1 id="page-title">Appliance Energy Analyzer</h1>
        <p className="intro">
          The API and interface foundation is in place. Sample analysis will
          appear when the analysis pipeline is integrated.
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
              ? "The service is ready."
              : "The service is not ready because artifact loading and sample analysis are not connected yet."}
          </p>
        )}
        {error && <p className="error-message">{error}</p>}
      </section>
    </main>
  );
}
