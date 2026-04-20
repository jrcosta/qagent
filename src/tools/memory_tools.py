"""Tools for reading and writing memories from LanceDB."""

import os
from pathlib import Path
from typing import List, Type, Dict, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import lancedb
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "lancedb"

# Initialize embedding model lazily
_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer("all-MiniLM-L6-v2")
    return _encoder

class MemoryModel(lancedb.pydantic.LanceModel):
    id: str
    repo: str
    pr_number: int
    lesson: str
    original_comment: str
    author: str
    created_at: str
    tags: str
    vector: lancedb.pydantic.Vector(384)

def _get_table() -> Any:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(DB_PATH))
    if "memories" not in db.table_names():
        db.create_table("memories", schema=MemoryModel)
    return db.open_table("memories")


def fetch_all_lessons(limit: int = None) -> list[dict]:
    table = _get_table()
    if table.count_rows() == 0:
        return []
    
    query = table.search(None).limit(limit if limit else 1000)
    
    # Simple sort via Python since lance python api sometimes lacks direct sorting without vector
    results = query.to_list()
    results.sort(key=lambda x: x['created_at'], reverse=True)
    return results


# ---------------------------------------------------------------------------
# CrewAI Tool: query memories
# ---------------------------------------------------------------------------

class QueryMemoriesInput(BaseModel):
    query: str = Field(..., description="Texto de busca para encontrar memórias/lições relevantes.")
    limit: int = Field(10, description="Quantidade máxima de memórias retornadas.")


class QueryMemoriesTool(BaseTool):
    name: str = "query_memories"
    description: str = (
        "Consulta o banco de memórias (lições aprendidas) para evitar erros já cometidos. "
        "Retorna lições relevantes baseadas n busca semântica."
    )
    args_schema: Type[BaseModel] = QueryMemoriesInput

    def _run(self, query: str, limit: int = 10) -> str:
        if not DB_PATH.exists():
            return "Nenhuma memória disponível ainda (banco não existe)."
        
        table = _get_table()
        if table.count_rows() == 0:
            return "Nenhuma memória registrada ainda."

        encoder = get_encoder()
        query_vector = encoder.encode(query).tolist()
        
        results = table.search(query_vector).limit(limit).to_list()

        output_lines: list[str] = []
        for mem in results:
            dist = mem.get("_distance", 2.0)
            if dist > 1.3: # Cosine distance threshold. 1.3 ensures somewhat semantically related texts
                continue
            output_lines.append(
                f"[distance={dist:.3f}] (PR #{mem['pr_number']} em {mem['repo']}, por {mem['author']})\n"
                f"  Lição: {mem['lesson']}"
            )

        if not output_lines:
            return "Nenhuma memória relevante encontrada para esta consulta."

        return "\n\n".join(output_lines)


class ListAllMemoriesInput(BaseModel):
    limit: int = Field(20, description="Quantidade máxima de memórias.")


class ListAllMemoriesTool(BaseTool):
    name: str = "list_all_memories"
    description: str = "Lista todas as memórias/lições aprendidas armazenadas, ordenadas por data decrescente."
    args_schema: Type[BaseModel] = ListAllMemoriesInput

    def _run(self, limit: int = 20) -> str:
        if not DB_PATH.exists():
            return "Nenhuma memória disponível ainda (banco não existe)."

        table = _get_table()
        if table.count_rows() == 0:
            return "Nenhuma memória registrada ainda."

        all_memories = fetch_all_lessons(limit=limit)

        lines: list[str] = []
        for mem in all_memories:
            lines.append(
                f"- [{mem['created_at']}] PR #{mem['pr_number']} ({mem['repo']}): {mem['lesson']}"
            )

        return "\n".join(lines)
