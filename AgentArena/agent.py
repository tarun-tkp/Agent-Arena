"""
Agent Arena autonomous competitor — Google ADK + FastMCP.

Tutorial:  https://tutorial.agent-arena.dev/
Reference: https://github.com/xprilion/agent-arena-bot

Usage:
  python agent.py
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import json
import operator
import re
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from traceloop.sdk import set_association_properties
from traceloop.sdk.decorators import workflow
from traceloop.sdk.tracing import set_conversation_id

import config
from evaluation import RunState
from prompts import build_system_prompt, build_task_prompt, detect_task_type
from tracing import agent_logger, init_tracing, task_logger

try:
    from google.adk.models.lite_llm import LiteLlm

    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(tag: str, msg: str) -> None:
    emoji = {
        "REGISTER": "📝", "FETCH": "📥", "SUBMIT": "📤", "SCORE": "🏆",
        "LEVEL": "🚀", "SKIP": "⏭️", "ERROR": "❌", "WARN": "⚠️",
        "DONE": "✅", "TASK": "📋", "LOOP": "🔄", "AGENT": "🤖",
    }.get(tag, "•")
    print(f"[{_ts()}] {emoji} [{tag}] {msg}")


def active_model():
    if config.OPENCODE_GO_API_KEY and _LITELLM_AVAILABLE:
        return LiteLlm(
            model=f"openai/{config.OPENCODE_GO_MODEL}",
            api_base=config.OPENCODE_GO_BASE,
            api_key=config.OPENCODE_GO_API_KEY,
        )
    return config.MODEL


def active_model_name() -> str:
    if config.OPENCODE_GO_API_KEY and _LITELLM_AVAILABLE:
        return f"opencode-go/{config.OPENCODE_GO_MODEL}"
    return config.MODEL


def parse_submission_result(result: str) -> tuple[int, bool, int]:
    score_match = re.search(r"(?:Score|score)[:\s=]+(\d+)(?:/100)?", result, re.I)
    score = int(score_match.group(1)) if score_match else -1
    levelled_up = bool(re.search(r"LEVEL[_\s-]?UP", result, re.I))
    level_match = re.search(r"level[=:\s]+(\d+)", result, re.I)
    level = int(level_match.group(1)) if level_match else 0
    return score, levelled_up, level


# ── Helper tools (tutorial section 10 — boost scores to 85+) ───────────────

_SAFE_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_SAFE_UNOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def eval_math(expression: str) -> str:
    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNOPS:
            return _SAFE_UNOPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
            return _SAFE_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError(f"Unsupported expression: {expression}")

    tree = ast.parse(expression.strip(), mode="eval")
    value = _eval(tree)
    return str(int(value)) if value == int(value) else str(value)


async def web_search(query: str) -> str:
    """Search the internet for current facts."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        return f"Search failed: {exc}"

    parts: list[str] = []
    if data.get("AbstractText"):
        parts.append(data["AbstractText"])
    for topic in data.get("RelatedTopics", [])[:5]:
        if isinstance(topic, dict) and topic.get("Text"):
            parts.append(f"- {topic['Text']}")
    return "\n".join(parts) if parts else f"No results for: {query}"


async def calculate(expression: str) -> str:
    """Evaluate a math expression safely."""
    try:
        return f"Result: {eval_math(expression)}"
    except Exception as exc:
        return f"Error: {exc}"


async def run_python(code: str) -> str:
    """Execute Python code in a restricted sandbox."""
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "float": float, "int": int, "len": len,
        "list": list, "max": max, "min": min, "print": print, "range": range,
        "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip,
    }
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, {"__builtins__": safe_builtins}, {})  # noqa: S102
    except Exception as exc:
        return f"Execution error: {exc}\n{stdout.getvalue()}"
    out = stdout.getvalue().strip()
    return out or "Code ran successfully (no printed output)."


# ── MCP + Arena tools ────────────────────────────────────────────────────────

async def mcp_call(tool_name: str, arguments: dict, state: RunState) -> str:
    transport = StreamableHttpTransport(url=config.MCP_ENDPOINT)
    try:
        async with Client(transport=transport, name=config.APP_NAME) as client:
            set_association_properties({
                "execution.id": state.execution_id,
                "run.id": state.run_id,
                "agent.id": state.agent_id,
                "task.id": state.task_id,
                "agent.name": config.AGENT_NAME,
            })
            if state.conversation_id:
                set_conversation_id(state.conversation_id)
            result = await client.call_tool(tool_name, arguments)
            if result is None:
                return f"ERROR: {tool_name} returned no response"
            return "\n".join(
                getattr(b, "text", "") for b in result.content if getattr(b, "text", None)
            )
    except ToolError as exc:
        _log("ERROR", f"{tool_name}: {exc}")
        return f"ERROR: {exc}"
    except Exception as exc:
        _log("ERROR", f"{tool_name}: {exc}")
        return f"ERROR: {exc}"


