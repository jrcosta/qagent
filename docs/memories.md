# Memórias de Revisão (PR Comment → Lessons Learned)

## Visão geral

Quando o agente gerador de testes unitários cria um PR no **repo alvo**, ele
posta automaticamente o comentário:

> @copilot valide os testes deste pr, sua estrutura e aderência ao projeto.

Quando o Copilot (ou um revisor) responde com observações, um workflow no
repo alvo encaminha esse comentário para o repositório `qagent` via
`repository_dispatch`. No `qagent`, um **agente sumarizador** (CrewAI) extrai
as lições aprendidas e as persiste utilizando um banco vetorial com **LanceDB** na 
pasta `data/lancedb`, com auxílio de sentence-transformers.

Na próxima execução do gerador de testes, essas lições são consultadas via buscas
de similaridade nos embeddings vetoriais e repassadas ao prompt,
injetadas no prompt, evitando que os mesmos erros se repitam.

## Arquitetura

```
Repo Alvo                              Repo qagent
─────────                              ───────────
PR criado pelo agente
  └─ comentário automático:
     "@copilot valide os testes..."
         │
         ▼
Copilot/revisor responde
  com observações
         │
         ▼
forward-pr-comment.yml                ingest-pr-comment.yml
  (issue_comment trigger)       ──►      (repository_dispatch)
  envia payload via dispatch              │
                                          ▼
                                   ingest_comment.py
                                     → MemoryCrewRunner
                                       (agente sumarizador)
                                          │
                                          ▼
                                   data/memories.db
                                     (SQLite, commitado)
                                          │
                                          ▼
                                   Próxima execução do
                                   gerador de testes lê
                                   memórias via QueryMemoriesTool
```

## Arquivos envolvidos

### No repo qagent

| Arquivo | Descrição |
|---------|-----------|
| `.github/workflows/ingest-pr-comment.yml` | Workflow que recebe `repository_dispatch` tipo `pr_comment_created` e executa o script de ingestão |
| `.github/scripts/ingest_comment.py` | Script que chama o agente sumarizador e persiste lições no SQLite |
| `src/agent/memory_agent.py` | Factory do agente sumarizador (CrewAI) |
| `src/tasks/memory_task.py` | Task que instrui o agente a extrair lições do comentário |
| `src/crew/memory_crew.py` | Crew runner do agente sumarizador |
| `src/tools/memory_tools.py` | Tools CrewAI: `QueryMemoriesTool` e `ListAllMemoriesTool` para leitura do banco |
| `src/crew/test_generator_crew.py` | Atualizado para consultar memórias antes de gerar testes |
| `src/tasks/test_generator_task.py` | Atualizado para injetar memórias no prompt |
| `src/main_test_generator.py` | Atualizado para postar comentário `@copilot` após criar PR |
| `src/utils/pr_utils.py` | Nova função `add_pr_comment` |
| `data/memories.db` | Banco SQLite com as lições (commitado no repo) |

### No repo alvo

| Arquivo | Descrição |
|---------|-----------|
| `.github/workflows/forward-pr-comment.yml` | Workflow que escuta `issue_comment` em PRs contendo "Copilot" e encaminha para `qagent` via `repository_dispatch` |

## Configuração de Secrets

### No repo alvo

| Secret | Descrição |
|--------|-----------|
| `QAGENT_DISPATCH_PAT` | Personal Access Token (classic) com scope `repo` que permite disparar `repository_dispatch` no repo `jrcosta/qagent` |

### No repo qagent

| Secret | Descrição |
|--------|-----------|
| `GROQ_API_KEY` | Chave de API para o LLM usado pelo agente sumarizador |

## Esquema do banco SQLite

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    lesson TEXT NOT NULL,
    original_comment TEXT,
    author TEXT,
    created_at TEXT,
    tags TEXT
);
```

- `lesson`: frase curta e acionável extraída pelo agente sumarizador
- `original_comment`: texto completo do comentário original (para auditoria)
- Deduplicação por fuzzy match (score >= 90) antes de inserir

## Como funciona a consulta de memórias

Antes de gerar testes, o `TestGeneratorCrewRunner` chama `QueryMemoriesTool`
com o nome do arquivo sendo testado. A tool faz fuzzy match (rapidfuzz) contra
todas as lições armazenadas e retorna as mais relevantes. Essas lições são
injetadas no prompt do agente de testes na seção "Lições aprendidas".

## Persistência

O workflow `ingest-pr-comment.yml` faz commit automático de `data/memories.db`
na branch `main` após cada ingestão. Isso garante que as memórias estejam
disponíveis para todas as execuções futuras.

## Como testar localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Criar evento fake
cat > /tmp/event.json << 'EOF'
{
  "client_payload": {
    "comment_body": "Copilot: os testes usam nomes genéricos como test1, deveriam descrever o cenário. Também faltou mockar o serviço externo.",
    "author": "reviewer1",
    "repo": "jrcosta/repo_alvo_api_simples",
    "pr_number": "42"
  }
}
EOF

# Executar ingestão
GITHUB_EVENT_PATH=/tmp/event.json python .github/scripts/ingest_comment.py

# Verificar memórias salvas
python -c "
import sqlite3
conn = sqlite3.connect('data/memories.db')
for r in conn.execute('SELECT id, lesson, created_at FROM memories'):
    print(r)
conn.close()
"
```

## Limitações e próximos passos

- **Busca**: atualmente usa fuzzy match textual (rapidfuzz). Para buscas
  semânticas, considerar gerar embeddings e migrar para pgvector
  (Supabase/Neon).
- **Concorrência**: SQLite com WAL suporta baixa taxa de escrita; suficiente
  para comentários esporádicos de revisão.
- **Escala multi-repo**: o forwarding workflow precisa ser adicionado a cada
  repo alvo. Para muitos repos, considerar uma GitHub App centralizada.
