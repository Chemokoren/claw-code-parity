"""ListDirectory tool — list files and directories in a path."""
from __future__ import annotations

from .base import LiveTool, ToolResult, resolve_path


class ListDirectoryTool(LiveTool):
    name = 'list_directory'
    description = (
        'List the contents of a directory. Returns file names, types (file/dir), '
        'and sizes. Use this to explore project structure. '
        'Relative paths are resolved against the user workspace.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'Absolute or relative path to list. Defaults to workspace root.',
            },
        },
        'required': ['path'],
    }

    def execute(self, path: str = '.', **kwargs) -> ToolResult:
        target = resolve_path(path)
        if not target.exists():
            return ToolResult(success=False, output=f'Path does not exist: {target}')
        if not target.is_dir():
            return ToolResult(success=False, output=f'Not a directory: {target}')

        entries = []
        try:
            for child in sorted(target.iterdir()):
                if child.name.startswith('.') and child.name not in ('.env',):
                    continue
                kind = 'dir' if child.is_dir() else 'file'
                size = ''
                if child.is_file():
                    size = f'  ({child.stat().st_size} bytes)'
                entries.append(f'  {kind}  {child.name}{size}')
        except PermissionError:
            return ToolResult(success=False, output=f'Permission denied: {target}')

        header = f'Contents of {target}/ ({len(entries)} items):\n'
        return ToolResult(success=True, output=header + '\n'.join(entries))
