"""
Dynamic prompt engine for Agent Arena.

Adapted from the presentation reference:
https://github.com/xprilion/agent-arena-bot
"""

from __future__ import annotations

TASK_PATTERNS = {
    "code": [
        "code", "function", "implement", "write a", "program", "script",
        "class", "algorithm", "api", "method", "library", "module", "package",
        "build", "create a", "develop", "application", "service", "endpoint",
    ],
    "debug": [
        "debug", "fix", "error", "bug", "issue", "broken", "fails",
        "exception", "traceback", "crash", "wrong", "incorrect", "not working",
        "repair", "resolve", "troubleshoot",
    ],
    "explain": [
        "explain", "describe", "what is", "how does", "why", "difference between",
        "concept", "theory", "overview", "introduction", "compare", "contrast",
        "elaborate", "clarify", "discuss",
    ],
    "optimize": [
        "optimize", "performance", "efficient", "slow", "bottleneck", "memory",
        "speed", "complexity", "scale", "improve", "faster", "latency",
        "throughput", "resource", "cache", "compress", "reduce",
    ],
    "design": [
        "design", "architecture", "system", "database schema", "pattern",
        "structure", "model", "diagram", "plan", "blueprint", "component",
        "microservice", "flow", "sequence", "entity relationship",
    ],
    "test": [
        "test", "unit test", "pytest", "assert", "coverage", "mock", "testing",
        "tdd", "spec", "validate", "verify", "bdd", "integration test",
        "regression", "benchmark",
    ],
    "data": [
        "data", "csv", "json", "sql", "query", "database", "etl", "pipeline",
        "transform", "clean", "analyze", "visualization", "chart", "pandas",
        "dataframe", "dataset",
    ],
    "security": [
        "security", "auth", "authentication", "authorization", "jwt", "oauth",
        "encrypt", "hash", "vulnerability", "sanitize", "xss", "csrf",
        "sql injection", "penetration", "secure",
    ],
}


def detect_task_type(title: str = "", description: str = "") -> str:
    text = f"{title} {description}".lower()
    scores = {
        task_type: sum(1 for kw in keywords if kw in text)
        for task_type, keywords in TASK_PATTERNS.items()
    }
    if not scores or max(scores.values(), default=0) == 0:
        return "general"
    return max(scores, key=scores.get)


def _format_task(task: dict) -> str:
    return "\n".join(
        [
            f"Title: {task.get('title', 'N/A')}",
            f"Level: {task.get('level', 'N/A')}",
            f"Points: {task.get('points', 'N/A')}",
            f"Description:\n{task.get('description', 'N/A')}",
        ]
    )


def build_task_prompt(task: dict, agent_id: str, task_id: str) -> str:
    """Composite prompt: analyze → solve → submit in one turn."""
    task_type = detect_task_type(task.get("title", ""), task.get("description", ""))

    type_guidance = {
        "code": (
            "Write clean, commented code with type hints and error handling. "
            "Use run_python to verify before submitting."
        ),
        "debug": (
            "Identify root cause, provide fixed code, explain why the fix works."
        ),
        "explain": (
            "Use clear structure, examples, and step-by-step breakdowns."
        ),
        "optimize": (
            "Show before/after reasoning, optimized solution, and trade-offs."
        ),
        "design": (
            "Provide architecture overview, components, data flow, and scalability notes."
        ),
        "test": (
            "Provide complete tests with positive, negative, and edge cases."
        ),
        "data": (
            "Provide pipeline logic, schema, validation, and sample outputs."
        ),
        "security": (
            "Summarize threat model, secure implementation, and verification steps."
        ),
        "general": (
            "Provide a complete, well-structured solution with reasoning and examples."
        ),
    }
    guidance = type_guidance.get(task_type, type_guidance["general"])

    return f"""
You have been assigned a new task. Solve it completely in this turn.

TASK ({task_type.upper()}):
{_format_task(task)}

HELPER TOOLS (use when they improve accuracy):
- web_search — factual or current-information tasks
- calculate — exact numeric expressions (never guess math)
- run_python — verify algorithms or code before submitting

INSTRUCTIONS:
1. ANALYZE — Restate the problem, requirements, edge cases, and your approach.
2. SOLVE — {guidance}
3. REVIEW — Verify correctness, completeness, and clarity.
4. SUBMIT — Call submit_task with:
     agent_id = "{agent_id}"
     task_id = "{task_id}"
     content = <your complete answer>

Aim for 90+/100. Do NOT stop after analysis. Call submit_task in this same turn.
""".strip()


def build_system_prompt(agent_name: str, agent_stack: str) -> str:
    """Base system instruction aligned with the official tutorial lifecycle."""
    return f"""
You are an expert autonomous agent competing in the Agent Arena evaluation system.
Your goal is to solve tasks with high quality and advance through levels (score >= 70).

AVAILABLE TOOLS:
- register_agent(name, stack) — register once at start; returns AGENT_ID
- get_tasks(agent_id) — fetch current task JSON (sticky until skip/submit)
- skip_task(agent_id, task_id) — abandon impossible or already-submitted tasks
- submit_task(agent_id, task_id, content) — submit answer for AI scoring (0-100)
- report_status() — summarize run progress
- web_search(query) — search the web for facts
- calculate(expression) — exact math evaluation
- run_python(code) — sandboxed code execution for verification

CORE PRINCIPLES:
1. THOROUGHNESS — analyze deeply, handle edge cases, verify with tools
2. QUALITY — aim for 90+/100; shallow answers score poorly
3. AUTONOMY — do not ask for confirmation; state assumptions clearly
4. PRECISION — use temperature-friendly factual answers; prefer tools over guesses

RULES:
- Never submit the same task_id twice
- Always use task_id from the most recent get_tasks call
- Score >= 70 triggers LEVEL_UP; tasks get harder each level

IDENTITY:
- Agent Name: {agent_name}
- Stack: {agent_stack}
""".strip()
