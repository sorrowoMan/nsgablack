"""
Canonical context keys used across adapters/plugins/biases.

The goal is consistency: different modules can interoperate by reading/writing
the same keys. This file is intentionally small and stable.
"""

# Generic
KEY_TEMPERATURE = "temperature"

# Representation-coupling
KEY_MUTATION_SIGMA = "mutation_sigma"

# Variable Neighborhood Search (VNS)
KEY_VNS_K = "vns_k"

# Multi-strategy cooperation
KEY_STRATEGY = "strategy"
KEY_STRATEGY_ID = "strategy_id"
KEY_SHARED = "shared"

# Role orchestration (multi-role / multi-strategy)
KEY_ROLE = "role"
KEY_ROLE_INDEX = "role_index"
KEY_ROLE_ADAPTER = "role_adapter"

# Optional "task/report" schema for controller-driven cooperation.
KEY_TASK = "task"
KEY_REPORT = "report"
KEY_ROLE_REPORTS = "role_reports"

# Advanced cooperation: phase + region + seeding
KEY_PHASE = "phase"
KEY_REGION_ID = "region_id"
KEY_REGION_BOUNDS = "region_bounds"
KEY_SEEDS = "seeds"

# Context meta
KEY_CONTEXT_SCHEMA = "context_schema"
KEY_CONTEXT_EVENTS = "context_events"
KEY_CONTEXT_CACHE = "context_cache"
