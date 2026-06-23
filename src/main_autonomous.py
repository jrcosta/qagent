from argparse import ArgumentParser
import threading

import uvicorn

from src.api.app import create_app
from src.config.settings import get_settings
from src.services.automation_store import AutomationStore
from src.services.automation_worker import AutomationWorker
from src.services.repository_workspace import RepositoryWorkspaceManager
from src.services.repository_monitor import RepositoryMonitor


def parse_args():
    parser = ArgumentParser(
        description="API e worker autônomo do QAgent em um único processo"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--worker-id", default="embedded-worker")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    store = AutomationStore(settings.automation_database_path)
    worker = AutomationWorker(
        settings=settings,
        store=store,
        workspace_manager=RepositoryWorkspaceManager(
            settings.automation_workspace_root
        ),
        worker_id=args.worker_id,
        lease_seconds=settings.worker_lease_seconds,
    )
    stop = threading.Event()
    thread = threading.Thread(
        target=worker.run_forever,
        kwargs={
            "poll_interval_seconds": settings.worker_poll_seconds,
            "stop_event": stop,
        },
        daemon=True,
    )
    thread.start()
    monitor_thread = None
    if settings.monitor_enabled:
        monitor = RepositoryMonitor(
            store=store,
            github_token=settings.github_token,
        )
        monitor_thread = threading.Thread(
            target=monitor.run_forever,
            kwargs={
                "interval_seconds": settings.monitor_poll_seconds,
                "stop_event": stop,
            },
            daemon=True,
        )
        monitor_thread.start()
    try:
        uvicorn.run(
            create_app(settings, store),
            host=args.host,
            port=args.port,
            reload=False,
        )
    finally:
        stop.set()
        thread.join(timeout=5)
        if monitor_thread:
            monitor_thread.join(timeout=5)


if __name__ == "__main__":
    main()
