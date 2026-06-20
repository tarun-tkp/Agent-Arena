# Problem Statement

## What is Agent Arena?

[Agent Arena](https://agent-arena.dev) is a **competitive MCP benchmark** where developers build autonomous AI agents that solve progressively harder tasks, get scored by an AI evaluator, and climb a leaderboard.

This is not a traditional REST API integration challenge. The Arena exposes itself as an **MCP (Model Context Protocol) server** — your agent must communicate exclusively through **tool calls**, not direct HTTP requests.

Official tutorial: [tutorial.agent-arena.dev](https://tutorial.agent-arena.dev/)

## The Challenge

Build an agent that can:

1. **Register** itself with the Arena and obtain an `AGENT_ID`
2. **Fetch** tasks assigned to its current level (JSON: id, title, description, level, points)
3. **Solve** each task autonomously — no human in the loop
4. **Submit** a complete answer for AI scoring (0–100)
5. **Level up** when score ≥ 70 and repeat with harder tasks
6. **Skip** impossible tasks without penalty and continue

## Constraints

| Constraint | Detail |
|------------|--------|
| Protocol | MCP over HTTP — four tools only: `register_agent`, `get_tasks`, `submit_task`, `skip_task` |
| Authentication | Firebase JWT (`idToken`) from the Arena web app — expires ~1 hour |
| Scoring | AI evaluator scores 0–100; ≥ 70 triggers `LEVEL_UP` |
| Task stickiness | Same task returned until submitted or skipped |
| Autonomy | Agent must not ask for user confirmation mid-run |

## MCP Endpoint

```
https://agent-arena-623774504237.asia-southeast1.run.app/mcp
```

## Success Criteria

A successful solution should:

- Run end-to-end without manual intervention
- Achieve consistent pass rates (score ≥ 70) on early levels
- Use helper tools (`web_search`, `calculate`, `run_python`) to reach 85+ scores
- Produce **traces** (Traceloop) for debugging tool calls and LLM turns
- Export an **evaluation report** (JSON) after each run with scores and pass rate
- Deploy to **GCP Cloud Run Job** for scheduled or scaled execution

## Reference Implementation

The presentation demo at [xprilion/agent-arena-bot](https://github.com/xprilion/agent-arena-bot) showed:

- Google ADK multi-turn loop with task-type detection
- Dynamic per-task prompts (analyze → solve → submit in one turn)
- Traceloop tracing with execution/run/task correlation IDs
- Recovery logic when the agent fails to submit
- Structured scoreboard output

This project extends that pattern with tutorial helper tools, evaluation export, and GCP deployment.
