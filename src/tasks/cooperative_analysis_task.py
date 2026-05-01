from crewai import Task


class CooperativeAnalysisTaskFactory:
    """Quatro tasks sequenciais com comunicação direta via barramento inter-agente."""

    @staticmethod
    def create_qa_task(
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_context: str,
    ) -> Task:
        description = f"""
Você é o QA Sênior Investigador. Analise o arquivo abaixo com profundidade.

Arquivo: {file_path}

Diff:
[INICIO_DIFF]
{file_diff}
[FIM_DIFF]

Conteúdo atual:
[INICIO_CODIGO]
{code_content}
[FIM_CODIGO]

Contexto do repositório:
[INICIO_CONTEXTO]
{repo_context}
[FIM_CONTEXTO]

Instruções:
1. Analise o diff, o código e o contexto.
2. Identifique riscos reais com evidências no diff/código (não invente).
3. Liste cenários de teste relevantes para a mudança.
4. Ao concluir, publique suas descobertas no barramento usando a ferramenta publish_message:
   - topic: 'qa_findings'
   - sender: 'QA Sênior Investigador'
   - message: resumo estruturado dos riscos e cenários de teste

Regras:
- não invente regra de negócio sem evidência no diff
- não produza checklist superficial
- não diga apenas "testar funcionalidade"
"""
        return Task(
            description=description,
            expected_output=(
                "Análise de riscos fundamentada no diff com cenários de teste específicos. "
                "Mensagem publicada no barramento no tópico 'qa_findings'."
            ),
        )

    @staticmethod
    def create_strategy_task(file_path: str) -> Task:
        description = f"""
Você é o Especialista em Estratégia de Testes para Código de Alto Risco.

Arquivo em análise: {file_path}

Instruções:
1. Use a ferramenta read_messages com topic='qa_findings' para ler as descobertas do agente QA.
2. Com base nessas descobertas, proponha uma estratégia de testes detalhada:
   - Testes unitários (com nomes e cenários específicos)
   - Testes de integração (quando justificado pelo diff)
   - Testes de regressão (focados no que mudou)
3. Priorize por criticidade (HIGH / MEDIUM / LOW).
4. Publique sua estratégia no barramento usando publish_message:
   - topic: 'test_strategy'
   - sender: 'Especialista em Estratégia de Testes'
   - message: estratégia estruturada completa

Regras:
- leia as descobertas do QA antes de propor qualquer estratégia
- não descarte achados do agente anterior sem justificativa
- não sugira testes de carga/performance sem indício real no diff
"""
        return Task(
            description=description,
            expected_output=(
                "Estratégia de testes priorizada com base nas descobertas do agente QA. "
                "Mensagem publicada no tópico 'test_strategy'."
            ),
        )

    @staticmethod
    def create_critic_task(file_path: str) -> Task:
        description = f"""
Você é o Crítico de Análise de QA.

Arquivo em análise: {file_path}

Instruções:
1. Use a ferramenta read_messages com topic='qa_findings' para ler a análise do agente QA.
2. Use a ferramenta read_messages com topic='test_strategy' para ler a estratégia proposta.
3. Critique ambas com rigor:
   - Quais achados têm evidência real no diff?
   - Quais conclusões são genéricas ou sem fundamento?
   - A estratégia cobre os riscos identificados?
   - Há lacunas importantes não cobertas?
4. Publique sua crítica no barramento usando publish_message:
   - topic: 'critique'
   - sender: 'Crítico de Análise de QA'
   - message: crítica estruturada com achados válidos, achados questionáveis e lacunas

Regras:
- seu papel é validar, não gerar novos testes
- seja preciso: aponte linha/trecho específico quando rejeitar um achado
- destaque incertezas reais que o gerente deve considerar
"""
        return Task(
            description=description,
            expected_output=(
                "Crítica estruturada da análise QA e da estratégia de testes. "
                "Mensagem publicada no tópico 'critique'."
            ),
        )

    @staticmethod
    def create_consolidation_task(file_path: str) -> Task:
        description = f"""
Você é o Gerente de Qualidade e Coordenação Multiagente.

Arquivo em análise: {file_path}

Instruções:
1. Use a ferramenta read_messages com topic='all' para ler todas as mensagens dos agentes.
2. Consolide uma análise final única em Markdown com base no que os especialistas publicaram.
3. Onde houver conflito entre a análise e a crítica, resolva com base nas evidências do diff.
4. Não repita conteúdo redundante — sintetize.

Sua resposta final deve conter exatamente estas seções:

# Tipo da mudança
Classifique a mudança.

# Evidências observadas
Aponte trechos ou comportamentos do diff/código que sustentam a análise.

# Impacto provável
Explique o que provavelmente foi afetado.

# Riscos identificados
Liste riscos reais e contextualizados (apenas os validados pelo crítico).

# Cenários de testes manuais
Sugira cenários específicos para a mudança.

# Sugestões de testes unitários
Sugira testes unitários específicos.

# Sugestões de testes de integração
Sugira testes de integração específicos.

# Sugestões de testes de carga ou desempenho
Inclua apenas se a mudança justificar claramente.

# Pontos que precisam de esclarecimento
Liste dúvidas relevantes de negócio ou implementação.

# Validação cooperativa
Explique brevemente como as conclusões foram revisadas pelos especialistas e quais conflitos foram resolvidos.

Regras:
- não invente regra de negócio sem evidência
- não produza checklist superficial
- preserve o formato das seções para que o parser estruturado continue funcionando
"""
        return Task(
            description=description,
            expected_output=(
                "Relatório final em Markdown consolidado a partir das mensagens dos três agentes especialistas, "
                "com todas as seções exigidas e conclusões baseadas em evidências do diff."
            ),
            markdown=True,
        )

    @staticmethod
    def create(
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_context: str,
    ) -> Task:
        """Compat: single-task for non-sequential use (deprecated, prefer the 4-task split)."""
        return CooperativeAnalysisTaskFactory.create_qa_task(
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_context=repo_context,
        )
