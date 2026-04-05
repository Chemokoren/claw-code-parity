"""FileEdit tool — search and replace within a file."""
from __future__ import annotations

from .base import LiveTool, ToolResult, guard_path, resolve_path


class FileEditTool(LiveTool):
    name = 'file_edit'
    description = (
        'Edit an existing file by replacing an exact string with new content. '
        'The old_str must match exactly (including whitespace). '
        'Use this to modify existing code — always read the file first to get the exact content. '
        'Relative paths are resolved against the user workspace.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'Path to the file to edit.',
            },
            'old_str': {
                'type': 'string',
                'description': 'The exact string to find in the file. Must match precisely.',
            },
            'new_str': {
                'type': 'string',
                'description': 'The replacement string.',
            },
        },
        'required': ['path', 'old_str', 'new_str'],
    }

    def execute(self, path: str, old_str: str, new_str: str, **kwargs) -> ToolResult:
        target = resolve_path(path)

        # Safety: never edit files inside Claw's own source tree
        error = guard_path(target)
        if error:
            return ToolResult(success=False, output=error)

        if not target.exists():
            return ToolResult(success=False, output=f'File does not exist: {target}')
        if not target.is_file():
            return ToolResult(success=False, output=f'Not a file: {target}')

        try:
            content = target.read_text(encoding='utf-8')
        except PermissionError:
            return ToolResult(success=False, output=f'Permission denied: {target}')

        count = content.count(old_str)
        if count == 0:
            # Show a snippet of the file to help the LLM
            preview = content[:500]
            return ToolResult(
                success=False,
                output=f'old_str not found in {target}.\n\nFile starts with:\n{preview}',
            )
        if count > 1:
            return ToolResult(
                success=False,
                output=f'old_str found {count} times in {target}. Make it more specific to match exactly once.',
            )

        new_content = content.replace(old_str, new_str, 1)
        target.write_text(new_content, encoding='utf-8')
        return ToolResult(
            success=True,
            output=f'Edited {target}: replaced 1 occurrence ({len(old_str)} chars → {len(new_str)} chars)',
        )
