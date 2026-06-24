# Runtime autônomo

## Visão geral

O runtime autônomo recebe eventos GitHub, persiste jobs em SQLite e executa o
coordinator em worktrees Git isolados.

```text
GitHub webhook
    ↓ assinatura HMAC
FastAPI
    ↓ delivery idempotente
SQLite queue
    ↓ lease + heartbeat
Worker
    ↓ worktree isolado
AgenticRepositoryCoordinator
    ↓ comentário idempotente no PR
COMPLETED | ESCALATED | FAILED
```

O runtime não cria commits, pushes ou PRs. Ele produz testes e artefatos no
worktree temporário, salva os outputs do QAgent no diretório configurado e,
quando `GITHUB_TOKEN` está configurado, publica ou atualiza um comentário
consolidado no PR.

## Configuração

Defina no `.env`:

```dotenv
GITHUB_WEBHOOK_SECRET=segredo-configurado-no-github
QAGENT_ADMIN_TOKEN=token-administrativo-longo
QAGENT_AUTOMATION_DB=runtime/automation.db
QAGENT_WORKSPACE_ROOT=runtime/workspaces
QAGENT_WORKER_LEASE_SECONDS=900
QAGENT_WORKER_POLL_SECONDS=2
QAGENT_MONITOR_ENABLED=false
QAGENT_MONITOR_POLL_SECONDS=300
GITHUB_TOKEN=
```

Também configure as credenciais LLM já usadas pelo QAgent.

## Registrar um repositório

Somente repositórios registrados aceitam eventos:

```bash
python -m src.main_registry owner/repository \
  --local-path /srv/repos/repository \
  --output-root /srv/qagent-outputs
```

Por padrão, apenas eventos `pull_request` são permitidos. Para aceitar `push`:

```bash
python -m src.main_registry owner/repository \
  --local-path /srv/repos/repository \
  --output-root /srv/qagent-outputs \
  --allow-push
```

Por segurança, o registro padrão executa somente a análise. Para permitir
geração e execução de testes:

```bash
python -m src.main_registry owner/repository \
  --local-path /srv/repos/repository \
  --output-root /srv/qagent-outputs \
  --allow-test-execution
```

Essa opção executa código do PR via pytest. Ative somente para repositórios
confiáveis e execute o worker em usuário sem privilégios ou sandbox dedicado.

O checkout registrado deve ter um remote `origin` acessível. O worker cria um
worktree descartável por job e não modifica o checkout principal.

## Iniciar

Modo simples, API e worker no mesmo processo:

```bash
python -m src.main_autonomous --host 127.0.0.1 --port 8000
```

Modo separado:

```bash
python -m src.main_api --host 127.0.0.1 --port 8000
python -m src.main_worker
```

Reconciliação periódica opcional:

```bash
python -m src.main_monitor
```

Ou defina `QAGENT_MONITOR_ENABLED=true` no modo all-in-one. O monitor consulta
PRs abertos e cria jobs sintéticos idempotentes quando um webhook foi perdido.
Ele requer `GITHUB_TOKEN`.

## Feedback automático no PR

Para eventos `pull_request`, o worker publica um comentário idempotente com:

- status da execução e `run_id`;
- distribuição de risco;
- arquivos analisados e principais recomendações;
- arquivos de teste gerados, quando houver;
- links locais dos artefatos estruturados;
- aviso explícito quando houver escalação humana.

O comentário é identificado por um marcador HTML interno e atualizado em novas
execuções do mesmo PR, evitando duplicatas. A falha ao publicar o comentário é
registrada em `feedback_status=FAILED`, mas não invalida uma análise já
concluída.

Para processar somente um job:

```bash
python -m src.main_worker --once
```

## Configurar o webhook GitHub

No repositório GitHub:

1. Abra **Settings → Webhooks → Add webhook**.
2. Payload URL: `https://seu-dominio/webhooks/github`.
3. Content type: `application/json`.
4. Secret: o mesmo `GITHUB_WEBHOOK_SECRET`.
5. Selecione Pull requests e, se autorizado no registro, Pushes.

Use TLS no proxy reverso. O servidor escuta em `127.0.0.1` por padrão.

## Endpoints

| Endpoint | Autenticação | Função |
|---|---|---|
| `POST /webhooks/github` | Assinatura GitHub | Receber eventos |
| `GET /health` | Pública | Saúde de banco, configuração e worker |
| `GET /metrics` | Token admin | Métricas da fila |
| `GET /jobs` | Token admin | Listar jobs |
| `GET /jobs/{id}` | Token admin | Consultar job |
| `POST /jobs/{id}/retry` | Token admin | Reencaminhar dead-letter |
| `GET /repositories` | Token admin | Listar registros |
| `POST /repositories` | Token admin | Registrar/atualizar repo |

O token administrativo deve ser enviado no header:

```text
X-QAgent-Admin-Token: <QAGENT_ADMIN_TOKEN>
```

## Confiabilidade

- `X-GitHub-Delivery` possui índice único e evita jobs duplicados.
- Claims usam transação `BEGIN IMMEDIATE`.
- Jobs `RUNNING` possuem lease renovada por heartbeat.
- Leases expiradas retornam automaticamente para a fila.
- Falhas usam retry exponencial e depois `DEAD_LETTER`.
- PRs de forks são buscados por `refs/pull/<n>/head`.
- O monitor periódico reconcilia PRs abertos e deduplica por head SHA.
- Cada job usa worktree isolado e descartável.
- Jobs escalados preservam `coordinator_status=ESCALATED`.
- O coordinator run usa o próprio `job_id`, permitindo retomada após crash.

## Limites

- SQLite suporta bem um nó ou baixa concorrência. Múltiplos nós exigirão um
  backend transacional compartilhado.
- O checkout registrado precisa ter acesso Git ao remote.
- Ações externas como abrir PR, push ou commit continuam desabilitadas.
- Comentários no PR dependem de `GITHUB_TOKEN` com permissão de escrita no repo.
- Recomenda-se executar o processo com usuário de sistema sem privilégios.
- `allow_test_execution` é desativado por padrão porque PRs podem conter código
  hostil.
