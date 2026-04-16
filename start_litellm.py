# ============================================
# CHAMP V3 -- LiteLLM Launcher
# Loads .env into environment BEFORE starting
# LiteLLM so API keys are available.
#
# Profile-based config (Nemoclaw blueprint pattern):
#   CHAMP_PROFILE=local   → litellm_config_local.yaml (includes Ollama)
#   CHAMP_PROFILE=railway → litellm_config.yaml (cloud only, spend tracking)
#   CHAMP_PROFILE=hetzner → litellm_config.yaml (same as railway for now)
#   Default (no env var)  → litellm_config.yaml
#
# Usage:
#   python start_litellm.py          # default profile
#   python start_litellm.py 4001     # custom port
#   CHAMP_PROFILE=local python start_litellm.py  # local dev with Ollama
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

# Profile-based config selection (Nemoclaw pattern)
profile = os.getenv("CHAMP_PROFILE", "default").lower()
project_root = Path(__file__).resolve().parent

PROFILE_CONFIGS = {
    "local": project_root / "litellm_config_local.yaml",
    "railway": project_root / "litellm_config.yaml",
    "hetzner": project_root / "litellm_config.yaml",
    "default": project_root / "litellm_config.yaml",
}

config_path = PROFILE_CONFIGS.get(profile, PROFILE_CONFIGS["default"])
if not config_path.exists():
    print(f"WARNING: Config {config_path} not found, falling back to default")
    config_path = PROFILE_CONFIGS["default"]

# Verify critical keys are set (local profile only needs LITELLM_MASTER_KEY)
if profile == "local":
    keys_needed = ["LITELLM_MASTER_KEY"]
else:
    keys_needed = ["ANTHROPIC_API_KEY", "LITELLM_MASTER_KEY"]

missing = [k for k in keys_needed if not os.getenv(k)]
if missing:
    print(f"ERROR: Missing env vars: {', '.join(missing)}")
    print(f"Check your .env file at: {env_path}")
    sys.exit(1)

# Show what's loaded (masked)
print(f"  Profile: {profile}")
for k in keys_needed:
    val = os.getenv(k, "")
    print(f"  {k}: {val[:8]}...{val[-4:]}")

port = sys.argv[1] if len(sys.argv) > 1 else "4001"
config = str(config_path)

print(f"\nStarting LiteLLM on port {port}...")
print(f"Config: {config}\n")

subprocess.run(
    ["litellm", "--config", config, "--port", port],
    env=os.environ.copy(),
)
