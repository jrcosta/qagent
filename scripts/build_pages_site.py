from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import html as html_mod
import json
import shutil

import markdown

ROOT = Path.cwd()
SITE_DIR = ROOT / "site"
HISTORY_DIR = SITE_DIR / "history"
PREVIOUS_PAGES_DIR = ROOT / "previous-pages"

# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

SHARED_CSS = """
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --surface-hover: #1c2129;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent: #58a6ff;
  --accent-hover: #79c0ff;
  --green: #3fb950;
  --red: #f85149;
  --yellow: #d29922;
  --purple: #bc8cff;
  --radius: 10px;
  --font-mono: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
}
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--font-sans);
  background: var(--bg);
  color: var(--text);
  margin: 0; padding: 0;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; transition: color .15s; }
a:hover { color: var(--accent-hover); }
.container { max-width: 960px; margin: 0 auto; padding: 32px 20px; }
"""

INDEX_CSS = SHARED_CSS + """
.hero { text-align: center; padding: 48px 0 24px; }
.hero h1 { font-size: 2rem; margin: 0; }
.hero h1 span { color: var(--accent); }
.hero p { color: var(--text-muted); margin: 8px 0 0; font-size: 1.05rem; }
.badge { display: inline-block; font-size: .75rem; padding: 2px 10px; border-radius: 20px;
         background: var(--surface); border: 1px solid var(--border); color: var(--text-muted); margin-left: 8px; }
.cards { display: grid; gap: 12px; margin-top: 24px; }
.card {
  display: flex; align-items: center; gap: 16px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 20px;
  transition: background .15s, border-color .15s;
}
.card:hover { background: var(--surface-hover); border-color: var(--accent); }
.card-icon { font-size: 1.4rem; flex-shrink: 0; }
.card-body { flex: 1; min-width: 0; }
.card-title { font-weight: 600; font-size: .95rem; }
.card-meta { color: var(--text-muted); font-size: .82rem; margin-top: 2px; }
.card-arrow { color: var(--text-muted); font-size: 1.2rem; transition: transform .15s; }
.card:hover .card-arrow { transform: translateX(3px); color: var(--accent); }
.empty { text-align: center; color: var(--text-muted); padding: 60px 0; font-size: 1.1rem; }
footer { text-align: center; color: var(--text-muted); font-size: .8rem; padding: 40px 0 20px;
         border-top: 1px solid var(--border); margin-top: 40px; }
"""

