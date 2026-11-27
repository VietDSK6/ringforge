// Kiểu dữ liệu của API RingForge (khớp services/api). Tiền luôn là số nguyên VNĐ.

export type Decision = "ALLOW" | "MONITOR" | "HOLD" | "BLOCK";
export type AuthLevel = "NONE" | "OTP" | "BIOMETRIC";
export type RuleKind = "FRAUD" | "FRICTION" | "REGULATORY";
export type RuleStatus = "ACTIVE" | "CANDIDATE" | "SHADOW" | "RETIRED";

export type Condition = Record<string, unknown>;

export interface RuleRender {
  when_vi: string;
  then_vi: string;
  sentence_vi: string;
  has_exemption: boolean;
}

export interface Rule {
  id: string;
  version: number;
  name: string;
  description: string;
  kind: RuleKind;
  status: RuleStatus;
  locked: boolean;
  when: Condition;
  then: { decision?: Decision; auth?: AuthLevel; exempt_auth?: boolean; hold_seconds?: number };
  assumptions: string[];
  provenance: { created_by: "human" | "ai_compile" | "ai_repair" | "det_repair"; parent?: string; ai_call_id?: string };
  render?: RuleRender;
}

export interface Assumption {
  phrase: string;
  interpretation: string;
  editable: boolean;
}

export interface CompileResult {
  status: "OK" | "NEEDS_CLARIFICATION" | "OUT_OF_SCOPE" | "INVALID";
  rule: Rule | null;
  assumptions: Assumption[];
  clarifying_questions: string[];
  unsupported_parts: string[];
  errors: string[];
  source: "ai" | "cache";
  model: string;
  ai_call_id: string | null;
}

export type Transaction = Record<string, number | boolean | string>;

export interface Grounding {
  tx_count: number;
  amount_sum: number;
  by_scenario: Record<string, { label_vi: string; count: number; amount_sum: number }>;
  by_label: Record<string, number>;
  days: number[];
  note_vi: string;
}

export interface Check {
  code: "VC-01" | "VC-03" | "VC-04" | "VC-05" | "VC-06" | string;
  severity: "ERROR" | "WARN" | "INFO";
  status?: "VIOLATED" | "DEAD" | "UNKNOWN" | "REDUNDANT" | "CONFLICT";
  grounding?: Grounding;
  redundant?: string;
  covered_by?: string;
  conflicts_with?: string;
  message_vi: string;
  invariant?: string;
  rule_id?: string;
  path?: string;
  blamed_rules?: string[];
  counterexample?: Transaction;
  outcome?: { decision: Decision; auth: AuthLevel };
  conflicting_conditions_vi?: string[];
}

export type Verdict = "PASS" | "PASS_WITH_WARNINGS" | "FAIL" | "UNKNOWN";

export interface VerifyReport {
  verdict: Verdict;
  ms: number;
  checked: { rules: string[]; invariants: string[]; pack_version?: string };
  checks: Check[];
  rules_vi?: Record<string, string>;
  verify_run_id?: string;
}

export interface Invariant {
  id: string;
  type: "AUTH_AT_LEAST" | "DECISION_AT_MOST";
  level: string;
  when: Condition;
  source: string;
}

export interface PackParam {
  value: number;
  unit: string;
  source: string;
}

export interface PolicyPack {
  id: string;
  version: string;
  disclaimer: string;
  params: Record<string, PackParam>;
  invariants: Invariant[];
  params_vi?: Record<string, string>;
  invariants_vi?: Record<string, string>;
}

export interface CatalogField {
  name: string;
  type: "int" | "bool" | "enum";
  label_vi: string;
  unit?: string;
  min?: number;
  max?: number;
  values?: string[];
  value_labels_vi?: Record<string, string>;
  label_false_vi?: string;
}

export interface Catalog {
  dsl_version: string;
  fields: CatalogField[];
}

export interface RepairCandidate {
  source: "ai" | "det";
  strategy: "NARROW_SCOPE" | "CHANGE_ACTION" | "SPLIT_RULE" | "OTHER";
  rationale_vi: string;
  intent_preserved_vi: string;
  intent_lost_vi: string;
  rules: Rule[];
  verdict: Verdict;
  passes: boolean;
  scope_ok: boolean;
  coverage_bp: number | null;
  l_net: number;
  delta: Record<string, number>;
  leaves: number;
  diff: { added_vi: string[]; removed_vi: string[] };
  rank: number;
}

