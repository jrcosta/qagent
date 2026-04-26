# AGENTS.md

Guia de trabalho para agentes de IA, contribuidores e automações que atuarem no QAgent.

Este arquivo existe para manter consistência entre mudanças feitas por humanos, agentes de IA e pipelines automatizados. Antes de alterar o projeto, leia este guia junto com `README.md`, `CONTRIBUTING.md` e `docs/memories.md`.

---

## Objetivo do projeto

O QAgent é um pipeline de apoio à qualidade de software. Ele analisa diffs de repositórios, identifica riscos, sugere estratégias de teste, gera testes automatizados e pode reutilizar aprendizados de revisões anteriores por meio de memória vetorial.

A prioridade do projeto é produzir recomendações e artefatos úteis para revisão humana. O QAgent não deve ser tratado como substituto de aprovação técnica humana.

---

## Princípios de arquitetura

Ao modificar o projeto, preserve estes princípios:

1. **Contratos explícitos**
   - Dados entre etapas devem trafegar por schemas Pydantic em `src/schemas/`.
   - Evite dicionários soltos quando o dado representa contrato entre componentes.

2. **Orquestração clara**
   - Fluxos multi-step devem ficar em `src/services/` ou runners em `src/crew/`.
   - Evite esconder decisões importantes dentro de prompts.

3. **Fallback determinístico**
   - Quando um LLM falhar, o sistema deve manter uma saída segura e explicável.
   - Decisões críticas, como classificação de risco e recomendação de geração, devem ter regras rastreáveis.

4. **Agentes com responsabilidade única**
   - `QA Agent`: análise de mudança e riscos.
   - `High Risk Strategy Agent`: enriquecimento para arquivos de alto risco.
   - `Test Generator Agent`: geração de testes.
   - `Test Reviewer Agent`: revisão crítica dos testes gerados.
   - `Memory Agent`: extração e reutilização de aprendizados.

5. **Observabilidade**
   - Fluxos relevantes devem gerar artefatos ou logs com duração, status e decisões aplicadas.
   - Prefira outputs estruturados em JSON quando a informação alimentar outra etapa.

---

## Organização esperada

```text
src/
├─ agent/       # Definições de perfil dos agentes
├─ crew/        # Runners CrewAI e coordenação dos agentes
├─ config/      # Settings, LLM e variáveis de ambiente
├─ prompts/     # Prompts de sistema e instruções especializadas
├─ schemas/     # Contratos Pydantic
├─ services/    # Regras de negócio e orquestração determinística
├─ tasks/       # Tarefas usadas pelos agentes
├─ tools/       # Ferramentas auxiliares para agentes
└─ utils/       # Funções utilitárias sem dependência forte de domínio
```

Use `tests/` para testes unitários e de regressão.
Use `docs/` para documentação técnica que explique decisões, fluxos e limitações.
Use `templates/` para exemplos de GitHub Actions ou integrações externas.

---

## Boas práticas de código

- Escreva código simples, direto e testável.
- Prefira funções pequenas, com nomes claros.
- Evite acoplamento entre agentes e serviços determinísticos.
- Não coloque lógica de negócio dentro de arquivos de prompt.
- Não misture leitura de ambiente com regra de negócio.
- Não faça chamadas externas em import-time.
- Preserve compatibilidade com execução local via `python -m ...`.
- Ao adicionar um novo contrato, crie ou atualize testes cobrindo campos obrigatórios e comportamento esperado.

---

## Boas práticas para prompts

Prompts devem ser tratados como parte do produto.

Ao alterar arquivos em `src/prompts/` ou tarefas em `src/tasks/`:

- Seja explícito sobre formato de saída.
- Peça respostas estruturadas quando o resultado alimentar código.
- Evite instruções vagas como “faça melhor” ou “analise bem”.
- Inclua limites: o que o agente deve fazer e o que deve evitar.
- Não peça ao agente para assumir que código gerado está correto sem validação.
- Não inclua segredos, tokens, URLs privadas ou dados sensíveis.

---

## Segurança

Nunca adicionar ao repositório:

- Chaves de API.
- Tokens do GitHub.
- `.env` real.
- Dados pessoais ou dados de clientes.
- Outputs contendo segredos de outro repositório analisado.

Use `.env.example` para documentar variáveis esperadas.
Use variáveis de ambiente para credenciais.

---

## Memória vetorial

A memória do QAgent deve ser usada para melhorar futuras análises e gerações de testes, mas não deve substituir validação humana.

Ao trabalhar com memória:

- Consulte `docs/memories.md`.
- Prefira metadados claros: repositório, arquivo, linguagem, tipo de feedback e origem.
- Evite armazenar conteúdo sensível de PRs privados.
- Trate resultados recuperados via RAG como contexto auxiliar, não como verdade absoluta.

---

## Testes

Antes de abrir PR ou concluir uma alteração, rode quando possível:

```bash
python -m pytest
```

Para mudanças específicas, priorize testes próximos ao componente alterado:

- `src/services/context_builder.py` → `tests/test_context_builder.py`
- `src/utils/pr_utils.py` → `tests/test_pr_utils.py`
- `src/utils/review_comment_utils.py` → `tests/test_review_comment_utils.py`
- `src/tools/memory_tools.py` → testes de memória e artefatos

Ao adicionar nova regra determinística, adicione teste unitário.
Ao alterar prompt, adicione pelo menos fixture ou documentação do comportamento esperado.

---

## Commits e PRs

Use Conventional Commits:

```text
feat: adicionar revisão crítica de testes gerados
fix: corrigir parsing de comentários de review
refactor: separar estratégia de risco alto
chore: atualizar dependências
```

PRs devem explicar:

- O problema resolvido.
- A solução aplicada.
- Como foi testado.
- Riscos ou limitações conhecidas.

---

## O que evitar

- Adicionar nova feature antes de estabilizar o fluxo existente.
- Criar dependência circular entre `crew`, `services` e `tools`.
- Tornar o LLM obrigatório para caminhos que poderiam ter fallback determinístico.
- Abrir PR automático sem validação mínima do teste gerado.
- Atualizar documentação sem verificar se ela bate com o código atual.

---

## Prioridade atual de evolução

A fase atual do projeto é estabilização.

Prioridades:

1. Manter documentação alinhada ao código.
2. Fixar dependências críticas.
3. Padronizar versão de Python suportada.
4. Melhorar cobertura de testes dos serviços determinísticos.
5. Criar fluxo demo reproduzível para portfólio.