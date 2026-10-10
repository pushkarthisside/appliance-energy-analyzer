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

function applianceSourceLabel(provenance: string) {
  return provenance === "synthetic_trace" ? "Simulated trace" : "Model estimate";
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
  const periodValid =
    Boolean(billing.startDate) &&
    Boolean(billing.endDate) &&
    billing.startDate <= billing.endDate;
  const billValid =
    billing.amount !== "" &&
    billing.units !== "" &&
    Number.isFinite(amount) &&
    Number.isFinite(units) &&
    amount > 0 &&
    units > 0 &&
    amount <= 10_000_000 &&
    units <= 10_000_000;

  const appliances = useMemo(
    () =>
      (analysis?.appliances ?? [])
        .filter((appliance) => appliance.provenance !== "residual")
        .sort((left, right) => (right.kwh_period ?? -1) - (left.kwh_period ?? -1)),
    [analysis],
  );
  const maxApplianceKwh = Math.max(0, ...appliances.map((appliance) => appliance.kwh_period ?? 0));
  const selectedAppliance = appliances.find((appliance) => appliance.id === selectedApplianceId);
  const topOpportunity = analysis?.issues[0] ?? null;

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
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="Appliance Energy Analyzer overview">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M17.8 3.8 7 17h7.1l-.7 11.2L25 14.8h-7.3l.1-11Z" />
            </svg>
          </span>
          <span className="brand-copy">
            <strong>Appliance Energy</strong>
            <small>Analyzer</small>
          </span>
        </a>

        <nav className="primary-nav" aria-label="Dashboard sections">
          <a className="nav-link is-active" href="#overview"><span>01</span> Overview</a>
          <a className="nav-link" href="#appliances"><span>02</span> Appliances</a>
          <a className="nav-link" href="#insights"><span>03</span> Insights</a>
          <a className="nav-link" href="#history"><span>04</span> History</a>
        </nav>

        <div className="sidebar-note">
          <span className={`service-indicator ${health?.ready ? "is-online" : ""}`} />
          <div>
            <strong>{healthError ? "API unavailable" : health?.ready ? "Samples ready" : "Engine not ready"}</strong>
            <small>{health?.ready ? "Analysis service online" : "Waiting for sample pipeline"}</small>
          </div>
        </div>
        <p className="sidebar-footnote">Estimates from one meter signal. Results depend on data availability.</p>
      </aside>

      <main className="dashboard" id="overview">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Energy overview</div>
          <div className={`status-pill ${health?.ready ? "status-pill-ready" : ""}`}>
            <span /> {healthError ? "Connection issue" : health?.ready ? "Ready to analyze" : "Analysis unavailable"}
          </div>
        </header>

        <section className="page-heading">
          <div>
            <p className="eyebrow">Household energy, made clearer</p>
            <h1>Understand where your electricity goes.</h1>
            <p className="heading-copy">
              Review appliance estimates, costs, and possible next steps from a prepared meter sample.
            </p>
          </div>
          <div className="period-chip">
            <span className="period-icon" aria-hidden="true">◷</span>
            <span>{analysis ? `${formatDate(analysis.period.start)} – ${formatDate(analysis.period.end)}` : "21-day sample window"}</span>
          </div>
        </section>

        {(healthError || !health?.ready) && (
          <section className="readiness-banner" role="status">
            <div className="readiness-icon" aria-hidden="true">i</div>
            <div>
              <strong>{healthError ? "We couldn’t reach the analysis service" : "Analysis engine is getting ready"}</strong>
              <p>
                {healthError ?? "Prepared samples and the analysis pipeline are not available yet. This dashboard will show results only after the API reports a ready sample."}
              </p>
            </div>
            <span className="readiness-label">No results loaded</span>
          </section>
        )}

        {analysis?.source.simulated && (
          <section className="simulation-banner" role="status">
            <strong>Simulated demonstration</strong>
            <span>This sample contains synthetic data. It is not a real household appliance prediction.</span>
          </section>
        )}

        <section className="metrics-grid" aria-label="Energy overview">
          <article className="metric-card bill-metric">
            <div className="metric-heading"><span>Bill amount entered</span><span className="metric-icon">₹</span></div>
            <strong className="metric-value">{billing.amount ? formatCurrency(amount) : "—"}</strong>
            <p>{billing.startDate && billing.endDate ? `${formatDate(billing.startDate)} – ${formatDate(billing.endDate)}` : "Enter your billed amount and dates"}</p>
            {billing.units && <small>{billing.units} billed kWh</small>}
          </article>
          <article className="metric-card">
            <div className="metric-heading"><span>Estimated energy</span><span className="metric-icon icon-teal">ϟ</span></div>
            <strong className="metric-value">{formatKwh(analysis?.summary.total_kwh_period)}</strong>
            <p>{analysis ? "For the analyzed sample window" : "Available after sample analysis"}</p>
          </article>
          <article className="metric-card">
            <div className="metric-heading"><span>Estimated cost</span><span className="metric-icon icon-blue">≈</span></div>
            <strong className="metric-value">{formatCurrency(analysis?.summary.estimated_cost_period_inr)}</strong>
            <p>{analysis ? `Using ₹${analysis.cost.effective_rate_inr_per_kwh.toFixed(2)}/kWh blended rate` : "Calculated from estimates and bill inputs"}</p>
          </article>
          <article className="metric-card savings-metric">
            <div className="metric-heading"><span>Possible savings</span><span className="metric-icon icon-gold">↗</span></div>
            <strong className="metric-value savings-value">
              {topOpportunity
                ? `${formatCurrency(topOpportunity.savings.inr_per_month.low)}–${formatCurrency(topOpportunity.savings.inr_per_month.high)}`
                : "—"}
            </strong>
            <p>{topOpportunity ? "Monthly range for the top issue, not guaranteed" : "Shown only when supported by analysis"}</p>
          </article>
        </section>

        <div className="content-grid">
          <section className="panel bill-panel" aria-labelledby="bill-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Analysis setup</p>
                <h2 id="bill-title">Your bill & tariff</h2>
              </div>
              <span className="panel-step">01</span>
            </div>

            <form onSubmit={analyzeSample} className="bill-form">
              <fieldset>
                <legend>Choose a prepared sample</legend>
                <div className="sample-options">
                  {(["typical_period", "simulated_scenario"] as const).map((id) => {
                    const status = health?.samples.find((sample) => sample.id === id);
                    const available = status?.state === "ready";
                    return (
                      <label className={`sample-option ${sampleId === id ? "selected" : ""} ${!available ? "unavailable" : ""}`} key={id}>
                        <input
                          type="radio"
                          name="sample"
                          value={id}
                          checked={sampleId === id}
                          disabled={!available || submitting}
                          onChange={() => setSampleId(id)}
                        />
                        <span className="sample-option-copy">
                          <strong>{sampleTitles[id]}</strong>
                          <small>{id === "simulated_scenario" ? "Synthetic demonstration" : "Real-data sample, when a model passes evaluation"}</small>
                          <em>{status ? (available ? "Available" : "Not ready") : health ? "Not available" : "Checking availability"}</em>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className="form-section-label">Billed details</div>
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

              <button className="primary-button" type="submit" disabled={!selectedSample || !billValid || !periodValid || submitting}>
                {submitting ? "Analyzing sample…" : "Analyze selected sample"}
                <span aria-hidden="true">→</span>
              </button>
              {!selectedSample && <p className="form-footnote">Analysis is disabled until a prepared sample is ready.</p>}
            </form>
          </section>

          <section className="panel breakdown-panel" id="appliances" aria-labelledby="appliances-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Estimated from aggregate meter data</p>
                <h2 id="appliances-title">Appliance breakdown</h2>
              </div>
              {analysis && <span className="appliance-count">{appliances.length} monitored</span>}
            </div>
            {appliances.length > 0 ? (
              <div className="appliance-list">
                {appliances.map((appliance, index) => {
                  const barWidth = maxApplianceKwh > 0 && appliance.kwh_period != null
                    ? Math.max(2, (appliance.kwh_period / maxApplianceKwh) * 100)
                    : 0;
                  return (
                    <button className="appliance-row" key={appliance.id} onClick={() => setSelectedApplianceId(appliance.id)}>
                      <span className="appliance-rank">{String(index + 1).padStart(2, "0")}</span>
                      <span className="appliance-main">
                        <span className="appliance-name-line">
                          <strong>{appliance.name}</strong>
                          <small className={appliance.provenance === "synthetic_trace" ? "source-tag simulated-tag" : "source-tag"}>
                            {applianceSourceLabel(appliance.provenance)}
                          </small>
                        </span>
                        <span className="energy-track"><span style={{ width: `${barWidth}%` }} /></span>
                      </span>
                      <span className="appliance-energy">{formatKwh(appliance.kwh_period)}</span>
                      <span className="appliance-cost">{formatCurrency(appliance.cost_period_inr)}</span>
                      <span className="row-arrow" aria-hidden="true">↗</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state breakdown-empty">
                <span className="empty-glyph" aria-hidden="true">⌁</span>
                <strong>No appliance estimates yet</strong>
                <p>When a sample and analysis pipeline are ready, supported appliances will appear here ranked by estimated energy use.</p>
                <small>Appliance-level ground truth is not available from the aggregate meter alone.</small>
              </div>
            )}
            <div className="panel-footnote">
              <span>ⓘ</span> Appliance energy and cost are estimates, not independent meter readings.
            </div>
          </section>
        </div>

        <div className="lower-grid">
          <section className="panel insights-panel" id="insights" aria-labelledby="insights-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Explainable next steps</p>
                <h2 id="insights-title">Insights & alerts</h2>
              </div>
              {analysis && <span className="alert-status">{alertLabel(analysis.alert.status)}</span>}
            </div>
            {analysis?.issues.length ? (
              <div className="insight-list">
                {analysis.issues.map((issue) => (
                  <article className="insight-item" key={issue.appliance_id}>
                    <div className="insight-index">{String(issue.rank).padStart(2, "0")}</div>
                    <div className="insight-copy">
                      <div className="insight-title-line">
                        <h3>{issue.appliance_name}</h3>
                        <span className={issue.basis === "synthetic_trace" ? "source-tag simulated-tag" : "source-tag"}>
                          {issue.basis === "synthetic_trace" ? "Simulated" : "Model-based"}
                        </span>
                      </div>
                      <p>{issue.driver_text ?? "The analysis identified an eligible change, but could not determine a usage driver."}</p>
                      <strong className="recommendation">{issue.recommendation.text}</strong>
                      <div className="savings-assumption">
                        <span>{issue.savings.label}</span>
                        <strong>{formatCurrency(issue.savings.inr_per_month.low)}–{formatCurrency(issue.savings.inr_per_month.high)} / month</strong>
                      </div>
                      {issue.caveats.map((caveat) => <small className="caveat" key={caveat}>{caveat}</small>)}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state insights-empty">
                <span className="empty-glyph" aria-hidden="true">✳</span>
                <strong>{analysis ? "No eligible recommendations" : "Insights appear after analysis"}</strong>
                <p>{analysis ? "No unusual-use recommendation was returned for this sample." : "Recommendations and alert status will be shown only when supported by an API analysis result."}</p>
              </div>
            )}
            <p className="assumption-note">Possible savings are hypothetical estimates based on the recent-use baseline. They are not guaranteed or measured.</p>
          </section>

          <section className="panel history-panel" id="history" aria-labelledby="history-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Monthly comparison</p>
                <h2 id="history-title">History</h2>
              </div>
            </div>
            <div className="empty-state history-empty">
              <span className="history-symbol" aria-hidden="true">↻</span>
              <strong>No saved months</strong>
              <p>Analyses and bills are not stored in this MVP. Monthly comparisons will appear only when supported historical data is available.</p>
            </div>
          </section>
        </div>

        {analysis && (
          <footer className="evidence-footer">
            <span>Analysis period: {formatDate(analysis.period.start)} – {formatDate(analysis.period.end)} ({analysis.period.days} days)</span>
            <span>Evidence: {analysis.source.evidence_level ?? "not available"}</span>
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
            <p className="eyebrow">Appliance estimate</p>
            <h2 id="detail-title">{selectedAppliance.name}</h2>
            <span className={selectedAppliance.provenance === "synthetic_trace" ? "source-tag simulated-tag" : "source-tag"}>
              {applianceSourceLabel(selectedAppliance.provenance)}
            </span>
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
            <p className="ground-truth-note">These figures are estimates from aggregate meter data. Independent appliance-level ground truth is unavailable in this result. A confidence interval is not provided by the current API contract.</p>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
