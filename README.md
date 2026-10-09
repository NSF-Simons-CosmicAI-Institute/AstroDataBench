# AstroDataBench 

> **Status: under active development.** The benchmark framework is functional, but the prompt set is being expanded and revised. Current prompts and scores should be treated as preliminary and may change between versions. Please check back for updates before citing results.

AstroDataBench is a reusable benchmarking framework that evaluates how well LLMs perform on two kinds of tasks: multiwavelength data discovery (finding the right data across archives) and cross-regime domain expertise (answering conceptual questions that come up when working in an unfamiliar wavelength regime). These tasks are separated into two suites that are implemented and organized as follows:


| | Domain Expertise | Data Discovery |
|---|---|---|
| Testing | Qualitative domain knowledge about astronomical archives and multiwavelength data | Writing/executing code to find data across the ALMA Science Archive and the NOIRLab Astro Data Lab platform |
| Implementation | A model directly answers a domain knowledge prompt | An agent works inside a Docker container with archive access |
| Grading | LLM-as-judge, against a gold-standard checklist + rubric | Programmatic pytest verification against a live archive query |
| Location | [`domain-expertise/`](domain-expertise/README.md) | [`data-discovery/`](data-discovery/README.md) |
| Requirements | Python + an Anthropic API key | Docker + [Harbor](https://www.harborframework.com) + an Anthropic API key |

The suites each run through their own tooling, but the `benchmark.py` wrapper provides easy access to the tests and results in both. If you want more information on one of the suites or need coarser control on a specific run than the wrapper allows, please see the README document in the suite directory ([`domain-expertise/`](domain-expertise/README.md) or [`data-discovery/`](data-discovery/README.md)).



## Quickstart

```bash
git clone <this repo>
cd AstroDataBench
cp domain-expertise/.env.example domain-expertise/.env   # add your ANTHROPIC_API_KEY

# Domain Expertise: just needs Python (sets up its own venv on first run)
# --model here is a bare model id (domain-expertise calls the Anthropic API directly)
./benchmark.py run --suite domain-expertise --filter category=optical --model claude-sonnet-5

# Data Discovery: needs Docker + Harbor installed first (see data-discovery/README.md)
# --model here is "provider/model_name" (data-discovery runs through Harbor); there's no
# --filter for this suite yet, so select tasks individually with --tasks (below) or omit
# --tasks to run everything
./benchmark.py run --suite data-discovery --tasks HH212 --agent terminus-2 --model anthropic/claude-sonnet-5

# Or run everything with defaults:
./benchmark.py run --all

# Compile whatever you've run into one report:
./benchmark.py report
```

`./benchmark.py --help` lists every command; `run`/`report`/`new-task` each
also accept `--help` for their own flags.

## Compiled results

`./benchmark.py report` prints and merges the results from the latest run from each suite into `runs/<run-id>/summary.csv` and `summary.md`. **It intentionally does not average the two suites into a single overall score.** The Domain Expertise and Data Discovery suites assess different skills and use different evaluation methods, and they are meant to be viewed together rather than combined into one number. 

Add `--suite domain-expertise`/`--suite data-discovery`/`--suite all` to scope the report to one suite (or explicitly both). Two optional PDF flags are also available: `--pdf` creates a compiled `summary.pdf` (overall results / quick overview of each task); `--task-pdfs` creates one detailed PDF per (task, trial) under `runs/<run-id>/pdf/` for **both** suites (or one suite if specified using the --suite flag).


## Adding a task

To create a new task, use `./benchmark.py new-task`, with the following flags:
- `--suite`: task suite, either `domain-expertise` or `data-discovery`
- `--id`: task ID (name)
- `--category`: category within the suite (`data-discovery` options: `alma-archive`, `astro-data-lab`, `cross-archive`, etc.; `domain-expertise` options: `radio`, `optical`, `cross-regime`, etc.)

Examples:
```bash
./benchmark.py new-task --suite domain-expertise --id my-new-optical-task --category optical
./benchmark.py new-task --suite data-discovery --id my-new-alma-task --category alma-archive
```
Both create a new task directory with the component files (see each suite's README for details and examples).

Categories aren't a fixed list; `--category` accepts any name, and a new category is created automatically the first time you use it, no other setup required:
```bash
./benchmark.py new-task --suite domain-expertise --id my-new-xray-task --category xray
./benchmark.py new-task --suite data-discovery --id my-new-mast-task --category mast-archive
```

## Repo layout

```
STABLE_benchmark/
├── benchmark.py            # wrapper CLI entry point
├── benchmark_cli/          # wrapper logic (no third-party dependencies)
├── domain-expertise/       # Domain Expertise suite (with its own README, venv, tasks/)
├── data-discovery/         # Data Discovery suite (with its own README, Harbor tasks, jobs/)
├── runs/                   # compiled cross-suite reports (gitignored)
└── tests/                  # tests for benchmark_cli/ 
```