export interface RepairResponse {
  needed: boolean | null;
  message_vi?: string;
  original?: Rule;
  violated_invariants?: string[];
  baseline?: { l_net: number; friction_biometric: number; valid: boolean };
  candidates: RepairCandidate[];
  rejected: { source: "ai" | "det"; strategy: string; reason_vi: string }[];
  llm: "used" | "unavailable" | "quota" | "error" | "not_requested" | "not_needed";
}

export interface ApiErrorBody {
  error_code: string;
  message_vi: string;
  details?: unknown;
}

// ---------- Policy Pack: phân tích tác động (T4.1) + VC-07 (T4.2) ----------

export interface Outcome {
  decision: Decision;
  auth: AuthLevel;
}

export type PatchOp =
  | { op: "set_param"; param: string; value: number; source?: string }
  | { op: "add_invariant"; invariant: Invariant & { severity?: string } };

export interface InterpretResult {
  status: "OK" | "INVALID" | "OUT_OF_SCOPE";
  patch: PatchOp[];
  changes: (PackChange & { description_vi?: string })[];
  errors?: string[];
  pack_after_version?: string | null;
  effective_date?: string | null;
  uncertainties: string[];
  model?: string;
}

export type PackChange =
  | { op: "set_param"; param: string; label_vi: string; old: number; new: number; unit: string }
  | { op: "add_invariant" | "remove_invariant"; invariant_id: string };

export interface ImpactReason {
  code: "VC-01" | "VC-03" | "VC-04" | "STALE_LITERAL" | "SCOPE_SHIFT" | string;
  severity: "ERROR" | "WARN";
  message_vi: string;
  invariant?: string;
  counterexample?: Transaction;
  outcome?: Outcome;
  outcomes?: { before: Outcome; after: Outcome };
  grounding?: Grounding;
}

export type ImpactCategory = "incompatible" | "review" | "adaptive" | "unaffected";

export interface ImpactFix {
  source: "det";
  rule: Rule | null;
  verdict: Verdict;
  passes: boolean;
  notes_vi: string[];
  remaining_checks?: Check[];
}

export interface ImpactRule {
  id: string;
  name: string;
  kind: RuleKind;
  status: RuleStatus;
  locked: boolean;
  category: ImpactCategory;
  params_referenced: string[];
  reasons: ImpactReason[];
  render_before: RuleRender;
  render_after: RuleRender;
  fix?: ImpactFix | null;
}

export interface DataSummary {
  tx_count: number;
  amount_sum: number;
  by_scenario: Record<string, { label_vi: string; count: number; amount_sum: number }>;
  by_label: Record<string, number>;
}

export interface DiffKind {
  decision: [Decision, Decision] | null;
  auth: [AuthLevel, AuthLevel] | null;
  label_vi: string;
  direction: "stricter" | "looser" | "mixed";
  before: Outcome;
  after: Outcome;
  counterexample: Transaction;
  data?: DataSummary;
}

export interface SemanticDiff {
  code: "VC-07";
  severity: "INFO";
  status: "DIFFERENT" | "EQUIVALENT" | "UNKNOWN";
  complete: boolean;
  diffs: DiffKind[];
  grounding?: DataSummary & { days: number[]; other_tx_count: number };
  message_vi: string;
}

export interface FrictionSnapshot {
  friction_biometric: number;
  friction_otp: number;
  l_net: number;
  fn_loss: number;
  review_cost: number;
  churn_loss: number;
  fp_hold: number;
  fp_block: number;
  valid: boolean;
}

export interface PackImpact {
  pack_before: { version: string; params: Record<string, PackParam> };
  pack_after: PolicyPack;
  changes: PackChange[];
  verify_before: { verdict: Verdict };
  verify_after: VerifyReport;
  rules: ImpactRule[];
  counts: Record<ImpactCategory, number>;
  semantic_diff: SemanticDiff;
  pack_findings: Check[];
  friction: { before: FrictionSnapshot; after: FrictionSnapshot; delta: Record<string, number>; days: number[] };
  ms: number;
}

// ---------- Backtest nhiều phương án (T4.4) ----------

export interface Assumptions {
  hold_stop_bp: number;
  c_review_block: number;
  churn_hold_bp: number;
  churn_block_bp: number;
  margin_bp: number;
}

