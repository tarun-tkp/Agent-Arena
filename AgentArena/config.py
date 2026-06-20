"""Central configuration — override via environment variables or .env file."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


# ── Arena identity ────────────────────────────────────────────────────────
AGENT_NAME = _env("AGENT_NAME", "AgentArena-Amadeus-v1")
AGENT_STACK = _env("AGENT_STACK", "Python / ADK / Gemini / Traceloop")
LINKEDIN_URL = _env("LINKEDIN_URL", "")
GITHUB_URL = _env("GITHUB_URL", "")

# ── Model ───────────────────────────────────────────────────────────────────
MODEL = _env("MODEL", "gemini-2.0-flash")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
TEMPERATURE = _env_float("TEMPERATURE", 0.1)
MAX_OUTPUT_TOKENS = _env_int("MAX_OUTPUT_TOKENS", 8192)

# Optional LiteLLM provider (OpenCode Go, etc.)
OPENCODE_GO_API_KEY = _env("OPENCODE_GO_API_KEY")
OPENCODE_GO_MODEL = _env("OPENCODE_GO_MODEL", "kimi-k2.6")
OPENCODE_GO_BASE = _env("OPENCODE_GO_BASE", "https://opencode.ai/zen/go/v1")

# ── Arena MCP ───────────────────────────────────────────────────────────────
MCP_ENDPOINT = _env(
    "MCP_ENDPOINT",
    "https://agent-arena-623774504237.asia-southeast1.run.app/mcp",
)
# Tutorial uses ARENA_ID_TOKEN; presentation bot uses ID_TOKEN
ID_TOKEN = _env("ARENA_ID_TOKEN") or _env("ID_TOKEN")

# ── Run limits ──────────────────────────────────────────────────────────────
MAX_TASKS = _env_int("MAX_TASKS", _env_int("MAX_TURNS", 20))
APP_NAME = _env("APP_NAME", "agent-arena-amadeus")
USER_ID = _env("USER_ID", "arena-user")

# ── Tracing (Traceloop / OpenTelemetry) ─────────────────────────────────────
TRACELOOP_API_KEY = _env("TRACELOOP_API_KEY")
TRACELOOP_APP_NAME = _env("TRACELOOP_APP_NAME", APP_NAME)
OTEL_SERVICE_NAME = _env("OTEL_SERVICE_NAME", APP_NAME)

# ── Evaluation output ───────────────────────────────────────────────────────
EVAL_OUTPUT_DIR = _env("EVAL_OUTPUT_DIR", "runs")
EVAL_OUTPUT_FILE = _env("EVAL_OUTPUT_FILE", "")  # auto: runs/<run_id>.json
