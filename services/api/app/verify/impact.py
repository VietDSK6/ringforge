"""Phân tích tác động khi đổi Policy Pack (FR-P2, FR-P3; docs/07 mục 3.6 — Demo 2).

Bộ luật giữ nguyên, Policy Pack đổi theo một bản vá → kiểm chứng lại toàn bộ, rồi phân loại từng luật:
- incompatible ❌: lỗi VC-01 theo pack mới (ví dụ hold_seconds ngoài khoảng mới), thành luật chết (VC-03),
  bị quy lỗi một vi phạm invariant mới phát sinh (VC-04), hoặc VIẾT CỨNG đúng giá trị cũ của tham số vừa đổi
  (mốc không tự cập nhật — LG-07 viết cứng 10.000.000 khi ngưỡng sinh trắc học/lần đổi).
- review ⚠: quan hệ của luật với phạm vi một invariant thay đổi (trước nằm ngoài, nay nằm trong…) dù không viết cứng.
- adaptive ✅: tham chiếu tham số vừa đổi → tự đúng theo giá trị mới.
- unaffected: còn lại.
Ma sát trước/sau (FR-P3) = backtest cùng bộ luật với pack cũ và pack mới. Mọi con số do code tính, không do LLM.
"""

from __future__ import annotations

import copy
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from typing import Annotated, Any, Literal, Union

import z3
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from app.backtest.interpreter import condition_mask
from app.backtest.metrics import BACKTEST_DAYS, Assumptions, run_backtest
from app.dsl.catalog import AUTH_LEVELS, CATALOG, DECISIONS
from app.dsl.render_vi import PARAM_LABELS_VI, format_vnd, render_condition, render_rule
from app.dsl.validator import Issue, check_pack, check_rule
from app.verify.checks import TIMEOUT_MS, solver_status, verify_rules
from app.verify.det_repair import deterministic_repair
from app.verify.encoder import domain, enc, make_vars, model_to_tx, outcome
from app.verify.grounding import ground_findings, summarize
from app.verify.optimize import readable_model
from app.verify.semantic_diff import semantic_diff

# ---------- Bản vá Policy Pack ----------


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetParam(_Op):
    op: Literal["set_param"]
    param: StrictStr = Field(min_length=1, max_length=64)
    value: StrictInt = Field(ge=0, le=2_000_000_000)
    source: StrictStr | None = Field(default=None, max_length=300, description="Ghi chú nguồn, ví dụ 'Kịch bản giả lập'")


class AddInvariant(_Op):
    op: Literal["add_invariant"]
    invariant: dict[str, Any]


class RemoveInvariant(_Op):
    op: Literal["remove_invariant"]
    invariant_id: StrictStr = Field(min_length=1, max_length=64)


PatchOp = Annotated[Union[SetParam, AddInvariant, RemoveInvariant], Field(discriminator="op")]


def next_version(version: str) -> str:
    """'2026.11-sim.1' → '2026.11-sim.2'; không có số cuối thì thêm '.1'."""
    m = re.match(r"^(.*?)(\d+)$", version)
    return f"{m.group(1)}{int(m.group(2)) + 1}" if m else f"{version}.1"


def apply_patch(pack: dict[str, Any], ops: list[SetParam | AddInvariant | RemoveInvariant]) -> tuple[dict[str, Any] | None, list[Issue], list[dict[str, Any]]]:
    """Áp bản vá lên bản sao của pack → (pack mới đã qua VC-01 | None, lỗi, danh sách thay đổi thực sự)."""
    new = copy.deepcopy(pack)
    issues: list[Issue] = []
    changes: list[dict[str, Any]] = []
    for i, op in enumerate(ops):
        path = f"patch[{i}]"
        if isinstance(op, SetParam):
            p = new["params"].get(op.param)
            if p is None:
                issues.append(Issue(f"Tham số không tồn tại trong Policy Pack: '{op.param}'.", path))
                continue
            if p["value"] != op.value:
                changes.append({"op": "set_param", "param": op.param, "label_vi": PARAM_LABELS_VI.get(op.param, op.param),
                                "old": p["value"], "new": op.value, "unit": p["unit"]})
            p["value"] = op.value
            if op.source:
                p["source"] = op.source
        elif isinstance(op, AddInvariant):
            inv_id = op.invariant.get("id")
            if any(inv["id"] == inv_id for inv in new["invariants"]):
                issues.append(Issue(f"Invariant '{inv_id}' đã có trong Policy Pack.", path))
                continue
            new["invariants"].append(copy.deepcopy(op.invariant))
            changes.append({"op": "add_invariant", "invariant_id": inv_id})
        else:
            before = len(new["invariants"])
            new["invariants"] = [inv for inv in new["invariants"] if inv["id"] != op.invariant_id]
            if len(new["invariants"]) == before:
                issues.append(Issue(f"Không có invariant '{op.invariant_id}' để bỏ.", path))
                continue
            changes.append({"op": "remove_invariant", "invariant_id": op.invariant_id})
    lo, hi = new["params"].get("hold_min_seconds"), new["params"].get("hold_max_seconds")
    if lo and hi and lo["value"] > hi["value"]:
        issues.append(Issue("Thời gian giữ tối thiểu không được lớn hơn thời gian giữ tối đa.", "patch"))
    if issues:
        return None, issues, changes
    new["version"] = next_version(pack["version"])
    clean, errs = check_pack(new)
    return clean, errs, changes


