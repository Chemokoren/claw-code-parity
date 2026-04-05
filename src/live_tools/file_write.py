"""FileWrite tool — create or overwrite a file."""
from __future__ import annotations

from .base import LiveTool, ToolResult, guard_path, resolve_path


class FileWriteTool(LiveTool):
    name = 'file_write'
    description = (
        'Create a new file or overwrite an existing file with the provided content. '
        'Parent directories are created automatically. '
        'Use this to create new source files, configs, templates, etc. '
        'Relative paths are resolved against the user workspace.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'Absolute or relative path to the file to create/overwrite.',
            },
            'content': {
                'type': 'string',
                'description': 'The full text content to write to the file.',
            },
        },
        'required': ['path', 'content'],
    }

    def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        target = resolve_path(path)

        # Safety: never write into Claw's own source tree
        error = guard_path(target)
        if error:
            return ToolResult(success=False, output=error)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            target.write_text(content, encoding='utf-8')
            action = 'Overwrote' if existed else 'Created'
            return ToolResult(
                success=True,
                output=f'{action} {target} ({len(content)} chars, {content.count(chr(10)) + 1} lines)',
            )
        except PermissionError:
            return ToolResult(success=False, output=f'Permission denied: {target}')
        except OSError as exc:
            return ToolResult(success=False, output=f'Write failed: {exc}')
