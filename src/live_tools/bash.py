"""Bash tool — execute shell commands with safety checks."""
from __future__ import annotations

import subprocess

from .base import LiveTool, ToolResult, get_workspace

# Commands that are too dangerous to run without explicit confirmation
BLOCKED_PATTERNS = [
    'rm -rf /',
    'mkfs',
    'dd if=',
    ':(){',  # fork bomb
    '> /dev/sda',
]

TIMEOUT_SECONDS = 120


class BashTool(LiveTool):
    name = 'bash'
    description = (
        'Execute a shell command and return its stdout and stderr. '
        'Use this for running tests, installing packages, git operations, '
        'checking processes, and any system interaction. '
        'Commands run with a timeout of 120 seconds. '
        'If cwd is not specified, commands run in the user workspace directory.'
    )
    input_schema = {
        'type': 'object',
        'properties': {
            'command': {
                'type': 'string',
                'description': 'The shell command to execute.',
            },
            'cwd': {
                'type': 'string',
                'description': 'Working directory for the command. Optional, defaults to user workspace.',
            },
        },
        'required': ['command'],
    }

    def execute(self, command: str, cwd: str | None = None, **kwargs) -> ToolResult:
        # Default cwd to workspace, NOT Python's CWD
        if cwd is None:
            cwd = str(get_workspace())

        # Safety check
        lowered = command.lower().strip()
        for pattern in BLOCKED_PATTERNS:
            if pattern in lowered:
                return ToolResult(
                    success=False,
                    output=f'BLOCKED: Command contains dangerous pattern "{pattern}". Refusing to execute.',
                )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=cwd,
            )
            parts = []
            if result.stdout:
                parts.append(result.stdout)
            if result.stderr:
                parts.append(f'STDERR:\n{result.stderr}')
            parts.append(f'\nExit code: {result.returncode}')

            output = '\n'.join(parts)
            # Truncate very long output
            if len(output) > 20_000:
                output = output[:20_000] + f'\n\n... output truncated (was {len(output)} chars)'

            return ToolResult(success=result.returncode == 0, output=output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output=f'Command timed out after {TIMEOUT_SECONDS}s: {command}')
        except OSError as exc:
            return ToolResult(success=False, output=f'Failed to execute: {exc}')
