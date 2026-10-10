import { useEffect, useMemo, useState } from "react";

import type {
  AnalysisResponse,
  ApiErrorResponse,
  HealthResponse,
  SampleAnalysisRequest,
} from "./types";

type TariffStructure = "single_rate" | "tiered" | "additional_charges" | "unknown";
type BillingDetails = {
  amount: string;
  units: string;
  startDate: string;
  endDate: string;
  tariff: TariffStructure;
};

const sampleTitles = {
  typical_period: "Typical period",
  simulated_scenario: "Simulated scenario",
} as const;

const tariffNotes: Record<TariffStructure, string> = {
  single_rate: "The analysis uses the blended effective rate returned by the API.",
  tiered:
    "The API uses bill total ÷ billed units as a blended average. It does not reproduce individual tariff tiers.",
  additional_charges:
    "The API uses bill total ÷ billed units as a blended average; fixed charges and taxes are not separated.",
  unknown:
    "The API uses bill total ÷ billed units as a blended average. Review your bill for tiers and additional charges.",
};

const initialBilling: BillingDetails = {
  amount: "",
  units: "",
  startDate: "",
  endDate: "",
  tariff: "unknown",
};

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

function formatCurrency(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? "—" : currency.format(value);
}

function formatKwh(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(1)} kWh`;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function alertLabel(status: AnalysisResponse["alert"]["status"]) {
  const labels = {
    sent: "Notification sent",
    failed: "Notification failed",
    disabled: "Alerts disabled",
    no_issues: "No eligible insights",
    cooldown: "Alert held by cooldown",
  };
  return labels[status];
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [sampleId, setSampleId] = useState<"typical_period" | "simulated_scenario" | "">("");
  const [billing, setBilling] = useState(initialBilling);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [selectedApplianceId, setSelectedApplianceId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/health")
      .then(async (response) => {
        const payload = (await response.json()) as HealthResponse;
        if (!response.ok && payload.status !== "not_ready") {
          throw new Error(`Service status request failed (${response.status}).`);
        }
        if (active) setHealth(payload);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setHealthError(
            requestError instanceof Error ? requestError.message : "The API could not be reached.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const availableSamples = health?.samples.filter((sample) => sample.state === "ready") ?? [];
  const selectedSample = availableSamples.find((sample) => sample.id === sampleId);
  const amount = Number(billing.amount);
  const units = Number(billing.units);
  const amountValid = billing.amount !== "" && Number.isFinite(amount) && amount > 0 && amount <= 10_000_000;
  const unitsValid = billing.units !== "" && Number.isFinite(units) && units > 0 && units <= 10_000_000;
  const periodValid =
    Boolean(billing.startDate) &&
    Boolean(billing.endDate) &&
    billing.startDate <= billing.endDate;
  const billValid =
    amountValid && unitsValid;

  const appliances = useMemo(
    () =>
      (analysis?.appliances ?? [])
        .sort((left, right) => (right.cost_period_inr ?? -1) - (left.cost_period_inr ?? -1)),
    [analysis],
  );
  const selectedAppliance = appliances.find((appliance) => appliance.id === selectedApplianceId);
  const topOpportunity = analysis?.issues[0] ?? null;
  const leadingApplianceId = appliances.find((appliance) => appliance.provenance !== "residual")?.id;

  function updateBilling<K extends keyof BillingDetails>(key: K, value: BillingDetails[K]) {
    setBilling((current) => ({ ...current, [key]: value }));
    setAnalysis(null);
    setAnalysisError(null);
  }

  async function analyzeSample(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSample || !billValid || !periodValid || !sampleId) return;

    const request: SampleAnalysisRequest = {
      sample_id: sampleId,
      bill: { amount_inr: amount, units_kwh: units },
    };
    setSubmitting(true);
    setAnalysisError(null);
    setAnalysis(null);
    try {
      const response = await fetch("/api/analyze/sample", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const apiError = payload as ApiErrorResponse;
        throw new Error(apiError.error?.message ?? `Analysis request failed (${response.status}).`);
      }
      setAnalysis(payload as AnalysisResponse);
    } catch (requestError: unknown) {
      setAnalysisError(
        requestError instanceof Error ? requestError.message : "The analysis request failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="#overview" aria-label="Appliance Energy Analyzer overview">Appliance Energy</a>
        <nav className="primary-nav" aria-label="Dashboard sections">
          <a className="nav-link" href="#overview">Overview</a>
          <a className="nav-link" href="#appliances">Breakdown</a>
          <a className="nav-link" href="#insights">Recommendations</a>
          <a className="nav-link" href="#history">History</a>
        </nav>
      </header>

      <main className="dashboard" id="overview">

        <section className="page-heading">
          <div>
            <h1>Energy overview</h1>
            <p className="heading-copy">See how your electricity use is distributed across appliances.</p>
          </div>
          {analysis && <div className="period-chip"><span>Analysis period</span><strong>{formatDate(analysis.period.start)} – {formatDate(analysis.period.end)}</strong></div>}
        </section>

        {(healthError || !health?.ready) && (
          <section className="readiness-banner" role="status">
            <div>
              <strong>{healthError ? "Analysis service unavailable" : health ? "No prepared sample is ready" : "Checking sample availability"}</strong>
              <p>
                {healthError ?? (health ? "The analysis action will become available when the service has a ready sample." : "The analysis action will be available when the service responds.")}
              </p>
            </div>
          </section>
        )}

        {analysis?.source.simulated && (
          <section className="simulation-banner" role="status">
            <strong>Demonstration data</strong>
            <span>Synthetic scenario; these are estimates, not household measurements.</span>
          </section>
        )}

        <section className="summary-band" aria-label="Analysis summary">
          <div className="energy-total">
            <span className="summary-label">Estimated energy</span>
            <strong>{analysis ? formatKwh(analysis.summary.total_kwh_period) : "—"}</strong>
            <span className="summary-context">{analysis ? `${analysis.period.days}-day sample analysis` : "Run an analysis to see the sample total"}</span>
          </div>
          <div className="summary-support">
            <article className="summary-item">
              <span className="summary-label">Bill amount</span>
              <strong>{billing.amount ? formatCurrency(amount) : "—"}</strong>
              <small>{billing.units ? `${billing.units} kWh billed` : "Amount and units from your bill"}</small>
            </article>
            <article className="summary-item">
              <span className="summary-label">Estimated cost</span>
              <strong>{formatCurrency(analysis?.summary.estimated_cost_period_inr)}</strong>
              <small>{analysis ? `Approx. ₹${analysis.cost.effective_rate_inr_per_kwh.toFixed(2)} per kWh` : "Based on the bill's blended rate"}</small>
            </article>
            <article className="summary-item">
              <span className="summary-label">Potential monthly savings</span>
              <strong>{topOpportunity ? `${formatCurrency(topOpportunity.savings.inr_per_month.low)}–${formatCurrency(topOpportunity.savings.inr_per_month.high)}` : "—"}</strong>
              <small>{topOpportunity ? "Estimate if use returns to baseline" : "Shown when recommendations support it"}</small>
            </article>
          </div>
        </section>

        <div className="content-grid">
          <section className="panel bill-panel" aria-labelledby="bill-title">
            <div className="panel-heading"><h2 id="bill-title">Analysis inputs</h2></div>

            <form onSubmit={analyzeSample} className="bill-form">
              <fieldset>
                <legend>Sample</legend>
                <div className="sample-options">
                  {(["typical_period", "simulated_scenario"] as const).filter((id) => health?.samples.some((sample) => sample.id === id && sample.state === "ready")).map((id) => {
                    return (
                      <label className={`sample-option ${sampleId === id ? "selected" : ""}`} key={id}>
                        <input
                          type="radio"
                          name="sample"
                          value={id}
                          checked={sampleId === id}
                          disabled={submitting}
                          onChange={() => setSampleId(id)}
                        />
                        <span className="sample-option-copy">
                          <strong>{id === "simulated_scenario" ? "Demonstration sample" : sampleTitles[id]}</strong>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className="form-section-label">Bill details</div>
              <p className="input-hint">Enter the amount and units shown on your bill. Costs use the blended rate (amount ÷ units).</p>
              <div className="form-two-col">
                <label className="field-label">
                  Bill amount <span>₹</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    max="10000000"
                    step="0.01"
                    placeholder="e.g. 3,250"
                    value={billing.amount}
                    onChange={(event) => updateBilling("amount", event.target.value)}
                    required
                  />
                </label>
                <label className="field-label">
                  Billed units <span>kWh</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    max="10000000"
                    step="0.01"
                    placeholder="e.g. 410"
                    value={billing.units}
                    onChange={(event) => updateBilling("units", event.target.value)}
                    required
                  />
                </label>
                <label className="field-label">
                  Billing period starts
                  <input type="date" value={billing.startDate} onChange={(event) => updateBilling("startDate", event.target.value)} required />
                </label>
                <label className="field-label">
                  Billing period ends
                  <input type="date" value={billing.endDate} min={billing.startDate || undefined} onChange={(event) => updateBilling("endDate", event.target.value)} required />
                </label>
              </div>
              {billing.startDate && billing.endDate && <p className="input-hint period-hint">Billing period: {formatDate(billing.startDate)} – {formatDate(billing.endDate)}. Analysis uses the separate sample period shown above.</p>}

              {billing.amount && !amountValid && <p className="validation-message" role="alert">Enter a bill amount greater than zero, up to ₹10,000,000.</p>}
              {billing.units && !unitsValid && <p className="validation-message" role="alert">Enter billed units greater than zero, up to 10,000,000 kWh.</p>}

              <label className="field-label tariff-field">
                Tariff structure
                <select value={billing.tariff} onChange={(event) => updateBilling("tariff", event.target.value as TariffStructure)}>
                  <option value="unknown">I’m not sure</option>
                  <option value="single_rate">Single / flat rate</option>
                  <option value="tiered">Tiered or time-of-use rates</option>
                  <option value="additional_charges">Includes fixed charges or taxes</option>
                </select>
                <small className="field-note">{tariffNotes[billing.tariff]}</small>
              </label>

              {!periodValid && billing.startDate && billing.endDate && (
                <p className="validation-message" role="alert">The billing period end date must be on or after the start date.</p>
              )}
              {analysisError && <p className="form-error" role="alert">{analysisError}</p>}

              <button className="primary-button" type="submit" disabled={!selectedSample || !billValid || !periodValid || submitting || Boolean(healthError) || !health?.ready}>
                {submitting ? "Analyzing…" : "Run analysis"}
              </button>
              {!selectedSample && <p className="form-footnote">No prepared sample is currently available.</p>}
            </form>
          </section>

          <section className="panel breakdown-panel" id="appliances" aria-labelledby="appliances-title">
              <div className="panel-heading breakdown-heading">
                <div><h2 id="appliances-title">Where the energy goes</h2><p>Estimated share of total sample energy</p></div>
                {analysis && <span className="breakdown-total">{formatKwh(analysis.summary.total_kwh_period)} total</span>}
              </div>
            {appliances.length > 0 ? (
              <div className="appliance-breakdown">
                {appliances.map((appliance) => (
                  <article className={`appliance-row ${appliance.id === leadingApplianceId ? "is-leading" : ""} ${appliance.provenance === "residual" ? "is-residual" : ""}`} key={appliance.id}>
                    <div className="appliance-row-top">
                      {appliance.provenance === "residual"
                        ? <strong className="appliance-name">{appliance.name}</strong>
                        : <button className="appliance-link" onClick={() => setSelectedApplianceId(appliance.id)}>{appliance.name}</button>}
                      <span className="appliance-share">{appliance.share_pct == null ? "—" : `${appliance.share_pct.toFixed(1)}%`}</span>
                    </div>
                    <div className="share-track" role="img" aria-label={`${appliance.share_pct == null ? "Unknown share" : `${appliance.share_pct.toFixed(1)} percent`} of estimated energy`}>
                      <span style={{ width: `${Math.max(0, Math.min(100, appliance.share_pct ?? 0))}%` }} />
                    </div>
                    <div className="appliance-row-values">
                      <span><small>Energy</small><strong>{formatKwh(appliance.kwh_period)}</strong></span>
                      <span><small>Estimated cost</small><strong>{formatCurrency(appliance.cost_period_inr)}</strong></span>
                      <span><small>Coverage</small><strong>{appliance.coverage_pct == null ? "—" : `${appliance.coverage_pct.toFixed(1)}%`}</strong></span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state breakdown-empty">
                <strong>No appliance estimates yet</strong>
                <p>Your sample breakdown will appear here after analysis.</p>
              </div>
            )}
            {analysis && <div className="panel-footnote">“Other” is included in the returned total; its appliance-level split is unavailable.</div>}
          </section>
        </div>

        <div className="lower-grid">
          <section className="panel insights-panel" id="insights" aria-labelledby="insights-title">
            <div className="panel-heading">
              <div>
                <h2 id="insights-title">Recommendations</h2>
              </div>
              {analysis && <span className="alert-status">{alertLabel(analysis.alert.status)}</span>}
            </div>
            {analysis?.issues.length ? (
              <div className="insight-list">
                {analysis.issues.map((issue) => (
                  <article className="insight-item" key={issue.appliance_id}>
                    <div className="insight-copy">
                      <div className="recommendation-topline">
                        <div><h3>{issue.appliance_name}</h3><p>{issue.driver_text ?? "The analysis identified an eligible change, but could not determine a usage driver."}</p></div>
                        <div className="recommendation-savings"><small>Potential / month</small><strong>{formatCurrency(issue.savings.inr_per_month.low)}–{formatCurrency(issue.savings.inr_per_month.high)}</strong></div>
                      </div>
                      <strong className="recommendation">{issue.recommendation.text}</strong>
                      <small className="savings-label">{issue.savings.label}; an estimate, not a guaranteed saving.</small>
                      {issue.caveats.map((caveat) => <small className="caveat" key={caveat}>{caveat}</small>)}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state insights-empty">
                <span className="empty-glyph" aria-hidden="true">✳</span>
                <strong>{analysis ? "No unusual use found." : "Recommendations appear after analysis"}</strong>
                {!analysis && <p>Run an analysis to see actions tied to this sample’s results.</p>}
              </div>
            )}
            {analysis?.issues.length ? <p className="assumption-note">Potential savings are estimates, not guaranteed outcomes.</p> : null}
          </section>

          <section className="panel history-panel" id="history" aria-labelledby="history-title">
            <div className="panel-heading">
              <div>
                <h2 id="history-title">History</h2>
              </div>
            </div>
            <div className="empty-state history-empty">
              <strong>No saved analyses</strong>
              <p>Analyses are not stored.</p>
            </div>
          </section>
        </div>

        {analysis && (
          <footer className="evidence-footer">
            <span>Analysis period: {formatDate(analysis.period.start)} – {formatDate(analysis.period.end)} ({analysis.period.days} days)</span>
            <span>Coverage: {analysis.period.coverage_pct.toFixed(1)}%</span>
          </footer>
        )}
      </main>

      {selectedAppliance && analysis && (
        <div className="detail-backdrop" onClick={() => setSelectedApplianceId(null)}>
          <section
            className="detail-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button className="drawer-close" type="button" aria-label="Close appliance details" onClick={() => setSelectedApplianceId(null)}>×</button>
            <h2 id="detail-title">{selectedAppliance.name}</h2>
            <div className="drawer-metrics">
              <div><small>Energy, analyzed period</small><strong>{formatKwh(selectedAppliance.kwh_period)}</strong></div>
              <div><small>Estimated cost</small><strong>{formatCurrency(selectedAppliance.cost_period_inr)}</strong></div>
              <div><small>Data coverage</small><strong>{selectedAppliance.coverage_pct == null ? "—" : `${selectedAppliance.coverage_pct.toFixed(1)}%`}</strong></div>
              <div><small>Usage status</small><strong>{selectedAppliance.status ?? "Not classified"}</strong></div>
            </div>
            <h3>Weekly comparison</h3>
            <div className="week-list">
              {(["baseline_1", "baseline_2", "current"] as const).map((week) => (
                <div key={week}>
                  <span>{week.replace("_", " ")}</span>
                  <strong>
                    {analysis.period.weeks[week].valid && selectedAppliance.weekly_kwh[week] != null
                      ? formatKwh(selectedAppliance.weekly_kwh[week])
                      : "Insufficient data"}
                  </strong>
                </div>
              ))}
            </div>
            {selectedAppliance.status_reason && <p className="detail-reason">Comparison unavailable: {selectedAppliance.status_reason.replaceAll("_", " ")}.</p>}
            <p className="ground-truth-note">Coverage indicates how much valid data was available for this appliance in the sample period.</p>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
