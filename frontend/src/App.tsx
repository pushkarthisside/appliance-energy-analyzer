import { useEffect, useMemo, useState } from "react";

import type {
  AnalysisResponse,
  ApiErrorResponse,
  EvaluationArtifact,
  EvaluationMetrics,
  HealthResponse,
  SampleAnalysisRequest,
} from "./types";

type BillingDetails = {
  amount: string;
  units: string;
  startDate: string;
  endDate: string;
};

const sampleTitles = {
  typical_period: "Typical period",
  simulated_scenario: "Simulated scenario",
} as const;

const initialBilling: BillingDetails = {
  amount: "",
  units: "",
  startDate: "",
  endDate: "",
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

function evidenceSummary(level: AnalysisResponse["source"]["evidence_level"]) {
  if (level === "independent_test") {
    return "Real-model estimates were evaluated on held-out weeks from the same household.";
  }
  if (level === "development_only") {
    return "Real-model estimates were checked on held-out development weeks; this is not independent validation.";
  }
  return "No real-data appliance model has been validated for this sample.";
}

function issueBasisLabel(basis: AnalysisResponse["issues"][number]["basis"]) {
  if (basis === "real_model") return "Finding based on a real-model estimate";
  return "Finding based on simulated appliance data";
}

function applianceStatusLabel(status: AnalysisResponse["appliances"][number]["status"], residual: boolean) {
  if (residual) return "Not itemized";
  if (status === "unusual") return "Unusual vs baseline";
  if (status === "typical") return "Within baseline";
  if (status === "insufficient_data") return "Insufficient data";
  return "Status unavailable";
}

function formatDate(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function formatPeriodEnd(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.valueOf())) return value;
  date.setDate(date.getDate() - 1);
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
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

function evidenceLevelLabel(level: EvaluationArtifact["evidence_level"]) {
  if (level === "independent_test") return "Independent test weeks";
  if (level === "development_only") return "Development-only evidence";
  return "No real-model evaluation evidence";
}

function metricValue(value: number | null | undefined, suffix = "") {
  return value == null || !Number.isFinite(value) ? "Unavailable" : `${value.toFixed(2)}${suffix}`;
}

function applianceSourceLabel(provenance: AnalysisResponse["appliances"][number]["provenance"]) {
  if (provenance === "real_model") return "Real appliance model estimate";
  if (provenance === "synthetic_trace") return "Prepared synthetic appliance trace";
  return "Unitemized remainder";
}

function EvaluationMetricsTable({ model, naive }: { model: EvaluationMetrics; naive: EvaluationMetrics }) {
  const rows = [
    ["Mean absolute error", metricValue(model.mae_w, " W"), metricValue(naive.mae_w, " W")],
    ["Weekly energy error (median)", metricValue(model.weekly_energy_error_pct?.median, "%"), metricValue(naive.weekly_energy_error_pct?.median, "%")],
    ["Weekly energy error (worst)", metricValue(model.weekly_energy_error_pct?.worst, "%"), metricValue(naive.weekly_energy_error_pct?.worst, "%")],
    ["On/off F1", metricValue(model.onoff_f1), metricValue(naive.onoff_f1)],
    ["Coverage", metricValue(model.coverage_pct, "%"), "Not recorded"],
  ];
  return (
    <div className="evaluation-table-wrap">
      <table className="evaluation-table">
        <thead><tr><th scope="col">Metric</th><th scope="col">Model</th><th scope="col">Naive baseline</th></tr></thead>
        <tbody>{rows.map(([label, modelValue, naiveValue]) => <tr key={label}><th scope="row">{label}</th><td>{modelValue}</td><td>{naiveValue}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationArtifact | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(true);
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

  useEffect(() => {
    let active = true;
    fetch("/api/evaluation")
      .then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) {
          const apiError = payload as ApiErrorResponse;
          throw new Error(apiError.error?.message ?? `Evaluation request failed (${response.status}).`);
        }
        if (active) setEvaluation(payload as EvaluationArtifact);
      })
      .catch((requestError: unknown) => {
        if (active) setEvaluationError(requestError instanceof Error ? requestError.message : "Evaluation evidence could not be loaded.");
      })
      .finally(() => { if (active) setEvaluationLoading(false); });
    return () => { active = false; };
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
        .sort((left, right) => (right.kwh_period ?? -1) - (left.kwh_period ?? -1)),
    [analysis],
  );
  const selectedAppliance = appliances.find((appliance) => appliance.id === selectedApplianceId);
  const topOpportunity = analysis?.issues[0] ?? null;
  const leadingApplianceId = analysis?.summary.largest_monitored_appliance_id;
  const leadingAppliance = appliances.find((appliance) => appliance.id === leadingApplianceId);

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
          {analysis && (
            <div className="period-chip" aria-label="Periods used in this analysis">
              <div className="period-chip-group"><span>Prepared sample dates</span><strong>{formatDate(analysis.period.start)} – {formatPeriodEnd(analysis.period.end)}</strong></div>
              <div className="period-chip-group"><span>Your bill dates</span><strong>{formatDate(billing.startDate)} – {formatDate(billing.endDate)}</strong></div>
            </div>
          )}
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
            <strong>Simulated demonstration</strong>
            <span>Prepared synthetic data, not household measurements. Appliance use and savings are estimates.</span>
          </section>
        )}
        {analysis && !analysis.source.simulated && (
          <section className="evidence-banner" role="status">
            {evidenceSummary(analysis.source.evidence_level)}
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
              <span className="summary-label">Sample-period cost</span>
              <strong>{formatCurrency(analysis?.summary.estimated_cost_period_inr)}</strong>
              <small>{analysis ? `${analysis.period.days}-day sample at ₹${analysis.cost.effective_rate_inr_per_kwh.toFixed(2)}/kWh. Not your bill total.` : "Sample estimate at your bill's blended rate"}</small>
            </article>
            <article className="summary-item">
              <span className="summary-label">Largest appliance</span>
              <strong className="summary-name">{leadingAppliance?.name ?? "—"}</strong>
              <small>{leadingAppliance?.share_pct != null ? `${leadingAppliance.share_pct.toFixed(1)}% of sample energy` : "Share shown after analysis"}</small>
            </article>
            <article className="summary-item">
              <span className="summary-label">Potential monthly savings</span>
              <strong>{topOpportunity ? `${formatCurrency(topOpportunity.savings.inr_per_month.low)}–${formatCurrency(topOpportunity.savings.inr_per_month.high)}` : "—"}</strong>
              <small>{topOpportunity ? "Top finding estimate if use returns to baseline" : "Shown when recommendations support it"}</small>
            </article>
          </div>
        </section>

        <div className="content-grid">
          <section className="panel bill-panel" aria-labelledby="bill-title">
            <div className="panel-heading"><h2 id="bill-title">Your electricity bill</h2></div>

            <form onSubmit={analyzeSample} className="bill-form" aria-busy={submitting}>
              <fieldset>
                <legend>Appliance data</legend>
                <p className="input-hint sample-hint">Choose a prepared period to explore. Appliance estimates use its fixed dates; your bill dates below are for reference.</p>
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
                          <small>{id === "simulated_scenario" ? "Synthetic scenario; not household measurements" : "Prepared appliance analysis data"}</small>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className="form-section-label">Bill details</div>
              <p className="input-hint">Your bill amount and units set the blended cost rate used for appliance estimates.</p>
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
              <p className="input-hint period-hint">Your bill dates are for context. The prepared sample’s dates determine which appliance data is analyzed.</p>

              {billing.amount && !amountValid && <p className="validation-message" role="alert">Enter a bill amount greater than zero, up to ₹10,000,000.</p>}
              {billing.units && !unitsValid && <p className="validation-message" role="alert">Enter billed units greater than zero, up to 10,000,000 kWh.</p>}

              {!periodValid && billing.startDate && billing.endDate && (
                <p className="validation-message" role="alert">The billing period end date must be on or after the start date.</p>
              )}
              {analysisError && <p className="form-error" role="alert">{analysisError}</p>}

              <button className="primary-button" type="submit" disabled={!selectedSample || !billValid || !periodValid || submitting || Boolean(healthError) || !health?.ready}>
                {submitting ? "Analyzing sample…" : "Run analysis"}
              </button>
              {!selectedSample && <p className="form-footnote">No prepared sample is currently available.</p>}
            </form>
          </section>

          <section className="panel breakdown-panel" id="appliances" aria-labelledby="appliances-title">
              <div className="panel-heading breakdown-heading">
                <div><h2 id="appliances-title">Where the energy goes</h2><p>Estimated cost contribution and share of sample energy</p></div>
                {analysis && <span className="breakdown-total">{formatKwh(analysis.summary.total_kwh_period)} total</span>}
              </div>
            {appliances.length > 0 ? (
              <div className="appliance-breakdown">
                {appliances.map((appliance) => (
                  <article className={`appliance-row ${appliance.id === leadingApplianceId ? "is-leading" : ""} ${appliance.provenance === "residual" ? "is-residual" : ""}`} key={appliance.id}>
                    <div className="appliance-row-top">
                      <div className="appliance-title">
                        {appliance.provenance === "residual"
                          ? <strong className="appliance-name">{appliance.name} (not itemized)</strong>
                          : <button className="appliance-link" onClick={() => setSelectedApplianceId(appliance.id)}>{appliance.name}</button>}
                        {appliance.id === leadingApplianceId && <span className="largest-marker">Largest estimated load</span>}
                        <span className={`appliance-status status-${appliance.status ?? "none"}`}>{applianceStatusLabel(appliance.status, appliance.provenance === "residual")}</span>
                      </div>
                      <span className="appliance-share">{appliance.share_pct == null ? "—" : `${appliance.share_pct.toFixed(1)}%`}</span>
                    </div>
                    <div className="share-track" role="img" aria-label={`${appliance.share_pct == null ? "Unknown share" : `${appliance.share_pct.toFixed(1)} percent`} of estimated energy`}>
                      <span style={{ width: `${Math.max(0, Math.min(100, appliance.share_pct ?? 0))}%` }} />
                    </div>
                    <div className="appliance-row-values">
                      <span><small>Energy</small><strong>{formatKwh(appliance.kwh_period)}</strong></span>
                      <span><small>Estimated cost contribution</small><strong>{formatCurrency(appliance.cost_period_inr)}</strong></span>
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
                {analysis.issues.map((issue) => {
                  const comparisonMax = Math.max(issue.current_kwh, issue.baseline_kwh, 0.01);
                  return <article className="insight-item" key={issue.appliance_id}>
                    <div className="insight-copy">
                      <div className="recommendation-topline">
                        <div><h3>{issue.appliance_name}</h3><p>{issue.driver_text ?? "Usage increased, but the available data could not identify a likely driver."}</p><small className="issue-basis">{issueBasisLabel(issue.basis)}</small></div>
                        <div className="recommendation-savings">
                          <small>Possible monthly savings</small>
                          <div className="savings-range">
                            <span><small>Low</small><strong>{formatCurrency(issue.savings.inr_per_month.low)}</strong></span>
                            <span><small>Mid</small><strong>{formatCurrency(issue.savings.inr_per_month.mid)}</strong></span>
                            <span><small>High</small><strong>{formatCurrency(issue.savings.inr_per_month.high)}</strong></span>
                          </div>
                        </div>
                      </div>
                      <div className="issue-comparison" aria-label={`Estimated weekly usage comparison for ${issue.appliance_name}`}>
                        <span className="comparison-unit">Estimated weekly energy (kWh)</span>
                        <div className="usage-compare-bars">
                          <div className="usage-compare-row"><span>Prior two-week baseline</span><strong>{formatKwh(issue.baseline_kwh)}</strong><div className="usage-bar"><span style={{ width: `${(issue.baseline_kwh / comparisonMax) * 100}%` }} /></div></div>
                          <div className="usage-compare-row current"><span>Current week</span><strong>{formatKwh(issue.current_kwh)}</strong><div className="usage-bar"><span style={{ width: `${(issue.current_kwh / comparisonMax) * 100}%` }} /></div></div>
                        </div>
                        <small className="comparison-scale-note">Bars are scaled to the higher estimate in this comparison.</small>
                        <div className="comparison-deltas">
                          <div><small>Above baseline</small><strong>+{formatKwh(issue.excess_kwh_week)}</strong></div>
                          <div><small>Change</small><strong>+{issue.change_pct.toFixed(1)}%</strong></div>
                        </div>
                      </div>
                      <strong className="recommendation">{issue.recommendation.text}</strong>
                      <small className="savings-label">{issue.savings.label}. {issue.savings.illustrative ? "Illustrative estimate; not a real-model result or guaranteed saving." : "Estimate, not a guaranteed saving."}</small>
                      {issue.caveats.map((caveat) => <small className="caveat" key={caveat}>{caveat}</small>)}
                    </div>
                  </article>;
                })}
              </div>
            ) : (
              <div className="empty-state insights-empty">
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

        <section className="evidence-section" aria-label="Evidence and methodology">
          <details className="evidence-disclosure">
            <summary>
              <span>Data & methodology</span>
              <small>{analysis ? `${analysis.period.days}-day sample · bill rate · weekly comparison` : "How this analysis is calculated"}</small>
            </summary>
            <div className="evidence-content">
              <div className="method-grid">
                <article>
                  <h3>Analysis period</h3>
                  <p>{analysis
                    ? `${analysis.period.days} days, split into two baseline weeks and one current week (${formatDate(analysis.period.start)} to ${formatPeriodEnd(analysis.period.end)}). The window uses full local days in Asia/Kolkata. Prepared sample dates set it; bill dates are reference only.`
                    : "The prepared analysis uses a fixed 21-day window: two baseline weeks followed by one current week, using full local days in Asia/Kolkata. Prepared sample dates set it; bill dates are reference only."}</p>
                </article>
                <article>
                  <h3>Bill rate and sample cost</h3>
                  <p>{analysis
                    ? `The bill amount (${formatCurrency(analysis.cost.bill_amount_inr)}) divided by billed units (${analysis.cost.bill_units_kwh.toLocaleString("en-IN")} kWh) gives an average rate of ₹${analysis.cost.effective_rate_inr_per_kwh.toFixed(2)}/kWh. Sample-period cost is estimated kWh × that rate, so it is not the bill total.`
                    : "Your bill amount divided by billed units gives an average ₹/kWh rate. Estimated sample-period cost is sample kWh × that rate, not your bill total."} Fixed charges and tariff slabs are spread into this blended average; actual marginal cost can differ.</p>
                </article>
                <article>
                  <h3>Where appliance traces come from</h3>
                  {analysis ? <>
                    <p>This prepared sample is {analysis.source.simulated ? "marked as simulated" : "marked as non-simulated"} by the analysis API. Appliance-level sources:</p>
                    <ul className="source-list">{analysis.appliances.filter((appliance) => appliance.provenance !== "residual").map((appliance) => <li key={appliance.id}><strong>{appliance.name}</strong><span>{applianceSourceLabel(appliance.provenance)}</span></li>)}</ul>
                    {analysis.appliances.some((appliance) => appliance.provenance === "residual") && <p>The remaining aggregate energy is grouped as “Other” because it is not itemized by an appliance.</p>}
                    {analysis.source.simulated && <p className="method-callout">{analysis.source.description} Its appliance traces are not model predictions or household measurements.</p>}
                  </> : <p>Prepared samples disclose their source here after analysis. Simulated traces are demonstration data, not household measurements or real-model predictions.</p>}
                </article>
                <article>
                  <h3>How unusual use is flagged</h3>
                  <p>The current week is compared with the median of the two preceding weeks for that appliance. A flag requires the increase to clear a threshold based on the appliance’s stated energy-estimation uncertainty and a minimum excess amount. Weeks without enough valid data, or with a very small baseline, are marked insufficient instead.</p>
                  <p>Weather, season, occupancy, and holidays are not modeled. An unusual-use flag is a comparison with recent usage, not a diagnosis.</p>
                </article>
                <article>
                  <h3>Possible savings</h3>
                  <p>When shown, the range estimates possible savings if use returned to the recent baseline. It is a heuristic sensitivity range, not a calibrated confidence interval or a guarantee.</p>
                </article>
              </div>
            </div>
          </details>

          <details className="evidence-disclosure evaluation-disclosure">
            <summary>
              <span>Model evaluation evidence</span>
              <small>{evaluationLoading ? "Loading evaluation record" : evaluationError ? "Evidence unavailable" : evaluation ? evidenceLevelLabel(evaluation.evidence_level) : "Evidence unavailable"}</small>
            </summary>
            <div className="evidence-content">
              {evaluationLoading && <p className="evidence-state" role="status">Loading the evaluation record…</p>}
              {!evaluationLoading && evaluationError && <div className="evidence-state evidence-error" role="status"><strong>Evaluation evidence unavailable</strong><p>{evaluationError}</p></div>}
              {!evaluationLoading && evaluation && <>
                <div className="evaluation-overview">
                  <div><span>Evidence level</span><strong>{evidenceLevelLabel(evaluation.evidence_level)}</strong></div>
                  <div><span>Dataset</span><strong>{evaluation.dataset.name}</strong></div>
                  <div><span>Generated</span><strong>{formatDate(evaluation.generated_at)}</strong></div>
                </div>
                {evaluation.dataset.audit_ref && <p className="evaluation-note">Dataset audit: {evaluation.dataset.audit_ref}</p>}
                {evaluation.evidence_level === "none" && <div className="evidence-state"><strong>No real-data appliance model has been validated.</strong><p>{evaluation.no_evaluation_reason ?? "The artifact does not include a reason for the missing evaluation."}</p></div>}
                {evaluation.evidence_level === "development_only" && <p className="evidence-state">Real-model results use development evidence only. They are not independent validation.</p>}
                {evaluation.evidence_level === "independent_test" && <p className="evidence-state">Any GO results below were evaluated on held-out weeks from the same household. This does not establish performance in other homes.</p>}

                <h3 className="evidence-subheading">Real-model candidates and decisions</h3>
                {(health?.appliances ?? []).filter((item) => item.provenance === "real_model").length === 0 && Object.keys(evaluation.real).length === 0 && <p className="evaluation-note">No real-model candidates or evaluation records are listed by the available API responses.</p>}
                {(health?.appliances ?? []).filter((item) => item.provenance === "real_model").map((item) => {
                  const result = evaluation.real[item.id];
                  const displayName = item.id.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
                  const status = result?.decision === "go"
                    ? "Passed frozen GO criteria"
                    : result?.decision === "no_go"
                      ? "Evaluated · did not pass frozen GO criteria"
                      : item.registry_status === "candidate"
                        ? "Candidate · no GO decision recorded"
                        : item.registry_status === "go"
                          ? "Registry says GO · matching evaluation record unavailable"
                          : "No GO decision recorded";
                  return <article className="candidate-evidence" key={item.id}>
                    <div className="candidate-heading"><strong>{displayName}</strong><span>{status}</span></div>
                    {result ? <>
                      <p className="evaluation-note">Evaluation split: {result.evaluated_on ?? "Unavailable"}; weeks recorded: {result.n_weeks ?? "Unavailable"}. Decision: {result.decision === "go" ? "GO" : "NO-GO"}.</p>
                      {result.failed_criteria.length > 0 && <p className="evaluation-note">Failed criteria: {result.failed_criteria.join(", ")}</p>}
                      <EvaluationMetricsTable model={result.model} naive={result.naive} />
                    </> : <p className="evaluation-note">{item.registry_status === "candidate" ? "This registry candidate has not passed evaluation; no evaluation metrics are recorded." : "The evaluation artifact has no detailed record for this registry entry."}</p>}
                  </article>;
                })}
                {Object.entries(evaluation.real).filter(([id]) => !(health?.appliances ?? []).some((item) => item.id === id)).map(([id, result]) => <article className="candidate-evidence" key={id}>
                  <div className="candidate-heading"><strong>{id.replaceAll("_", " ")}</strong><span>{result.decision === "go" ? "Passed frozen GO criteria" : "Evaluated · did not pass frozen GO criteria"}</span></div>
                  <EvaluationMetricsTable model={result.model} naive={result.naive} />
                </article>)}

                <h3 className="evidence-subheading">Synthetic demo pipeline checks</h3>
                <p className="evaluation-note">These checks verify expected statuses in the simulated demo pipeline. They are not real-model accuracy or evaluation results.</p>
                {evaluation.synthetic.pipeline_checks.length ? <ul className="pipeline-checks">{evaluation.synthetic.pipeline_checks.map((check, index) => <li key={`${check.sample_id}-${check.appliance_id}-${index}`}><strong>{check.appliance_id.replaceAll("_", " ")}</strong><span>{check.sample_id.replaceAll("_", " ")}: expected {check.expected_status}, observed {check.observed_status}</span></li>)}</ul> : <p className="evaluation-note">No synthetic pipeline checks are recorded.</p>}
              </>}
            </div>
          </details>
        </section>

        {analysis && (
          <footer className="evidence-footer">
            <span>Analysis period: {formatDate(analysis.period.start)} – {formatPeriodEnd(analysis.period.end)} ({analysis.period.days} days)</span>
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
