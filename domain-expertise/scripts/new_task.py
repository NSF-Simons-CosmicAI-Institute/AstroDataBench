#!/usr/bin/env python3
"""Scaffold a new task YAML from a template.

Usage:
    python scripts/new_task.py --id xray-pile-up --category xray
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dkqa.config import load_config

TEMPLATE = """\
id: {id}
category: {category}
prompt: |
  TODO: write the domain-knowledge question here.
checklist:
  - id: TODO_item_1
    text: "TODO: a fact/concept the answer must include to get credit"
    weight: 1.0
  - id: TODO_item_2
    text: "TODO: another fact the answer must include to get credit"
    weight: 1.0
  - id: TODO_bonus_item
    text: "TODO: a bonus fact worth less credit -- give it a lower weight"
    weight: 0.5
rubric:
  - name: accuracy
    description: "Is everything stated in the response factually correct, including claims, terms, and
                  reasoning? This should be scored independently of checklist coverage, meaning an
                  answer can satisfy every checklist item and still contain an unrelated factual error,
                  a misapplied term, or an incorrect description, and any such error should lower this
                  score even if it doesn't affect whether the answer satisfies the checklist."
    scale: 5
    weight: 0.5
  - name: caveating
    description: "Does the response express an appropriate level of confidence about its own claims
                  (avoiding overconfident assertions on points that are wrong or genuinely uncertain),
                  and does it hedge or flag uncertainty about its own statements when scientifically
                  warranted? This assesses the model's self-assessed confidence in what it asserts,
                  not whether the response describes a concept, process, or result that is itself
                  inherently ambiguous or non-unique. Score this independently of checklist coverage
                  and of whether the underlying content is correct."
    scale: 5
    weight: 0.25
  - name: clarity
    description: "Is the response well-organized, appropriately detailed, and easy to act on, with enough
                  detail for a non-expert to follow and apply it without being overly verbose? A response
                  can be complete and accurate while still being disorganized, overly verbose, or too
                  generic to be useful; this score should capture that quality independent of content
                  correctness or coverage."
    scale: 5
    weight: 0.25
"""


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    config = load_config()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="Unique task id, e.g. xray-pile-up")
    parser.add_argument("--category", required=True, help="Category subdirectory under tasks/, e.g. xray")
    parser.add_argument("--tasks-dir", default=config["tasks_dir"])
    args = parser.parse_args()

    out_dir = root / args.tasks_dir / args.category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.id}.yaml"

    if out_path.exists():
        print(f"Refusing to overwrite existing file: {out_path}", file=sys.stderr)
        sys.exit(1)

    out_path.write_text(TEMPLATE.format(id=args.id, category=args.category))
    print(f"Created {out_path}")


if __name__ == "__main__":
    main()
