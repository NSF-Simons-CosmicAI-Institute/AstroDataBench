apt-get update
apt-get install -y curl

curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh

source $HOME/.local/bin/env

# CTRF produces a standard test report in JSON format which is useful for logging.
# pytest-json-report additionally writes per-test id/outcome to /logs/verifier/report.json
# (persisted by Harbor along with reward.txt) so reporting tools can show which
# individual checks passed/failed -- it doesn't affect the reward computed below.
uvx --python 3.13 \
    --with pytest==8.4.1 \
    --with astroquery==0.4.11 \
    --with astropy==8.0.0 \
    --with pytest-json-ctrf==0.3.5 \
    --with pytest-json-report \
    pytest /tests/test_outputs.py --json-report --json-report-file=/logs/verifier/report.json

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
