export interface Trigger {
  trigger_id: string;
  type: string;
  check_cadence?: string;
  next_check_date?: string;
  date?: string;
  on_match?: string;
  workflow?: string;
  source_path?: string;
  date_status?: string;
}

export interface Correction {
  original_claim: string;
  correction: string;
}

export interface Candidate {
  run_id: string;
  ticker: string;
  state: string;
  bucket: string | null;
  setup: string;
  variant_wedge: string;
  first_rejection: string;
  suggested_workflow: string | null;
  next_workflow: string | null;
  target_workflow: string | null;
  triggers: Trigger[];
  manual_review_date: string | null;
  status_reason: string | null;
  completed_workflows: string[];
  corrections: Correction[];
  last_event_at: string;
}

export interface NextItem {
  work_item_id?: string;
  run_id: string;
  ticker: string;
  bucket: string | null;
  workflow: string;
  requested_workflow: string;
  reason: string;
  action: "prepare" | "attach_result";
  artifact_dir?: string;
  required_context_artifacts?: string[];
}

export interface RunSummary {
  run_id: string;
  state: string;
  artifact_dir: string | null;
  tickers: string[];
  result_path: string | null;
  last_event_at: string | null;
}

export interface StatusPayload {
  event_count: number;
  last_event_at: string | null;
  candidates: Candidate[];
  next: NextItem[];
  runs: RunSummary[];
}

export interface ValidationReport {
  status: "valid" | "valid_with_review" | "rejected";
  [key: string]: unknown;
}

export interface WorkflowArtifact {
  role: string;
  path: string;
  sha256: string;
}

export interface WorkflowEvent {
  schema_version: number;
  event_id: string;
  event_type: string;
  recorded_at: string;
  run_id: string;
  ticker: string | null;
  source_artifacts: WorkflowArtifact[];
  payload: Record<string, unknown>;
}

export interface EventsPayload {
  events: WorkflowEvent[];
  total: number;
}

export interface CatalogWorkflow {
  pack_step: string | null;
  required_workflows: string[];
  allowed_next: string[];
  result_contract: string;
}

export interface CatalogPayload {
  schema_version: number;
  workflows: Record<string, CatalogWorkflow>;
}

export interface ThesisEntry {
  ticker: string;
  thesis_id: string;
  file: string;
  records: Record<string, unknown>[];
}

export interface ThesisPayload {
  theses: ThesisEntry[];
}

export interface PortfolioPosition {
  ticker: string;
  shares: number;
  avg_cost: number;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  target_price?: number | null;
  stop_loss?: number | null;
  position_type?: "Long" | "Short";
  conviction?: "High" | "Medium" | "Low";
  notes?: string;
  updated_at?: string;
}

export interface PortfolioPayload {
  schema_version: number;
  updated_at: string | null;
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions: PortfolioPosition[];
}

export interface WatchlistItem {
  ticker: string;
  current_price?: number | null;
  target_entry?: number | null;
  distance_to_target_pct?: number | null;
  priority?: "A" | "B" | "C";
  catalyst?: string;
  watch_reason?: string;
  alert_condition?: string;
  added_at?: string;
  updated_at?: string;
}

export interface WatchlistPayload {
  schema_version: number;
  updated_at: string | null;
  total_items: number;
  items: WatchlistItem[];
}

export interface UniverseMember {
  ticker: string;
  name: string;
  exchange: string;
  sector: string;
}

export interface UniversePayload {
  members: UniverseMember[];
}

