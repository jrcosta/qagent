from argparse import ArgumentParser

from src.config.settings import get_settings
from src.services.automation_store import AutomationStore
from src.services.automation_worker import AutomationWorker
from src.services.repository_workspace import RepositoryWorkspaceManager


def parse_args():
    parser = ArgumentParser(description="Worker autônomo do QAgent")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    worker = AutomationWorker(
        settings=settings,
        store=AutomationStore(settings.automation_database_path),
        workspace_manager=RepositoryWorkspaceManager(
            settings.automation_workspace_root
        ),
        worker_id=args.worker_id,
        lease_seconds=settings.worker_lease_seconds,
    )
    if args.once:
        job = worker.run_once()
        print(job.model_dump_json(indent=2) if job else "Nenhum job disponível.")
        return
    worker.run_forever(
        poll_interval_seconds=settings.worker_poll_seconds
    )


if __name__ == "__main__":
    main()

