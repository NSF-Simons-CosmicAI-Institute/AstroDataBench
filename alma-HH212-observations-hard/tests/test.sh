#!/bin/bash
apt-get update && apt-get install -y curl
curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh
source "$HOME/.local/bin/env"

uvx --from reward-kit rewardkit /tests \
  --workspace /app \
  --output /logs/verifier/reward.json \
  --max-concurrent-programmatic 8 \
  --max-concurrent-llm 8