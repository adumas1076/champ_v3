# ============================================
# CHAMP V3 -- LiteLLM Launcher
# Loads .env into environment BEFORE starting
# LiteLLM so API keys are available.
#
# Usage: python start_litellm.py
# ============================================

import os
import subprocess
import sys
from pathlib import Path

# Fix Windows Unicode encoding (LiteLLM banner has special chars)
os.environ["PYTHONIOENCODING"] = "utf-8"

from dotenv import load_dotenv

# Load .env from this directory
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

# Verify critical keys are set
keys_needed = ["ANTHROPIC_API_KEY", "LITELLM_MASTER_KEY"]
missing = [k for k in keys_needed if not os.getenv(k)]
if missing:
    print(f"ERROR: Missing env vars: {', '.join(missing)}")
    print(f"Check your .env file at: {env_path}")
    sys.exit(1)

# Show what's loaded (masked)
for k in keys_needed:
    val = os.getenv(k, "")
    print(f"  {k}: {val[:8]}...{val[-4:]}")

port = sys.argv[1] if len(sys.argv) > 1 else "4001"
config = str(Path(__file__).resolve().parent / "litellm_config.yaml")

print(f"\nStarting LiteLLM on port {port}...")
print(f"Config: {config}\n")

subprocess.run(
    ["litellm", "--config", config, "--port", port],
    env=os.environ.copy(),
)
