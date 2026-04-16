from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import html
import json
import re
import shutil


ROOT = Path.cwd()
SITE_DIR = ROOT / "site"
HISTORY_DIR = SITE_DIR / "history"
PREVIOUS_PAGES_DIR = ROOT / "previous-pages"


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--analysis-file",
        default="outputs/analysis.md",
        help="Caminho do relatório markdown a ser publicado",
    )
    parser.add_argument(
        "--repo-owner",
        default="unknown-owner",
        help="Owner do repositório analisado",
    )
    parser.add_argument(
        "--repo-name",
        default="unknown-repo",
        help="Nome do repositório analisado",
    )
    parser.add_argument(
        "--base-sha",
        default="",
        help="SHA base usado na comparação",
    )
    parser.add_argument(
        "--head-sha",
        default="",
        help="SHA final usado na comparação",
    )
    return parser.parse_args()


def copy_previous_history() -> None:
    previous_history = PREVIOUS_PAGES_DIR / "history"
    if previous_history.exists():
        shutil.copytree(previous_history, HISTORY_DIR, dirs_exist_ok=True)


def ensure_site_dirs() -> None:
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_slug_part(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-._")
    return sanitized or "unknown"


def current_run_slug(repo_owner: str, repo_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
    owner = sanitize_slug_part(repo_owner)
    repo = sanitize_slug_part(repo_name)
    return f"{timestamp}__{owner}__{repo}"


def read_analysis(analysis_file: Path) -> str:
    if not analysis_file.exists():
        return "# Nenhum relatório foi gerado\n"
    return analysis_file.read_text(encoding="utf-8")


def short_sha(sha: str) -> str:
    sha = (sha or "").strip()
    if not sha:
        return "-"
    return sha[:8]


def build_run_metadata(repo_owner: str, repo_name: str, base_sha: str, head_sha: str, run_slug: str) -> dict:
    return {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "repo_full_name": f"{repo_owner}/{repo_name}",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "base_sha_short": short_sha(base_sha),
        "head_sha_short": short_sha(head_sha),
        "run_slug": run_slug,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_run_pages(run_slug: str, analysis_md: str, metadata: dict) -> None:
    run_dir = HISTORY_DIR / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)

    md_file = run_dir / "analysis.md"
    md_file.write_text(analysis_md, encoding="utf-8")

    metadata_file = run_dir / "metadata.json"
    metadata_file.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    repo_full_name = html.escape(metadata["repo_full_name"])
    base_sha_short = html.escape(metadata["base_sha_short"])
    head_sha_short = html.escape(metadata["head_sha_short"])

    html_file = run_dir / "index.html"
    html_file.write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>QAgent Report - {html.escape(run_slug)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 16px; line-height: 1.5; }}
    pre {{ white-space: pre-wrap; word-wrap: break-word; background: #f6f8fa; padding: 16px; border-radius: 8px; }}
    a {{ text-decoration: none; }}
    .meta {{ background: #f6f8fa; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }}
  </style>
</head>
<body>
  <p><a href="../../index.html">← Voltar ao histórico</a></p>
  <h1>Relatório QAgent</h1>
  <div class="meta">
    <p><strong>Repositório:</strong> {repo_full_name}</p>
    <p><strong>Execução:</strong> {html.escape(run_slug)}</p>
    <p><strong>Comparação:</strong> {base_sha_short} → {head_sha_short}</p>
  </div>
  <pre>{html.escape(analysis_md)}</pre>
</body>
</html>
""",
        encoding="utf-8",
    )


def load_run_metadata(run_dir: Path) -> dict:
    metadata_file = run_dir / "metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    name_parts = run_dir.name.split("__")
    repo_owner = name_parts[1] if len(name_parts) > 1 else "unknown-owner"
    repo_name = name_parts[2] if len(name_parts) > 2 else "unknown-repo"

    return {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "repo_full_name": f"{repo_owner}/{repo_name}",
        "base_sha": "",
        "head_sha": "",
        "base_sha_short": "-",
        "head_sha_short": "-",
        "run_slug": run_dir.name,
        "generated_at_utc": "",
    }


def list_runs() -> list[dict]:
    if not HISTORY_DIR.exists():
        return []

    run_dirs = [p for p in HISTORY_DIR.iterdir() if p.is_dir()]
    run_dirs.sort(key=lambda path: path.name, reverse=True)

    runs = []
    for run_dir in run_dirs:
        metadata = load_run_metadata(run_dir)
        runs.append(
            {
                "slug": run_dir.name,
                "repo_full_name": metadata.get("repo_full_name", "unknown-owner/unknown-repo"),
                "base_sha_short": metadata.get("base_sha_short", "-"),
                "head_sha_short": metadata.get("head_sha_short", "-"),
            }
        )
    return runs


def write_index(runs: list[dict]) -> None:
    if not runs:
        items = "<li>Nenhuma execução registrada.</li>"
    else:
        items = "\n".join(
            (
                '<li>'
                f'<a href="history/{html.escape(run["slug"])}\/index.html">'
                f'{html.escape(run["repo_full_name"])}'
                '</a>'
                f' — {html.escape(run["slug"])}'
                f' — {html.escape(run["base_sha_short"])} → {html.escape(run["head_sha_short"])}'
                '</li>'
            )
            for run in runs
        )

    index_file = SITE_DIR / "index.html"
    index_file.write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>QAgent History</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 16px; line-height: 1.5; }}
    li {{ margin: 8px 0; }}
    a {{ text-decoration: none; }}
  </style>
</head>
<body>
  <h1>QAgent - Histórico de Relatórios</h1>
  <p>Execuções mais recentes primeiro.</p>
  <ul>
    {items}
  </ul>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    analysis_file = Path(args.analysis_file)

    ensure_site_dirs()
    copy_previous_history()

    analysis_md = read_analysis(analysis_file)
    run_slug = current_run_slug(args.repo_owner, args.repo_name)
    metadata = build_run_metadata(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        run_slug=run_slug,
    )

    write_run_pages(run_slug, analysis_md, metadata)
    runs = list_runs()
    write_index(runs)


if __name__ == "__main__":
    main()
