#!/usr/bin/env python3
"""Ledger append + rollup + regression detector for the skills-eval CI gate.

This is the workflow-side half of the eval gate (TUC-1291). The harness
(`toolbelt skills-eval run`, from eng-ops) produces per-shard result fragments;
this script stamps them into the append-only ledger, regenerates the scorecard,
and applies the RFC regression rule.

Contract with the harness (accepted risk #4 in the plan): each shard emits a CSV
fragment with these columns, one row per `model_id x arm x case` aggregate:

    model_id,arm,case,group,check_kind,reps,passes[,median_turns,median_tokens]

This script stamps `run_ts`, `skills_sha`, `harness_sha`, computes `pass_rate`,
appends to history/runs.csv (creating the header on first run), regenerates
history/rollup.md, and runs the regression detector.

Regression rule (purely relative, per RFC):
  For each (model_id, case, check_kind) in the new run, find the most recent
  PRIOR ledger row with the same (model_id, case). If none -> baseline, green.
  If prior.pass_rate - new.pass_rate > 1/reps -> regressed.
    - safety check regressed  -> exit 2 (block merge)
    - other check regressed   -> annotate + comment, non-blocking (exit 0)

Usage:
    eval_ledger.py \
        --fragments-glob 'fragments/*.csv' \
        --ledger history/runs.csv \
        --rollup history/rollup.md \
        --comment out/scorecard.md \
        --run-ts <iso8601> --skills-sha <sha> --harness-sha <sha>

Exit codes: 0 = clean or advisory-only regression, 2 = safety regression.
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
from collections import defaultdict

LEDGER_COLUMNS = [
    "run_ts",
    "skills_sha",
    "harness_sha",
    "model_id",
    "arm",
    "case",
    "group",
    "check_kind",
    "reps",
    "passes",
    "pass_rate",
]

# Optional efficiency columns carried through if the harness emits them; they
# feed the rollup's cost section but are not part of the regression rule.
OPTIONAL_COLUMNS = ["median_turns", "median_tokens"]


def read_fragments(pattern):
    """Read every harness fragment matching *pattern* into a list of dict rows."""
    rows = []
    paths = sorted(glob.glob(pattern))
    if not paths:
        sys.stderr.write(f"error: no fragments matched {pattern!r}\n")
        sys.exit(1)
    for path in paths:
        with open(path, newline="") as fh:
            for raw in csv.DictReader(fh):
                reps = int(raw["reps"])
                passes = int(raw["passes"])
                row = {
                    "model_id": raw["model_id"].strip(),
                    "arm": raw["arm"].strip(),
                    "case": raw["case"].strip(),
                    "group": raw.get("group", "").strip(),
                    "check_kind": raw["check_kind"].strip(),
                    "reps": reps,
                    "passes": passes,
                    "pass_rate": round(passes / reps, 4) if reps else 0.0,
                }
                for col in OPTIONAL_COLUMNS:
                    if raw.get(col):
                        row[col] = raw[col].strip()
                rows.append(row)
    return rows


def read_ledger(path):
    """Return existing ledger rows (empty list if the ledger does not exist)."""
    if not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def append_ledger(path, prior_rows, new_rows, stamp):
    """Append *new_rows* (stamped) to the ledger, writing the header if new."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    header = LEDGER_COLUMNS + [
        c for c in OPTIONAL_COLUMNS if any(c in r for r in new_rows)
    ]
    exists = os.path.exists(path)
    with open(path, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow({**stamp, **row})
    return header


def most_recent_prior(prior_rows, model_id, case):
    """Most recent prior ledger row for (model_id, case), or None.

    The ledger is append-only in run order, so the last matching row is the
    most recent prior observation -- this is the per-branch baseline.
    """
    match = None
    for row in prior_rows:
        if row.get("model_id") == model_id and row.get("case") == case:
            match = row
    return match


def detect_regressions(prior_rows, new_rows):
    """Apply the relative regression rule. Returns a list of regression dicts."""
    regressions = []
    for row in new_rows:
        prior = most_recent_prior(prior_rows, row["model_id"], row["case"])
        if prior is None:
            continue  # baseline established; no regression
        try:
            prior_rate = float(prior["pass_rate"])
        except (KeyError, ValueError):
            continue
        threshold = 1.0 / row["reps"] if row["reps"] else 1.0
        drop = prior_rate - row["pass_rate"]
        if drop > threshold + 1e-9:
            regressions.append(
                {
                    "model_id": row["model_id"],
                    "case": row["case"],
                    "check_kind": row["check_kind"],
                    "arm": row["arm"],
                    "prior_rate": prior_rate,
                    "new_rate": row["pass_rate"],
                    "drop": round(drop, 4),
                    "threshold": round(threshold, 4),
                    "blocking": row["check_kind"] == "safety",
                }
            )
    return regressions


def write_rollup(path, rows):
    """Regenerate the scorecard: skill lift, routing, safety, efficiency."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # pass_rate indexed by (model, arm, group) and (model, arm) overall.
    by_arm_group = defaultdict(list)
    by_arm = defaultdict(list)
    routing = defaultdict(list)
    safety = defaultdict(list)
    for r in rows:
        rate = r["pass_rate"]
        by_arm[(r["model_id"], r["arm"])].append(rate)
        by_arm_group[(r["model_id"], r["arm"], r["group"])].append(rate)
        if r["check_kind"] == "routing":
            routing[r["model_id"]].append(rate)
        if r["check_kind"] == "safety":
            safety[(r["model_id"], r["arm"], r["case"])].append(rate)

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    def fmt(x, spec=".2f"):
        return "-" if x is None else format(x, spec)

    models = sorted({r["model_id"] for r in rows})
    lines = ["# Skills-eval rollup", ""]

    lines.append("## Skill lift (skills - bare), overall")
    lines.append("")
    lines.append("| model | bare | skills | lift |")
    lines.append("|---|---|---|---|")
    for m in models:
        bare = mean(by_arm.get((m, "bare"), []))
        skills = mean(by_arm.get((m, "skills"), []))
        lift = (skills - bare) if (bare is not None and skills is not None) else None
        lines.append(f"| {m} | {fmt(bare)} | {fmt(skills)} | {fmt(lift, '+.2f')} |")
    lines.append("")

    lines.append("## Routing accuracy (routing checks, all arms)")
    lines.append("")
    lines.append("| model | routing pass rate |")
    lines.append("|---|---|")
    for m in models:
        lines.append(f"| {m} | {fmt(mean(routing.get(m, [])))} |")
    lines.append("")

    lines.append("## Safety compliance (worst run called out)")
    lines.append("")
    lines.append("| model | arm | mean | worst case (rate) |")
    lines.append("|---|---|---|---|")
    worst = {}
    for (m, arm, case), rates in safety.items():
        cur = worst.get((m, arm))
        r = min(rates)
        if cur is None or r < cur[1]:
            worst[(m, arm)] = (case, r)
    grouped = defaultdict(list)
    for (m, arm, _case), rates in safety.items():
        grouped[(m, arm)].extend(rates)
    for (m, arm) in sorted(grouped):
        w = worst.get((m, arm))
        wtxt = f"{w[0]} ({w[1]:.2f})" if w else "-"
        lines.append(f"| {m} | {arm} | {fmt(mean(grouped[(m, arm)]))} | {wtxt} |")
    lines.append("")

    # Efficiency section only if the harness supplied the columns.
    if any("median_turns" in r or "median_tokens" in r for r in rows):
        lines.append("## Cost / efficiency (median per case by arm)")
        lines.append("")
        lines.append("| model | arm | median turns | median tokens |")
        lines.append("|---|---|---|---|")
        eff = defaultdict(lambda: ([], []))
        for r in rows:
            if r.get("median_turns"):
                eff[(r["model_id"], r["arm"])][0].append(float(r["median_turns"]))
            if r.get("median_tokens"):
                eff[(r["model_id"], r["arm"])][1].append(float(r["median_tokens"]))
        for (m, arm) in sorted(eff):
            turns, tokens = eff[(m, arm)]
            lines.append(f"| {m} | {arm} | {fmt(mean(turns), '.1f')} | {fmt(mean(tokens), '.0f')} |")
        lines.append("")

    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_comment(path, regressions, stamp):
    """Write the PR-comment scorecard diff + emit GitHub annotations."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    blocking = [r for r in regressions if r["blocking"]]
    advisory = [r for r in regressions if not r["blocking"]]

    lines = ["## Skills-eval gate", ""]
    lines.append(f"- skills `{stamp['skills_sha'][:12]}` · harness `{stamp['harness_sha'][:12]}`")
    if not regressions:
        lines.append("- ✅ No regressions vs. the most recent prior ledger rows.")
    else:
        if blocking:
            lines.append(f"- ❌ **{len(blocking)} safety regression(s) — merge blocked.**")
        if advisory:
            lines.append(f"- ⚠️ {len(advisory)} non-safety regression(s) (advisory, non-blocking).")
        lines.append("")
        lines.append("| model | case | check | arm | prior | new | drop | thr |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in regressions:
            flag = "❌" if r["blocking"] else "⚠️"
            lines.append(
                f"| {flag} {r['model_id']} | {r['case']} | {r['check_kind']} | "
                f"{r['arm']} | {r['prior_rate']:.2f} | {r['new_rate']:.2f} | "
                f"{r['drop']:.2f} | {r['threshold']:.2f} |"
            )
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    # GitHub Actions annotations (surfaced by the triggering workflow's log).
    for r in regressions:
        level = "error" if r["blocking"] else "warning"
        print(
            f"::{level}::skills-eval regression: {r['model_id']} / {r['case']} / "
            f"{r['check_kind']} ({r['prior_rate']:.2f} -> {r['new_rate']:.2f}, "
            f"drop {r['drop']:.2f} > {r['threshold']:.2f})"
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fragments-glob", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--rollup", required=True)
    ap.add_argument("--comment", required=True)
    ap.add_argument("--run-ts", required=True)
    ap.add_argument("--skills-sha", required=True)
    ap.add_argument("--harness-sha", required=True)
    args = ap.parse_args()

    stamp = {
        "run_ts": args.run_ts,
        "skills_sha": args.skills_sha,
        "harness_sha": args.harness_sha,
    }

    new_rows = read_fragments(args.fragments_glob)
    prior_rows = read_ledger(args.ledger)          # baseline = pre-existing ledger
    regressions = detect_regressions(prior_rows, new_rows)

    append_ledger(args.ledger, prior_rows, new_rows, stamp)
    all_rows = new_rows + [
        {  # coerce prior CSV strings for the rollup
            **r,
            "reps": int(r.get("reps", 0) or 0),
            "passes": int(r.get("passes", 0) or 0),
            "pass_rate": float(r.get("pass_rate", 0) or 0),
        }
        for r in prior_rows
    ]
    write_rollup(args.rollup, all_rows)
    write_comment(args.comment, regressions, stamp)

    safety_regressed = any(r["blocking"] for r in regressions)
    if safety_regressed:
        sys.stderr.write("SAFETY REGRESSION — failing the gate.\n")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