# ---------- Duyệt điều kiện ----------


def leaves(c: dict[str, Any]) -> Iterator[dict[str, Any]]:
    if "all" in c or "any" in c:
        for x in c.get("all", c.get("any", [])):
            yield from leaves(x)
    elif "not" in c:
        yield from leaves(c["not"])
    elif "field" in c:
        yield c


def map_leaves(c: dict[str, Any], fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    if "all" in c or "any" in c:
        key = "all" if "all" in c else "any"
        return {key: [map_leaves(x, fn) for x in c[key]]}
    if "not" in c:
        return {"not": map_leaves(c["not"], fn)}
    if "field" in c:
        return fn(copy.deepcopy(c))
    return copy.deepcopy(c)


def _values(leaf: dict[str, Any]) -> list[Any]:
    return list(leaf["value"]) if isinstance(leaf["value"], list) else [leaf["value"]]


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def params_used(c: dict[str, Any]) -> set[str]:
    return {v["param"] for leaf in leaves(c) for v in _values(leaf) if isinstance(v, dict) and "param" in v}


def param_fields(conds: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Tham số → các trường được so với nó (trong invariant và luật), để biết mốc viết cứng thuộc tham số nào."""
    out: dict[str, set[str]] = defaultdict(set)
    for c in conds:
        for leaf in leaves(c):
            for v in _values(leaf):
                if isinstance(v, dict) and "param" in v:
                    out[v["param"]].add(leaf["field"])
    return out


def substitute_literal(c: dict[str, Any], field: str, old: int, param: str) -> dict[str, Any]:
    """Thay mọi giá trị viết cứng == old của `field` bằng {"param": param}."""

    def fn(leaf: dict[str, Any]) -> dict[str, Any]:
        if leaf["field"] != field:
            return leaf
        if isinstance(leaf["value"], list):
            leaf["value"] = [{"param": param} if _is_int(x) and x == old else x for x in leaf["value"]]
        elif _is_int(leaf["value"]) and leaf["value"] == old:
            leaf["value"] = {"param": param}
        return leaf

    return map_leaves(c, fn)


def shift_literals(c: dict[str, Any], field: str, delta: int) -> dict[str, Any]:
    """Dịch các mốc số còn lại của `field` cùng độ lệch (kẹp trong miền) để giữ dải tương đối với ngưỡng."""
    f = CATALOG[field]

    def move(x: Any) -> Any:
        return min(max(x + delta, f.lo), f.hi) if _is_int(x) else x

    def fn(leaf: dict[str, Any]) -> dict[str, Any]:
        if leaf["field"] == field and leaf["op"] not in ("in", "not_in", "==", "!="):
            leaf["value"] = [move(x) for x in leaf["value"]] if isinstance(leaf["value"], list) else move(leaf["value"])
        return leaf

    return map_leaves(c, fn)


# ---------- Z3 ----------


class Z3Box:
    """Một context Z3 + biến + miền dùng chung cho nhiều truy vấn dưới nhiều bộ tham số."""

    def __init__(self, timeout_ms: int = TIMEOUT_MS):
        self.ctx = z3.Context()
        self.v = make_vars(self.ctx)
        self.dom = domain(self.v, self.ctx)
        self.timeout_ms = timeout_ms

    def enc(self, cond: dict[str, Any], params: dict[str, Any]) -> z3.BoolRef:
        return enc(cond, self.v, params, self.ctx)

    def _solver(self, *cs: z3.BoolRef) -> z3.Solver:
        s = z3.Solver(ctx=self.ctx)
        s.set("timeout", self.timeout_ms)
        s.add(self.dom, *cs)
        return s

    def check(self, *cs: z3.BoolRef) -> str:
        return solver_status(self._solver(*cs).check())

    def witness(self, *cs: z3.BoolRef) -> z3.ModelRef | None:
        """Nhân chứng dễ đọc (sát mốc, giá trị trung tính) hoặc None nếu không có / không kết luận được."""
        s = self._solver(*cs)
        if solver_status(s.check()) != "sat":
            return None
        return readable_model(self.ctx, self.v, z3.And(self.dom, *cs), self.timeout_ms) or s.model()


REL_VI = {
    "outside": "nằm ngoài phạm vi",
    "inside": "nằm trọn trong phạm vi",
    "partial": "giao một phần với phạm vi",
    "dead": "không khớp giao dịch nào trong",
    "unknown": "chưa xác định được quan hệ với",
}


def relation(z: Z3Box, rule_when: z3.BoolRef, scope: z3.BoolRef) -> str:
    """Quan hệ giữa vùng luật khớp và phạm vi invariant: outside | inside | partial | dead | unknown."""
    inside, outside = z.check(rule_when, scope), z.check(rule_when, z3.Not(scope))
    if "unknown" in (inside, outside):
        return "unknown"
    return {("unsat", "unsat"): "dead", ("unsat", "sat"): "outside", ("sat", "unsat"): "inside", ("sat", "sat"): "partial"}[(inside, outside)]


# ---------- Phân tích tác động ----------


def _finding_key(f: dict[str, Any]) -> tuple:
    return (f.get("code"), f.get("invariant"), f.get("rule_id"), tuple(f.get("blamed_rules", [])), f.get("status"))


def _outcome_at(m: z3.ModelRef, dec: z3.ArithRef, auth: z3.ArithRef) -> dict[str, str]:
    return {
        "decision": DECISIONS[m.eval(dec, model_completion=True).as_long()],
        "auth": AUTH_LEVELS[m.eval(auth, model_completion=True).as_long()],
    }


def _fmt(value: int, unit: str) -> str:
    return format_vnd(value) if unit == "VND" else f"{value:,}".replace(",", ".") + (f" {unit}" if unit else "")


def _data_note(n: int, amount: int, what: str, n_days: int) -> str:
    if n == 0:
        return "Dữ liệu quá khứ không có giao dịch nào trong vùng này: backtest sẽ KHÔNG thấy, chỉ kiểm chứng hình thức phát hiện được."
    return f"Trong {n_days} ngày dữ liệu tổng hợp: {n:,} giao dịch · {format_vnd(amount)} {what}.".replace(",", ".")


FRICTION_KEYS = ("friction_biometric", "friction_otp", "l_net", "fn_loss", "review_cost", "churn_loss", "fp_hold", "fp_block", "valid")


def pack_impact(
    rules: list[dict[str, Any]],
    old_pack: dict[str, Any],
    new_pack: dict[str, Any],
    changes: list[dict[str, Any]],
    df,
    assumptions: Assumptions | None = None,
    timeout_ms: int = TIMEOUT_MS,
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    live = [r for r in rules if r["status"] != "RETIRED"]
    old_p, new_p = old_pack["params"], new_pack["params"]
    changed = {c["param"]: c for c in changes if c["op"] == "set_param"}
    part = df[df["day"].isin(BACKTEST_DAYS)]
    n_days = len(BACKTEST_DAYS)

    before = verify_rules(rules, old_pack, timeout_ms)
    after = verify_rules(rules, new_pack, timeout_ms)
    ground_findings(after["checks"], rules, new_pack, df)
    after["rules_vi"] = {r["id"]: render_rule(r, new_pack)["sentence_vi"] for r in rules}
    old_keys = {_finding_key(f) for f in before["checks"]}
    for f in after["checks"]:
        f["new"] = _finding_key(f) not in old_keys

    z = Z3Box(timeout_ms)
    dec_o, auth_o, _ = outcome(rules, z.v, old_p, z.ctx)
    dec_n, auth_n, _ = outcome(rules, z.v, new_p, z.ctx)

    def outcomes(m: z3.ModelRef) -> dict[str, Any]:
        return {"before": _outcome_at(m, dec_o, auth_o), "after": _outcome_at(m, dec_n, auth_n)}

    # Invariant có phạm vi đổi theo tham số vừa đổi (cùng id trước và sau).
    old_invs = {i["id"]: i for i in old_pack["invariants"]}
    shifted_invs = [inv for inv in new_pack["invariants"] if inv["id"] in old_invs and params_used(inv["when"]) & changed.keys()]
    fields_of = param_fields([i["when"] for i in old_pack["invariants"]] + [r["when"] for r in live])

    out_rules = []
    for r in live:
        reasons: list[dict[str, Any]] = []
        refs = sorted(params_used(r["when"]) & changed.keys())
        w_new = z.enc(r["when"], new_p)

        _, errs = check_rule(r, new_pack)
        reasons += [{"code": "VC-01", "severity": "ERROR", "message_vi": e.message_vi} for e in errs]
        for f in after["checks"]:
            if not f.get("new"):
                continue
            if f["code"] == "VC-03" and f.get("rule_id") == r["id"]:
                reasons.append({"code": "VC-03", "severity": "ERROR", "message_vi": f["message_vi"] + " (theo Policy Pack mới)"})
            if f["code"] == "VC-04" and r["id"] in f.get("blamed_rules", []):
                reasons.append({k: f[k] for k in ("code", "severity", "message_vi", "invariant", "counterexample", "outcome", "grounding") if k in f})

        # Quan hệ với phạm vi invariant trước/sau.
        shifts = []
        for inv in shifted_invs:
            s_old, s_new = z.enc(old_invs[inv["id"]]["when"], old_p), z.enc(inv["when"], new_p)
            rel_b = relation(z, z.enc(r["when"], old_p), s_old)
            rel_a = relation(z, w_new, s_new)
            if rel_b != rel_a:
                shifts.append({"invariant": inv["id"], "before": rel_b, "after": rel_a, "scope_old": s_old, "scope_new": s_new,
                               "message_vi": (f"Trước khi đổi, luật {REL_VI[rel_b]} {inv['id']} ({render_condition(old_invs[inv['id']]['when'], old_pack)}); "
                                              f"sau khi đổi, luật {REL_VI[rel_a]} {inv['id']} ({render_condition(inv['when'], new_pack)}).")})

        # Mốc viết cứng đúng bằng giá trị cũ của tham số vừa đổi.
        stale_when = r["when"]
        stale = []
        for name, ch in changed.items():
            hits = [lf for lf in leaves(r["when"]) if lf["field"] in fields_of.get(name, ()) and ch["old"] in [x for x in _values(lf) if _is_int(x)]]
            if hits:
                stale.append((name, ch, sorted({lf["field"] for lf in hits})))
                for fld in {lf["field"] for lf in hits}:
                    stale_when = substitute_literal(stale_when, fld, ch["old"], name)
        if stale:
            w_sub = z.enc(stale_when, new_p)
            m = z.witness(w_new, z3.Not(w_sub))
            extra = m is not None
            if m is None:
                m = z.witness(z3.Not(w_new), w_sub)
            labels = ", ".join(f"{_fmt(ch['old'], ch['unit'])} (giá trị cũ của {ch['label_vi']}, nay là {_fmt(ch['new'], ch['unit'])})" for _, ch, _ in stale)
            msg = f"Luật {r['id']} viết cứng {labels}: mốc này không tự cập nhật theo Policy Pack."
            reason: dict[str, Any] = {"code": "STALE_LITERAL", "severity": "ERROR", "params": [n for n, _, _ in stale]}
            if m is not None:
                tx = model_to_tx(m, z.v)
                msg += (" Luật vẫn khớp giao dịch như phản ví dụ dưới đây, dù nếu tham chiếu tham số thì không còn khớp."
                        if extra else " Luật bỏ sót giao dịch như phản ví dụ dưới đây, dù nếu tham chiếu tham số thì sẽ khớp.")
                reason |= {"counterexample": tx, "outcomes": outcomes(m)}
            mask = condition_mask(r["when"], part, new_p) ^ condition_mask(stale_when, part, new_p)
            g = summarize(part, mask)
            g["note_vi"] = _data_note(g["tx_count"], g["amount_sum"], "khớp khác đi chỉ vì mốc viết cứng", n_days)
            reason["grounding"] = g
            reason["scope_shift"] = [{k: v for k, v in s.items() if not k.startswith("scope_")} for s in shifts]
            reason["message_vi"] = msg + "".join(" " + s["message_vi"] for s in shifts)
            reasons.append(reason)
        else:
            for s in shifts:
                m = z.witness(w_new, s["scope_old"] != s["scope_new"])
                reason = {"code": "SCOPE_SHIFT", "severity": "WARN", "invariant": s["invariant"],
                          "before": s["before"], "after": s["after"], "message_vi": s["message_vi"]}
                if m is not None:
                    reason |= {"counterexample": model_to_tx(m, z.v), "outcomes": outcomes(m)}
                reasons.append(reason)

        if any(x["severity"] == "ERROR" for x in reasons):
            category = "incompatible"
        elif reasons:
            category = "review"
        elif refs:
            category = "adaptive"
        else:
            category = "unaffected"
        entry = {
            "id": r["id"], "name": r["name"], "kind": r["kind"], "status": r["status"], "locked": bool(r.get("locked")),
            "category": category, "params_referenced": refs, "reasons": reasons,
            "render_before": render_rule(r, old_pack), "render_after": render_rule(r, new_pack),
        }
        if category == "incompatible" and not r.get("locked"):
            entry["fix"] = _fix(r, stale, stale_when, after["checks"], rules, new_pack, timeout_ms)
        out_rules.append(entry)

    bt_before = run_backtest(rules, df, old_pack, assumptions)
    bt_after = run_backtest(rules, df, new_pack, assumptions)
    pick = lambda b: {k: b[k] for k in FRICTION_KEYS} | {"compliance_exposure": b["compliance_exposure"]}  # noqa: E731
    counts = {c: sum(1 for x in out_rules if x["category"] == c) for c in ("incompatible", "review", "adaptive", "unaffected")}
    return {
        "pack_before": {"version": old_pack["version"], "params": old_pack["params"]},
        "pack_after": new_pack,
        "changes": changes,
        "verify_before": {"verdict": before["verdict"]},
        "verify_after": after,
        "rules": out_rules,
        "counts": counts,
        "semantic_diff": semantic_diff(rules, old_p, rules, new_p, df, timeout_ms=timeout_ms),
        "pack_findings": [f for f in after["checks"] if f.get("new") and f["code"] == "VC-04" and not f.get("blamed_rules")],
        "friction": {
            "before": pick(bt_before),
            "after": pick(bt_after),
            "delta": {k: int(bt_after[k]) - int(bt_before[k]) for k in FRICTION_KEYS if k != "valid"},
            "days": list(BACKTEST_DAYS),
        },
        "ms": (time.perf_counter_ns() - started) // 1_000_000,
    }


def _fix(
    rule: dict[str, Any], stale: list, stale_when: dict[str, Any], findings: list[dict[str, Any]],
    rules: list[dict[str, Any]], pack: dict[str, Any], timeout_ms: int,
) -> dict[str, Any] | None:
    """Bản sửa tất định cho luật không còn tương thích, đã kiểm chứng lại với Policy Pack mới.

    Mốc viết cứng → tham chiếu tham số, các mốc khác của cùng trường dịch theo cùng độ lệch (giữ dải "sát ngưỡng");
    còn vi phạm invariant thì thêm điều kiện loại trừ đúng vùng vi phạm (docs/03 mục 5).
    """
    fixed = copy.deepcopy(rule)
    fixed.pop("render", None)
    notes = []
    if stale:
        when = stale_when
        for name, ch, fields in stale:
            for fld in fields:
                when = shift_literals(when, fld, ch["new"] - ch["old"])
                notes.append(f"Thay mốc {_fmt(ch['old'], ch['unit'])} của '{CATALOG[fld].label_vi}' bằng tham số {ch['label_vi']}"
                             f" và dịch các mốc khác của trường này {'+' if ch['new'] >= ch['old'] else '−'}{_fmt(abs(ch['new'] - ch['old']), ch['unit'])} để giữ dải tương đối với ngưỡng.")
        fixed["when"] = when
    candidate_rules = [fixed if r["id"] == rule["id"] else r for r in rules]
    report = verify_rules(candidate_rules, pack, timeout_ms)
    det = deterministic_repair(fixed, report["checks"], pack)
    if det is not None:
        fixed = det
        notes.append("Thêm điều kiện loại trừ vùng vi phạm invariant (sửa tất định).")
        candidate_rules = [fixed if r["id"] == rule["id"] else r for r in rules]
        report = verify_rules(candidate_rules, pack, timeout_ms)
    if not notes:
        return None
    fixed["version"] = rule.get("version", 1) + 1
    fixed["provenance"] = {"created_by": "det_repair", "parent": f"{rule['id']}@v{rule.get('version', 1)}"}
    clean, issues = check_rule(fixed, pack)
    if clean is None:
        return {"rule": None, "verdict": "FAIL", "notes_vi": notes, "issues": [i.to_dict() for i in issues]}
    mine = [f for f in report["checks"] if f.get("rule_id") == rule["id"] or rule["id"] in f.get("blamed_rules", [])]
    return {
        "source": "det",
        "rule": clean | {"render": render_rule(clean, pack)},
        "verdict": report["verdict"],
        "passes": not any(f["severity"] == "ERROR" for f in mine) and report["verdict"] != "FAIL",
        "remaining_checks": mine,
        "notes_vi": notes,
    }
