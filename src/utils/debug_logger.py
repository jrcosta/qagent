
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class DebugLogger:
    base_dir: Path

    @classmethod
    def for_file_analysis(cls, repo_name: str, file_path: str) -> "DebugLogger":
        safe_repo = repo_name.replace("/", "__").replace(" ", "_")
        safe_file = file_path.replace("/", "__").replace("\\", "__").replace(" ", "_")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
        base_dir = Path("outputs") / "debug" / f"{timestamp}__{safe_repo}__{safe_file}"
        base_dir.mkdir(parents=True, exist_ok=True)
        return cls(base_dir=base_dir)

    def write_text(self, name: str, content: str) -> None:
        path = self.base_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or "", encoding="utf-8")

    def write_json(self, name: str, payload: dict[str, Any]) -> None:
        path = self.base_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def log_tool_start(self, tool_name: str, payload: dict[str, Any]) -> None:
        self._append_log("tool_calls.log", {"event": "START", "tool": tool_name, "payload": payload})

    def log_tool_success(self, tool_name: str, payload: dict[str, Any]) -> None:
        self._append_log("tool_calls.log", {"event": "SUCCESS", "tool": tool_name, "payload": payload})

    def log_tool_error(self, tool_name: str, payload: dict[str, Any]) -> None:
        self._append_log("tool_calls.log", {"event": "ERROR", "tool": tool_name, "payload": payload})

    def _append_log(self, name: str, payload: dict[str, Any]) -> None:
        path = self.base_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
