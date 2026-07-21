#!/usr/bin/env python3
"""Ledger append + rollup + regression detector for the skills-eval CI gate.

This is the workflow-side half of the eval gate. The harness
(`toolbelt skills-eval run`) writes one `results.jsonl` per model
run (via `--results-dir`); this script distills those raw per-rep records into
the append-only ledger, regenerates the scorecard, and applies the RFC
regression rule.

Contract with the harness: each `results.jsonl` holds one JSON record per
`case x condition x rep`, with at least these fields (see
`toolbelt/skills_eval/models.py::RunRecord.to_dict`):

    case, group, condition, rep, model, passed,
    graders:[{grader, category, passed, reason}], num_turns,
    input_tokens, output_tokens, error

`category` is one of outcome | routing | guardrail | exploration; the top-level
`passed` is true iff every *outcome* grader passed. This script collapses the
reps of each (model, arm, case) into ONE aggregate row — classified by the
case's primary check (guardrail -> "safety", else routing -> "routing", else
"outcome") — stamps `run_ts`, `skills_sha`, `harness_sha`, computes `pass_rate`,
appends to history/runs.csv (creating the header on first run), regenerates
history/rollup.md, and runs the regression detector. Classifying by the primary
check keeps the row's pass_rate aligned with what each rollup section / the
safety gate reads (a guardrail regression is what trips the block).

Relative rule (purely relative, per RFC), applied symmetrically:
  For each (model_id, case, check_kind) in the new run, find the most recent
  PRIOR ledger row with the same (model_id, case). If none -> baseline, green.
  Compare against 1/reps (one flipped rep of noise never registers):
    prior.pass_rate - new.pass_rate > 1/reps -> regressed
      - safety check regressed  -> exit 2 (block merge)
      - other check regressed   -> annotate + comment, non-blocking (exit 0)
    new.pass_rate - prior.pass_rate > 1/reps -> improved
      - which evals the skills change moved up, surfaced in the comment /
        as ::notice:: annotations; informational, never changes the exit code
  A (model, case) with no prior ledger row is reported as a new baseline.

Also, independent of history, the comment reports per-case skill lift for THIS
run: skills-arm rate minus bare-arm rate on the same (model, case), for pairs
whose gap clears the per-rep threshold. This answers "did the skill help on
this eval, right now" rather than "did this case move vs. last time".

Usage:
    eval_ledger.py \
        --results-glob 'fragments/*/results.jsonl' \
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
import json
import os
import statistics
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


# The harness emits per-rep records tagging each grader with a category
# (outcome | routing | guardrail | exploration). We collapse each
# (model, arm, case) into ONE ledger row, classified by the case's primary
# check so the downstream rollup sections and safety gate keep their meaning:
#   guardrail graders present -> "safety"  (blocks the merge on regression)
#   else routing graders       -> "routing" (feeds the routing-accuracy section)
#   else                       -> "outcome" (task success; feeds skill lift)
# The row's pass_rate is that check_kind's own rate, so a guardrail-compliance
# drop is what trips the safety gate rather than an unrelated task-success dip.
def _rep_category_passed(record, category):
    """True iff this rep has >=1 grader in *category* and all of them passed.

    Mirrors the harness's top-level `passed` (all outcome graders passed),
    applied to an arbitrary category so per-rep counts stay integral.
    """
    graders = [g for g in record.get("graders", []) if g.get("category") == category]
    return bool(graders) and all(g.get("passed") for g in graders)


def _classify(records):
    """Pick a case's primary (check_kind, grader-category) from its records.

    Returns category=None for the "outcome" kind, signalling the caller to use
    the record's top-level `passed` field rather than a grader category.
    """
    categories = {g.get("category") for r in records for g in r.get("graders", [])}
    if "guardrail" in categories:
        return "safety", "guardrail"
    if "routing" in categories:
        return "routing", "routing"
    return "outcome", None


def _median_int(values):
    return round(statistics.median(values)) if values else None


def read_results(pattern):
    """Distill harness results.jsonl files into per-(model, arm, case) rows.

    Each matched file is one model's suite run
    (``<results-dir>/results.jsonl``), holding one JSON record per
    case x condition x rep. Reps are collapsed to a pass count for the case's
    primary check_kind; the emitted rows are shaped exactly like the old CSV
    fragments so the ledger/rollup/gate code below is unchanged.
    """
    rows = []
    paths = sorted(glob.glob(pattern))
    if not paths:
        sys.stderr.write(f"error: no results.jsonl matched {pattern!r}\n")
        sys.exit(1)
    for path in paths:
        with open(path) as fh:
            records = [json.loads(line) for line in fh if line.strip()]
        meta = {}
        meta_path = os.path.join(os.path.dirname(path), "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as fh:
                meta = json.load(fh)

        by_key = defaultdict(list)
        for r in records:
            model_id = (r.get("model") or meta.get("model") or "").strip()
            by_key[(model_id, r["condition"], r["case"])].append(r)

        for (model_id, arm, case), runs in by_key.items():
            check_kind, category = _classify(runs)
            reps = len(runs)
            if category is None:
                passes = sum(1 for r in runs if r.get("passed"))
            else:
                passes = sum(1 for r in runs if _rep_category_passed(r, category))
            ok = [r for r in runs if not r.get("error")]
            row = {
                "model_id": model_id,
                "arm": arm.strip(),
                "case": case.strip(),
                "group": (runs[0].get("group") or case).strip(),
                "check_kind": check_kind,
                "reps": reps,
                "passes": passes,
                "pass_rate": round(passes / reps, 4) if reps else 0.0,
            }
            # Efficiency medians over non-errored reps (feed the rollup's cost
            # section). "tokens" is input+output, the whole-run token cost.
            turns = _median_int([r["num_turns"] for r in ok if "num_turns" in r])
            tokens = _median_int(
                [r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in ok]
            )
            if turns is not None:
                row["median_turns"] = turns
            if tokens is not None:
                row["median_tokens"] = tokens
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


def detect_deltas(prior_rows, new_rows):
    """Apply the relative rule symmetrically vs. the most recent prior row.

    A move counts only when it clears the per-rep threshold (one flipped rep of
    noise never registers), so the same rule that blocks a safety *drop* also
    surfaces a genuine *gain*. Returns ``(regressions, improvements, baselines)``:

      - regressions: prior_rate - new_rate > threshold (safety ones block)
      - improvements: new_rate - prior_rate > threshold (informational only)
      - baselines:   no prior ledger row for (model, case) — first observation,
                     so there is nothing to compare against yet (informational)
    """
    regressions, improvements, baselines = [], [], []
    for row in new_rows:
        base = {
            "model_id": row["model_id"],
            "case": row["case"],
            "check_kind": row["check_kind"],
            "arm": row["arm"],
            "new_rate": row["pass_rate"],
        }
        prior = most_recent_prior(prior_rows, row["model_id"], row["case"])
        if prior is None:
            baselines.append(base)  # first time we've seen this (model, case)
            continue
        try:
            prior_rate = float(prior["pass_rate"])
        except (KeyError, ValueError):
            continue
        threshold = 1.0 / row["reps"] if row["reps"] else 1.0
        delta = row["pass_rate"] - prior_rate  # +ve = better than before
        base = {**base, "prior_rate": prior_rate, "threshold": round(threshold, 4)}
        if -delta > threshold + 1e-9:
            regressions.append(
                {**base, "drop": round(-delta, 4), "blocking": row["check_kind"] == "safety"}
            )
        elif delta > threshold + 1e-9:
            improvements.append({**base, "gain": round(delta, 4)})
    return regressions, improvements, baselines


def compute_case_lift(new_rows):
    """Per-case skill lift within THIS run: skills-arm rate minus bare-arm rate.

    Unlike the delta rule (which compares a case against its own history), this
    answers "did the skill help on this eval, right now?" by pairing the two
    arms of the same (model, case). Only pairs where both arms ran and the lift
    clears the per-rep threshold are returned — positive (skill helped) and
    negative (skill hurt) alike. Sorted worst-first so drags surface at the top.
    """
    by_case = defaultdict(dict)  # (model, case) -> {arm: row}
    for row in new_rows:
        by_case[(row["model_id"], row["case"])][row["arm"]] = row

    lifts = []
    for (model_id, case), arms in by_case.items():
        bare, skills = arms.get("bare"), arms.get("skills")
        if not bare or not skills:
            continue  # need both arms to compute a lift
        lift = skills["pass_rate"] - bare["pass_rate"]
        reps = min(skills.get("reps") or 0, bare.get("reps") or 0)
        threshold = 1.0 / reps if reps else 1.0
        if abs(lift) <= threshold + 1e-9:
            continue  # within noise — not a real per-case difference
        lifts.append(
            {
                "model_id": model_id,
                "case": case,
                "check_kind": skills["check_kind"],
                "bare_rate": bare["pass_rate"],
                "skills_rate": skills["pass_rate"],
                "lift": round(lift, 4),
                "threshold": round(threshold, 4),
            }
        )
    lifts.sort(key=lambda x: x["lift"])  # most-negative (skill hurt) first
    return lifts


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


def write_comment(path, regressions, improvements, baselines, case_lift, stamp):
    """Write the PR-comment scorecard diff + emit GitHub annotations.

    Four sections, all keyed to the same per-rep threshold:
      - Regressions: dropped vs. the most recent prior ledger row (safety ones
        block the merge; others advisory).
      - Improvements: rose vs. the most recent prior ledger row (informational).
      - New baselines: (model, case) with no prior ledger row — first observation.
      - Skill lift by case: skills-arm vs. bare-arm WITHIN this run — did the
        skill help (or hurt) on each eval, right now.
    """
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
    if improvements:
        lines.append(f"- 📈 {len(improvements)} improvement(s) vs. the most recent prior ledger rows.")
    if baselines:
        lines.append(f"- 🆕 {len(baselines)} new baseline(s) (no prior ledger row to compare).")

    if regressions:
        lines.append("")
        lines.append("### Regressions")
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

    if improvements:
        lines.append("")
        lines.append("### Improvements")
        lines.append("")
        lines.append("| model | case | check | arm | prior | new | gain | thr |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in improvements:
            lines.append(
                f"| 📈 {r['model_id']} | {r['case']} | {r['check_kind']} | "
                f"{r['arm']} | {r['prior_rate']:.2f} | {r['new_rate']:.2f} | "
                f"+{r['gain']:.2f} | {r['threshold']:.2f} |"
            )

    if case_lift:
        lines.append("")
        lines.append("### Skill lift by case (skills − bare, this run)")
        lines.append("")
        lines.append("| model | case | check | bare | skills | lift | thr |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in case_lift:
            flag = "📈" if r["lift"] > 0 else "📉"
            lines.append(
                f"| {flag} {r['model_id']} | {r['case']} | {r['check_kind']} | "
                f"{r['bare_rate']:.2f} | {r['skills_rate']:.2f} | "
                f"{r['lift']:+.2f} | {r['threshold']:.2f} |"
            )

    if baselines:
        lines.append("")
        lines.append("### New baselines")
        lines.append("")
        lines.append("| model | case | check | arm | new |")
        lines.append("|---|---|---|---|---|")
        for r in baselines:
            lines.append(
                f"| 🆕 {r['model_id']} | {r['case']} | {r['check_kind']} | "
                f"{r['arm']} | {r['new_rate']:.2f} |"
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
    for r in improvements:
        print(
            f"::notice::skills-eval improvement: {r['model_id']} / {r['case']} / "
            f"{r['check_kind']} ({r['prior_rate']:.2f} -> {r['new_rate']:.2f}, "
            f"gain {r['gain']:.2f} > {r['threshold']:.2f})"
        )
    for r in case_lift:
        print(
            f"::notice::skills-eval case lift: {r['model_id']} / {r['case']} / "
            f"{r['check_kind']} (bare {r['bare_rate']:.2f} -> skills "
            f"{r['skills_rate']:.2f}, lift {r['lift']:+.2f})"
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--results-glob",
        "--fragments-glob",
        dest="results_glob",
        required=True,
        help="Glob over the harness results.jsonl files (one per model run).",
    )
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

    new_rows = read_results(args.results_glob)
    prior_rows = read_ledger(args.ledger)          # baseline = pre-existing ledger
    regressions, improvements, baselines = detect_deltas(prior_rows, new_rows)
    case_lift = compute_case_lift(new_rows)

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
    write_comment(args.comment, regressions, improvements, baselines, case_lift, stamp)

    safety_regressed = any(r["blocking"] for r in regressions)
    if safety_regressed:
        sys.stderr.write("SAFETY REGRESSION — failing the gate.\n")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
