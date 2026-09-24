#!/usr/bin/env python3
"""Report effort metrics per arm from `claude plugin eval` traces.

The suite's score only asks whether the final artifact was correct. With a high
max_turns a determined agent gets there either way, so the score saturates and
the plugin's real effect -- fewer retries, fewer error messages, fewer turns --
goes unmeasured. This reads the kept traces and reports that effort directly.

Usage:
    trace-metrics.py evals/results/<stamp>/aggregate-result.json ...
    trace-metrics.py --csv ...            # machine-readable
Traces live in the --keep-temp scaffold dirs, so only runs kept with that flag
(and not yet reaped from /private/tmp) can be measured.
"""
import json, os, re, sys, collections

# Verbs worth counting separately: each repeat past the first is a retry of a
# step that should succeed once.
VERBS = ["coa plan", "coa deploy", "coa refresh", "coa validate", "coa describe",
         "coa environments create", "coa init"]

# Match only real CLI failures. The plain word "failed" also appears in `coa
# --help` ("rerun  Re-run a failed pipeline"), so anchor on the ✖ marker, the
# structured error[code] form, and the CLI's HTTP error preamble.
ERR_LINE = re.compile(r"(^\s*✖)|(\berror\[)|(^An error occurred during)", re.M)


def read_trace(path):
    """-> (list of bash commands, list of their result texts, tool-call count)"""
    calls, results, ntools = {}, {}, 0
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    ntools += 1
                    if c.get("name") == "Bash":
                        calls[c["id"]] = c.get("input", {}).get("command", "")
                elif c.get("type") == "tool_result":
                    t = c.get("content")
                    if isinstance(t, list):
                        t = "".join(x.get("text", "") for x in t if isinstance(x, dict))
                    results[c.get("tool_use_id")] = str(t)
    ordered = list(calls.items())
    return [c for _, c in ordered], [results.get(i, "") for i, _ in ordered], ntools


def metrics(path):
    cmds, outs, ntools = read_trace(path)
    coa = [c for c in cmds if re.search(r"(?<![\w-])coa(?![\w-])", c)]
    errs = sum(1 for c, o in zip(cmds, outs)
               if ERR_LINE.search(o) and re.search(r"(?<![\w-])coa(?![\w-])", c))
    rep = collections.Counter(c.strip() for c in cmds)
    m = {"tools": ntools, "bash": len(cmds), "coa": len(coa), "coa_err": errs,
         "repeat3x": sum(1 for v in rep.values() if v > 2)}
    for v in VERBS:
        m[v] = sum(1 for c in cmds
                   if re.search(r"(?<![\w-])" + v.replace(" ", r"\s+") + r"(?![\w-])", c))
    return m


def rows(aggregate_paths):
    for f in aggregate_paths:
        agg = json.load(open(f))
        stamp = os.path.basename(os.path.dirname(f))
        for case in agg.get("cases", []):
            for arm, runs in (case.get("arms") or {}).items():
                for i, r in enumerate(runs):
                    tp = r.get("tracePath") or ""
                    row = {"stamp": stamp, "case": case["name"], "arm": arm, "run": i,
                           "score": round(r["score"], 3), "turns": r.get("turns"),
                           "cost": round(r.get("costUsd") or 0, 2),
                           "secs": r.get("durationSeconds")}
                    row.update(metrics(tp) if tp and os.path.exists(tp)
                               else {"tools": None})
                    yield row


def main(argv):
    csv = "--csv" in argv
    paths = [a for a in argv if not a.startswith("--")]
    data = list(rows(paths))
    cols = ["stamp", "case", "arm", "score", "turns", "cost", "secs", "bash", "coa",
            "coa_err", "repeat3x"] + VERBS
    if csv:
        print(",".join(cols))
        for r in data:
            print(",".join("" if r.get(c) is None else str(r.get(c)) for c in cols))
        return 0
    hdr = ["STAMP", "ARM", "SCORE", "TURNS", "COST", "SECS", "BASH", "COA", "ERR", "LOOP"] \
          + [v.replace("coa ", "").replace("environments ", "env-")[:9] for v in VERBS]
    w = [12, 8, 6, 6, 6, 5, 5, 4, 4, 5] + [9] * len(VERBS)
    print("  ".join(h.ljust(x) for h, x in zip(hdr, w)))
    for r in data:
        if r.get("tools") is None:
            print(f"{r['stamp'][:12]:12}  {r['arm']:8}  (trace reaped -- rerun with --keep-temp)")
            continue
        vals = [r["stamp"][5:13], r["arm"], f"{r['score']:.2f}", r["turns"], r["cost"],
                r["secs"], r["bash"], r["coa"], r["coa_err"], r["repeat3x"]] \
               + [r[v] for v in VERBS]
        print("  ".join(str(v).ljust(x) for v, x in zip(vals, w)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
