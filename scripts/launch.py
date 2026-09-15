#!/usr/bin/env python3
"""Set up the project (venv, Python deps, .env) and start Multi-DB Select."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
APP_URL = "http://127.0.0.1:5000"


class LaunchError(RuntimeError):
    pass


def _is_windows() -> bool:
    return os.name == "nt"


def venv_python() -> Path:
    if _is_windows():
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(_quote(part) for part in command))
    try:
        subprocess.run(command, cwd=cwd or ROOT, env=env, check=True)
    except FileNotFoundError as exc:
        raise LaunchError(
            f"Could not start {command[0]!r}. Is it installed and on PATH?\n{exc}"
        ) from exc


def _quote(part: str) -> str:
    if _is_windows() and any(ch in part for ch in (" ", "\t")):
        return f'"{part}"'
    return part


def ensure_venv() -> Path:
    python = venv_python()
    if not python.exists():
        print("Creating virtualenv...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    return python


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
    print(
        "Created .env from .env.example. "
        "Fill MSSQL_PROD_* and MSSQL_STAGE_* if you want saved logins."
    )


def _open_browser(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def main() -> int:
    os.chdir(ROOT)
    python = ensure_venv()

    print("Installing Python packages...")
    run([str(python), "-m", "pip", "install", "-q", "-U", "pip"])
    run([str(python), "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])

    ensure_env_file()

    env = os.environ.copy()
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(VENV)

    print(f"Starting Multi-DB Select on {APP_URL}")
    threading.Thread(target=_open_browser, args=(APP_URL,), daemon=True).start()
    run([str(python), str(ROOT / "app.py")], env=env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LaunchError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    except KeyboardInterrupt:
        raise SystemExit(130) from None