def _register_payload(name: str, stack: str) -> dict:
    payload: dict = {"idToken": config.ID_TOKEN, "name": name, "stack": stack}
    if config.LINKEDIN_URL:
        payload["linkedinUrl"] = config.LINKEDIN_URL
    if config.GITHUB_URL:
        payload["githubUrl"] = config.GITHUB_URL
    return payload


def make_tools(state: RunState) -> list:
    async def register_agent(name: str, stack: str) -> str:
        """Register this agent in Agent Arena. Call once at start."""
        result = await mcp_call("register_agent", _register_payload(name, stack), state)
        match = re.search(r"AGENT_ID:\s*(\S+?)\.?(\s|$)", result)
        if match:
            state.agent_id = match.group(1)
            state.conversation_id = state.agent_id
            set_association_properties({"agent.id": state.agent_id})
            set_conversation_id(state.agent_id)
        level_match = re.search(r"Level[:\s]+(\d+)", result, re.I)
        if level_match:
            state.current_level = int(level_match.group(1))
        agent_logger.info("Registered", extra={"agent_id": state.agent_id})
        _log("REGISTER", f"agent_id={state.agent_id} level={state.current_level}")
        return result

    async def get_tasks(agent_id: str) -> str:
        """Fetch the currently assigned task for this agent's level."""
        result = await mcp_call(
            "get_tasks", {"idToken": config.ID_TOKEN, "agentId": agent_id}, state
        )
        try:
            data = json.loads(result)
            task_obj: Optional[dict] = None
            if isinstance(data, dict) and "id" in data:
                task_obj = data
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                task_obj = data[0]
            if task_obj:
                state.task_id = task_obj["id"]
                state.current_task = task_obj
                state.conversation_id = f"{state.agent_id}-{state.task_id}"
                set_association_properties({"task.id": state.task_id})
                set_conversation_id(state.conversation_id)
                _log("FETCH", f"'{task_obj.get('title')}' L{task_obj.get('level')}")
        except json.JSONDecodeError:
            pass
        return result

    async def skip_task(agent_id: str, task_id: str, reason: str = "") -> str:
        """Abandon the current task and fetch a new one via get_tasks."""
        _log("SKIP", f"{task_id[:8]} reason={reason[:50]}")
        args: dict = {"idToken": config.ID_TOKEN, "agentId": agent_id, "taskId": task_id}
        if reason:
            args["reason"] = reason
        return await mcp_call("skip_task", args, state)

    async def submit_task(agent_id: str, task_id: str, content: str) -> str:
        """Submit your answer. Scored 0-100. Score >= 70 means LEVEL_UP."""
        state.execution_id = str(uuid.uuid4())
        set_association_properties({"execution.id": state.execution_id, "task.id": task_id})
        task_logger.info("Submitting", extra={"task_id": task_id})

        result = await mcp_call("submit_task", {
            "idToken": config.ID_TOKEN,
            "agentId": agent_id,
            "taskId": task_id,
            "executionId": state.execution_id,
            "content": content,
            "metadata": {
                "agent_name": config.AGENT_NAME,
                "agent_stack": config.AGENT_STACK,
                "run_id": state.run_id,
                "model": active_model_name(),
            },
        }, state)

        score, levelled_up, level = parse_submission_result(result)
        title = (
            state.current_task.get("title", task_id)
            if state.current_task else task_id
        )
        state.record(
            level or state.current_level, title, score, levelled_up,
            task_id=task_id, raw_response=result,
        )
        _log("SCORE", f"{score}/100 {'🚀 LEVEL_UP!' if levelled_up else ''}")
        print(state.scoreboard(active_model_name()))
        return result

    async def report_status() -> str:
        """Report current agent progress and score history."""
        return json.dumps(state.summary(active_model_name()), indent=2)

    return [
        register_agent, get_tasks, skip_task, submit_task, report_status,
        web_search, calculate, run_python,
    ]


def build_agent(state: RunState) -> LlmAgent:
    stack = config.AGENT_STACK or f"Python / ADK / {active_model_name()} / Traceloop"
    return LlmAgent(
        name="arena_agent",
        model=active_model(),
        instruction=build_system_prompt(config.AGENT_NAME, stack),
        tools=make_tools(state),
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=config.TEMPERATURE,
            max_output_tokens=config.MAX_OUTPUT_TOKENS,
        ),
    )


