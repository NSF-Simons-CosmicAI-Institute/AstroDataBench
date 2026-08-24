#!/usr/bin/env python3
"""
Tools for running, creating, and reporting tasks in both the Data Discovery and Domain Expertise suites.

    ./benchmark.py run --suite domain-expertise [--filter category=optical] [--model ...] [--judge-model ...] [--trials N]
    ./benchmark.py run --suite data-discovery [--tasks HH212 ...] [--agent ...] [--model ...]
    ./benchmark.py run --all                       # both suites, defaults, sequentially
    ./benchmark.py report [--run-id ...] [--suite ...] [--pdf] [--task-pdfs]  # compiled cross-suite table
    ./benchmark.py new-task --suite domain-expertise --id ... --category ...
    ./benchmark.py new-task --suite data-discovery --id ... --category ...

NOTE: This is a thin wrapper, and each suite runs through its own tooling. See domain-expertise/README.md
and data-discovery/README.md for what each suite tests and how it's graded.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from benchmark_cli import compile_report, data_discovery, domain_expertise  # noqa: E402


def cmd_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.py run")
    parser.add_argument("--suite", choices=["domain-expertise", "data-discovery"])
    parser.add_argument("--all", action="store_true", help="Run both suites with default settings")
    parser.add_argument(
        "--model",
        help="Model id. domain-expertise: bare id (e.g. claude-sonnet-5). "
        "data-discovery: provider/model_name (e.g. anthropic/claude-sonnet-5)",
    )
    # domain-expertise-specific
    parser.add_argument("--filter", help="e.g. category=optical or id=<task_id> (domain-expertise only)")
    parser.add_argument("--judge-model", help="Judge model id (domain-expertise only)")
    parser.add_argument("--trials", default="1", help="Trials per task (domain-expertise only)")
    parser.add_argument("--run-id", help="Run identifier, for either suite (default: current UTC timestamp)")
    # data-discovery-specific
    parser.add_argument("--tasks", nargs="+", help="Task directory name(s) under data-discovery/ (data-discovery only)")
    parser.add_argument("--agent", help="Harbor agent to run, e.g. oracle, claude-code (data-discovery only)")
    parser.add_argument(
        "--harbor-arg",
        action="append",
        default=[],
        help="Extra raw arg to pass through to `harbor run`, repeatable (data-discovery only). "
        "Use this for any Harbor flag this wrapper doesn't otherwise expose.",
    )
    args = parser.parse_args(argv)

    if args.all and args.suite:
        parser.error("pass either --suite or --all, not both")
    if not args.all and not args.suite:
        parser.error("pass --suite <name> or --all")

    if args.all:
        de_code = _run_domain_expertise(args)
        dd_code = _run_data_discovery(args)
        return de_code or dd_code

    if args.suite == "domain-expertise":
        return _run_domain_expertise(args)
    return _run_data_discovery(args)


def _run_domain_expertise(args: argparse.Namespace) -> int:
    forwarded = []
    if args.model:
        forwarded += ["--model", args.model]
    if getattr(args, "filter", None):
        forwarded += ["--filter", args.filter]
    if getattr(args, "judge_model", None):
        forwarded += ["--judge-model", args.judge_model]
    if getattr(args, "trials", None):
        forwarded += ["--trials", args.trials]
    if getattr(args, "run_id", None):
        forwarded += ["--run-id", args.run_id]
    return domain_expertise.run(ROOT, forwarded)


def _run_data_discovery(args: argparse.Namespace) -> int:
    tasks = getattr(args, "tasks", None) or []
    return data_discovery.run(
        ROOT,
        tasks,
        getattr(args, "agent", None),
        args.model,
        getattr(args, "run_id", None),
        getattr(args, "harbor_arg", []),
    )


def cmd_report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.py report")
    parser.add_argument("--run-id", help="Name for the compiled report directory under runs/ (default: timestamp)")
    parser.add_argument("--domain-expertise-run-id", help="Which domain-expertise run to pull (default: latest)")
    parser.add_argument("--data-discovery-run-id", help="Which data-discovery job to pull (default: latest)")
    parser.add_argument(
        "--suite",
        choices=["domain-expertise", "data-discovery", "all"],
        help="Only show/report this suite's results (default, and same as 'all': both)",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also render summary.pdf: a compiled overview of every task in the run "
        "(same fields as summary.md's table), styled like the domain-expertise PDF reports "
        "(uses domain-expertise/.venv's markdown+xhtml2pdf, set up on first use)",
    )
    parser.add_argument(
        "--task-pdfs",
        action="store_true",
        help="Also render one detailed PDF per (task, trial) under runs/<run-id>/pdf/, for both suites -- "
        "prompt/checklist for domain-expertise, metadata/instruction/per-test grading for data-discovery. "
        "Neither suite makes these automatically during `run` (domain-expertise only writes the underlying "
        "markdown report there); PDFs are rendered here, on demand, using domain-expertise/.venv's "
        "markdown+xhtml2pdf (set up on first use). Respects --suite, same as the rest of this command.",
    )
    args = parser.parse_args(argv)

    suite_filter = None if args.suite in (None, "all") else args.suite
    rows = compile_report.compile_rows(ROOT, args.domain_expertise_run_id, args.data_discovery_run_id)
    suites = (suite_filter,) if suite_filter else ("domain-expertise", "data-discovery")
    if suite_filter:
        rows = [r for r in rows if r["suite"] == suite_filter]
    if not rows:
        print("No results found in either suite yet -- run something first with `benchmark.py run`.", file=sys.stderr)
        return 1

    csv_path, md_path = compile_report.write_report(ROOT, rows, args.run_id, suites=suites)
    print(md_path.read_text())
    print(f"(also wrote {csv_path})", file=sys.stderr)

    run_id = md_path.parent.name

    if args.pdf:
        pdf_source_path = compile_report.write_pdf_source(ROOT, rows, run_id, suites)
        pdf_path = md_path.with_suffix(".pdf")
        domain_expertise.render_markdown_pdf(ROOT, pdf_source_path, pdf_path)
        pdf_source_path.unlink()
        print(f"(also wrote {pdf_path})", file=sys.stderr)

    if args.task_pdfs:
        pdf_dir = ROOT / "runs" / run_id / "pdf"

        if "data-discovery" in suites:
            dd_rows = [r for r in rows if r["suite"] == "data-discovery"]
            if not dd_rows:
                print("(--task-pdfs: no data-discovery rows in this report, nothing to render)", file=sys.stderr)
            for pdf_path in compile_report.write_task_pdfs(ROOT, dd_rows, run_id):
                print(f"(also wrote {pdf_path})", file=sys.stderr)

        if "domain-expertise" in suites:
            de_run_id = args.domain_expertise_run_id or domain_expertise.latest_run_id(ROOT)
            rendered = domain_expertise.render_task_pdfs(ROOT, de_run_id, pdf_dir) if de_run_id else []
            if not rendered:
                print(
                    "(--task-pdfs: no domain-expertise results found -- "
                    "run `benchmark.py run --suite domain-expertise` first)",
                    file=sys.stderr,
                )
            for pdf_path in rendered:
                print(f"(also wrote {pdf_path})", file=sys.stderr)

    return 0


def cmd_new_task(argv: list[str]) -> int:
    # --suite is pulled out manually rather than via argparse so the *rest* of
    # argv can be forwarded verbatim to each suite's own scaffolder (which
    # already has its own argparse parser, e.g. --id/--category) instead of
    # being re-parsed and re-serialized here.
    if "--suite" not in argv:
        print("usage: benchmark.py new-task --suite {domain-expertise,data-discovery} [suite-specific args]", file=sys.stderr)
        return 1
    idx = argv.index("--suite")
    try:
        suite = argv[idx + 1]
    except IndexError:
        print("--suite requires a value", file=sys.stderr)
        return 1
    remainder = argv[:idx] + argv[idx + 2 :]

    if suite == "domain-expertise":
        return domain_expertise.new_task(ROOT, remainder)
    if suite == "data-discovery":
        return data_discovery.new_task(ROOT, remainder)
    print(f"Unknown suite: {suite!r} (expected domain-expertise or data-discovery)", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0

    command, rest = sys.argv[1], sys.argv[2:]
    if command == "run":
        return cmd_run(rest)
    if command == "report":
        return cmd_report(rest)
    if command == "new-task":
        return cmd_new_task(rest)

    print(f"Unknown command: {command!r}\n\n{__doc__}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
