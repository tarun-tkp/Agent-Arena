"""Run state, scoreboard, and evaluation report export."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import AGENT_NAME, AGENT_STACK, EVAL_OUTPUT_DIR, EVAL_OUTPUT_FILE, MODEL


class RunState:
    """Shared mutable state for a single Arena run."""

    def __init__(self) -> None:
        self.run_id = str(uuid.uuid4())
        self.execution_id = str(uuid.uuid4())
        self.agent_id = ""
        self.task_id = ""
        self.conversation_id = ""
        self.current_level = 1
        self.total_score = 0
        self.tasks_attempted = 0
        self.tasks_passed = 0
        self.level_history: list[dict[str, Any]] = []
        self.current_task: Optional[dict] = None
        self.started_at = datetime.now(timezone.utc).isoformat()

    def record(
        self,
        level: int,
        task_title: str,
        score: int,
        levelled_up: bool,
        *,
        task_id: str = "",
        raw_response: str = "",
    ) -> None:
        self.tasks_attempted += 1
        if score >= 0:
            self.total_score += score
        if levelled_up or score >= 70:
            self.tasks_passed += 1
        if levelled_up:
            self.current_level = level + 1
        self.level_history.append(
            {
                "level": level,
                "task": task_title,
                "task_id": task_id,
                "score": score,
                "levelled_up": levelled_up,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_response_preview": raw_response[:200],
            }
        )

    def scoreboard(self, model_name: str) -> str:
        lines = [
            f"\n{'─' * 60}",
            f"  SCOREBOARD (run {self.run_id[:8]})  model: {model_name}",
            f"{'─' * 60}",
            f"  Current Level : {self.current_level}",
            f"  Total Score   : {self.total_score}",
            f"  Tasks Done    : {self.tasks_attempted} (passed: {self.tasks_passed})",
            f"{'─' * 60}",
        ]
        for entry in self.level_history:
            icon = (
                "✅"
                if entry["levelled_up"]
                else ("🟡" if entry["score"] >= 70 else "❌")
            )
            title = entry["task"][:40]
            lines.append(
                f"  {icon} L{entry['level']} {title:<40} {entry['score']:>3}/100"
            )
        lines.append(f"{'─' * 60}\n")
        return "\n".join(lines)

    def summary(self, model_name: str) -> dict[str, Any]:
        avg = (
            round(self.total_score / self.tasks_attempted, 1)
            if self.tasks_attempted
            else 0.0
        )
        pass_rate = (
            round(100 * self.tasks_passed / self.tasks_attempted, 1)
            if self.tasks_attempted
            else 0.0
        )
        return {
            "run_id": self.run_id,
            "agent_name": AGENT_NAME,
            "agent_stack": AGENT_STACK,
            "model": model_name,
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "final_level": self.current_level,
            "total_score": self.total_score,
            "tasks_attempted": self.tasks_attempted,
            "tasks_passed": self.tasks_passed,
            "average_score": avg,
            "pass_rate_percent": pass_rate,
            "level_history": self.level_history,
        }

    def export_report(self, model_name: str) -> Path:
        out_dir = Path(EVAL_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = Path(EVAL_OUTPUT_FILE) if EVAL_OUTPUT_FILE else out_dir / f"{self.run_id}.json"
        out_path.write_text(json.dumps(self.summary(model_name), indent=2), encoding="utf-8")
        return out_path
