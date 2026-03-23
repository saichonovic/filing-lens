from __future__ import annotations

import os
import sys
from pathlib import Path


def load_repo_env() -> Path | None:
    """Load .env or .env.example into os.environ without overwriting existing values."""
    repo_root = Path(__file__).resolve().parents[1]
    env_candidates = [repo_root / ".env", repo_root / ".env.example"]

    for env_path in env_candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return env_path

    return None


def prefer_local_docetl_repo() -> Path | None:
    """Prefer the sibling local `docetl` checkout over a globally installed package."""
    repo_root = Path(__file__).resolve().parents[2]
    local_docetl_root = repo_root / "docetl"
    local_pkg = local_docetl_root / "docetl" / "__init__.py"
    if local_pkg.exists():
        local_docetl_root_str = str(local_docetl_root)
        if local_docetl_root_str not in sys.path:
            sys.path.insert(0, local_docetl_root_str)
        return local_docetl_root
    return None


def warn_if_not_using_project_venv() -> Path | None:
    """Warn if the current interpreter is not the repo's local virtual environment."""
    repo_root = Path(__file__).resolve().parents[1]
    expected_python = repo_root / ".venv" / "Scripts" / "python.exe"
    current_python = Path(sys.executable).resolve()

    if expected_python.exists() and current_python != expected_python.resolve():
        print(
            "[FilingLens] Warning: not using project .venv Python.\n"
            f"  current:  {current_python}\n"
            f"  expected: {expected_python}"
        )
    return expected_python if expected_python.exists() else None


def ensure_proxy_openai_env() -> None:
    """
    LiteLLM/OpenAI-compatible wrappers require a non-empty OPENAI_API_KEY even
    when requests are sent to a local proxy.
    """
    api_base = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_API_BASE_URL") or ""
    if api_base and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-placeholder"


def ensure_docetl_home(base_dir: str | Path | None = None) -> Path:
    """Ensure DocETL uses a repo-local writable cache directory."""
    if base_dir is None:
        repo_root = Path(__file__).resolve().parents[1]
        home_dir = Path(os.getenv("DOCETL_HOME_DIR", repo_root / ".docetl_home"))
    else:
        home_dir = Path(base_dir)

    cache_root = home_dir / ".cache" / "docetl"
    (cache_root / "general").mkdir(parents=True, exist_ok=True)
    (cache_root / "llm").mkdir(parents=True, exist_ok=True)
    os.environ["DOCETL_HOME_DIR"] = str(home_dir)
    return home_dir
