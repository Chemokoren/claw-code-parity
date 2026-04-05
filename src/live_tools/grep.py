"""Grep tool — search for text patterns across files."""
from __future__ import annotations

import re
from pathlib import Path

from .base import LiveTool, ToolResult, resolve_path

MAX_RESULTS = 50


class GrepTool(LiveTool):
    name = 'grep'
    description = (
        'Search for a text pattern across files in a directory. '
        'Returns matching lines with file paths and line numbers. '
        'Supports regex patterns. Skips binary files and hidden directories.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'pattern': {
                'type': 'string',
                'description': 'The text or regex pattern to search for.',
            },
            'path': {
                'type': 'string',
                'description': 'Directory or file to search in.',
            },
            'include': {
                'type': 'string',
                'description': 'Glob pattern to filter files, e.g. "*.py" or "*.js". Optional.',
            },
        },
        'required': ['pattern', 'path'],
    }

    def execute(self, pattern: str, path: str = '.', include: str | None = None, **kwargs) -> ToolResult:
        target = resolve_path(path)
        if not target.exists():
            return ToolResult(success=False, output=f'Path does not exist: {target}')

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return ToolResult(success=False, output=f'Invalid regex pattern: {exc}')

        results = []
        files = [target] if target.is_file() else self._collect_files(target, include)

        for file_path in files:
            if len(results) >= MAX_RESULTS:
                break
            try:
                text = file_path.read_text(encoding='utf-8', errors='replace')
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        rel = file_path.relative_to(target) if target.is_dir() else file_path.name
                        results.append(f'{rel}:{line_no}: {line.rstrip()}')
                        if len(results) >= MAX_RESULTS:
                            break
            except (PermissionError, OSError):
                continue

        if not results:
            return ToolResult(success=True, output=f'No matches for pattern "{pattern}" in {target}')

        header = f'Found {len(results)} matches for "{pattern}":\n\n'
        truncation = f'\n\n... capped at {MAX_RESULTS} results' if len(results) >= MAX_RESULTS else ''
        return ToolResult(success=True, output=header + '\n'.join(results) + truncation)

    @staticmethod
    def _collect_files(root: Path, include: str | None) -> list[Path]:
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.tox', 'dist', 'build'}
        files = []
        for child in sorted(root.rglob(include or '*')):
            if any(part in skip_dirs for part in child.parts):
                continue
            if child.is_file() and child.stat().st_size < 500_000:
                files.append(child)
        return files
