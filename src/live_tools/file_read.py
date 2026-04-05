"""FileRead tool — read file contents with line numbers."""
from __future__ import annotations

from .base import LiveTool, ToolResult, resolve_path

MAX_LINES = 500


class FileReadTool(LiveTool):
    name = 'file_read'
    description = (
        'Read the contents of a file. Returns the text with line numbers. '
        'Optionally read a specific line range with start_line and end_line. '
        'Use this to understand existing code before editing. '
        'Relative paths are resolved against the user workspace.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'Absolute or relative path to the file to read.',
            },
            'start_line': {
                'type': 'integer',
                'description': 'First line to read (1-indexed). Optional.',
            },
            'end_line': {
                'type': 'integer',
                'description': 'Last line to read (1-indexed, inclusive). Optional.',
            },
        },
        'required': ['path'],
    }

    def execute(self, path: str, start_line: int | None = None, end_line: int | None = None, **kwargs) -> ToolResult:
        target = resolve_path(path)
        if not target.exists():
            return ToolResult(success=False, output=f'File does not exist: {target}')
        if not target.is_file():
            return ToolResult(success=False, output=f'Not a file: {target}')

        try:
            text = target.read_text(encoding='utf-8', errors='replace')
        except PermissionError:
            return ToolResult(success=False, output=f'Permission denied: {target}')

        lines = text.splitlines()
        total = len(lines)

        # Apply range if specified
        s = (start_line or 1) - 1
        e = end_line or total
        s = max(0, s)
        e = min(total, e)

        selected = lines[s:e]
        if len(selected) > MAX_LINES:
            selected = selected[:MAX_LINES]
            truncated = f'\n... truncated at {MAX_LINES} lines (file has {total} lines total)'
        else:
            truncated = ''

        numbered = [f'{s + i + 1:>4} | {line}' for i, line in enumerate(selected)]
        header = f'File: {target} ({total} lines)\n'
        return ToolResult(success=True, output=header + '\n'.join(numbered) + truncated)
