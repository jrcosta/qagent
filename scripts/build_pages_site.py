from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import html
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


def current_run_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")


def read_analysis(analysis_file: Path) -> str:
    if not analysis_file.exists():
        return "# Nenhum relatório foi gerado\n"
    return analysis_file.read_text(encoding="utf-8")


def write_run_pages(run_slug: str, analysis_md: str) -> None:
    run_dir = HISTORY_DIR / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)

    md_file = run_dir / "analysis.md"
    md_file.write_text(analysis_md, encoding="utf-8")

    html_file = run_dir / "index.html"
    html_file.write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>QAgent Report - {run_slug}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 16px; line-height: 1.5; }}
    pre {{ white-space: pre-wrap; word-wrap: break-word; background: #f6f8fa; padding: 16px; border-radius: 8px; }}
    a {{ text-decoration: none; }}
  </style>
</head>
<body>
  <p><a href="../../index.html">← Voltar ao histórico</a></p>
  <h1>Relatório QAgent</h1>
  <p><strong>Execução:</strong> {html.escape(run_slug)}</p>
  <pre>{html.escape(analysis_md)}</pre>
</body>
</html>
""",
        encoding="utf-8",
    )


def list_runs() -> list[str]:
    if not HISTORY_DIR.exists():
        return []

    runs = [p.name for p in HISTORY_DIR.iterdir() if p.is_dir()]
    runs.sort(reverse=True)
    return runs


def write_index(runs: list[str]) -> None:
    if not runs:
        items = "<li>Nenhuma execução registrada.</li>"
    else:
        items = "\n".join(
            f'<li><a href="history/{html.escape(run)}/index.html">{html.escape(run)}</a></li>'
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
    run_slug = current_run_slug()

    write_run_pages(run_slug, analysis_md)
    runs = list_runs()
    write_index(runs)


if __name__ == "__main__":
    main()