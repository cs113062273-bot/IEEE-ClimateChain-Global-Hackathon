export type Json = null | boolean | number | string | Json[] | {[key: string]: Json};
export type Scenario = {
  battery_capacity_kwh: number; solar_kwp: number;
  ev_jobs: {id: string; energy_kwh: number; arrival_slot: number; deadline_slot: number; max_kw: number}[];
  [key: string]: unknown;
};
export type Slot = {
  start_utc: string; end_utc: string; ci_forecast_g_per_kwh: number; ci_actual_g_per_kwh: number;
  fixed_load_kwh: number; pv_available_kwh: number; tariff_gbp_per_kwh: number;
  grid_import_kwh: number; battery_charge_kwh: number; battery_discharge_kwh: number;
  soc_start_kwh: number; soc_end_kwh: number; ev_charge_kwh: number; ev_by_job_kwh: number[];
  batch_load_kwh: number; pv_used_kwh: number; pv_curtail_kwh: number;
};
export type Plan = {
  policy: string; solver: {status: string; success: boolean; seconds: number; constraints_verified: boolean; message: string};
  constraints: {verified: boolean; violations: string[]; max_balance_residual_kwh: number; terminal_soc_delta_kwh: number};
  dispatch: Slot[];
  metrics: {emissions_kgco2: number; forecast_emissions_kgco2: number; cost_gbp: number; grid_import_kwh: number; pv_used_kwh: number; peak_grid_kw: number; workload_kwh: number};
  batch_starts: Record<string, number>;
};
export type Comparison = {
  run_id: string; date: string; carbon_weight: number; scenario: Scenario; intervals: Slot[];
  plans: Record<"immediate" | "cost_first" | "carbon_first" | "hybrid" | "oracle", Plan>;
  forecast_model: unknown; provenance_status: unknown; units: unknown; data_timestamp: string;
};
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST", cache: "no-store",
    headers: body === undefined ? undefined : {"Content-Type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(120000),
  });
  let result;
  try {result = await response.json();} catch {throw new Error(`Service returned HTTP ${response.status}. Start the local API and retry.`);}
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : result.error?.message ?? JSON.stringify(result.detail ?? result));
  return result as T;
}
export const number = (value: number | undefined, digits = 1) => Number.isFinite(value) ? value!.toLocaleString("en-GB", {minimumFractionDigits: digits, maximumFractionDigits: digits}) : "—";
export const clock = (iso: string) => iso.slice(11,16);
export function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:"application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}
