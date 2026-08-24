#!/bin/bash
apt-get update && apt-get install -y curl
curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh
source "$HOME/.local/bin/env"

uvx --python 3.13 \
  --with pytest==8.4.1 \
  --with pytest-json-report \
  --with astroquery \
  --with astropy \
  pytest /tests/test_outputs.py --json-report --json-report-file=/logs/verifier/report.json

python3 -c "
import json
report = json.load(open('/logs/verifier/report.json'))
passed = report['summary'].get('passed', 0)
total = report['summary']['total']
print(passed / total if total else 0)
" > /logs/verifier/reward.txt