REPORT_CSS = SHARED_CSS + """
.topbar {
  position: sticky; top: 0; z-index: 10;
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 12px 20px; display: flex; align-items: center; gap: 12px;
}
.topbar a { font-size: .9rem; }
.topbar .sep { color: var(--border); }
.topbar .slug { color: var(--text-muted); font-size: .85rem; font-family: var(--font-mono); }
.report { padding-top: 16px; }
.report h1 { font-size: 1.6rem; border-bottom: 1px solid var(--border); padding-bottom: 12px; }
.report h2 { font-size: 1.3rem; margin-top: 32px; color: var(--accent); }
.report h3 { font-size: 1.1rem; margin-top: 24px; }
.report p { margin: 12px 0; }
.report ul, .report ol { padding-left: 24px; }
.report li { margin: 6px 0; }
.report code {
  font-family: var(--font-mono); font-size: .88em;
  background: var(--surface); padding: 2px 6px; border-radius: 4px;
  border: 1px solid var(--border);
}
.report pre {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; overflow-x: auto;
  font-family: var(--font-mono); font-size: .88rem; line-height: 1.5;
}
.report pre code { background: none; border: none; padding: 0; }
.report blockquote {
  border-left: 3px solid var(--accent); margin: 16px 0;
  padding: 8px 16px; color: var(--text-muted); background: var(--surface);
  border-radius: 0 var(--radius) var(--radius) 0;
}
.report table { width: 100%; border-collapse: collapse; margin: 16px 0; }
.report th, .report td {
  border: 1px solid var(--border); padding: 8px 12px; text-align: left;
}
.report th { background: var(--surface); font-weight: 600; }
.report hr { border: none; border-top: 1px solid var(--border); margin: 32px 0; }
.report strong { color: #f0f6fc; }
.meta-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 20px; margin-bottom: 24px;
  display: flex; flex-wrap: wrap; gap: 24px; font-size: .88rem;
}
.meta-item label { color: var(--text-muted); display: block; font-size: .78rem; margin-bottom: 2px; }
.meta-item span { font-family: var(--font-mono); }

/* Novas seções de artefatos */
.section-title { font-size: 1.4rem; margin: 40px 0 20px; color: var(--accent); display: flex; align-items: center; gap: 10px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; text-align: center; }
.stat-value { font-size: 1.8rem; font-weight: 700; color: var(--accent); display: block; }
.stat-label { color: var(--text-muted); font-size: .8rem; text-transform: uppercase; letter-spacing: 1px; }

.artifact-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 40px; }
.artifact-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.artifact-header { padding: 12px 20px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; transition: background .15s; }
.artifact-header:hover { background: var(--surface-hover); }
.artifact-title { font-family: var(--font-mono); font-size: .9rem; display: flex; align-items: center; gap: 8px; }
.artifact-content { padding: 0 20px 20px; border-top: 1px solid var(--border); background: #161b2255; }

.sub-section { margin-top: 20px; }
.sub-section-title { font-size: .9rem; font-weight: 600; margin-bottom: 10px; color: var(--text-muted); text-transform: uppercase; display: flex; align-items: center; gap: 8px; }
.data-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }
.data-item { background: #0d111755; padding: 10px 14px; border-radius: 6px; border: 1px solid var(--border); }
.data-label { font-size: .75rem; color: var(--text-muted); display: block; }
.data-value { font-size: .9rem; }

.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
.badge-low { background: #23863633; color: #3fb950; border: 1px solid #238636; }
.badge-medium { background: #9e6a0333; color: #d29922; border: 1px solid #9e6a03; }
.badge-high { background: #da363333; color: #f85149; border: 1px solid #da3633; }
.badge-info { background: #388bfd33; color: #58a6ff; border: 1px solid #388bfd; }
.badge-policy { background: #8957e533; color: #bc8cff; border: 1px solid #8957e5; }
.memory-list { display: flex; flex-direction: column; gap: 10px; }
.memory-item { background: #0d111755; border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; }
.memory-meta { color: var(--text-muted); font-size: .75rem; font-family: var(--font-mono); margin-bottom: 6px; }
.memory-lesson { font-size: .86rem; margin: 0; }
.memory-empty { color: var(--text-muted); font-size: .86rem; background: #0d111755; border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; }

details summary { cursor: pointer; padding: 8px 0; color: var(--accent); font-size: .9rem; font-weight: 500; }
details summary:hover { color: var(--accent-hover); }
.raw-json { font-family: var(--font-mono); font-size: .8rem; background: #00000044; padding: 12px; border-radius: 6px; overflow-x: auto; margin-top: 10px; border: 1px solid var(--border); }

.error-msg { background: #f8514922; border: 1px solid var(--red); color: var(--red); padding: 12px; border-radius: var(--radius); margin: 20px 0; font-size: .9rem; }
.md-content p { margin: 8px 0; }
.md-content ul, .md-content ol { padding-left: 20px; margin: 8px 0; }
.md-content li { margin: 4px 0; }
.md-content hr { border: none; border-top: 1px solid var(--border); margin: 12px 0; }
footer { text-align: center; color: var(--text-muted); font-size: .8rem; padding: 40px 0 20px;
         border-top: 1px solid var(--border); margin-top: 40px; }
"""

