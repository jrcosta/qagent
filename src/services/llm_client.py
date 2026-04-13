from openai import OpenAI

from src.config.settings import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        if not self.settings.llm_api_key:
            raise ValueError("LLM_API_KEY não configurada.")

        self.client = OpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
        )

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        return response.choices[0].message.content or ""