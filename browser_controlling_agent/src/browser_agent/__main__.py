from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Import run_task. When this module is executed as a script (python src/browser_agent/__main__.py)
# relative imports fail because there is no parent package. Try the relative import first
# (normal package usage), then fall back to a few other strategies so the file can be run
# directly for convenience during development.
try:
    from .runner import run_task
except Exception:
    # First try an absolute import if package is available as `browser_agent`
    try:
        from browser_agent.runner import run_task  # type: ignore
    except Exception:
        # Last-resort: import runner.py by path so running the file directly still works.
        import importlib.util
        import sys
        from pathlib import Path

        runner_path = Path(__file__).resolve().parent / "runner.py"
        spec = importlib.util.spec_from_file_location("browser_agent.runner", str(runner_path))
        module = importlib.util.module_from_spec(spec)
        # Register under a sensible name so tools referencing browser_agent.runner can find it
        sys.modules["browser_agent.runner"] = module
        if spec and spec.loader:
            spec.loader.exec_module(module)
        run_task = getattr(module, "run_task")


@dataclass
class Args:
    prompt: str
    headless: bool


def parse_args() -> Args:
    p = argparse.ArgumentParser(description="PydanticAI Browser Agent (Helium + Selenium)")
    p.add_argument("prompt", help="Task prompt, e.g. 'Go to Wikipedia Chicago page and find sentence with 1992 and accident.'")
    p.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    ns = p.parse_args()
    return Args(prompt=ns.prompt, headless=ns.headless)


def main() -> None:
    load_dotenv()
    args = parse_args()
    asyncio.run(run_task(args.prompt, headless=args.headless))


if __name__ == "__main__":
    main()