REPORT_JS = r"""
<script>
document.addEventListener('DOMContentLoaded', async () => {
  const summaryContainer = document.getElementById('run-summary-container');
  const artifactsContainer = document.getElementById('artifacts-container');

  const formatMs = (ms) => {
    if (!ms) return '0ms';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getRiskBadge = (level) => {
    const map = {
      'HIGH': { text: 'Alto risco', class: 'badge-high' },
      'MEDIUM': { text: 'Risco médio', class: 'badge-medium' },
      'LOW': { text: 'Baixo risco', class: 'badge-low' }
    };
    const info = map[level] || { text: level, class: 'badge-info' };
    return `<span class="badge ${info.class}">${info.text}</span>`;
  };

  const getQualityBadge = (quality) => {
    const map = {
      'OK': { text: 'Review suficiente', class: 'badge-low' },
      'INCOMPLETE': { text: 'Review incompleto', class: 'badge-high' }
    };
    const info = map[quality] || { text: quality, class: 'badge-info' };
    return `<span class="badge ${info.class}">${info.text}</span>`;
  };

  const getRecBadge = (rec) => {
    const map = {
      'RECOMMENDED': { text: 'Geração recomendada', class: 'badge-low' },
      'SKIPPED': { text: 'Geração pulada', class: 'badge-medium' }
    };
    const info = map[rec] || { text: rec, class: 'badge-info' };
    return `<span class="badge ${info.class}">${info.text}</span>`;
  };

  const escapeHtml = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const renderMemories = (artifact) => {
    const memories = artifact.memories_used || [];
    if (!memories.length) {
      return `
        <div class="memory-empty">
          Nenhuma memória relevante do banco vetorial foi usada na geração deste arquivo.
        </div>
      `;
    }

    return `
      <div class="memory-list">
        ${memories.map((mem) => `
          <div class="memory-item">
            <div class="memory-meta">
              PR #${escapeHtml(mem.pr_number || '--')} · ${escapeHtml(mem.repo || 'repo desconhecido')} ·
              distância ${escapeHtml(mem.distance ?? '--')} · por ${escapeHtml(mem.author || '--')}
            </div>
            <p class="memory-lesson">${escapeHtml(mem.lesson || '')}</p>
          </div>
        `).join('')}
      </div>
    `;
  };

  // 1. Carregar Run Summary
  try {
    const resp = await fetch('run_summary.json');
    if (resp.ok) {
      const data = await resp.json();
      summaryContainer.innerHTML = `
        <div class="section-title">📊 Resumo da Execução</div>
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-value">${data.total_files || 0}</span>
            <span class="stat-label">Arquivos</span>
          </div>
          <div class="stat-card">
            <div style="display:flex; flex-direction:column; gap:4px; align-items:center;">
              ${getRiskBadge('HIGH')} x ${data.risk_distribution?.HIGH || 0}
              ${getRiskBadge('MEDIUM')} x ${data.risk_distribution?.MEDIUM || 0}
              ${getRiskBadge('LOW')} x ${data.risk_distribution?.LOW || 0}
            </div>
            <span class="stat-label" style="margin-top:8px">Distribuição</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">${data.total_steps_skipped || 0}</span>
            <span class="stat-label">Etapas Puladas</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">${data.total_fallbacks_triggered || 0}</span>
            <span class="stat-label">Fallbacks</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">${formatMs(data.total_duration_ms)}</span>
            <span class="stat-label">Duração Total</span>
          </div>
        </div>
        <details>
          <summary>Ver dados brutos do resumo</summary>
          <pre class="raw-json">${JSON.stringify(data, null, 2)}</pre>
        </details>
      `;
    }
  } catch (e) {
    console.error('Erro ao carregar run_summary.json', e);
  }

  // 2. Carregar Artifacts
  try {
    const resp = await fetch('artifacts.json');
    if (resp.ok) {
      const artifacts = await resp.json();
      let html = '<div class="section-title">📦 Artefatos Estruturados</div><div class="artifact-list">';
      
      artifacts.forEach((a, index) => {
        const id = `art-${index}`;
        html += `
          <div class="artifact-card">
            <div class="artifact-header" onclick="document.getElementById('${id}').style.display = document.getElementById('${id}').style.display === 'none' ? 'block' : 'none'">
              <div class="artifact-title">
                <span>📄</span> <strong>${a.file_path}</strong>
              </div>
              <div style="display:flex; gap:8px">
                ${getRiskBadge(a.risk_level)}
                ${getQualityBadge(a.review_quality)}
              </div>
            </div>
            <div id="${id}" class="artifact-content" style="display:none">
              
              <div class="data-grid" style="margin-top:20px">
                <div class="data-item">
                  <span class="data-label">Recomendação de Testes</span>
                  <span class="data-value">${getRecBadge(a.test_generation_recommendation)}</span>
                </div>
                <div class="data-item">
                  <span class="data-label">Políticas Aplicadas</span>
                  <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:4px">
                    ${(a.applied_policies || []).map(p => `<span class="badge badge-policy">${p}</span>`).join('') || '--'}
                  </div>
                </div>
              </div>

              <div class="sub-section">
                <div class="sub-section-title">🔍 Visão Geral e Contexto</div>
                <div class="data-grid">
                   <div class="data-item">
                    <span class="data-label">Linguagem</span>
                    <span class="data-value">${a.context_result?.language || '--'}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Propósito</span>
                    <span class="data-value">${a.context_result?.file_purpose || '--'}</span>
                  </div>
                </div>
              </div>

              <div class="sub-section">
                <div class="sub-section-title">🛡️ Review de QA</div>
                <div class="md-content" style="font-size:.85rem; color:var(--text-muted)">${a.review_result?.summary_html || escapeHtml(a.review_result?.summary || 'Sem resumo disponível')}</div>
                <div class="data-grid">
                  <div class="data-item">
                    <span class="data-label">Principais Riscos</span>
                    <ul style="margin:5px 0; padding-left:18px; font-size:.85rem">
                      ${(a.review_result?.security_vulnerabilities || []).slice(0,2).map(v => `<li>${v}</li>`).join('') || '<li>Nenhum detectado</li>'}
                    </ul>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Impacto Funcional</span>
                    <span class="data-value">${a.review_result?.impact_assessment || '--'}</span>
                  </div>
                </div>
              </div>

              <div class="sub-section">
                <div class="sub-section-title">⏱️ Observabilidade e Performance</div>
                <div class="data-grid">
                  <div class="data-item">
                    <span class="data-label">Etapas Executadas</span>
                    <div style="font-size:.8rem; display:flex; flex-wrap:wrap; gap:4px">
                      ${(a.executed_steps || []).map(s => `<span class="badge badge-info">${s}</span>`).join('')}
                    </div>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Etapas Puladas</span>
                    <div style="font-size:.8rem; color:var(--red)">
                      ${(a.skipped_steps || []).join(', ') || 'Nenhuma'}
                    </div>
                  </div>
                   <div class="data-item">
                    <span class="data-label">Duração das Etapas</span>
                    <div style="font-size:.8rem">
                      ${Object.entries(a.step_durations_ms || {}).map(([s, d]) => `<div>${s}: <strong>${formatMs(d)}</strong></div>`).join('')}
                    </div>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Fallbacks</span>
                    <div style="font-size:.8rem; color:var(--yellow)">
                      ${(a.fallbacks_triggered || []).join(', ') || 'Nenhum'}
                    </div>
                  </div>
                </div>
              </div>

              <div class="sub-section">
                <div class="sub-section-title">🧠 Memórias do Banco Vetorial</div>
                <div class="data-grid" style="margin-bottom:12px">
                  <div class="data-item">
                    <span class="data-label">Memória usada na geração</span>
                    <span class="data-value">${(a.memories_used || []).length ? 'Sim' : 'Não'}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Quantidade recuperada</span>
                    <span class="data-value">${(a.memories_used || []).length}</span>
                  </div>
                </div>
                ${renderMemories(a)}
                ${a.memory_query ? `
                  <details style="margin-top:10px">
                    <summary>Ver consulta usada no banco vetorial</summary>
                    <pre class="raw-json">${escapeHtml(a.memory_query)}</pre>
                  </details>
                ` : ''}
              </div>

              <details style="margin-top:20px">
                <summary>Ver JSON completo do arquivo</summary>
                <pre class="raw-json">${JSON.stringify(a, null, 2)}</pre>
              </details>
            </div>
          </div>
        `;
      });
      html += '</div>';
      artifactsContainer.innerHTML = html;
    }
  } catch (e) {
    console.error('Erro ao carregar artifacts.json', e);
    artifactsContainer.innerHTML = '<div class="error-msg">Aviso: Não foi possível carregar os artefatos estruturados para esta execução.</div>';
  }
});
</script>
"""


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------

