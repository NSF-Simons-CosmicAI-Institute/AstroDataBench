# Domain Expertise

Domain Expertise tasks test LLM performance in answering domain knowledge and methodology questions about an astronomical archive or wavelength regime, with no code execution or internet access involved. These tasks assess how well an LLM can accomplish things such as...
- Answering domain-specific questions about astronomical data and archives.
- Helping with synthesizing observations across wavelength regimes and data types.
- Flagging where terms or conventions differ across wavelength regimes and archives.

This is a separate, standalone framework from the Harbor/container-based Data Discovery tasks.

Each task = a prompt + a gold-standard checklist of must-include facts + a grading rubric. A candidate model answers the prompt; a judge model (LLM-as-judge) scores the answer against the checklist and rubric.

## Setup

```bash
cd domain-expertise
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

Requires Python 3.9+.

## Running the benchmark

One command runs the full pipeline (generate answers → grade → report):

```bash
./scripts/run_benchmark.sh --model claude-sonnet-5 --judge-model claude-opus-5
```

Useful flags:
- `--filter category=optical` or `--filter id=optical-seeing` — run a subset of tasks
- `--trials 3` — run each task multiple times (results are averaged per task in the report)
- `--run-id <id>` — pick a specific run identifier (default: current UTC timestamp)

Results are stored in `results/<run-id>/`:
- `responses/<task_id>__trial<N>.json` — the candidate model's raw answer
- `grades/<task_id>__trial<N>.json` — the judge's checklist verdicts, rubric scores, and computed score
- `markdown/<task_id>__trial<N>.md` — human-readable report plus a checklist table (ID, summary, weight, satisfied, evidence) and a rubric table
- `summary.json` — full detail, aggregated per task (averaged across trials)
- `summary.csv` — flat table for a quick look or loading into pandas/Excel

PDF reports aren't generated as part of this pipeline — from the repo root (not
`domain-expertise/`), `./benchmark.py report --suite domain-expertise --task-pdfs`
renders one detailed PDF per (task, trial) into `runs/<run-id>/pdf/`, and `--pdf`
renders a compiled overview PDF across whatever's been run. See the top-level
`README.md` for details.

The three stages can also be run independently:

```bash
python scripts/run.py --run-id 20260810-153000 --model claude-sonnet-5
python scripts/grade.py --run-id 20260810-153000 --judge-model claude-opus-5
python scripts/report.py --run-id 20260810-153000
```

## Scoring

Each task produces one composite `final_score` in [0, 1]:

```
checklist_coverage  = (sum of weights of satisfied checklist items) / (sum of all checklist item weights)
rubric_normalized   = (sum of weight * score/scale over rubric criteria) / (sum of rubric weights)
final_score         = checklist_weight * checklist_coverage + rubric_weight * rubric_normalized
```

Default weights (`checklist_weight=0.6`, `rubric_weight=0.4`) are stored in `config.yaml`
and can be overridden per-task via a `scoring:` block in the task YAML. See `dkqa/scorer.py` for the implementation and `tests/test_scorer.py` for worked examples.

## Adding a task

```bash
./benchmark.py new-task --suite domain-expertise --id primary-beam --category radio
```
- `--suite`: which suite the task belongs in: `data-discovery` or `domain-expertise`
- `--id`: task ID (name)
- `--category`: task category (`radio`, `optical`, `cross-regime`, etc.)

Or,
```bash
python scripts/new_task.py --id primary-beam --category radio
```

This scaffolds `tasks/radio/primary-beam.yaml` from a template. Fill in the prompt and checklist items (and modify the rubric if desired).

```yaml
id: optical-seeing            # unique across the whole task bank
category: optical              # subdirectory under tasks/; used for --filter
prompt: |
  What is "seeing" in optical data and how does it limit measurement?

checklist:
  - id: definition
    text: "Defines seeing as ..."               # full text shown to the judge for grading
    summary: "Defines seeing."                   # optional; short label used in markdown report tables
    weight: 1.0                # defaults to 1.0
rubric:
  - name: accuracy
    description: "Is everything stated in the response factually correct, including claims, terms, and reasoning?"
    scale: 5                    # judge scores 1-5 scale
    weight: 1.0
scoring:                        # optional; overrides config.yaml defaults for this task only
  checklist_weight: 0.6
  rubric_weight: 0.4
```

See `tasks/optical/seeing.yaml` and `tasks/radio/interferometry.yaml` for two fully worked examples.

## Notes

- **Extending to other models**: `dkqa/models/base.py` defines a `ModelClient` interface; `dkqa/runner.py` and `dkqa/grader.py` only depend on that interface. Only an Anthropic implementation (`dkqa/models/anthropic_client.py`) exists today — adding OpenAI/Gemini/etc. later is a new `ModelClient` subclass, no changes to the pipeline.
- **Structured grading**: the judge is forced (via `tool_choice`) to call a `submit_grade` tool whose JSON schema mirrors `dkqa.schema.Grade`, so grading output is always structured and parseable rather than relying on free-text parsing.
- **Separate judge model recommended**: using a different (typically stronger) model than the candidate for grading reduces self-grading bias.


