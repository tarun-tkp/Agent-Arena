# Solution Guide

## How We Solve It

This project implements a **Google ADK + FastMCP** autonomous agent following the [official tutorial](https://tutorial.agent-arena.dev/) and patterns from the [presentation reference bot](https://github.com/xprilion/agent-arena-bot).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  agent.py — main loop                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ prompts.py  │  │ evaluation.py│  │  tracing.py   │  │
│  │ task-type   │  │ RunState     │  │  Traceloop    │  │
│  │ detection   │  │ scoreboard   │  │  OTel logs    │  │
│  │ dynamic     │  │ JSON export  │  │               │  │
│  │ prompts     │  │              │  │               │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│                          │                              │
│  Google ADK LlmAgent ────┼── Arena tools (MCP)          │
│                          └── Helper tools (local)       │
└──────────────────────────┬──────────────────────────────┘
                           │ FastMCP HTTP
                           ▼
              Agent Arena MCP Server (/mcp)
```

## What You Need To Do

### Step 1 — Get credentials

| Credential | Where |
|------------|-------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) |
| `ARENA_ID_TOKEN` | Sign in at [agent-arena.dev](https://agent-arena.dev) → DevTools → Application → Storage → copy Firebase JWT |
| `TRACELOOP_API_KEY` (optional) | [Traceloop](https://app.traceloop.com) for trace visibility |

### Step 2 — Configure

```bash
cp .env.example .env
# Edit .env with your keys
```

Key settings in `config.py` (all overridable via env):

| Variable | Purpose |
|----------|---------|
| `AGENT_NAME` | Leaderboard name |
| `MODEL` | Gemini model (`gemini-2.0-flash` or `gemini-2.5-pro-preview`) |
| `MAX_TASKS` | How many tasks to attempt per run |
| `TEMPERATURE` | `0.1` recommended for precision |
| `EVAL_OUTPUT_DIR` | Where JSON evaluation reports are saved |

### Step 3 — Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python agent.py
```

### Step 4 — Review evaluation

After each run, a JSON report is written to `runs/<run_id>.json`:

```json
{
  "run_id": "...",
  "final_level": 4,
  "total_score": 388,
  "tasks_attempted": 4,
  "tasks_passed": 3,
  "average_score": 97.0,
  "pass_rate_percent": 75.0,
  "level_history": [...]
}
```

### Step 5 — Deploy to GCP

See [DEPLOYMENT.md](./DEPLOYMENT.md).

## Run Lifecycle

The agent follows this loop (tutorial + presentation bot):

```
1. Bootstrap
   register_agent → get_tasks (fetch first task, do NOT submit)

2. For each task (up to MAX_TASKS):
   a. Detect task type (code, debug, explain, …)
   b. Build dynamic prompt (analyze + solve + submit)
   c. Single ADK turn with helper tools
   d. Recovery turn if submit was missed
   e. get_tasks for next challenge

3. Finalize
   report_status() → scoreboard → export JSON report
```

## Tools Available to the LLM

### Arena MCP tools (required)

| Tool | When to use |
|------|-------------|
| `register_agent` | Once at start |
| `get_tasks` | Before each task |
| `submit_task` | After solving |
| `skip_task` | Impossible or stuck tasks |
| `report_status` | End of run summary |

### Helper tools (tutorial — boost scores)

| Tool | When to use |
|------|-------------|
| `web_search` | Factual / current-info tasks |
| `calculate` | Exact math — never guess |
| `run_python` | Verify code/algorithms before submit |

## Scoring Strategy

| Tip | Impact |
|-----|--------|
| Search first | 65 → 85 on factual tasks |
| Exact math via `calculate` | Avoids LLM arithmetic errors |
| Verify with `run_python` | Catches logic bugs before submit |
| `temperature=0.1` | More precise technical answers |
| Task-type prompts | Tailored structure per task category |

## Project Files

| File | Role |
|------|------|
| `agent.py` | Main entry — ADK agent, tools, run loop |
| `prompts.py` | Task-type detection + dynamic prompts |
| `config.py` | Environment-based configuration |
| `evaluation.py` | RunState, scoreboard, JSON export |
| `tracing.py` | Traceloop / OpenTelemetry setup |
| `Dockerfile` | Container for Cloud Run |
| `cloudbuild.yaml` | GCP build + deploy pipeline |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Token expired | Refresh `ARENA_ID_TOKEN` from web app (~1h TTL) |
| Task not submitted | Recovery turn runs automatically; check Traceloop traces |
| Low scores | Enable helper tools; try `gemini-2.5-pro-preview` |
| MCP timeout | Fresh connection per call is by design |

## External Links

- [Agent Arena Platform](https://agent-arena.dev)
- [Complete Tutorial](https://tutorial.agent-arena.dev/)
- [Presentation Reference Bot](https://github.com/xprilion/agent-arena-bot)
- [Google ADK Docs](https://google.github.io/adk-docs/)
