"""Lightweight trace of agent runs and tool calls, for debugging.

Each event is printed to stdout (visible in the uvicorn terminal or
``docker compose logs -f api``) and appended to a plain-text log file:
<repo>/data/agent_tool_log.txt locally, /data/agent_tool_log.txt in Docker.
Override the file with AGENT_TOOL_LOG_FILE, or set it to an empty string to
disable file logging.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

_DEFAULT_LOG_FILE = Path(__file__).resolve().parents[3] / "data" / "agent_tool_log.txt"
_LOG_FILE = os.environ.get("AGENT_TOOL_LOG_FILE", str(_DEFAULT_LOG_FILE))


def _emit(message: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    # flush=True: stdout is block-buffered when not attached to a TTY (e.g. in
    # Docker), which would otherwise delay these lines.
    print(line, flush=True)
    if not _LOG_FILE:
        return
    try:
        path = Path(_LOG_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def log_agent_called(agent_name: str) -> None:
    _emit(f"Agent '{agent_name}' is being called...")


def log_tool_used(tool_name: str, args: dict[str, Any] | None = None) -> None:
    suffix = f" {json.dumps(args, default=str)}" if args else ""
    _emit(f"  Tool used: {tool_name}{suffix}")
