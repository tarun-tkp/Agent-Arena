# AgentArena-Amadeus

Autonomous AI agent for [Agent Arena](https://agent-arena.dev) — register, solve progressively harder MCP tasks, level up on scores ≥ 70, and export evaluation reports.

Built from the [official tutorial](https://tutorial.agent-arena.dev/) with patterns from the [presentation reference bot](https://github.com/xprilion/agent-arena-bot).

## Problem → Solution

| | |
|---|---|
| **Problem** | Build an autonomous agent that competes on Agent Arena via MCP tool calls only |
| **Solution** | Google ADK + FastMCP loop with dynamic prompts, helper tools, Traceloop traces, and JSON evaluation export |
| **Deploy** | GCP Cloud Run Job for batch execution and parallel scaling |

Full details: [docs/PROBLEM.md](docs/PROBLEM.md) · [docs/GUIDE.md](docs/GUIDE.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Quick Start

```bash
cp .env.example .env          # set GEMINI_API_KEY + ARENA_ID_TOKEN
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python agent.py
```

**Tokens:** Gemini key from [aistudio.google.com](https://aistudio.google.com) · Arena JWT from [agent-arena.dev](https://agent-arena.dev) (DevTools → Application → Storage)

## Project Structure

```
agent.py          # Main agent — run this
prompts.py        # Task-type detection + dynamic prompts
config.py         # Environment configuration
evaluation.py     # Scoreboard + JSON report export
tracing.py        # Traceloop / OpenTelemetry
runs/             # Evaluation reports (gitignored)
deploy/           # GCP Cloud Run Job manifests
Dockerfile        # Container image
cloudbuild.yaml   # GCP build + deploy
docs/             # Problem statement, guide, deployment
```

## Features

- **Tutorial-compliant** — four MCP Arena tools + helper tools (`web_search`, `calculate`, `run_python`)
- **Presentation patterns** — task-type prompts, recovery turns, scoreboard ([reference](https://github.com/xprilion/agent-arena-bot))
- **Tracing** — Traceloop with run/task/execution correlation IDs
- **Evaluation** — JSON report per run (`runs/<run_id>.json`) with pass rate and level history
- **GCP-ready** — Dockerfile + Cloud Run Job + Cloud Build pipeline

## Configuration

All settings via environment variables (see `.env.example`):

```bash
AGENT_NAME=AgentArena-Amadeus-v1
MODEL=gemini-2.0-flash
MAX_TASKS=20
TEMPERATURE=0.1
TRACELOOP_API_KEY=...          # optional
```

## Example Output

```
════════════════════════════════════════════════════════════
  AGENT ARENA — AgentArena-Amadeus-v1
  Model: gemini-2.0-flash  |  Max tasks: 20
════════════════════════════════════════════════════════════

[12:01:03] 📝 [REGISTER] agent_id=abc123 level=1
[12:01:15] 📋 [TASK] #1 | Implement binary search | CODE
[12:02:40] 🏆 [SCORE] 88/100 🚀 LEVEL_UP!

────────────────────────────────────────────────────────────
  SCOREBOARD (run a1b2c3d4)  model: gemini-2.0-flash
  Current Level : 2
  Total Score   : 88
────────────────────────────────────────────────────────────

[12:05:00] ✅ [DONE] Evaluation report → runs/a1b2c3d4-....json
```

## Deploy to GCP

```bash
./deploy/setup-gcp.sh YOUR_PROJECT_ID
gcloud builds submit --config cloudbuild.yaml
gcloud run jobs execute agent-arena-amadeus --region=asia-southeast1
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).
