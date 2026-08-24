"""Data Discovery suite: invoke Harbor (https://www.harborframework.com), and
normalize its job output for the cross-suite compiled report.

Tasks live in category subdirectories (data-discovery/<category>/<task_id>/,
e.g. data-discovery/alma-archive/HH212/) rather than directly under
data-discovery/. Harbor's own task discovery under `--path <dir>` only looks
one level deep (verified against the installed harbor==0.6.1 source,
harbor/models/job/config.py's _get_local_task_configs uses a plain
`self.path.iterdir()`, no recursion) -- so a run spanning more than one
category needs one Harbor invocation per category, not one pointed at all of
data-discovery/. See run()'s docstring for how that's handled.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SUITE_DIR_NAME = "data-discovery"
_CATEGORY_RE = re.compile(r'category\s*=\s*"([^"]*)"')


def suite_dir(root: Path) -> Path:
    return root / SUITE_DIR_NAME


def jobs_dir(root: Path) -> Path:
    return suite_dir(root) / "jobs"


def _category_dirs(root: Path) -> list[Path]:
    """Category subdirectories under data-discovery/ (e.g. alma-archive,
    astro-data-lab, cross-archive) -- anything there except jobs/ and dotfiles,
    discovered from disk rather than a hardcoded list so a new category needs
    no code change. An empty category dir (no tasks yet) is still included;
    callers that need tasks filter it out naturally since it has none."""
    sdir = suite_dir(root)
    if not sdir.exists():
        return []
    return sorted(
        p for p in sdir.iterdir() if p.is_dir() and p.name != "jobs" and not p.name.startswith(".")
    )


def task_dir(root: Path, task_id: str) -> Path | None:
    """Resolve a task id (its leaf directory name, e.g. "HH212") to its actual
    path under data-discovery/<category>/<task_id>/. None if no category
    subdirectory has a task by that name."""
    for cat_dir in _category_dirs(root):
        candidate = cat_dir / task_id
        if (candidate / "task.toml").exists():
            return candidate
    return None


def _check_prerequisites() -> str | None:
    """Return a user-facing error message if Docker or `harbor` aren't
    available, else None. Checked up front so a missing prerequisite fails
    fast with a clear message instead of a cryptic error partway through a
    container build."""
    if shutil.which("harbor") is None:
        return (
            "Harbor is not installed or not on PATH.\n"
            "See data-discovery/README.md for setup instructions."
        )
    docker_check = subprocess.run(["docker", "info"], capture_output=True)
    if docker_check.returncode != 0:
        return "Docker doesn't appear to be running. Start Docker and try again."
    return None


def _has_agent_kwarg(extra_harbor_args: list[str], key: str) -> bool:
    """Whether extra_harbor_args already sets a given --ak/--agent-kwarg key
    (e.g. "temperature"), so an automatic default doesn't clobber/duplicate one
    the user explicitly passed themselves."""
    for i, arg in enumerate(extra_harbor_args):
        if arg in ("--ak", "--agent-kwarg") and i + 1 < len(extra_harbor_args):
            if extra_harbor_args[i + 1].split("=", 1)[0] == key:
                return True
    return False


def available_tasks(root: Path) -> list[str]:
    """Task ids (leaf directory names) that actually exist right now, across
    every category subdirectory -- discovered from disk on every call, not
    cached or hardcoded, so a deleted/renamed/added task is picked up
    immediately."""
    return sorted(p.parent.name for cat_dir in _category_dirs(root) for p in cat_dir.glob("*/task.toml"))


def run(
    root: Path,
    tasks: list[str],
    agent: str | None,
    model: str | None,
    run_id: str | None,
    extra_harbor_args: list[str],
) -> int:
    """Invoke Harbor against one or more Data Discovery tasks.

    Verified against a live `harbor==0.6.1` install (`harbor run --help`):
    --path, --jobs-dir, --include-task-name, --agent, --model, and --job-name
    are all real flags. Two things learned the hard way from earlier bugs:
      - `--include-task-name` doesn't match this repo's "STABLE/<dir>"
        task.toml [task] name field, only the bare directory name -- so a
        single requested task always points --path directly at that task's
        own directory instead (no name-matching involved at all, can't have
        this class of bug); multiple tasks within the same category fall back
        to --include-task-name with bare directory names.
      - Harbor's task discovery under --path only looks one directory level
        deep (see module docstring), and a second `harbor run` with the same
        --job-name but a *different* --path raises FileExistsError rather
        than merging (verified against harbor/job.py's resume-config check) --
        so a run spanning more than one category subdirectory needs one
        Harbor invocation per category, each with its own --job-name. Those
        share the base run_id as a prefix (<run_id>-<category>) so
        latest_run_id()/load_rows() can find and combine them back into one
        logical run; a single-category run keeps the plain <run_id> name,
        unchanged from before. Per-category invocations are launched
        concurrently (not one after another) so a multi-category run doesn't
        lose the parallelism Harbor's own --n-concurrent (default 4) would
        otherwise give a single invocation -- tasks in different categories
        used to be able to overlap within one `harbor run` before tasks were
        split into category subdirectories, and this keeps that true.
      - `--agent terminus-2` gets `--ak temperature=1` added automatically
        unless the caller already passed their own `--ak temperature=...` via
        extra_harbor_args. Harbor's bundled terminus-2 (0.6.1) hardcodes
        temperature=0.7 unconditionally, which Anthropic rejects outright for
        Claude 4.6-family models (extended thinking requires temperature to be
        1 or omitted) -- a real bug in Harbor's agent plus litellm's stale
        supported-params list for that model family, not something fixable in
        this repo, so it's patched around here instead of just failing.

    Every requested name is validated against what's actually on disk before
    Harbor is invoked at all, so a stale/deleted task name fails immediately
    with a real, current task list instead of Harbor's own error.
    """
    existing = available_tasks(root)
    unknown = [t for t in tasks if t not in existing]
    if unknown:
        print(f"Unknown task(s): {unknown}", file=sys.stderr)
        print(f"Tasks that actually exist in data-discovery/: {existing}", file=sys.stderr)
        return 1

    problem = _check_prerequisites()
    if problem:
        print(problem, file=sys.stderr)
        return 1

    groups = _group_tasks_by_category(root, tasks)
    if not groups:
        print("No tasks to run.", file=sys.stderr)
        return 1

    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    multi_category = len(groups) > 1

    commands = []
    for cat_dir, task_ids in sorted(groups.items(), key=lambda kv: kv[0].name):
        all_in_category = sorted(p.parent.name for p in cat_dir.glob("*/task.toml"))
        if len(task_ids) == 1:
            path = cat_dir / task_ids[0]
            name_filters: list[str] = []
        elif set(task_ids) == set(all_in_category):
            path = cat_dir
            name_filters = []
        else:
            path = cat_dir
            name_filters = task_ids

        job_name = f"{run_id}-{cat_dir.name}" if multi_category else run_id

        # --yes auto-confirms Harbor's environment-access prompt so this runs
        # non-interactively; it does not affect sharing, which stays off unless
        # --share-org/--share-user are explicitly passed via extra_harbor_args.
        cmd = ["harbor", "run", "--path", str(path), "--jobs-dir", str(jobs_dir(root)), "--yes"]
        for name in name_filters:
            cmd += ["--include-task-name", name]
        if agent:
            cmd += ["--agent", agent]
        if model:
            cmd += ["--model", model]
        if agent == "terminus-2" and not _has_agent_kwarg(extra_harbor_args, "temperature"):
            # Harbor's bundled terminus-2 agent (0.6.1) hardcodes temperature=0.7
            # unconditionally; Anthropic rejects any non-1 temperature for
            # Claude 4.6-family models once extended thinking is in play (which
            # it always is for that family), so a plain `--agent terminus-2` run
            # fails outright with "`temperature` is deprecated for this model."
            # This is a real bug in Harbor's agent + litellm's stale supported-
            # params list for that model family, not something this repo
            # controls -- worked around here so it doesn't just fail. Pass your
            # own `--harbor-arg --ak --harbor-arg temperature=<value>` to override.
            cmd += ["--ak", "temperature=1"]
        cmd += ["--job-name", job_name]
        cmd += extra_harbor_args
        commands.append(cmd)

    # Launched concurrently (Popen, not subprocess.run) rather than one after
    # another -- see the docstring above. Each still streams straight to this
    # process's stdout/stderr, so with more than one category involved their
    # output interleaves; that's the same trade-off Harbor's own
    # --n-concurrent already makes for concurrent trials within one invocation.
    for cmd in commands:
        print("Running:", " ".join(cmd), file=sys.stderr)
    processes = [subprocess.Popen(cmd) for cmd in commands]
    exit_codes = [p.wait() for p in processes]

    return max(exit_codes)


def _group_tasks_by_category(root: Path, tasks: list[str]) -> dict[Path, list[str]]:
    """Requested task ids grouped by their category directory (empty `tasks`
    means "run everything", grouped the same way, skipping categories with no
    tasks in them yet -- e.g. an empty cross-archive/)."""
    if tasks:
        groups: dict[Path, list[str]] = {}
        for t in tasks:
            cat_dir = task_dir(root, t).parent
            groups.setdefault(cat_dir, []).append(t)
        return groups

    groups = {}
    for cat_dir in _category_dirs(root):
        task_ids = sorted(p.parent.name for p in cat_dir.glob("*/task.toml"))
        if task_ids:
            groups[cat_dir] = task_ids
    return groups


def new_task(root: Path, args: list[str]) -> int:
    from benchmark_cli.new_task_data_discovery import main as scaffold_main

    return scaffold_main(root, args)


def _job_dirs_for_run(root: Path, run_id: str) -> list[Path]:
    """All job-name directories belonging to one wrapper "run": either a
    single jobs/<run_id>/ (a run whose tasks were all in one category) or
    several jobs/<run_id>-<category>/ (a run whose tasks spanned categories --
    see run()'s docstring for why that needs multiple Harbor job names)."""
    jdir = jobs_dir(root)
    if not jdir.exists():
        return []
    exact = jdir / run_id
    dirs = [exact] if exact.is_dir() else []
    dirs += sorted(p for p in jdir.iterdir() if p.is_dir() and p.name.startswith(f"{run_id}-"))
    return dirs


def _strip_category_suffix(root: Path, job_dir_name: str) -> str:
    """"<run_id>-<category>" -> "<run_id>", for a real category name currently
    on disk; a plain "<run_id>" (single-category run) is returned unchanged."""
    for cat_dir in _category_dirs(root):
        suffix = f"-{cat_dir.name}"
        if job_dir_name.endswith(suffix):
            return job_dir_name[: -len(suffix)]
    return job_dir_name


def latest_run_id(root: Path) -> str | None:
    """The most recent base run id. jobs/<run_id>-<category>/ variants (see
    run()'s docstring) are collapsed back to their shared <run_id> prefix so a
    run whose tasks spanned categories is still recognized as one run rather
    than several unrelated ones."""
    jdir = jobs_dir(root)
    if not jdir.exists():
        return None
    base_ids = {_strip_category_suffix(root, p.name) for p in jdir.iterdir() if p.is_dir()}
    return sorted(base_ids)[-1] if base_ids else None


def _task_category(root: Path, task_dir_name: str) -> str:
    d = task_dir(root, task_dir_name)
    task_toml = d / "task.toml" if d else None
    if not task_toml or not task_toml.exists():
        return "uncategorized"
    match = _CATEGORY_RE.search(task_toml.read_text())
    return match.group(1) if match else "uncategorized"


def load_rows(root: Path, run_id: str | None) -> list[dict]:
    """Normalized rows for the compiled report: one per trial, scored 0-100.
    Returns [] if this suite has no matching job rather than raising -- the
    compiled report is meant to work even when only one suite has run."""
    resolved_run_id = run_id or latest_run_id(root)
    if resolved_run_id is None:
        return []

    job_dirs = _job_dirs_for_run(root, resolved_run_id)
    if not job_dirs:
        return []

    rows = []
    trial_counts: dict[str, int] = {}
    for job_dir in job_dirs:
        for result_path in sorted(job_dir.glob("*/result.json")):
            try:
                data = json.loads(result_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            task_id = (data.get("task_id") or {}).get("path")
            if not task_id:
                task_name = data.get("task_name", "")
                task_id = task_name.split("/", 1)[-1] if task_name else result_path.parent.name
            task_id = Path(task_id).name  # task_id.path is an absolute filesystem path; keep just the task dir name

            reward = ((data.get("verifier_result") or {}).get("rewards") or {}).get("reward")
            if reward is None:
                continue  # verifier didn't run or produced no reward for this trial

            # Harbor's own trial_name is task_id + a random suffix, not a sequential
            # attempt number, so number attempts ourselves in the order their result
            # dirs sort -- stable, and matches how -k/--n-attempts reruns show up.
            trial_counts[task_id] = trial_counts.get(task_id, 0) + 1
            trial = trial_counts[task_id]

            agent_info = data.get("agent_info") or {}
            agent_cfg = ((data.get("config") or {}).get("agent")) or {}
            exception_info = data.get("exception_info")

            started_at = data.get("started_at")
            finished_at = data.get("finished_at")
            duration_s = None
            if started_at and finished_at:
                try:
                    # fromisoformat() only accepts "Z" as UTC on Python 3.11+; normalize it
                    # to "+00:00" so this also works on the older python3 that ./benchmark.py
                    # (no venv of its own) might be invoked with.
                    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                    duration_s = round((end - start).total_seconds(), 1)
                except ValueError:
                    pass

            rows.append(
                {
                    "suite": "data-discovery",
                    "task_id": task_id,
                    "category": _task_category(root, task_id),
                    "trial": trial,
                    "score_pct": round(reward * 100, 1),
                    "agent": agent_info.get("name") or agent_cfg.get("name"),
                    "model": agent_cfg.get("model_name"),
                    "duration_s": duration_s,
                    "error": _short_error(exception_info),
                    "trial_dir": str(result_path.parent),
                }
            )
    return rows


_SENTENCE_END = re.compile(r"[.?!](?=\s|$)")


def _first_sentence(text: str) -> str:
    """Just the first sentence of a test's docstring, so a long multi-line
    docstring doesn't blow up the Grading table's Summary column -- mirrors
    domain-expertise/dkqa/markdown_report.py's _first_sentence() for rubric
    descriptions."""
    text = " ".join(text.split())
    match = _SENTENCE_END.search(text)
    return text[: match.end()].strip() if match else text.strip()


def _test_docstrings(task_dir: Path) -> dict[str, str]:
    """{test function name: first sentence of its docstring} for every top-level
    test_* function in tests/test_outputs.py, via Python's ast module rather than
    importing/running the file (its imports -- astropy, pyvo, etc. -- aren't
    installed outside the task's own container). A test with no docstring is
    just omitted; the caller falls back to showing no summary for it."""
    test_file = task_dir / "tests" / "test_outputs.py"
    if not test_file.exists():
        return {}
    try:
        tree = ast.parse(test_file.read_text())
    except SyntaxError:
        return {}
    docstrings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            doc = ast.get_docstring(node)
            if doc:
                docstrings[node.name] = _first_sentence(doc)
    return docstrings


def instruction(root: Path, task_id: str) -> str | None:
    """A task's instruction.md content, for the report's Prompt section. None if
    the task (or its instruction.md) no longer exists on disk."""
    d = task_dir(root, task_id)
    if d is None:
        return None
    path = d / "instruction.md"
    return path.read_text().strip() if path.exists() else None


def grading_detail(root: Path, task_id: str, trial_dir: str) -> list[dict] | None:
    """Per-test [{"id", "summary", "satisfied"}, ...] for one trial, combining
    <trial_dir>/verifier/report.json (pytest-json-report output; test.sh writes
    it there specifically so Harbor persists it alongside reward.txt -- see
    data-discovery/README.md) with each test's own docstring (pytest-json-report
    doesn't carry docstrings, so those come from _test_docstrings() instead).
    Returns None if report.json isn't present -- e.g. a job run before test.sh
    started writing it there, so callers should render no Grading section
    rather than an empty one."""
    report_path = Path(trial_dir) / "verifier" / "report.json"
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    d = task_dir(root, task_id)
    docstrings = _test_docstrings(d) if d else {}
    detail = []
    for test in report.get("tests", []):
        nodeid = test.get("nodeid", "")
        full_name = nodeid.split("::")[-1] or nodeid  # e.g. "test_correct_urls[r]" for a parametrized test
        base_name = full_name.split("[")[0]  # docstrings are keyed by the function name, not each parametrized id
        detail.append(
            {
                "id": full_name,
                "summary": docstrings.get(base_name, ""),
                "satisfied": test.get("outcome") == "passed",
            }
        )
    return detail


def _short_error(exception_info) -> str | None:
    """A one-line summary of a trial's exception_info, or None if it didn't error.
    exception_info's exact shape isn't pinned down by Harbor's public docs, so this
    stays defensive rather than assuming a specific structure."""
    if not exception_info:
        return None
    if isinstance(exception_info, str):
        return exception_info.splitlines()[0]
    if isinstance(exception_info, dict):
        msg = exception_info.get("message") or exception_info.get("error") or str(exception_info)
        return str(msg).splitlines()[0]
    return str(exception_info).splitlines()[0]
