"""Shadow mode mô phỏng (FR-A4, docs/04 mục 2): chạy song song bộ luật cũ và mới trên "ngày phát lại" (ngày 7 —
không dùng cho backtest), so quyết định từng giao dịch. Không giao dịch nào bị ảnh hưởng thật; mọi số do interpreter tính."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.backtest.interpreter import interpret
from app.backtest.metrics import Assumptions, delta, run_backtest
from app.dsl.catalog import AUTH, AUTH_LEVELS, DEC, DECISIONS
from app.verify.grounding import summarize

SHADOW_DAYS = (7,)
SAMPLE = 12
KEEP = ("l_net", "fn_loss", "review_cost", "churn_loss", "prevented", "fp_hold", "fp_block", "friction_biometric",
        "mule_flow_stopped", "valid", "n_tx")
FRAUD_FIRST = {"APP_VICTIM": 0, "ATO": 1, "MULE_LAYER": 2, "LEGIT": 3}


def run_shadow(
    old_rules: list[dict[str, Any]], new_rules: list[dict[str, Any]], pack: dict[str, Any], df: pd.DataFrame,
    assumptions: Assumptions | None = None, sample: int = SAMPLE,
) -> dict[str, Any]:
    params = pack["params"]
    part = df[df["day"].isin(SHADOW_DAYS)]
    oa = interpret(old_rules, part, params, with_matched=False)
    ob = interpret(new_rules, part, params, with_matched=False)
    da, db = oa["decision"].to_numpy(), ob["decision"].to_numpy()
    aa, ab = oa["auth"].to_numpy(), ob["auth"].to_numpy()
    changed = (da != db) | (aa != ab)
    stricter = changed & (db >= da) & (ab >= aa)
    looser = changed & (db <= da) & (ab <= aa)

    rows = part[changed].assign(sd0=da[changed], sd1=db[changed], sa0=aa[changed], sa1=ab[changed])
    rows = rows.assign(srank=rows["label"].map(FRAUD_FIRST).fillna(9)).sort_values(["srank", "amount"], ascending=[True, False])
    samples = [
        {
            "tx_id": str(r.tx_id), "hour": int(r.hour), "amount": int(r.amount), "channel": str(r.channel),
            "label": str(r.label), "scenario": str(r.scenario),
            "before": {"decision": DECISIONS[int(r.sd0)], "auth": AUTH_LEVELS[int(r.sa0)]},
            "after": {"decision": DECISIONS[int(r.sd1)], "auth": AUTH_LEVELS[int(r.sa1)]},
        }
        for r in rows.head(sample).itertuples()
    ]
    before = run_backtest(old_rules, df, pack, assumptions, days=SHADOW_DAYS)
    after = run_backtest(new_rules, df, pack, assumptions, days=SHADOW_DAYS)
    legit = (part["label"] == "LEGIT").to_numpy()
    fraud = part["label"].isin(("APP_VICTIM", "ATO", "MULE_LAYER")).to_numpy()
    newly_stopped = (db >= DEC["HOLD"]) & (da < DEC["HOLD"])
    return {
        "days": list(SHADOW_DAYS),
        "n_tx": int(len(part)),
        "changed": summarize(part, changed),
        "stricter_count": int(stricter.sum()),
        "looser_count": int(looser.sum()),
        "fraud_newly_stopped": int((fraud & newly_stopped).sum()),
        "legit_newly_stopped": int((legit & newly_stopped).sum()),
        "legit_newly_biometric": int((legit & (ab == AUTH["BIOMETRIC"]) & (aa < AUTH["BIOMETRIC"])).sum()),
        "auth_lost": int(((ab < aa) & (aa > AUTH["NONE"])).sum()),
        "before": {k: before[k] for k in KEEP},
        "after": {k: after[k] for k in KEEP},
        "delta": delta(after, before),
        "samples": samples,
        "sample_truncated": bool(changed.sum() > sample),
    }
