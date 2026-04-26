import pytest

from src.tools import memory_tools


class FakeVector:
    def tolist(self) -> list[float]:
        return [0.1] * 384


class FakeEncoder:
    def __init__(self) -> None:
        self.encoded_text = ""

    def encode(self, text: str) -> FakeVector:
        self.encoded_text = text
        return FakeVector()


class FakeTable:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, rows: list[dict]) -> None:
        self.rows.extend(rows)


def test_save_lesson_persists_official_memory_row(monkeypatch) -> None:
    encoder = FakeEncoder()
    table = FakeTable()
    monkeypatch.setattr(memory_tools, "get_encoder", lambda: encoder)
    monkeypatch.setattr(memory_tools, "_get_table", lambda: table)

    row = memory_tools.save_lesson(
        repo="org/repo",
        pr_number=42,
        lesson="  Mockar servicos externos.  ",
        original_comment="#qagent-test-review ...",
        author="qagent[bot]",
        tags="test-review,mock",
    )

    assert table.rows == [row]
    assert encoder.encoded_text == "Mockar servicos externos."
    assert row["repo"] == "org/repo"
    assert row["pr_number"] == 42
    assert row["lesson"] == "Mockar servicos externos."
    assert row["original_comment"] == "#qagent-test-review ..."
    assert row["author"] == "qagent[bot]"
    assert row["tags"] == "test-review,mock"
    assert len(row["vector"]) == 384


def test_save_lesson_rejects_empty_lesson() -> None:
    with pytest.raises(ValueError, match="lesson não pode ser vazia"):
        memory_tools.save_lesson(
            repo="org/repo",
            pr_number=42,
            lesson="   ",
            original_comment="comentario",
            author="qagent[bot]",
        )
