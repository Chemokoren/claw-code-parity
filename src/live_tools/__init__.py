"""Live tool implementations — real tools that interact with the filesystem and shell."""
from __future__ import annotations

from .base import LiveTool, ToolResult
from .bash import BashTool
from .file_edit import FileEditTool
from .file_read import FileReadTool
from .file_write import FileWriteTool
from .grep import GrepTool
from .list_dir import ListDirectoryTool

# Registry: every tool the LLM can invoke.
LIVE_TOOLS: dict[str, LiveTool] = {
    'list_directory': ListDirectoryTool(),
    'file_read': FileReadTool(),
    'file_write': FileWriteTool(),
    'file_edit': FileEditTool(),
    'bash': BashTool(),
    'grep': GrepTool(),
}


def execute_live_tool(name: str, arguments: dict) -> ToolResult:
    """Execute a registered live tool by name."""
    tool = LIVE_TOOLS.get(name)
    if tool is None:
        return ToolResult(success=False, output=f'Unknown tool: {name}')
    return tool.execute(**arguments)


__all__ = [
    'LIVE_TOOLS',
    'LiveTool',
    'ToolResult',
    'execute_live_tool',
]
