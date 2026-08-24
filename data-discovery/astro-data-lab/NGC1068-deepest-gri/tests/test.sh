#!/bin/bash

# Use this file to install test dependencies and run the tests.
# It will be copied to /tests/test.sh and run from the working directory.

apt-get update
apt-get install -y curl
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
source $HOME/.local/bin/env

# CTRF produces a standard test report in JSON format which is useful for logging.
uvx \
  --with pytest==8.4.1 \
  --with pytest-json-report \
  --with numpy==2.5.0 \
  --with pyvo==1.9.1 \
  --with astropy==8.0.0 \
  --with astro-datalab==2.22.1 \
  --with pandas==3.0.3 \
  --with astroquery==0.4.6 \
  pytest /tests/test_outputs.py --json-report --json-report-file=/logs/verifier/report.json

python3 -c "
import json
report = json.load(open('/logs/verifier/report.json'))
passed = report['summary'].get('passed', 0)
total = report['summary']['total']
print(passed / total if total else 0)
" > /logs/verifier/reward.txt