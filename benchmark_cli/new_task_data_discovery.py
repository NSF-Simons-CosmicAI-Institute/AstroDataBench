"""Scaffold a new Data Discovery (Harbor) task from a template.

Mirrors domain-expertise/scripts/new_task.py so task creation feels the same
in both suites. Uses the simple pytest -> reward.txt verification pattern
(matching most existing tasks, e.g. astro-data-lab/NGC1068-deepest-gri) rather than
the reward-kit/judge.toml pattern -- see alma-HH212-observations-hard for a
worked example of that alternative if a task needs LLM-judge criteria instead
of (or alongside) programmatic pytest checks.
"""

from __future__ import annotations

import argparse
from pathlib import Path

_TASK_TOML = """\
schema_version = "1.2"
artifacts = ["/app/output.json"]

[task]
name = "STABLE/{id}"
description = "TODO: one-line description of what the agent must find/produce"
authors = []
keywords = []

[metadata] # metadata that isn't actually used in the running / grading
difficulty_explanation = "TODO: easy | medium | hard, and why"
category = "{category}"

[environment] # Used at build time (before the agent and verifier run) to set the container conditions
build_timeout_sec = 600.0
network_mode = "public"
os = "linux"
cpus = 1
memory_mb = 2048
storage_mb = 10240
gpus = 0
mcp_servers = []
ANTHROPIC_API_KEY = "${{ANTHROPIC_API_KEY}}"

[agent] # Controls sandbox conditions as the agent is running (overrides the environment baseline only during the agent's turn)
timeout_sec = 600.0
network_mode = "allowlist"
allowed_hosts = [
  # TODO: list the archive host(s) the agent needs, e.g. "datalab.noirlab.edu", "*datalab.noirlab.edu",
  "pypi.org", "files.pythonhosted.org",
]

[verifier] # Controls conditions for verification (test.sh)
timeout_sec = 600.0
network_mode = "allowlist"
allowed_hosts = [
  # TODO: list the archive host(s) the verifier needs to re-check the answer against, if any
]
"""

_INSTRUCTION_MD = """\
TODO: write the task prompt here -- what should the agent find or produce,
and from which archive?

Write your report to `/app/output.json` as a JSON object. Field names are up
to you, but document the expected shape here so `tests/test_outputs.py` can
check it.

You have internet access to TODO: archive name/host and PyPI. TODO: list any
packages already installed in the environment (see environment/Dockerfile).
"""

_DOCKERFILE = """\
FROM python:3.13-slim

WORKDIR /app

# TODO: pin the packages this task's solution/tests actually need
RUN pip install --no-cache-dir \\
    astroquery==0.4.11 \\
    astropy==8.0.0

RUN apt-get update && apt-get install -y --no-install-recommends curl jq \\
    && rm -rf /var/lib/apt/lists/*
"""

_SOLVE_SH = """\
#!/bin/bash
set -euo pipefail

# TODO: reference solution. Should query the archive live (not hardcode
# results) and write /app/output.json in the shape instruction.md describes.
python3 - <<'EOF'
import json

result = {}  # TODO

with open("/app/output.json", "w") as f:
    json.dump(result, f)
EOF
"""

_TEST_SH = """\
#!/bin/bash

# Use this file to install test dependencies and run the tests.
# It will be copied to /tests/test.sh and run from the working directory.

apt-get update
apt-get install -y curl
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
source $HOME/.local/bin/env

# TODO: add any `--with <package>==<version>` pins the tests need
uvx \\
  --with pytest==8.4.1 \\
  --with pytest-json-report \\
  --with astropy==8.0.0 \\
  --with astroquery==0.4.11 \\
  pytest /tests/test_outputs.py --json-report --json-report-file=/logs/verifier/report.json

python3 -c "
import json
report = json.load(open('/logs/verifier/report.json'))
passed = report['summary'].get('passed', 0)
total = report['summary']['total']
print(passed / total if total else 0)
" > /logs/verifier/reward.txt
"""

_TEST_OUTPUTS_PY = """\
\"\"\"Verify /app/output.json against ground truth re-queried live from the
archive, rather than hardcoded expected values (so the check stays correct
if the archive's holdings change).\"\"\"

import json


def _load_output():
    with open("/app/output.json") as f:
        return json.load(f)


def test_output_file_exists():
    \"\"\"Check that the agent wrote /app/output.json\"\"\"
    _load_output()  # raises if missing/invalid JSON


def test_output_shape():
    \"\"\"Check that the output has the fields instruction.md promises\"\"\"
    # TODO: assert the fields instruction.md promises are present
    output = _load_output()
    assert output  # placeholder


# TODO: add tests that re-query the archive live and check the agent's answer
# against it -- see data-discovery/astro-data-lab/NGC1068-deepest-gri/tests/test_outputs.py
# for a worked example of this pattern.
"""

_GITIGNORE = """\
.git/
.DS_Store
__pycache__/
*.pyc
*.egg-info/
.venv/
.pytest_cache/
.env
dist.tar.gz
"""

_README = "# STABLE/{id}\n"


def main(root: Path, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark.py new-task --suite data-discovery",
        description="Scaffold a new Data Discovery (Harbor) task from a template.",
    )
    parser.add_argument(
        "--id",
        required=True,
        help="Unique task id (just the target/subject, no archive prefix -- that's what "
        "--category and the directory it lands in are for), e.g. NGC253-continuum",
    )
    parser.add_argument(
        "--category",
        required=True,
        help="Which archive(s) the task queries, and the data-discovery/ subdirectory it's "
        "scaffolded into: 'alma-archive' (ALMA Science Archive only), 'astro-data-lab' "
        "(NOIRLab Astro Data Lab only), or 'cross-archive' (spans both). Not a strict enum, "
        "but keep new tasks on this taxonomy unless there's a real reason not to.",
    )
    args = parser.parse_args(argv)

    out_dir = root / "data-discovery" / args.category / args.id
    if out_dir.exists():
        print(f"Refusing to overwrite existing task directory: {out_dir}")
        return 1

    (out_dir / "environment").mkdir(parents=True)
    (out_dir / "solution").mkdir(parents=True)
    (out_dir / "tests").mkdir(parents=True)

    (out_dir / "task.toml").write_text(_TASK_TOML.format(id=args.id, category=args.category))
    (out_dir / "instruction.md").write_text(_INSTRUCTION_MD)
    (out_dir / "environment" / "Dockerfile").write_text(_DOCKERFILE)
    (out_dir / "solution" / "solve.sh").write_text(_SOLVE_SH)
    (out_dir / "tests" / "test.sh").write_text(_TEST_SH)
    (out_dir / "tests" / "test_outputs.py").write_text(_TEST_OUTPUTS_PY)
    (out_dir / ".gitignore").write_text(_GITIGNORE)
    (out_dir / "README.md").write_text(_README.format(id=args.id))

    print(f"Created {out_dir}")
    print("Fill in the TODOs in task.toml, instruction.md, solution/solve.sh, and tests/test_outputs.py.")
    return 0
