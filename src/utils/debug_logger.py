from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class DebugLogger:
    base_dir: Path

    @classmethod
    def for_file_analysis(cls, repo_name: str, file_path: str) -> "DebugLogger":
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
        safe_repo = cls._slugify(repo_name)
        safe_file = cls._slugify(file_path)
        run_dir = Path("outputs/debug") / f"{timestamp}__{safe_repo}__{safe_file}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(base_dir=run_dir)

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "unknown"

    def write_text(self, filename: str, content: str) -> None:
        path = self.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def append_text(self, filename: str, content: str) -> None:
        path = self.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(content)

    def write_json(self, filename: str, payload: Any) -> None:
        path = self.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def log_tool_event(self, event: str, payload: dict[str, Any]) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        block = {
            "timestamp": timestamp,
            "event": event,
            **payload,
        }
        self.append_text("tool_calls.log", json.dumps(block, ensure_ascii=False) + "\n")
