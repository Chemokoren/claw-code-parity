"""Base class, result type, and workspace guard for live tools."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


# ── Global workspace reference ──────────────────────────────────────
# Set by the Agent before tool execution begins.
# All tools use this to resolve relative paths and enforce boundaries.
_workspace: Path | None = None

# The directory where Claw's own source code lives — NEVER write here.
_CLAW_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent  # claw-code-parity/


def set_workspace(workspace: Path) -> None:
    """Set the active workspace. Called by Agent on init."""
    global _workspace
    _workspace = workspace.resolve()


def get_workspace() -> Path:
    """Get the active workspace. Falls back to CWD if not set."""
    return _workspace or Path.cwd()


def resolve_path(path: str) -> Path:
    """Resolve a path relative to the workspace (not CWD).

    - Absolute paths are used as-is.
    - Relative paths are resolved against the workspace.
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (get_workspace() / p).resolve()


def guard_path(resolved: Path) -> str | None:
    """Check if a path is safe to write to.

    Returns an error message if the path is dangerous, or None if safe.
    """
    # NEVER allow writing into Claw's own source directory
    try:
        resolved.relative_to(_CLAW_SOURCE_DIR)
        return (
            f'BLOCKED: Refusing to write to {resolved} — '
            f'this is inside Claw\'s own source directory ({_CLAW_SOURCE_DIR}). '
            f'Use paths inside the workspace: {get_workspace()}'
        )
    except ValueError:
        pass  # Not inside Claw source — good

    return None


@dataclass(frozen=True)
class ToolResult:
    """The output of a tool execution."""
    success: bool
    output: str


class LiveTool(ABC):
    """Base class for all live tools that interact with the real system."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict: ...

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult: ...
