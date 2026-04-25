from pathlib import Path
import shutil
import sys


def main() -> None:
    current_file = Path(__file__).resolve()
    qagent_root = current_file.parent.parent
    repo_root = qagent_root.parent

    templates_dir = qagent_root / "templates"
    workflow_templates = [
        templates_dir / "qagent-review.yml",
        templates_dir / "forward-qagent-test-review-comment.yml",
    ]

    target_workflows_dir = repo_root / ".github" / "workflows"
    target_workflows_dir.mkdir(parents=True, exist_ok=True)

    for workflow_template in workflow_templates:
        if not workflow_template.exists():
            raise FileNotFoundError(
                f"Template não encontrado: {workflow_template}"
            )

        target_workflow = target_workflows_dir / workflow_template.name
        shutil.copyfile(workflow_template, target_workflow)
        print(f"Arquivo criado: {target_workflow}")

    print("✅ Workflow instalado com sucesso.")
    print()
    print("Próximos passos:")
    print("1. Adicione o secret GROQ_API_KEY no repositório principal.")
    print("2. Adicione o secret QAGENT_DISPATCH_PAT para encaminhar críticas ao QAgent.")
    print("3. Faça git add .")
    print('4. Faça commit com algo como: "chore: install qagent workflow"')
    print("5. Faça push para disparar o workflow.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"❌ Erro na instalação: {error}")
        sys.exit(1)