async def run_turn(
    runner: Runner,
    session_id: str,
    message: str,
) -> str:
    content = genai_types.Content(
        role="user", parts=[genai_types.Part(text=message)]
    )
    final_text = ""
    async for event in runner.run_async(
        user_id=config.USER_ID,
        session_id=session_id,
        new_message=content,
    ):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                _log("AGENT", f"→ {fc.name}")
            elif hasattr(part, "function_response") and part.function_response:
                fr = part.function_response
                preview = str(fr.response)[:120].replace("\n", " ")
                _log("AGENT", f"← {fr.name} {preview}")
            elif hasattr(part, "text") and part.text and getattr(event, "turn_complete", False):
                final_text = part.text
    return final_text


@workflow(name="arena_adk_run")
async def run() -> None:
    if not config.ID_TOKEN:
        raise SystemExit(
            "Missing ARENA_ID_TOKEN (or ID_TOKEN). Sign in at https://agent-arena.dev, "
            "open DevTools → Application → Storage, copy your Firebase JWT."
        )
    if not config.GEMINI_API_KEY and not config.OPENCODE_GO_API_KEY:
        raise SystemExit("Missing GEMINI_API_KEY (or configure OPENCODE_GO_API_KEY).")

    state = RunState()
    model_name = active_model_name()

    print(f"\n{'═' * 60}")
    print(f"  AGENT ARENA — {config.AGENT_NAME}")
    print(f"  Model: {model_name}  |  Max tasks: {config.MAX_TASKS}")
    print(f"{'═' * 60}\n")

    set_association_properties({
        "run.id": state.run_id,
        "agent.name": config.AGENT_NAME,
    })

    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name=config.APP_NAME,
        user_id=config.USER_ID,
        session_id=state.run_id,
    )
    runner = Runner(
        agent=build_agent(state),
        app_name=config.APP_NAME,
        session_service=sessions,
    )

    # Bootstrap: register + fetch first task (tutorial lifecycle)
    _log("REGISTER", "Bootstrapping...")
    await run_turn(
        runner, state.run_id,
        f"Call register_agent(name='{config.AGENT_NAME}', "
        f"stack='{config.AGENT_STACK or model_name}'). "
        f"Then get_tasks. Return a one-line task summary only — do NOT submit yet.",
    )

    if not state.current_task:
        await run_turn(runner, state.run_id, "Call get_tasks to fetch the first challenge.")

    # Main task loop (presentation bot pattern + tutorial scoring)
    for task_num in range(1, config.MAX_TASKS + 1):
        if not state.current_task or not state.task_id:
            _log("DONE", "No active task — stopping.")
            break

        task = state.current_task
        task_type = detect_task_type(task.get("title", ""), task.get("description", ""))
        print(f"\n{'━' * 60}")
        _log("TASK", f"#{task_num} | {task.get('title')} | {task_type.upper()}")
        print(f"{'━' * 60}")

        prev_attempted = state.tasks_attempted
        prompt = build_task_prompt(task, state.agent_id, state.task_id)
        await run_turn(runner, state.run_id, prompt)

        if state.tasks_attempted <= prev_attempted:
            _log("WARN", "Task not submitted — recovery turn...")
            await run_turn(
                runner, state.run_id,
                f"Call submit_task(agent_id='{state.agent_id}', "
                f"task_id='{state.task_id}', content=<full answer>) NOW. "
                f"Or skip_task if impossible.",
            )
            if state.tasks_attempted <= prev_attempted:
                await run_turn(
                    runner, state.run_id,
                    f"Call skip_task(agent_id='{state.agent_id}', "
                    f"task_id='{state.task_id}', reason='Recovery failed.')",
                )

        state.current_task = None
        state.task_id = ""
        _log("LOOP", "Fetching next task...")
        await run_turn(
            runner, state.run_id,
            "Call get_tasks for the next challenge. "
            "If no task, call report_status() and stop.",
        )
        if not state.current_task:
            _log("DONE", "No more tasks.")
            break

    await run_turn(runner, state.run_id, "Call report_status() to summarize the run.")
    print(state.scoreboard(model_name))
    report_path = state.export_report(model_name)
    _log("DONE", f"Evaluation report → {report_path}")
    agent_logger.info("Run complete", extra=state.summary(model_name))


if __name__ == "__main__":
    init_tracing()
    asyncio.run(run())
