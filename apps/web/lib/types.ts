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

export interface Check {
  code: "VC-01" | "VC-03" | "VC-04" | string;
  severity: "ERROR" | "WARN" | "INFO";
  status?: "VIOLATED" | "DEAD" | "UNKNOWN";
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

export interface PolicyPack {
  id: string;
  version: string;
  disclaimer: string;
  params: Record<string, { value: number; unit: string; source: string }>;
  invariants: Invariant[];
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

export interface ApiErrorBody {
  error_code: string;
  message_vi: string;
  details?: unknown;
}
