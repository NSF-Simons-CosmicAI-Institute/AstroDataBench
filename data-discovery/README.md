# Data Discovery

Data discovery tasks test whether an LLM can write and execute query code to find data an astronomer wants across NOIRLab's Astro Data Lab platform and the ALMA Science Archive. These tasks assess how well an LLM can accomplish things such as...

- Writing and executing archive-specific queries for a request.
- Summarizing available sources and observations.
- Recognizing when data are unavailable (nonexistent, proprietary, or failed quality assurance checks).


Each task creates a docker container with archive access, the agent writes and runs code inside it, and a `tests/test.sh` script grades the result programmatically (performing a new archive query and checking the agent's output against it) rather than via an LLM judge.

Tasks use the [Harbor](https://www.harborframework.com) format and are organized into category subdirectories by which archive(s) they query: `alma-archive/` (ALMA Science Archive only), `astro-data-lab/` (NOIRLab Astro Data Lab only), and `cross-archive/` (tasks spanning both). 

A task's full path is `data-discovery/<category>/<task-id>/`, e.g. `data-discovery/alma-archive/HH212/` — but its id for `--tasks`/`--include-task-name` purposes is just the leaf name, `HH212`, since task ids are unique across the whole suite regardless of category. 

## Setup

- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). Docker Desktop **must be running** when you create or start Data Discovery tasks.
- Install [Harbor](https://www.harborframework.com), the CLI these tasks run on (verified with version `0.6.1`):

  ```bash
  uv tool install harbor
  ```

- Add an `ANTHROPIC_API_KEY` to your environment. Tasks pass it into the container (`task.toml`'s `[environment]` section).

## Running

Through the repo-root wrapper (recommended; see the top-level `README.md`):

```bash
./benchmark.py run --suite data-discovery --tasks NGC1068-deepest-gri --agent terminus-2 --model anthropic/claude-sonnet-5
```

Or directly with `harbor` if you want full control over its flags (`harbor run --help` for the complete reference). Point `--path` straight at the **full directory** (not just the ID) of a task to run just that task:

```bash
harbor run --path data-discovery/astro-data-lab/NGC1068-deepest-gri \
  --jobs-dir data-discovery/jobs --agent oracle --model anthropic/claude-sonnet-5
```

**To run the reference solution** as a sanity check that a task and its verifier agree, use `--agent oracle`. **To evaluate an LLM**, use a real coding agent (e.g. `--agent claude-code` or `--agent terminus-2`).

**`--agent terminus-2` note:** Harbor's bundled `terminus-2` (0.6.1) hardcodes `temperature=0.7` for every request, which Anthropic rejects outright for Claude 4.6-family models (extended thinking there requires `temperature` to be `1` or omitted) — a real bug in Harbor's agent plus litellm's stale supported-params list for that model family. The wrapper (`./benchmark.py run --agent terminus-2 ...`) automatically adds `--ak temperature=1` to work around this, unless you've already passed your own `--ak temperature=...`. Calling `harbor run` directly, you'll need to add `--ak temperature=1` yourself.

## Viewing results

Individual task run results are stored under `data-discovery/jobs/<job-name>/`. Here, you can see the files that Harbor automatically stores from the sandbox environment (see [Harbor documentation](https://www.harborframework.com/docs/run-jobs/results-and-artifacts) for details).

To create a summary of the latest data-discovery run results, use the following:
```bash
./benchmark.py report --suite data-discovery
```
This generates `runs/<run-id>/summary.csv` and `summary.md`, which contain a table summarizing the results (task, category, trial, score, agent/model, duration, and status).

Two optional PDF flags are also available: `--pdf` creates a compiled `summary.pdf` (overall results / quick overview of each task); `--task-pdfs` creates one detailed PDF per (task, trial) under `runs/<run-id>/pdf/` for **both** suites (or one suite if specified using the --suite flag).


## Adding a task

```bash
./benchmark.py new-task --suite data-discovery --id NGC253-continuum --category alma-archive
```
- `--suite`: which suite the task belongs in: `data-discovery` or `domain-expertise`
- `--id`: task ID (name)
- `--category`: what archive/platform the task queries and the directory it is created in: `alma-archive` (ALMA
Science Archive only), `astro-data-lab` (NOIRLab Astro Data Lab only), or `cross-archive` (a task that has to combine results from both), etc.

This creates `data-discovery/<category>/<id>/` and populates it from a template (`task.toml`, `instruction.md`, `environment/Dockerfile`, `solution/solve.sh`, `tests/test.sh` + `tests/test_outputs.py`) using the plain pytest → `reward.txt` verification pattern most existing tasks use. Fill in the TODOs.

If a task needs LLM-judge grading (or a mix of programmatic + judged criteria) instead of pure pytest checks, Harbor supports this via its Reward Kit (`judge.toml` + a `reward-kit` pattern in `tests/`) — see [Harbor's documentation](https://www.harborframework.com/docs) for the schema. No task in this repo currently uses it (all existing tasks use the plain pytest → `reward.txt` pattern the scaffolder generates), so there's no local worked example to copy from yet.
