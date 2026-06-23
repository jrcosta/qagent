from argparse import ArgumentParser

from src.config.settings import get_settings
from src.services.automation_store import AutomationStore
from src.services.repository_monitor import RepositoryMonitor


def parse_args():
    parser = ArgumentParser(description="Monitor reconciliador do QAgent")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    monitor = RepositoryMonitor(
        store=AutomationStore(settings.automation_database_path),
        github_token=settings.github_token,
    )
    if args.once:
        print(f"{monitor.poll_once()} job(s) criado(s).")
        return
    monitor.run_forever(interval_seconds=settings.monitor_poll_seconds)


if __name__ == "__main__":
    main()
