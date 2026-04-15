from pathlib import Path
import shutil
import sys


def main() -> None:
    current_file = Path(__file__).resolve()
    qagent_root = current_file.parent.parent
    repo_root = qagent_root.parent

    templates_dir = qagent_root / "templates"
    workflow_template = templates_dir / "qagent-review.yml"

    target_workflows_dir = repo_root / ".github" / "workflows"
    target_workflows_dir.mkdir(parents=True, exist_ok=True)

    target_workflow = target_workflows_dir / "qagent-review.yml"

    if not workflow_template.exists():
        raise FileNotFoundError(
            f"Template não encontrado: {workflow_template}"
        )

    shutil.copyfile(workflow_template, target_workflow)

    print("✅ Workflow instalado com sucesso.")
    print(f"Arquivo criado: {target_workflow}")
    print()
    print("Próximos passos:")
    print("1. Adicione o secret GROQ_API_KEY no repositório principal.")
    print("2. Faça git add .")
    print('3. Faça commit com algo como: "chore: install qagent workflow"')
    print("4. Faça push para disparar o workflow.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"❌ Erro na instalação: {error}")
        sys.exit(1)