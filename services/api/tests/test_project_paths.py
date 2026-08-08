from pathlib import Path

from app.project_paths import find_project_root


def test_finds_repository_layout() -> None:
    root = Path(__file__).resolve().parents[3]

    assert find_project_root(Path(__file__)) == root


def test_finds_compact_runtime_layout(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    module_path = runtime_root / "app" / "project_paths.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    (runtime_root / "infra" / "db").mkdir(parents=True)

    assert find_project_root(module_path) == runtime_root
