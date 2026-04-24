# Descrição
Esta PR introduz uma melhoria significativa na observabilidade dos relatórios publicados no GitHub Pages do QAgent. Até então, os arquivos estruturados (`artifacts.json` e `run_summary.json`) eram acessíveis apenas via links brutos. Agora, o relatório conta com um dashboard interativo renderizado dinamicamente via Vanilla JavaScript.

## Mudanças Principais
- **Dashboard de Resumo**: Adicionados cards no topo do relatório que exibem:
  - Total de arquivos analisados.
  - Distribuição de risco (HIGH/MEDIUM/LOW) com codificação por cores.
  - Etapas puladas, fallbacks acionados e duração total da execução.
- **Lista de Artefatos Interativa**: Cada arquivo analisado agora possui um card expansível que revela:
  - **Visão Geral**: Linguagem e propósito do arquivo.
  - **Review de QA**: Resumo da análise, principais vulnerabilidades e impacto funcional.
  - **Observabilidade**: Detalhamento de etapas executadas/puladas e o tempo gasto em cada fase do pipeline.
- **CSS Dark Mode**: Estilos integrados ao tema escuro existente para uma experiência visual premium.

## Benefícios
- **Agilidade na Revisão**: O analista de QA pode identificar rapidamente arquivos de alto risco e o motivo do alerta.
- **Transparência do Pipeline**: Facilita a depuração de por que certas etapas foram puladas ou se houve algum fallback do modelo de IA.
- **Portabilidade**: A solução usa Vanilla JS puro, não exigindo dependências externas ou processos de build complexos para o frontend do Pages.

## Verificação
- Gerado HTML localmente com dados fictícios.
- Validado o carregamento assíncrono dos JSONs.
- Verificada a compatibilidade com o layout Markdown original.

## Checklist
- [x] Branch criada a partir da `main` (ou branch de desenvolvimento).
- [x] Push realizado para o repositório remoto.
- [x] Alterações restritas apenas à apresentação visual, sem afetar a lógica central dos agentes.
