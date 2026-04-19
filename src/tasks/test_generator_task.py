from crewai import Task


class TestGeneratorTaskFactory:
    @staticmethod
    def create(
        agent,
        qa_report: str,
        file_path: str,
        code_content: str,
        repo_context: str,
        memories: str = "",
    ) -> Task:
        memories_block = ""
        if memories and "Nenhuma memória" not in memories:
            memories_block = f"""
IMPORTANTE — Lições aprendidas de execuções anteriores (NÃO repita estes erros):
[INICIO_MEMORIAS]
{memories}
[FIM_MEMORIAS]
"""
            print(f"  🧠 Memory block INJECTED into prompt for '{file_path}'")
        else:
            print(f"  🧠 Memory block SKIPPED for '{file_path}' (no relevant memories)")

        description = f"""
Você deve gerar testes unitários baseados no relatório de QA abaixo.

Arquivo alvo: {file_path}
{memories_block}
Relatório de QA:
[INICIO_RELATORIO]
{qa_report}
[FIM_RELATORIO]

Código-fonte atual do arquivo:
[INICIO_CODIGO]
{code_content}
[FIM_CODIGO]

Contexto adicional do repositório:
[INICIO_CONTEXTO]
{repo_context}
[FIM_CONTEXTO]

Instruções:
1. Leia atentamente a seção "Sugestões de testes unitários" do relatório de QA.
2. Analise o código-fonte para entender a implementação real.
3. Analise o contexto adicional do repositório, incluindo os testes já existentes e arquivos de código relacionados.
4. Identifique a linguagem e o framework de testes usado no projeto (sem assumir stack específica).
5. Para cada sugestão do relatório, verifique se já existe cobertura equivalente nos testes existentes.
6. Gere apenas os testes que preencham lacunas reais de cobertura (evite duplicação e cenários redundantes).
7. Siga a estrutura de pastas e convenções do projeto.
8. Quando fizer sentido, priorize atualizar/expandir arquivos de teste já existentes em vez de criar novos arquivos.
9. Seja agnóstico de linguagem: respeite as convenções e ferramentas do repositório alvo, qualquer que seja a stack.

Sua resposta deve ser APENAS no formato abaixo, um bloco para cada arquivo de teste:

### FILE: <caminho_relativo_do_arquivo_de_teste>
```
<código completo do arquivo de teste>
```

Regras:
- gere código completo e executável
- inclua todos os imports necessários
- use nomes descritivos para os testes
- cubra cenários positivos e negativos
- use mocks quando necessário para isolar dependências externas
- não replique testes já existentes com pequenas variações sem ganho de cobertura
- NÃO inclua explicações fora dos blocos de código
"""

        expected_output = """
Arquivos de teste completos em formato Markdown com blocos de código, prontos para serem salvos e executados.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )
