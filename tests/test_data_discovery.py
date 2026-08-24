import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_cli import data_discovery


def _write_trial_result(
    root: Path,
    job_id: str,
    trial_name: str,
    task_path: str,
    reward: float | None,
    agent: str | None = None,
    model: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    exception_info=None,
) -> None:
    trial_dir = root / "data-discovery" / "jobs" / job_id / trial_name
    trial_dir.mkdir(parents=True)
    body = {
        "task_name": f"STABLE/{task_path}",
        "trial_name": trial_name,
        "task_id": {"path": task_path},
        "verifier_result": {"rewards": ({"reward": reward} if reward is not None else {})},
        "agent_info": {"name": agent} if agent else {},
        "config": {"agent": {"name": agent, "model_name": model}},
        "started_at": started_at,
        "finished_at": finished_at,
        "exception_info": exception_info,
    }
    (trial_dir / "result.json").write_text(json.dumps(body))


def _write_task_toml(root: Path, task_path: str, category: str | None, category_dir: str = "test-archive") -> None:
    """category_dir is the data-discovery/<category_dir>/ subdirectory the task
    physically lives in (see data_discovery.py's docstring on why tasks are
    nested one level into category subdirectories); category is the separate
    [metadata] category field a task.toml carries regardless of which
    subdirectory it's in."""
    task_dir = root / "data-discovery" / category_dir / task_path
    task_dir.mkdir(parents=True, exist_ok=True)
    lines = ['schema_version = "1.2"', "", "[metadata]"]
    if category is not None:
        lines.append(f'category = "{category}"')
    (task_dir / "task.toml").write_text("\n".join(lines))


def test_latest_run_id_picks_lexicographically_last(tmp_path):
    for job_id in ("2026-01-01__00-00-00", "2026-03-01__00-00-00", "2026-02-01__00-00-00"):
        (tmp_path / "data-discovery" / "jobs" / job_id).mkdir(parents=True)

    assert data_discovery.latest_run_id(tmp_path) == "2026-03-01__00-00-00"


def test_latest_run_id_none_when_no_jobs(tmp_path):
    assert data_discovery.latest_run_id(tmp_path) is None


def test_latest_run_id_collapses_category_suffixed_job_dirs(tmp_path):
    # A run whose tasks spanned categories produces one Harbor job per
    # category, named "<run_id>-<category>" -- latest_run_id() should
    # recognize these as one run and return just "<run_id>".
    (tmp_path / "data-discovery" / "alma-archive").mkdir(parents=True)
    (tmp_path / "data-discovery" / "astro-data-lab").mkdir(parents=True)
    for job_id in ("20260101-000000-alma-archive", "20260101-000000-astro-data-lab", "20251231-000000"):
        (tmp_path / "data-discovery" / "jobs" / job_id).mkdir(parents=True)

    assert data_discovery.latest_run_id(tmp_path) == "20260101-000000"


def test_available_tasks_discovers_tasks_nested_in_category_dirs(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="astro-data-lab")

    assert data_discovery.available_tasks(tmp_path) == ["task-a", "task-b"]


def test_task_dir_resolves_nested_task_path(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")

    assert data_discovery.task_dir(tmp_path, "task-a") == tmp_path / "data-discovery" / "alma-archive" / "task-a"


def test_task_dir_none_for_unknown_task(tmp_path):
    assert data_discovery.task_dir(tmp_path, "no-such-task") is None


def test_load_rows_normalizes_reward_to_percentage_and_reads_category(tmp_path):
    _write_trial_result(tmp_path, "job1", "datalab-NGC1068-deepest-gri__abc", "datalab-NGC1068-deepest-gri", 0.75)
    _write_task_toml(tmp_path, "datalab-NGC1068-deepest-gri", "data-query")

    rows = data_discovery.load_rows(tmp_path, "job1")

    assert len(rows) == 1
    row = rows[0]
    trial_dir = row.pop("trial_dir")
    assert trial_dir == str(tmp_path / "data-discovery" / "jobs" / "job1" / "datalab-NGC1068-deepest-gri__abc")
    assert row == {
        "suite": "data-discovery",
        "task_id": "datalab-NGC1068-deepest-gri",
        "category": "data-query",
        "trial": 1,
        "score_pct": 75.0,
        "agent": None,
        "model": None,
        "duration_s": None,
        "error": None,
    }


def test_load_rows_reads_agent_model_duration_and_error(tmp_path):
    _write_trial_result(
        tmp_path,
        "job1",
        "some-task__abc",
        "some-task",
        reward=0.0,
        agent="claude-code",
        model="anthropic/claude-sonnet-5",
        started_at="2026-08-21T12:00:00Z",
        finished_at="2026-08-21T12:01:30Z",
        exception_info="agent container crashed",
    )
    _write_task_toml(tmp_path, "some-task", "data-query")

    rows = data_discovery.load_rows(tmp_path, "job1")

    assert rows[0]["agent"] == "claude-code"
    assert rows[0]["model"] == "anthropic/claude-sonnet-5"
    assert rows[0]["duration_s"] == 90.0
    assert rows[0]["error"] == "agent container crashed"


def test_load_rows_aggregates_across_category_suffixed_job_dirs(tmp_path):
    # A run whose tasks spanned categories lands in jobs/myrun-<category>/ per
    # category (see run()'s docstring); load_rows() should combine them.
    _write_trial_result(tmp_path, "myrun-alma-archive", "task-a__aaa", "task-a", reward=1.0)
    _write_trial_result(tmp_path, "myrun-astro-data-lab", "task-b__bbb", "task-b", reward=0.5)
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="astro-data-lab")

    rows = data_discovery.load_rows(tmp_path, "myrun")

    assert {r["task_id"] for r in rows} == {"task-a", "task-b"}
    assert {r["score_pct"] for r in rows} == {100.0, 50.0}


def test_load_rows_numbers_repeat_trials_of_the_same_task_sequentially(tmp_path):
    _write_trial_result(tmp_path, "job1", "some-task__aaa", "some-task", reward=0.5)
    _write_trial_result(tmp_path, "job1", "some-task__bbb", "some-task", reward=1.0)
    _write_task_toml(tmp_path, "some-task", "data-query")

    rows = data_discovery.load_rows(tmp_path, "job1")

    assert [r["trial"] for r in rows] == [1, 2]


def test_instruction_reads_task_instruction_md(tmp_path):
    task_dir = tmp_path / "data-discovery" / "test-archive" / "some-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text('schema_version = "1.2"\n')
    (task_dir / "instruction.md").write_text("Find the thing.\n")

    assert data_discovery.instruction(tmp_path, "some-task") == "Find the thing."


def test_instruction_none_when_missing(tmp_path):
    assert data_discovery.instruction(tmp_path, "no-such-task") is None


def _write_test_outputs(task_dir: Path, body: str) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.toml").write_text('schema_version = "1.2"\n')
    tests_dir = task_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_outputs.py").write_text(body)


def test_grading_detail_combines_report_json_with_docstrings(tmp_path):
    task_dir = tmp_path / "data-discovery" / "test-archive" / "some-task"
    _write_test_outputs(
        task_dir,
        '''
def test_valid_json():
    """Check that the output is valid JSON."""
    pass


def test_no_docstring():
    pass
''',
    )
    trial_dir = tmp_path / "data-discovery" / "jobs" / "job1" / "some-task__abc"
    verifier_dir = trial_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    report = {
        "tests": [
            {"nodeid": "tests/test_outputs.py::test_valid_json", "outcome": "passed"},
            {"nodeid": "tests/test_outputs.py::test_no_docstring", "outcome": "failed"},
        ]
    }
    (verifier_dir / "report.json").write_text(json.dumps(report))

    detail = data_discovery.grading_detail(tmp_path, "some-task", str(trial_dir))

    assert detail == [
        {"id": "test_valid_json", "summary": "Check that the output is valid JSON.", "satisfied": True},
        {"id": "test_no_docstring", "summary": "", "satisfied": False},
    ]


def test_grading_detail_keeps_parametrize_suffix_in_id_but_not_docstring_lookup(tmp_path):
    task_dir = tmp_path / "data-discovery" / "test-archive" / "some-task"
    _write_test_outputs(
        task_dir,
        '''
def test_correct_urls(band):
    """Check that the URL for this band is correct."""
    pass
''',
    )
    trial_dir = tmp_path / "data-discovery" / "jobs" / "job1" / "some-task__abc"
    verifier_dir = trial_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    report = {
        "tests": [
            {"nodeid": "tests/test_outputs.py::test_correct_urls[g]", "outcome": "passed"},
            {"nodeid": "tests/test_outputs.py::test_correct_urls[r]", "outcome": "failed"},
        ]
    }
    (verifier_dir / "report.json").write_text(json.dumps(report))

    detail = data_discovery.grading_detail(tmp_path, "some-task", str(trial_dir))

    assert detail == [
        {"id": "test_correct_urls[g]", "summary": "Check that the URL for this band is correct.", "satisfied": True},
        {"id": "test_correct_urls[r]", "summary": "Check that the URL for this band is correct.", "satisfied": False},
    ]


def test_grading_detail_none_when_report_json_missing(tmp_path):
    trial_dir = tmp_path / "data-discovery" / "jobs" / "job1" / "some-task__abc"
    trial_dir.mkdir(parents=True)

    assert data_discovery.grading_detail(tmp_path, "some-task", str(trial_dir)) is None


def test_load_rows_falls_back_to_uncategorized_when_task_toml_has_no_category(tmp_path):
    _write_trial_result(tmp_path, "job1", "t__abc", "alma-VLA1623-observations", 0.5)
    _write_task_toml(tmp_path, "alma-VLA1623-observations", category=None)

    rows = data_discovery.load_rows(tmp_path, "job1")

    assert rows[0]["category"] == "uncategorized"


def test_load_rows_falls_back_to_uncategorized_when_task_toml_missing(tmp_path):
    _write_trial_result(tmp_path, "job1", "t__abc", "some-task", 0.5)
    # no task.toml written at all

    rows = data_discovery.load_rows(tmp_path, "job1")

    assert rows[0]["category"] == "uncategorized"


def test_load_rows_skips_trials_with_no_reward(tmp_path):
    _write_trial_result(tmp_path, "job1", "t__abc", "some-task", reward=None)
    _write_task_toml(tmp_path, "some-task", "data-query")

    rows = data_discovery.load_rows(tmp_path, "job1")

    assert rows == []


def test_load_rows_defaults_to_latest_job_when_run_id_omitted(tmp_path):
    _write_trial_result(tmp_path, "2026-01-01__00-00-00", "t__old", "old-task", 0.1)
    _write_trial_result(tmp_path, "2026-02-01__00-00-00", "t__new", "new-task", 0.9)
    _write_task_toml(tmp_path, "old-task", "data-query")
    _write_task_toml(tmp_path, "new-task", "data-query")

    rows = data_discovery.load_rows(tmp_path, None)

    assert [r["task_id"] for r in rows] == ["new-task"]


def test_load_rows_empty_when_no_job_exists(tmp_path):
    assert data_discovery.load_rows(tmp_path, None) == []


def test_group_tasks_by_category_single_category(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="alma-archive")

    groups = data_discovery._group_tasks_by_category(tmp_path, ["task-a", "task-b"])

    assert list(groups.keys()) == [tmp_path / "data-discovery" / "alma-archive"]
    assert groups[tmp_path / "data-discovery" / "alma-archive"] == ["task-a", "task-b"]


def test_group_tasks_by_category_splits_across_categories(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="astro-data-lab")

    groups = data_discovery._group_tasks_by_category(tmp_path, ["task-a", "task-b"])

    assert {d.name: ids for d, ids in groups.items()} == {
        "alma-archive": ["task-a"],
        "astro-data-lab": ["task-b"],
    }


