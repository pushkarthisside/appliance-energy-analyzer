export type HealthResponse = {
  status: "ok" | "degraded" | "not_ready";
  ready: boolean;
  samples: { id: "typical_period" | "simulated_scenario"; state: "ready" | "failed"; detail: string | null }[];
};
