export type HealthResponse = {
  status: "ok" | "degraded" | "not_ready";
  ready: boolean;
  samples: { id: "typical_period" | "simulated_scenario"; state: "ready" | "failed"; detail: string | null }[];
  appliances: {
    id: string;
    provenance: "real_model" | "synthetic_trace";
    registry_status: "go" | "no_go" | "candidate" | "demo";
    runtime_state: "loaded" | "load_failed" | "inactive";
    detail: string | null;
  }[];
};

export type EvaluationArtifact = {
  schema_version: number;
  generated_at: string;
  code_version: string;
  criteria_sha256: string;
  dataset: { name: string; audit_ref: string | null };
  evidence_level: "independent_test" | "development_only" | "none";
  no_evaluation_reason: string | null;
  splits: {
    gap_days: number;
    gap_dates: string[];
    train: { weeks: number; start: string | null; end: string | null } | null;
    validation: { weeks: number; start: string | null; end: string | null } | null;
    test: { weeks: number; start: string | null; end: string | null } | null;
  };
  real: Record<string, {
    decision: "go" | "no_go";
    failed_criteria: string[];
    evaluated_on: "test" | "validation" | null;
    n_weeks: number | null;
    model_version: string | null;
    test_reused: boolean | null;
    model: EvaluationMetrics;
    naive: EvaluationMetrics;
    weekly?: { week_start: string; actual_kwh: number; model_kwh: number; naive_kwh: number }[];
    example_day?: { date: string; rule: string; t: unknown[]; aggregate_w: unknown[]; actual_w: unknown[]; model_w: unknown[] } | null;
  }>;
  scenario_checks: {
    appliance_id: string;
    evaluated_on: string;
    injection: Record<string, unknown>;
    current_week_status: string;
    detected: boolean;
  }[];
  unmodified_window_check: { go_appliances_checked: number; unusual_flags: number };
  synthetic: {
    pipeline_checks: { sample_id: string; appliance_id: string; expected_status: string; observed_status: string }[];
  };
};

export type EvaluationMetrics = {
  mae_w?: number | null;
  weekly_energy_error_pct?: { median: number | null; worst: number | null } | null;
  onoff_f1?: number | null;
  coverage_pct?: number | null;
};

export type SampleAnalysisRequest = {
  sample_id: string;
  bill: { amount_inr: number; units_kwh: number };
};

export type ApiErrorResponse = {
  error: { code: string; message: string; details: unknown };
};

export type AnalysisResponse = {
  analysis_id: string;
  generated_at: string;
  source: {
    kind: "sample";
    sample_id: "typical_period" | "simulated_scenario";
    title: string;
    description: string;
    simulated: boolean;
    simulated_appliance_ids: string[];
    evidence_level: "independent_test" | "development_only" | "none" | null;
    validated_domain: boolean;
  };
  period: {
    start: string;
    end: string;
    days: number;
    coverage_pct: number;
    weeks: Record<"baseline_1" | "baseline_2" | "current", {
      start: string;
      end: string;
      valid: boolean;
      coverage_pct: number;
    }>;
  };
  cost: {
    bill_amount_inr: number;
    bill_units_kwh: number;
    effective_rate_inr_per_kwh: number;
  };
  summary: {
    total_kwh_period: number | null;
    estimated_cost_period_inr: number | null;
    monitored_count: number;
    largest_monitored_appliance_id: string | null;
    issues_count: number;
  };
  appliances: {
    id: string;
    name: string;
    provenance: "real_model" | "synthetic_trace" | "residual";
    kwh_period: number | null;
    cost_period_inr: number | null;
    share_pct: number | null;
    coverage_pct: number | null;
    weekly_kwh: Record<"baseline_1" | "baseline_2" | "current", number | null>;
    status: "typical" | "unusual" | "insufficient_data" | null;
    status_reason: "current_week_invalid" | "baseline_week_invalid" | "baseline_too_small" | null;
    daily_kwh: { date: string; kwh: number | null }[];
  }[];
  issues: {
    rank: number;
    appliance_id: string;
    appliance_name: string;
    basis: "real_model" | "synthetic_trace" | "simulated_scenario";
    current_kwh: number;
    baseline_kwh: number;
    excess_kwh_week: number;
    change_pct: number;
    threshold_pct: number;
    driver: "longer_operating_time" | "higher_power_when_on" | "unclear" | null;
    driver_text: string | null;
    caveats: string[];
    recommendation: { action_id: string; text: string };
    savings: {
      label: string;
      illustrative: boolean;
      kwh_per_month: { low: number; mid: number; high: number };
      inr_per_month: { low: number; mid: number; high: number };
      kg_co2e_per_month: { low: number; mid: number; high: number } | null;
    };
  }[];
  signals: {
    window: "current_week";
    start: string;
    step_minutes: number;
    aggregate_w: (number | null)[];
    by_appliance: Record<string, (number | null)[]>;
  };
  emissions: {
    factor_kg_co2e_per_kwh: number;
    source_name: string;
    source_url: string;
    edition: string;
    publication_year: number;
    geography: string;
    retrieved_on: string;
    verified_by: string;
  } | null;
  warnings: { code: "bill_rate_unusual" | "appliance_unavailable"; message: string }[];
  alert: { status: "sent" | "failed" | "disabled" | "no_issues" | "cooldown" };
};