def test_group_tasks_by_category_no_tasks_means_everything_grouped_skipping_empty_categories(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    (tmp_path / "data-discovery" / "cross-archive").mkdir(parents=True)  # empty category

    groups = data_discovery._group_tasks_by_category(tmp_path, [])

    assert {d.name: ids for d, ids in groups.items()} == {"alma-archive": ["task-a"]}


class _FakeProcess:
    """Stands in for subprocess.Popen -- records the command it was launched
    with, and .wait() returns a pre-set exit code instead of actually running
    anything."""

    def __init__(self, cmd, exit_code=0):
        self.cmd = cmd
        self._exit_code = exit_code

    def wait(self):
        return self._exit_code


def test_run_launches_one_process_per_category_with_job_name_suffixes(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="astro-data-lab")

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=_FakeProcess) as mock_popen,
    ):
        rc = data_discovery.run(tmp_path, [], None, None, "myrun", [])

    assert rc == 0
    assert mock_popen.call_count == 2  # one Harbor invocation per category, not one for the whole tree
    job_names = set()
    for call in mock_popen.call_args_list:
        cmd = call.args[0]
        job_names.add(cmd[cmd.index("--job-name") + 1])
    assert job_names == {"myrun-alma-archive", "myrun-astro-data-lab"}


def test_run_uses_plain_job_name_for_a_single_category_run(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=_FakeProcess) as mock_popen,
    ):
        rc = data_discovery.run(tmp_path, [], None, None, "myrun", [])

    assert rc == 0
    cmd = mock_popen.call_args_list[0].args[0]
    assert cmd[cmd.index("--job-name") + 1] == "myrun"  # no "-<category>" suffix needed for a single invocation


def test_run_launches_all_category_processes_before_waiting_on_any(tmp_path):
    """All per-category Harbor invocations should start before the wrapper blocks
    on any of them -- that's what actually gives a multi-category run back the
    cross-category parallelism a single flat invocation used to have for free."""
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="astro-data-lab")

    launched_before_any_wait = []

    class _OrderTrackingProcess(_FakeProcess):
        def wait(self):
            launched_before_any_wait.append(len(mock_popen.call_args_list))
            return super().wait()

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=_OrderTrackingProcess) as mock_popen,
    ):
        data_discovery.run(tmp_path, [], None, None, "myrun", [])

    # by the time the first process is wait()-ed on, both should already be launched
    assert launched_before_any_wait[0] == 2


def test_run_returns_the_worst_exit_code_across_categories(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")
    _write_task_toml(tmp_path, "task-b", "data-query", category_dir="astro-data-lab")

    exit_codes = {"alma-archive": 0, "astro-data-lab": 1}

    def fake_popen(cmd):
        job_name = cmd[cmd.index("--job-name") + 1]
        category = job_name.split("-", 1)[1]  # "myrun-<category>" -> "<category>"
        return _FakeProcess(cmd, exit_code=exit_codes[category])

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=fake_popen),
    ):
        rc = data_discovery.run(tmp_path, [], None, None, "myrun", [])

    assert rc == 1


def test_run_adds_temperature_workaround_for_terminus_2(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=_FakeProcess) as mock_popen,
    ):
        data_discovery.run(tmp_path, [], "terminus-2", None, "myrun", [])

    cmd = mock_popen.call_args_list[0].args[0]
    assert cmd[cmd.index("--ak") + 1] == "temperature=1"


def test_run_skips_temperature_workaround_for_other_agents(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=_FakeProcess) as mock_popen,
    ):
        data_discovery.run(tmp_path, [], "claude-code", None, "myrun", [])

    cmd = mock_popen.call_args_list[0].args[0]
    assert "--ak" not in cmd


def test_run_does_not_duplicate_a_user_supplied_temperature_kwarg(tmp_path):
    _write_task_toml(tmp_path, "task-a", "data-query", category_dir="alma-archive")

    with (
        patch.object(data_discovery, "_check_prerequisites", return_value=None),
        patch("benchmark_cli.data_discovery.subprocess.Popen", side_effect=_FakeProcess) as mock_popen,
    ):
        data_discovery.run(tmp_path, [], "terminus-2", None, "myrun", ["--ak", "temperature=0.5"])

    cmd = mock_popen.call_args_list[0].args[0]
    assert cmd.count("--ak") == 1
    assert cmd[cmd.index("--ak") + 1] == "temperature=0.5"
