#!/usr/bin/env python3
"""Render a `claude plugin eval` result as a pull request comment (Markdown).

Reads aggregate-result.json, adds the effort metrics from trace-metrics.py
(read them while the --keep-temp traces still exist), and prints Markdown.

Usage:
    pr-comment.py RESULT.json [--pr N] [--head SHA] [--base SHA] [--run-url URL]
                  [--redact-env VAR ...]

This repository is public and the comment is too. The comment carries scores,
counts and grader names only. Grader explanations are shown for failures, cut
short, with the value of every --redact-env variable masked, because an LLM
grader's explanation can quote the agent's output.
"""
import argparse, importlib.util, json, os, sys

MARKER = "<!-- coalesce-plugin-eval -->"
HERE = os.path.dirname(os.path.abspath(__file__))


def load_trace_metrics():
    # The sibling's filename has a hyphen, so it cannot be imported by name.
    # No __pycache__ next to it: CI checks the tree is clean.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("trace_metrics", os.path.join(HERE, "trace-metrics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def redactor(var_names):
    secrets = [os.environ[v] for v in var_names if len(os.environ.get(v, "")) >= 4]
    secrets.sort(key=len, reverse=True)

    def redact(text):
        for s in secrets:
            text = text.replace(s, "***")
        return text
    return redact


def fmt_score(x):
    return "n/a" if x is None else f"{x:.2f}"


def fmt_delta(x):
    return "n/a" if x is None else f"{x:+.2f}"


def one_line(text, limit=160):
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render(agg, args, tm, redact):
    out = [MARKER]
    title = "### Plugin eval"
    if args.pr:
        title += f": PR #{args.pr}"
    out.append(title)
    out.append("")

    suite = agg.get("suite", {})
    plugin = (suite.get("plugins") or [{}])[0]
    facts = []
    if args.head:
        facts.append(f"PR head `{args.head[:7]}`")
    if args.base:
        facts.append(f"merged into develop `{args.base[:7]}`")
    facts.append(f"plugin `{plugin.get('version', '?')}`")
    facts.append(f"Claude Code `{agg.get('claudeVersion', '?')}`")
    facts.append(f"judge `{suite.get('judgeModel', '?')}`")
    out.append(" · ".join(facts))
    total = agg.get("aggregates", {})
    secs = agg.get("durationSeconds") or 0
    took = f"{secs}s" if secs < 60 else f"{round(secs / 60)} min"
    out.append(
        f"**{total.get('casesPassed', 0)}/{total.get('casesTotal', 0)} cases passed** · "
        f"mean Δ **{fmt_delta(total.get('meanDelta'))}** · "
        f"${agg.get('costUsd') or 0:.2f} · {took}"
        + (" · **partial run (cost ceiling hit)**" if agg.get("partial") else "")
    )
    out.append("")

    # Effort metrics per (case, arm, run index), from the kept traces.
    effort = {}
    for r in tm.rows([args.result]):
        effort[(r["case"], r["arm"], r["run"])] = r

    for case in agg.get("cases", []):
        a = case.get("aggregates", {})
        out.append(f"#### `{case['name']}`")
        out.append(
            f"with plugin **{fmt_score(a.get('score'))}** · without **{fmt_score(a.get('scoreWithout'))}** · "
            f"Δ **{fmt_delta(a.get('delta'))}**"
        )
        out.append("")
        out.append("| arm | run | score | turns | cost | bash | coa | coa errors | coa describe | repeated 3x+ |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        failures = []
        for arm, runs in (case.get("arms") or {}).items():
            for i, run in enumerate(runs):
                e = effort.get((case["name"], arm, i), {})
                have = e.get("tools") is not None
                cell = (lambda k: str(e.get(k))) if have else (lambda k: "–")
                out.append(
                    f"| {arm} | {i + 1} | {fmt_score(run.get('score'))} | {run.get('turns', '–')} | "
                    f"${run.get('costUsd') or 0:.2f} | {cell('bash')} | {cell('coa')} | {cell('coa_err')} | "
                    f"{cell('coa describe')} | {cell('repeat3x')} |"
                )
                if run.get("error"):
                    failures.append(f"- **{arm} run {i + 1}** errored: {one_line(redact(str(run['error'])))}")
                for g in run.get("graders", []):
                    if g.get("scored", True) and not g.get("passed"):
                        failures.append(
                            f"- **{arm} run {i + 1}** ✗ `{g['name']}`: {one_line(redact(g.get('explanation', '')))}"
                        )
        out.append("")
        if failures:
            out.append(f"<details><summary>{len(failures)} failed grader(s)</summary>")
            out.append("")
            out.extend(failures)
            out.append("")
            out.append("</details>")
            out.append("")

    out.append(
        "Scores saturate on the live case, so read effort too: fewer `coa` calls, errors and "
        "`coa describe` lookups in the *with* arm is the plugin helping. See EVALS.md."
    )
    if any("live" in (c.get("tags") or []) or c["name"].startswith("01-") for c in agg.get("cases", [])):
        out.append("")
        out.append("> Live runs create a cloud Environment that nothing deletes. Clean it up by hand.")
    if args.run_url:
        out.append("")
        out.append(f"[Workflow run and full report]({args.run_url})")
    return "\n".join(out) + "\n"


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("result")
    p.add_argument("--pr")
    p.add_argument("--head")
    p.add_argument("--base")
    p.add_argument("--run-url")
    p.add_argument("--redact-env", nargs="*", default=[])
    args = p.parse_args(argv)
    with open(args.result) as fh:
        agg = json.load(fh)
    sys.stdout.write(render(agg, args, load_trace_metrics(), redactor(args.redact_env)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
