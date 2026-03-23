# ============================================
# CHAMP V3 — Operators Package
# OS spins up operators from configs.
# Each operator inherits BaseOperator (the OS layer).
# ============================================

from operators.base import BaseOperator
from operators.registry import OperatorRegistry
from operators.aioscp_bridge import (
    get_os_capabilities,
    get_capability,
    estimate_cost,
    generate_manifest,
)

__all__ = [
    "BaseOperator",
    "OperatorRegistry",
    "get_os_capabilities",
    "get_capability",
    "estimate_cost",
    "generate_manifest",
]