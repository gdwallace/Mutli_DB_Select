from pathlib import Path

from scripts.launch import ROOT, ensure_env_file, venv_python


def test_launch_root_is_the_repo():
    assert (ROOT / "app.py").is_file()
    assert (ROOT / "requirements.txt").is_file()
    assert (ROOT / "launch.bat").is_file()
    assert (ROOT / "scripts" / "launch.bat").is_file()


def test_venv_python_points_inside_repo_venv(monkeypatch):
    monkeypatch.setattr("scripts.launch._is_windows", lambda: True)
    assert venv_python() == ROOT / ".venv" / "Scripts" / "python.exe"
    monkeypatch.setattr("scripts.launch._is_windows", lambda: False)
    assert venv_python() == ROOT / ".venv" / "bin" / "python"


def test_ensure_env_file_copies_example(tmp_path, monkeypatch):
    example = tmp_path / ".env.example"
    example.write_text("MSSQL_PROD_USER=\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    monkeypatch.setattr("scripts.launch.ENV_EXAMPLE", example)
    monkeypatch.setattr("scripts.launch.ENV_FILE", env_file)

    ensure_env_file()
    assert env_file.read_text(encoding="utf-8") == "MSSQL_PROD_USER=\n"

    env_file.write_text("keep-me\n", encoding="utf-8")
    ensure_env_file()
    assert env_file.read_text(encoding="utf-8") == "keep-me\n"
