from argparse import ArgumentParser

from src.config.settings import get_settings
from src.schemas.automation import RepositoryRegistration
from src.services.automation_store import AutomationStore
from src.services.repository_workspace import validate_repository_registration


def parse_args():
    parser = ArgumentParser(description="Registro de repositórios do QAgent")
    parser.add_argument("full_name", help="owner/repository")
    parser.add_argument("--local-path", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--cooperative-analysis", action="store_true")
    parser.add_argument("--no-auto-fetch", action="store_true")
    parser.add_argument(
        "--allow-test-execution",
        action="store_true",
        help="Permite executar código/testes do PR; use apenas em sandbox confiável",
    )
    parser.add_argument(
        "--allow-push",
        action="store_true",
        help="Também aceita eventos push; padrão: somente pull_request",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    allowed_events = ["pull_request"]
    if args.allow_push:
        allowed_events.append("push")
    registration = RepositoryRegistration(
        full_name=args.full_name,
        local_path=args.local_path,
        output_root=args.output_root,
        cooperative_analysis=args.cooperative_analysis,
        auto_fetch=not args.no_auto_fetch,
        allow_test_execution=args.allow_test_execution,
        allowed_events=allowed_events,
    )
    validated = validate_repository_registration(registration)
    AutomationStore(settings.automation_database_path).register_repository(
        validated
    )
    print(validated.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
