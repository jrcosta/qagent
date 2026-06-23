from __future__ import annotations

import threading

from src.schemas.automation import AutomationEvent
from src.services.automation_store import AutomationStore


class RepositoryMonitor:
    """Reconcilia PRs abertos caso eventos webhook sejam perdidos."""

    def __init__(
        self,
        *,
        store: AutomationStore,
        github_token: str,
        github_client=None,
    ) -> None:
        if not github_token and github_client is None:
            raise ValueError("GITHUB_TOKEN é obrigatório para o monitor")
        self.store = store
        if github_client is not None:
            self.github = github_client
        else:
            try:
                from github import Github
            except ImportError as exc:
                raise RuntimeError(
                    "PyGithub não instalado; execute pip install -r requirements.txt"
                ) from exc
            self.github = Github(github_token)

    def poll_once(self, max_pulls_per_repository: int = 50) -> int:
        created = 0
        for registration in self.store.list_repositories():
            if (
                not registration.enabled
                or "pull_request" not in registration.allowed_events
            ):
                continue
            repository = self.github.get_repo(registration.full_name)
            pulls = repository.get_pulls(
                state="open",
                sort="updated",
                direction="desc",
            )
            for index, pull in enumerate(pulls):
                if index >= max_pulls_per_repository:
                    break
                event = AutomationEvent(
                    delivery_id=(
                        f"poll:{registration.full_name}:"
                        f"{pull.number}:{pull.head.sha}"
                    ),
                    event_name="pull_request",
                    action="poll",
                    repository=registration.full_name,
                    base_sha=pull.base.sha,
                    head_sha=pull.head.sha,
                    ref=pull.head.ref,
                    fetch_ref=f"refs/pull/{pull.number}/head",
                )
                _, was_created = self.store.enqueue(event)
                created += int(was_created)
        return created

    def run_forever(
        self,
        *,
        interval_seconds: float,
        stop_event: threading.Event | None = None,
    ) -> None:
        stop = stop_event or threading.Event()
        while not stop.is_set():
            self.poll_once()
            stop.wait(interval_seconds)
