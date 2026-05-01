import os
import re
import subprocess
from pathlib import Path
from typing import Optional


DEFAULT_PR_BODY_MAX_CHARS = 60_000
COMPACT_PR_BODY_MAX_LIST_ITEMS = 80


def _safe_resolve(repo_path: Path, relative_path: str) -> Path:
    """Resolve path and raise if it escapes repo_path (path traversal guard)."""
    resolved = (repo_path / relative_path).resolve()
    repo_root = repo_path.resolve()
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"Path traversal blocked: '{relative_path}' resolves outside repo root")
    return resolved


def parse_test_files_from_output(agent_output: str) -> dict[str, str]:
    """Extrai arquivos de teste do output do agente no formato ### FILE: path + bloco de código."""
    files: dict[str, str] = {}
    pattern = r"###\s*FILE:\s*(.+?)\s*\n```[^\n]*\n(.*?)```"
    matches = re.findall(pattern, agent_output, re.DOTALL)

    for file_path, code in matches:
        file_path = file_path.strip()
        code = code.strip()
        if not file_path or not code:
            continue
        # Reject absolute paths and obvious traversal before repo_path is known
        if os.path.isabs(file_path) or "\x00" in file_path:
            continue
        if ".." in Path(file_path).parts:
            continue
        files[file_path] = code

    return files


def write_test_files(repo_path: Path, test_files: dict[str, str]) -> list[str]:
    """Escreve os arquivos de teste no repositório e retorna lista de caminhos criados."""
    created_files: list[str] = []

    for relative_path, content in test_files.items():
        full_path = _safe_resolve(repo_path, relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        created_files.append(relative_path)

    return created_files


def run_git(args: list[str], repo_path: Path) -> subprocess.CompletedProcess:
    """Executa um comando git no repositório."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Erro git: {' '.join(args)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def create_branch_and_commit(
    repo_path: Path,
    branch_name: str,
    test_files: list[str],
    commit_message: str,
) -> None:
    """Cria branch, adiciona arquivos de teste e faz commit."""
    run_git(["config", "user.name", "qagent[bot]"], repo_path)
    run_git(["config", "user.email", "qagent[bot]@users.noreply.github.com"], repo_path)

    run_git(["checkout", "-b", branch_name], repo_path)

    for file_path in test_files:
        run_git(["add", file_path], repo_path)

    run_git(["commit", "-m", commit_message], repo_path)


def push_branch(repo_path: Path, branch_name: str) -> None:
    """Faz push da branch para o remote origin."""
    run_git(["push", "origin", branch_name], repo_path)


def commit_and_push_to_branch(
    repo_path: Path,
    branch_name: str,
    files: list[str],
    commit_message: str,
) -> None:
    """Configura git, adiciona arquivos e faz push para a branch existente."""
    run_git(["config", "user.name", "qagent[bot]"], repo_path)
    run_git(["config", "user.email", "qagent[bot]@users.noreply.github.com"], repo_path)

    for file_path in files:
        run_git(["add", file_path], repo_path)

    run_git(["commit", "-m", commit_message], repo_path)
    run_git(["push", "origin", branch_name], repo_path)


def build_pr_body(
    qa_report: str,
    test_files: list[str],
    analyzed_files: list[str],
) -> str:
    """Monta o corpo do PR descrevendo os testes criados."""
    max_body_chars = int(os.getenv("QAGENT_PR_BODY_MAX_CHARS", DEFAULT_PR_BODY_MAX_CHARS))
    files_list = "\n".join(f"- `{f}`" for f in test_files)
    analyzed_list = "\n".join(f"- `{f}`" for f in analyzed_files)

    full_body = f"""## 🧪 Testes Unitários Gerados Automaticamente

### Arquivos analisados
{analyzed_list}

### Arquivos de teste criados
{files_list}

### Motivação
Estes testes foram gerados automaticamente com base no relatório de QA produzido pelo agente de análise.
As sugestões de testes unitários do relatório foram transformadas em código executável para aumentar
a cobertura de testes e prevenir regressões.

### Base do relatório de QA
<details>
<summary>Clique para ver o relatório de QA completo</summary>

{qa_report}

</details>
"""

    if len(full_body) <= max_body_chars:
        return full_body

    compact_files_list = _format_compact_file_list(test_files)
    compact_analyzed_list = _format_compact_file_list(analyzed_files)

    return f"""## 🧪 Testes Unitários Gerados Automaticamente

### Arquivos analisados
{compact_analyzed_list}

### Arquivos de teste criados
{compact_files_list}

### Motivação
Estes testes foram gerados automaticamente com base no relatório de QA produzido pelo agente de análise.
As sugestões de testes unitários do relatório foram transformadas em código executável para aumentar
a cobertura de testes e prevenir regressões.

### Relatório de QA
O corpo completo do PR ficou com {len(full_body)} caracteres e excedeu o limite seguro de {max_body_chars} caracteres para a API do GitHub.

Agente: resuma o relatório de QA antes de publicar os detalhes completos no PR. Preserve os principais riscos, arquivos impactados,
cenários de teste cobertos e qualquer ponto que precise de atenção na revisão.
"""


def _format_compact_file_list(files: list[str]) -> str:
    displayed_files = files[:COMPACT_PR_BODY_MAX_LIST_ITEMS]
    files_list = "\n".join(f"- `{f}`" for f in displayed_files)

    hidden_count = len(files) - len(displayed_files)
    if hidden_count > 0:
        files_list += f"\n- ... e mais {hidden_count} arquivo(s)"

    return files_list or "- Nenhum arquivo informado"


def open_pull_request(
    github_token: str,
    repo_full_name: str,
    branch_name: str,
    base_branch: str,
    title: str,
    body: str,
) -> str:
    """Abre um Pull Request no GitHub e retorna a URL."""
    from github import Github

    gh = Github(github_token)
    repo = gh.get_repo(repo_full_name)

    pr = repo.create_pull(
        title=title,
        body=body,
        head=branch_name,
        base=base_branch,
    )

    return pr.html_url


def get_repo_full_name(repo_path: Path) -> str:
    """Obtém owner/repo do remote origin."""
    result = run_git(["remote", "get-url", "origin"], repo_path)
    url = result.stdout.strip()

    # SSH: git@github.com:owner/repo.git
    ssh_match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1)

    # HTTPS: https://github.com/owner/repo.git
    https_match = re.search(r"github\.com/(.+?)(?:\.git)?$", url)
    if https_match:
        return https_match.group(1)

    raise ValueError(f"Não foi possível extrair owner/repo da URL: {url}")


def get_current_branch(repo_path: Path) -> str:
    """Retorna o nome da branch atual."""
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    return result.stdout.strip()


def add_pr_comment(
    github_token: str,
    repo_full_name: str,
    branch_name: str,
    comment_body: str,
) -> None:
    """Post a comment on the open PR whose head matches branch_name."""
    from github import Github

    gh = Github(github_token)
    repo = gh.get_repo(repo_full_name)

    # Find the PR by head branch
    pulls = repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch_name}")
    for pr in pulls:
        pr.create_issue_comment(comment_body)
        return

    raise RuntimeError(f"PR not found for branch {branch_name}")