def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--analysis-file", default="outputs/analysis.md",
                        help="Caminho do relatório markdown")
    parser.add_argument("--artifacts-dir", default="",
                        help="Diretório com artifacts.json e run_summary.json (padrão: mesmo diretório do analysis-file)")
    parser.add_argument("--target-owner", default="", help="Owner do repo analisado")
    parser.add_argument("--target-repo", default="", help="Nome do repo analisado")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def copy_previous_history() -> None:
    previous_history = PREVIOUS_PAGES_DIR / "history"
    if previous_history.exists():
        shutil.copytree(previous_history, HISTORY_DIR, dirs_exist_ok=True)


def ensure_site_dirs() -> None:
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def run_slug(target_owner: str, target_repo: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
    if target_owner and target_repo:
        return f"{ts}__{target_owner}__{target_repo}"
    return ts


def parse_slug(slug: str) -> dict:
    """Extract date/time and repo info from a slug."""
    parts = slug.split("__", 2)
    ts_raw = parts[0]                       # 2026-04-17_05-03-41_UTC
    owner = parts[1] if len(parts) > 1 else ""
    repo = parts[2] if len(parts) > 2 else ""
    # Parse friendly date
    try:
        dt = datetime.strptime(ts_raw, "%Y-%m-%d_%H-%M-%S_UTC")
        friendly = dt.strftime("%d %b %Y – %H:%M:%S UTC")
    except ValueError:
        friendly = ts_raw
    return {"ts": ts_raw, "owner": owner, "repo": repo, "friendly": friendly}


def read_analysis(analysis_file: Path) -> str:
    if not analysis_file.exists():
        return "# Nenhum relatório foi gerado\n"
    return analysis_file.read_text(encoding="utf-8")


def md_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc", "nl2br", "sane_lists"],
    )


