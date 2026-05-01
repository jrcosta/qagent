"""Thread-safe inter-agent message bus for runtime communication."""

import threading
from datetime import datetime, timezone
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class AgentMessageBus:
    """Singleton message bus. Call reset() before each crew run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: dict[str, list[dict]] = {}

    def publish(self, topic: str, message: str, sender: str) -> None:
        with self._lock:
            if topic not in self._messages:
                self._messages[topic] = []
            self._messages[topic].append({
                "sender": sender,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def read(self, topic: str) -> list[dict]:
        with self._lock:
            return list(self._messages.get(topic, []))

    def read_all(self) -> dict[str, list[dict]]:
        with self._lock:
            return {t: list(msgs) for t, msgs in self._messages.items()}

    def reset(self) -> None:
        with self._lock:
            self._messages.clear()


_bus = AgentMessageBus()


def get_bus() -> AgentMessageBus:
    return _bus


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class PublishMessageInput(BaseModel):
    topic: str = Field(
        ...,
        description=(
            "Tópico da mensagem. Valores esperados: "
            "'qa_findings', 'test_strategy', 'critique', 'consolidation'."
        ),
    )
    message: str = Field(..., description="Conteúdo completo da mensagem.")
    sender: str = Field(..., description="Nome/role do agente remetente.")


class PublishMessageTool(BaseTool):
    name: str = "publish_message"
    description: str = (
        "Publica uma mensagem no barramento inter-agente para que outros agentes possam lê-la. "
        "Use ao concluir sua análise para compartilhar descobertas com os agentes seguintes. "
        "Tópicos padrão: 'qa_findings', 'test_strategy', 'critique', 'consolidation'."
    )
    args_schema: Type[BaseModel] = PublishMessageInput

    def _run(self, topic: str, message: str, sender: str) -> str:
        get_bus().publish(topic=topic, message=message, sender=sender)
        return f"[BUS] Mensagem publicada no tópico '{topic}' por '{sender}'."


class ReadMessagesInput(BaseModel):
    topic: str = Field(
        ...,
        description=(
            "Tópico a consultar. Use 'all' para ler todos os tópicos. "
            "Tópicos disponíveis: 'qa_findings', 'test_strategy', 'critique', 'consolidation'."
        ),
    )


class ReadMessagesTool(BaseTool):
    name: str = "read_messages"
    description: str = (
        "Lê mensagens publicadas por outros agentes no barramento inter-agente. "
        "Use no início da sua tarefa para aproveitar análises dos agentes anteriores. "
        "Passe topic='all' para ler todos os tópicos disponíveis."
    )
    args_schema: Type[BaseModel] = ReadMessagesInput

    def _run(self, topic: str) -> str:
        bus = get_bus()

        if topic == "all":
            all_msgs = bus.read_all()
            if not all_msgs:
                return "[BUS] Nenhuma mensagem disponível ainda."
            lines: list[str] = []
            for t, msgs in all_msgs.items():
                lines.append(f"=== Tópico: {t} ===")
                for m in msgs:
                    lines.append(f"[{m['sender']} @ {m['timestamp']}]\n{m['message']}")
            return "\n\n".join(lines)

        messages = bus.read(topic)
        if not messages:
            return f"[BUS] Nenhuma mensagem no tópico '{topic}'."

        lines = [f"=== Tópico: '{topic}' ==="]
        for m in messages:
            lines.append(f"[{m['sender']} @ {m['timestamp']}]\n{m['message']}")
        return "\n\n".join(lines)