export interface MoneyBlock {
  l_net: number;
  fn_loss: number;
  review_cost: number;
  churn_loss: number;
  loss_total: number;
  prevented: number;
  loss_count: number;
  loss_stopped_count: number;
  legit_count: number;
  fp_hold: number;
  fp_block: number;
  mule_flow_stopped: number;
  mule_flow_total: number;
}

export interface BacktestResult extends MoneyBlock {
  friction_biometric: number;
  compliance_exposure: { invariant: string; count: number; amount_sum: number }[];
  valid: boolean;
  by_scenario: Record<string, MoneyBlock & { label_vi: string; count: number }>;
  n_tx: number;
  days: number[];
  ms: number;
}

export interface BacktestVariant {
  name: string;
  result?: BacktestResult;
  delta?: Record<string, number>;
  verify?: { verdict: Verdict; errors: string[] };
  eligible: boolean;
  rank?: number;
  rules_vi?: Record<string, string>;
  error?: VerifyReport;
}

export interface BacktestResponse {
  baseline: BacktestResult;
  variants: BacktestVariant[];
  ms: number;
  backtest_run_id: string;
}

// ---------- Change set + phê duyệt + audit (T4.5) ----------

export type ChangeSetState = "DRAFT" | "VERIFIED" | "SHADOW" | "APPROVED" | "REJECTED";

export interface ShadowResult {
  days: number[];
  n_tx: number;
  changed: DataSummary;
  stricter_count: number;
  looser_count: number;
  fraud_newly_stopped: number;
  legit_newly_stopped: number;
  legit_newly_biometric: number;
  auth_lost: number;
  before: BacktestSummary & { prevented: number; n_tx: number };
  after: BacktestSummary & { prevented: number; n_tx: number };
  delta: Record<string, number>;
  samples: { tx_id: string; hour: number; amount: number; channel: string; label: string; scenario: string; before: Outcome; after: Outcome }[];
  sample_truncated: boolean;
}

export interface ChangeSetItem {
  op: "add" | "replace" | "retire";
  rule_id: string;
  rule?: Rule;
  before_vi?: string | null;
  after_vi?: string;
}

export interface BacktestSummary {
  l_net: number;
  fn_loss: number;
  review_cost: number;
  churn_loss: number;
  fp_hold: number;
  fp_block: number;
  friction_biometric: number;
  mule_flow_stopped: number;
  valid: boolean;
  compliance_exposure: { invariant: string; count: number; amount_sum: number }[];
}

export interface ChangeSet {
  id: string;
  state: ChangeSetState;
  items: ChangeSetItem[];
  pack_version: string;
  verify_run_id: string | null;
  backtest_run_id: string | null;
  summary: {
    verify: VerifyReport;
    backtest: { before: BacktestSummary; after: BacktestSummary; delta: Record<string, number>; days: number[] };
    semantic_diff: SemanticDiff;
    shadow?: ShadowResult;
    review_summary?: {
      summary_vi: string;
      source: "ai" | "template";
      ai: "used" | "unavailable" | "error" | "rejected";
      rejected_numbers?: string[];
      model?: string;
    };
  };
  note: string;
  decision_note: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  actor: "user:proposer" | "user:approver" | "ai" | "system" | string;
  action: string;
  ref: Record<string, unknown> | null;
  created_at: string;
  ai_call?: { model: string; prompt_version: string; prompt_hash: string; from_cache: boolean; schema_valid: boolean; latency_ms: number };
}

export interface PackRepairCandidate {
  source: "ai" | "det";
  strategy: string;
  rationale_vi?: string;
  intent_preserved_vi?: string;
  intent_lost_vi?: string;
  rules: Rule[];
  verdict: Verdict;
  passes: boolean;
  stale_params: string[];
  relations: { invariant: string; before: string; after: string; kept: boolean; message_vi: string }[];
  relation_ok: boolean;
  uses_param: boolean;
  l_net: number;
  delta: Record<string, number>;
  rank: number;
}

export interface PackRepairResponse {
  needed: boolean;
  message_vi?: string;
  candidates: PackRepairCandidate[];
  rejected: { source: "ai" | "det"; strategy: string; reason_vi: string }[];
  llm: "used" | "unavailable" | "quota" | "error" | "not_requested" | "not_needed";
}
