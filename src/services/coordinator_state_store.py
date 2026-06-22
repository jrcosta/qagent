import json
from pathlib import Path

from src.schemas.coordinator_state import CoordinatorState


class JsonCoordinatorStateStore:
    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: CoordinatorState) -> Path:
        state.touch()
        destination = self.path_for(state.run_id)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    def load(self, run_id: str) -> CoordinatorState:
        path = self.path_for(run_id)
        if not path.exists():
            raise FileNotFoundError(f"CoordinatorState não encontrado: {path}")
        return CoordinatorState.model_validate_json(path.read_text(encoding="utf-8"))

    def path_for(self, run_id: str) -> Path:
        return self.state_dir / f"{run_id}.json"

