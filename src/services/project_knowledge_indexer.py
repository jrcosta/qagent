"""Serviço para indexar e buscar conhecimento do repositório alvo (RAG)."""

import hashlib
import time
from pathlib import Path
from typing import Any

import lancedb
from pydantic import Field

from src.tools.memory_tools import DB_PATH, get_encoder


class ProjectKnowledgeModel(lancedb.pydantic.LanceModel):
    """Modelo do LanceDB para o conhecimento do repositório."""
    id: str
    source_type: str
    source_file: str
    repo: str
    content: str
    vector: lancedb.pydantic.Vector(384)


def _get_project_knowledge_table() -> Any:
    """Retorna a tabela project_knowledge, criando-a se necessário."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(DB_PATH))
    if "project_knowledge" not in db.table_names():
        db.create_table("project_knowledge", schema=ProjectKnowledgeModel)
    return db.open_table("project_knowledge")


def index_project_knowledge(repo_path: str) -> None:
    """
    Busca a pasta `.qagent/knowledge/` no repositório,
    lê os arquivos `.md` e `.txt`, faz o chunking e os adiciona ao LanceDB.
    """
    t0 = time.perf_counter()
    knowledge_dir = Path(repo_path) / ".qagent" / "knowledge"
    
    if not knowledge_dir.exists() or not knowledge_dir.is_dir():
        # Fallback silencioso: a pasta não existe, nada a fazer
        return

    try:
        db = lancedb.connect(str(DB_PATH))
        
        # Limpar o conhecimento antigo deste mesmo repositório
        # O LanceDB não suporta DELETE via where string out of the box muito fácil em algumas versões,
        # O mais seguro é simplesmente recriar a tabela ou dropar e criar se for o caso.
        # Mas como a chave id é um hash do arquivo+chunk, apenas adicionar dados que mudaram
        # pode duplicar se o chunk mudou e deixou sujeira? Sim.
        # Para evitar problemas e ser simples: se a tabela existe, a gente deleta ela inteira e recria.
        # ISSO SE TIVERMOS APENAS 1 REPO EM ANALISE POR VEZ.
        # Como o QAgent roda em um PR por vez no CI, dropar e recriar é seguro.
        if "project_knowledge" in db.table_names():
            db.drop_table("project_knowledge")
            
        table = _get_project_knowledge_table()
        
        encoder = get_encoder()
        rows_to_insert = []
        
        files_found = list(knowledge_dir.rglob("*.md")) + list(knowledge_dir.rglob("*.txt"))
        knowledge_root = knowledge_dir.resolve()

        for file_path in files_found:
            # Block symlinks that could point outside the knowledge directory
            if file_path.is_symlink():
                print(f"  [Knowledge] Symlink ignorado (segurança): {file_path}")
                continue
            resolved_file = file_path.resolve()
            if not resolved_file.is_relative_to(knowledge_root):
                print(f"  [Knowledge] Caminho fora de .qagent/knowledge/ bloqueado: {file_path}")
                continue
            content = file_path.read_text(encoding="utf-8").strip()
            if not content:
                continue
                
            # Chunking simples por parágrafo duplo
            chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
            
            for chunk in chunks:
                chunk_id = hashlib.sha256(f"{str(file_path)}_{chunk}".encode("utf-8")).hexdigest()
                vector = encoder.encode(chunk).tolist()
                
                rows_to_insert.append({
                    "id": chunk_id,
                    "source_type": "project_knowledge",
                    "source_file": str(file_path.relative_to(repo_path)),
                    "repo": str(repo_path),
                    "content": chunk,
                    "vector": vector,
                })
        
        if rows_to_insert:
            table.add(rows_to_insert)
            duration_ms = (time.perf_counter() - t0) * 1000
            print(f"  [Knowledge] Indexados {len(rows_to_insert)} chunks de conhecimento do projeto em {duration_ms:.0f}ms.")
            
    except Exception as exc:
        print(f"  [Knowledge] Erro ao indexar conhecimento do projeto (fallback seguro): {exc}")


def retrieve_project_knowledge(query: str, repo_path: str, k: int = 5) -> str:
    """
    Busca chunks relevantes no conhecimento do projeto.
    Retorna uma string pronta para injeção no prompt ou vazio em caso de erro/nada encontrado.
    """
    if not DB_PATH.exists():
        return ""
        
    try:
        db = lancedb.connect(str(DB_PATH))
        if "project_knowledge" not in db.table_names():
            return ""
            
        table = db.open_table("project_knowledge")
        if table.count_rows() == 0:
            return ""
            
        encoder = get_encoder()
        query_vector = encoder.encode(query).tolist()
        
        # Filtramos por repo local para garantir que n misturamos com outros
        # Usamos prefilter se a versão suportar, senão iteramos
        results = table.search(query_vector).limit(k * 2).to_list()
        
        # Filtrar pelo repositório atual
        valid_chunks = []
        for row in results:
            dist = row.get("_distance", 2.0)
            if dist > 1.3:  # Limite semântico razoável (cosine distance)
                continue
                
            if row.get("repo") == str(repo_path):
                valid_chunks.append(row)
                
            if len(valid_chunks) >= k:
                break
                
        if not valid_chunks:
            return ""
            
        snippets = []
        for row in valid_chunks:
            snippets.append(f"--- Fonte: {row['source_file']} ---\n{row['content']}")
            
        return "\n\n".join(snippets)
        
    except Exception as exc:
        print(f"  [Knowledge] Erro ao recuperar conhecimento do projeto (fallback seguro): {exc}")
        return ""
