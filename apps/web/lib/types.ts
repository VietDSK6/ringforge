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

export type PatchOp = { op: "set_param"; param: string; value: number; source?: string };

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
