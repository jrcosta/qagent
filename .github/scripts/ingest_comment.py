#!/usr/bin/env python3
"""Ingest a PR comment forwarded via repository_dispatch.

Runs the memory summariser agent to extract lessons learned and persists them
into data/lancedb. Designed to run inside a GitHub Actions
workflow triggered by `repository_dispatch` with event_type `pr_comment_created`.

Expected client_payload keys:
  - comment_body (str)
  - author       (str)
  - repo         (str)  e.g. "owner/repo"
  - pr_number    (str|int)
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Ensure the project root is in sys.path so `src.*` imports work.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config.settings import get_settings  # noqa: E402
from src.crew.memory_crew import MemoryCrewRunner  # noqa: E402
from src.tools.memory_tools import DB_PATH, DATA_DIR, _get_table, get_encoder  # noqa: E402


def read_dispatch_payload() -> dict:
    """Read client_payload from the GITHUB_EVENT_PATH JSON."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        print("GITHUB_EVENT_PATH not set", file=sys.stderr)
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as f:
        ev = json.load(f)
    return ev.get("client_payload") or ev


def is_duplicate(table, encoder, lesson: str, threshold: float = 0.2) -> bool:
    if table.count_rows() == 0:
        return False
    
    query_vector = encoder.encode(lesson).tolist()
    results = table.search(query_vector).limit(1).to_list()
    
    if not results:
        return False
        
    dist = results[0].get("_distance", 1.0)
    # Cosine distance: smaller means more similar. 0.2 is very similar.
    return dist < threshold


def save_lesson(table, encoder, repo, pr_number, lesson, original_comment, author):
    vector = encoder.encode(lesson).tolist()
    data = [{
        "id": str(uuid.uuid4()),
        "repo": repo,
        "pr_number": int(pr_number),
        "lesson": lesson,
        "original_comment": original_comment,
        "author": author,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "tags": "pr_comment",
        "vector": vector
    }]
    table.add(data)


def parse_lessons(agent_output: str) -> list[str]:
    """Extract lessons from agent output.

    Accepts lines prefixed with '- ' (standard bullet) or numbered lists
    like '1. ', '2. '.  Emoji prefixes (❌ ➕ ✅) are stripped so the stored
    lesson starts with meaningful text.
    """
    import re

    EMOJI_PREFIX = re.compile(r"^[\u2000-\u3300\U0001F000-\U0001FFFF\u2600-\u27BF\s]+")

    lessons: list[str] = []
    for line in agent_output.strip().splitlines():
        line = line.strip()
        # Match '- text' or '1. text'
        if line.startswith("- "):
            candidate = line[2:].strip()
        elif re.match(r"^\d+\.\s", line):
            candidate = re.sub(r"^\d+\.\s+", "", line).strip()
        else:
            continue
        # Strip leading emoji/symbols and markdown bold (**...**)
        candidate = EMOJI_PREFIX.sub("", candidate).strip()
        candidate = re.sub(r"\*\*(.+?)\*\*", r"\1", candidate).strip()
        if len(candidate) > 10:
            lessons.append(candidate)
    return lessons


def main():
    payload = read_dispatch_payload()

    comment_body = payload.get("comment_body", "")
    author = payload.get("author", "unknown")
    repo = payload.get("repo", "unknown")
    pr_number = payload.get("pr_number", 0)

    if not comment_body or len(comment_body.strip()) < 10:
        print("Comment too short or empty; exiting.")
        return

    print(f"🧠 Running memory summariser for PR #{pr_number} in {repo} ...")
    settings = get_settings()
    crew = MemoryCrewRunner(settings)
    agent_output = crew.run(
        comment_body=comment_body,
        repo=repo,
        pr_number=int(pr_number),
    )

    print(f"Agent output:\n{agent_output}\n")

    # Always ensure the DB exists (so git can track data/lancedb even on
    # runs where no lessons are extracted).
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    table = _get_table()
    encoder = get_encoder()

    lessons = parse_lessons(agent_output)
    if not lessons:
        print("No lessons extracted from the comment.")
        return

    saved = 0
    for lesson in lessons:
        if is_duplicate(table, encoder, lesson):
            print(f"  ⏭️  Duplicate skipped: {lesson[:60]}...")
            continue
        save_lesson(table, encoder, repo, pr_number, lesson, comment_body, author)
        print(f"  ✅ Saved: {lesson[:80]}")
        saved += 1
    print(f"\n💾 {saved} lesson(s) saved to {DB_PATH}")


if __name__ == "__main__":
    main()
