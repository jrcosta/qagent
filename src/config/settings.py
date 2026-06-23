import os
from dataclasses import dataclass
from dotenv import load_dotenv

# carrega variáveis do arquivo .env
load_dotenv()


@dataclass
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")

    llm_model: str = os.getenv(
        "LLM_MODEL",
        "groq/llama-3.3-70b-versatile"
    )

    llm_api_key: str = os.getenv(
        "LLM_API_KEY",
        ""
    )

    llm_base_url: str = os.getenv(
        "LLM_BASE_URL",
        "https://api.groq.com/openai/v1"
    )

    llm_temperature: float = float(
        os.getenv("LLM_TEMPERATURE", "0.2")
    )

    automation_database_path: str = os.getenv(
        "QAGENT_AUTOMATION_DB",
        "runtime/automation.db",
    )

    automation_workspace_root: str = os.getenv(
        "QAGENT_WORKSPACE_ROOT",
        "runtime/workspaces",
    )

    github_webhook_secret: str = os.getenv(
        "GITHUB_WEBHOOK_SECRET",
        "",
    )

    admin_token: str = os.getenv(
        "QAGENT_ADMIN_TOKEN",
        "",
    )

    worker_lease_seconds: int = int(
        os.getenv("QAGENT_WORKER_LEASE_SECONDS", "900")
    )

    worker_poll_seconds: float = float(
        os.getenv("QAGENT_WORKER_POLL_SECONDS", "2")
    )

    github_token: str = os.getenv("GITHUB_TOKEN", "")

    monitor_enabled: bool = os.getenv(
        "QAGENT_MONITOR_ENABLED",
        "false",
    ).lower() in {"1", "true", "yes"}

    monitor_poll_seconds: float = float(
        os.getenv("QAGENT_MONITOR_POLL_SECONDS", "300")
    )


def get_settings() -> Settings:
    return Settings()
