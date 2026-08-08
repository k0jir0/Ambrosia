from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = ROOT / "packages" / "cli"
SDK_DIR = ROOT / "packages" / "sdk-python"
CLI_MAIN = "from ambrosia_cli.main import main; raise SystemExit(main())"


def _pythonpath() -> str:
    existing = os.environ.get("PYTHONPATH", "")
    paths = [str(CLI_DIR), str(SDK_DIR)]
    if existing:
        paths.append(existing)
    return os.pathsep.join(paths)


def run_cli(*args: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": _pythonpath()}
    return subprocess.run(
        [sys.executable, "-c", CLI_MAIN, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_cli_no_args_is_discoverable_help() -> None:
    result = run_cli()

    assert result.returncode == 0
    assert "Ambrosia API/CLI decision platform" in result.stdout
    assert "commands" in result.stdout
    assert "signals" in result.stdout
    assert "enterprise" in result.stdout
    assert "Examples:" in result.stdout
    assert "Current target" in result.stdout
    assert "ambrosia quickstart" in result.stdout
    assert result.stderr == ""


def test_cli_version_examples_and_catalog_are_local_no_network_commands() -> None:
    version = run_cli("--version")
    examples = run_cli("examples")
    catalog = run_cli("commands", "list")

    assert version.returncode == 0
    assert version.stdout.strip() == "ambrosia 0.1.0"

    assert examples.returncode == 0
    assert "ambrosia commands list" in examples.stdout
    assert "ambrosia --json signals list" in examples.stdout

    assert catalog.returncode == 0
    assert "command(s)" in catalog.stdout
    for command in [
        "ambrosia scanner run",
        "ambrosia signals list",
        "ambrosia alpha list",
        "ambrosia paper-trades list",
        "ambrosia enterprise readiness",
    ]:
        assert command in catalog.stdout


def test_cli_command_detail_is_human_readable() -> None:
    catalog_result = run_cli("--json", "commands", "list")
    catalog = json.loads(catalog_result.stdout)
    health_index = next(item["index"] for item in catalog if item["command"] == "ambrosia health")

    result = run_cli("commands", "show", str(health_index))

    assert result.returncode == 0
    assert result.stdout.splitlines()[0] == "ambrosia health"
    assert "{" not in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_status_reports_target_and_recovery_without_failing() -> None:
    result = run_cli("--json", "--api-url", "http://127.0.0.1:1", "--timeout", "0.2", "status")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["apiUrl"] == "http://127.0.0.1:1"
    assert payload["apiUrlSource"] == "flag"
    assert payload["apiReachable"] is False
    assert any("Start the local API" in item["label"] for item in payload["recovery"])


def test_cli_api_unavailable_error_is_actionable() -> None:
    result = run_cli("--api-url", "http://127.0.0.1:1", "--timeout", "0.2", "market", "snapshot", "GOOG")

    assert result.returncode == 1
    assert "Status: error" in result.stdout
    assert "Tried: http://127.0.0.1:1/market/GOOG/snapshot" in result.stdout
    assert "Start the local API" in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_quickstart_can_write_profile(tmp_path: Path) -> None:
    env_home = tmp_path / "home"
    env_home.mkdir()
    env = {
        **os.environ,
        "PYTHONPATH": _pythonpath(),
        "HOME": str(env_home),
        "USERPROFILE": str(env_home),
        "AMBROSIA_STAGING_API_URL": "https://staging.ambrosia.example/api",
    }
    result = subprocess.run(
        [sys.executable, "-c", CLI_MAIN, "--json", "quickstart", "--target", "staging", "--write-profile"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["target"] == "staging"
    assert payload["apiUrl"] == "https://staging.ambrosia.example/api"

    config_path = env_home / ".ambrosia" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["profiles"]["default"]["api_url"] == "https://staging.ambrosia.example/api"


def test_cli_json_mode_and_token_file_are_scriptable(tmp_path: Path) -> None:
    token_file = tmp_path / "ambrosia-token.txt"
    token_file.write_text("test-token\n", encoding="utf-8")

    result = run_cli(
        "--json",
        "--api-url",
        "https://api.example.test",
        "--token-file",
        str(token_file),
        "auth",
        "whoami",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["apiUrl"] == "https://api.example.test"
    assert payload["authenticated"] is True
    assert "test-token" not in result.stdout


def test_cli_missing_token_file_fails_cleanly_without_traceback(tmp_path: Path) -> None:
    missing_token_file = tmp_path / "missing-token.txt"

    result = run_cli("--json", "--token-file", str(missing_token_file), "auth", "whoami")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "Token file not found" in payload["message"]
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_package_declares_sdk_dependency_and_local_source() -> None:
    pyproject = tomllib.loads((CLI_DIR / "pyproject.toml").read_text(encoding="utf-8"))

    assert "ambrosia-sdk==0.1.0" in pyproject["project"]["dependencies"]
    assert pyproject["project"]["scripts"]["ambrosia"] == "ambrosia_cli.main:main"
    assert pyproject["tool"]["uv"]["sources"]["ambrosia-sdk"]["path"] == "../sdk-python"
    assert pyproject["tool"]["uv"]["sources"]["ambrosia-sdk"]["editable"] is True


def test_root_scripts_expose_cli_install_and_distribution_flows() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    expected_scripts = {
        "cli:install",
        "cli:build",
        "cli:build:exe",
        "cli:install:dist",
        "cli:install:path",
        "cli:menu",
        "cli:status",
        "cli:quickstart",
        "cli:examples",
        "cli:version",
    }
    assert expected_scripts.issubset(scripts)
    assert "install-ambrosia-cli.ps1" in scripts["cli:install:path"]
    assert "build-ambrosia-cli-exe.ps1" in scripts["cli:build:exe"]


def test_windows_launcher_is_target_aware() -> None:
    launcher = (ROOT / "launch-ambrosia-cli-menu.bat").read_text(encoding="utf-8")

    assert "uv run ambrosia status" in launcher
    assert "Choose API target" in launcher
    assert "AMBROSIA_STAGING_API_URL" in launcher
    assert "quickstart --target custom" in launcher
    assert "Run common quick checks" in launcher


def test_standalone_executable_catalog_if_built() -> None:
    exe = ROOT / "dist" / "ambrosia-cli-exe" / "ambrosia.exe"
    if not exe.exists():
        pytest.skip("Single-file Ambrosia CLI executable has not been built in this workspace.")

    result = subprocess.run(
        [str(exe), "commands", "list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0
    assert "ambrosia commands list" in result.stdout
    assert "ambrosia enterprise readiness" in result.stdout
