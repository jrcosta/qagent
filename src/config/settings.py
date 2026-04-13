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


def get_settings() -> Settings:
    return Settings()