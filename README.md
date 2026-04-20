# QAgent 🚀

Um ecossistema de agentes de IA focado em **QA**, **Geração de Testes** e **Aprendizado Contínuo** para repositórios automatizados, garantindo qualidade, segurança e aprimoramento em cada ciclo.

![Python](https://img.shields.io/badge/Python-3.14.7+-3776AB?logo=python&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-Agent%20Orchestration-6B46C1)
![Groq](https://img.shields.io/badge/Groq-LLM-F55036)
![LanceDB](https://img.shields.io/badge/LanceDB-Vector%20DB-0066FF)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-2088FF?logo=githubactions&logoColor=white)

---

## Visão Geral

O QAgent fornece diferentes agentes de IA trabalhando em conjunto para garantir qualidade e extrair inteligência dos ciclos de pull request:

| Agente | Descrição |
|--------|-----------|
| **QA Agent** | Analisa mudanças de código a partir do *diff*, identificando riscos, tipo de mudança e sugerindo cenários de testes manuais e automatizados. |
| **Test Generator Agent** | Gera código real de testes automatizados com base na análise do QA Agent e submete PRs automáticos no repositório alvo. |
| **Memory Agent** | Extrai lições aprendidas a partir de comentários de Code Review e as persiste em um banco vetorial (**LanceDB**) para aprimorar futuras gerações. |

> 📚 **Documentação detalhada:** [Sistema de Memórias & Code Review](docs/memories.md) — como o QAgent captura lições de PRs e as reutiliza via busca vetorial.

---

## Funcionalidades Principais

- **Análise Inteligente de Diff** — filtra automaticamente arquivos irrelevantes (lock, lint, configs) e foca no que importa.
- **Relatórios de Risco** — identifica quebras de contrato, vazamento de credenciais e regressões prováveis.
- **Integração via CI** — invocado pelos repositórios alvo via GitHub Actions (`workflow_dispatch` / `repository_dispatch`).
- **Geração e Push de Testes** — cria testes usando o contexto da `main` e abre PRs automaticamente.
- **Inteligência Vetorial (RAG)** — retém conhecimento coletivo de reviews passados usando embeddings e busca por similaridade (*cosine distance*).

---

## Orquestração dos Agentes

```mermaid
flowchart TD
    subgraph TRIGGER ["🔔 Trigger"]
        PUSH["Push no Repo Alvo"]
        PR_COMMENT["Comentário em PR"]
    end

    subgraph QA_FLOW ["🔍 Fluxo de Análise de QA"]
        DIFF["Extrai diff dos<br/>arquivos alterados"]
        CTX1["RepoContextBuilder<br/>monta contexto"]
        QA_AGENT["🤖 QA Agent<br/><i>CrewAI · Groq LLM</i>"]
        REPORT["📄 Relatório de QA<br/><i>riscos · cenários · impacto</i>"]
    end

    subgraph TEST_FLOW ["🧪 Fluxo de Geração de Testes"]
        CTX2["RepoContextBuilder<br/>monta contexto"]
        MEM_QUERY["🧠 Busca semântica<br/>no LanceDB"]
        TEST_AGENT["🤖 Test Generator Agent<br/><i>CrewAI · Groq LLM</i>"]
        CODE["📝 Código de testes gerado"]
        PR_OPEN["🚀 Cria branch, push<br/>e abre PR no repo alvo"]
        COPILOT_REQ["💬 Posta comentário<br/>pedindo validação"]
    end

    subgraph MEM_FLOW ["💾 Fluxo de Memória"]
        DISPATCH["repository_dispatch<br/>com payload do comentário"]
        MEM_AGENT["🤖 Memory Agent<br/><i>CrewAI · Groq LLM</i>"]
        DEDUP["Deduplicação vetorial<br/><i>cosine distance</i>"]
        LANCEDB[("🗄️ LanceDB<br/>data/lancedb")]
    end

    PUSH -->|"workflow_dispatch"| DIFF
    DIFF --> CTX1 --> QA_AGENT --> REPORT

    REPORT --> CTX2
    CTX2 --> MEM_QUERY
    MEM_QUERY -->|"lições relevantes"| TEST_AGENT
    LANCEDB -.->|"embeddings"| MEM_QUERY
    TEST_AGENT --> CODE --> PR_OPEN --> COPILOT_REQ
    COPILOT_REQ -.->|"Copilot responde<br/>no PR"| PR_COMMENT

    PR_COMMENT -->|"repository_dispatch"| DISPATCH
    DISPATCH --> MEM_AGENT
    MEM_AGENT --> DEDUP --> LANCEDB
```

---

## Stack

| Componente | Tecnologia |
|------------|------------|
| Linguagem | Python |
| Orquestração de Agentes | CrewAI |
| LLM Provider | Groq (configurável via variáveis de ambiente) |
| Banco Vetorial | LanceDB |
| Embeddings | sentence-transformers |
| CI/CD | GitHub Actions |

---

## Estrutura do Projeto

```text
qagent/
├─ docs/                      # Documentações técnicas
├─ data/lancedb/              # Banco vetorial de memórias
├─ src/
│  ├─ agent/                  # Perfis dos Agentes (Role, Goal, Backstory)
│  ├─ crew/                   # Orquestração CrewAI (QA, TestGen, Memory)
│  ├─ config/                 # Settings e LLM
│  ├─ prompts/                # Prompts de sistema
│  ├─ schemas/                # Schemas Pydantic
│  ├─ services/               # Context Builder e LLM Client
│  ├─ tools/                  # Ferramentas customizadas (Memory, Repo)
│  ├─ utils/                  # Git, formatação, PR utils
│  ├─ main.py                 # Entrypoint — Agente de QA
│  └─ main_test_generator.py  # Entrypoint — Agente Gerador de Testes
├─ tests/                     # Testes unitários do QAgent
├─ templates/                 # Exemplos de GitHub Actions
└─ requirements.txt
```

---

## Como Instalar

```bash
# 1. Crie e ative um ambiente virtual
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env e defina GROQ_API_KEY, LLM_MODEL, etc.
```

---

## Como Usar Localmente

### Agente de QA (Analisador de Diff)

```bash
python -m src.main \
    --repo-path ./meu-repo \
    --base-sha COMMIT_A \
    --head-sha COMMIT_B \
    --output-file review.md
```

### Agente Gerador de Testes

```bash
python -m src.main_test_generator --repo-path ./meu-repo
```

---

## Status do Projeto

Em pleno desenvolvimento e evolução. As análises e a geração de testes agora contam com abstração completa do pipeline de memória (RAG) utilizando **LanceDB**, elevando a inteligência da CrewAI para os próximos ciclos de CI.