# ---------------------------------------------------------------------------
# Page writers
# ---------------------------------------------------------------------------

def write_run_pages(slug: str, analysis_md: str, artifacts_dir: Path | None = None) -> None:
    run_dir = HISTORY_DIR / slug
    run_dir.mkdir(parents=True, exist_ok=True)

    info = parse_slug(slug)
    repo_label = f"{info['owner']}/{info['repo']}" if info["repo"] else "—"
    rendered = md_to_html(analysis_md)

    # Save raw md
    (run_dir / "analysis.md").write_text(analysis_md, encoding="utf-8")

    # Save metadata
    (run_dir / "meta.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Copy structured artifacts if available
    has_artifacts = False
    has_summary = False
    if artifacts_dir and artifacts_dir.is_dir():
        # process artifacts.json to render markdown to html
        artifacts_json_path = artifacts_dir / "artifacts.json"
        if artifacts_json_path.exists():
            try:
                raw_data = json.loads(artifacts_json_path.read_text(encoding="utf-8"))
                for art in raw_data:
                    review = art.get("review_result")
                    if review and review.get("summary"):
                        review["summary_html"] = md_to_html(review["summary"])
                (run_dir / "artifacts.json").write_text(
                    json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                has_artifacts = True
            except Exception as e:
                print(f"Erro ao processar artifacts.json: {e}")
                shutil.copy2(artifacts_json_path, run_dir / "artifacts.json")
                has_artifacts = True
        
        # summary doesn't need enrichment usually, just copy it
        summary_json_path = artifacts_dir / "run_summary.json"
        if summary_json_path.exists():
            shutil.copy2(summary_json_path, run_dir / "run_summary.json")
            has_summary = True

    # Build data links bar
    data_links = []
    if has_artifacts:
        data_links.append('<a href="artifacts.json" style="margin-right:16px">📦 artifacts.json</a>')
    if has_summary:
        data_links.append('<a href="run_summary.json">📊 run_summary.json</a>')
    data_bar = ""
    if data_links:
        data_bar = f'<div class="meta-box" style="margin-top:12px;font-size:.85rem">{" ".join(data_links)}</div>'

    # Save HTML
    (run_dir / "index.html").write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>QAgent · {html_mod.escape(repo_label)} · {html_mod.escape(info["friendly"])}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{REPORT_CSS}</style>
</head>
<body>
  <nav class="topbar">
    <a href="../../index.html">← Histórico</a>
    <span class="sep">|</span>
    <span class="slug">{html_mod.escape(slug)}</span>
  </nav>
  <div class="container">
    <div class="meta-box">
      <div class="meta-item"><label>Repositório</label><span>{html_mod.escape(repo_label)}</span></div>
      <div class="meta-item"><label>Execução</label><span>{html_mod.escape(info["friendly"])}</span></div>
    </div>
    {data_bar}
    <div id="run-summary-container"></div>
    <div id="artifacts-container"></div>
    <article class="report">
      {rendered}
    </article>
  </div>
  <footer>QAgent — análise automatizada de QA com IA</footer>
  {REPORT_JS}
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
        cards = '<div class="empty">Nenhuma execução registrada ainda.</div>'
    else:
        card_items: list[str] = []
        for r in runs:
            info = parse_slug(r)
            repo_label = f"{info['owner']}/{info['repo']}" if info["repo"] else "execução local"
            card_items.append(f"""
      <a class="card" href="history/{html_mod.escape(r)}/index.html">
        <span class="card-icon">📋</span>
        <div class="card-body">
          <div class="card-title">{html_mod.escape(repo_label)}</div>
          <div class="card-meta">{html_mod.escape(info["friendly"])}</div>
        </div>
        <span class="card-arrow">→</span>
      </a>""")
        cards = "\n".join(card_items)

    count = len(runs)
    (SITE_DIR / "index.html").write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>QAgent · Histórico de Relatórios</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{INDEX_CSS}</style>
</head>
<body>
  <div class="container">
    <div class="hero">
      <h1>🤖 <span>QAgent</span></h1>
      <p>Histórico de análises automatizadas de QA</p>
    </div>
    <p style="color:var(--text-muted);font-size:.9rem;">
      {count} execuç{'ão' if count == 1 else 'ões'} registrada{'s' if count != 1 else ''}
      <span class="badge">mais recentes primeiro</span>
    </p>
    <div class="cards">
      {cards}
    </div>
  </div>
  <footer>QAgent — análise automatizada de QA com IA</footer>
</body>
</html>
""",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    analysis_file = Path(args.analysis_file)

    # Resolve artifacts dir
    if args.artifacts_dir:
        artifacts_dir = Path(args.artifacts_dir)
    else:
        artifacts_dir = analysis_file.parent

    ensure_site_dirs()
    copy_previous_history()

    analysis_md = read_analysis(analysis_file)
    slug = run_slug(args.target_owner, args.target_repo)

    write_run_pages(slug, analysis_md, artifacts_dir)
    runs = list_runs()
    write_index(runs)


if __name__ == "__main__":
    main()
