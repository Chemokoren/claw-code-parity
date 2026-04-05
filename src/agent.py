"""Agent — the core agentic loop that connects LLM ↔ Tools.

Works with any provider: Ollama, OpenAI, DeepSeek, Gemini, Anthropic, etc.
Includes fallback extraction for models that emit tool calls as text.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .config import ClawConfig
from .live_tools import LIVE_TOOLS, execute_live_tool
from .live_tools.base import set_workspace
from .live_tools.tool_call_parser import (
    extract_tool_calls_from_text,
    generate_tool_call_id,
)
from .llm import LLMClient
from .system_prompt import build_system_prompt, build_tool_schemas

console = Console()

# Tool names for fallback extraction
_KNOWN_TOOL_NAMES: set[str] = set(LIVE_TOOLS.keys())


@dataclass
class Agent:
    """The core agentic loop: prompt → LLM → tool_use → execute → loop."""

    config: ClawConfig
    llm: LLMClient = field(init=False)
    messages: list[dict] = field(default_factory=list)
    system: str = field(default='')
    tools: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.config.validate()
        # CRITICAL: Set workspace so all tools resolve paths correctly
        set_workspace(self.config.workspace)
        self.llm = LLMClient(self.config)
        self.tools = build_tool_schemas()
        project_context = self._detect_project_context()
        self.system = build_system_prompt(str(self.config.workspace), project_context)

    def chat(self, user_message: str) -> str:
        """Send a user message and run the full agentic loop.
        Returns the final text response.
        """
        self.messages.append({'role': 'user', 'content': user_message})

        final_text = ''
        rounds = 0

        while rounds < self.config.max_tool_rounds:
            rounds += 1
            text_was_extracted = False

            response = self.llm.create_message(
                messages=self.messages,
                system=self.system,
                tools=self.tools,
            )

            text_content = '\n'.join(response.text_parts) if response.text_parts else ''
            tool_calls = response.tool_calls

            # ── Fallback: extract tool calls from text ──────────────
            # Some models (especially small ones on Ollama) don't produce
            # proper tool_calls — they put JSON in the text instead.
            if not tool_calls and text_content:
                extracted, cleaned_text = extract_tool_calls_from_text(
                    text_content, _KNOWN_TOOL_NAMES,
                )
                if extracted:
                    # Assign synthetic IDs
                    for i, tc in enumerate(extracted):
                        tc['id'] = generate_tool_call_id(tc['name'], i)
                    tool_calls = extracted
                    text_content = cleaned_text
                    text_was_extracted = True
                    console.print(
                        f'[dim italic]⚡ Extracted {len(extracted)} tool call(s) '
                        f'from model text (model lacks native function calling)[/dim italic]'
                    )

            # Print any remaining text
            # If streaming was used, text was already printed to stdout —
            # only re-print if fallback extraction modified it
            if text_content.strip() and (not self.config.enable_streaming or text_was_extracted):
                final_text = text_content
                try:
                    console.print(Markdown(text_content))
                except Exception:
                    console.print(text_content)
            elif text_content.strip():
                final_text = text_content

            # If no tool calls, we're done
            if not tool_calls:
                if text_content.strip():
                    self._append_assistant_text(text_content)
                break

            # Add assistant message with tool calls
            self._append_assistant_with_tool_calls_raw(text_content, tool_calls)

            # Execute each tool call and add results
            for tc in tool_calls:
                self._print_tool_call(tc['name'], tc['arguments'])
                try:
                    result = execute_live_tool(tc['name'], tc['arguments'])
                except Exception as exc:
                    from .live_tools.base import ToolResult
                    result = ToolResult(success=False, output=f'Tool execution error: {exc}')
                self._print_tool_result(tc['name'], result.success, result.output)
                self._append_tool_result(tc['id'], tc['name'], result.output, result.success)

        if rounds >= self.config.max_tool_rounds:
            console.print(f'\n[yellow]⚠ Reached max tool rounds ({self.config.max_tool_rounds})[/yellow]')

        return final_text

    # ── Message formatting (provider-aware) ────────────────────────

    def _append_assistant_text(self, text: str) -> None:
        """Add a simple assistant text message."""
        if self.config.is_anthropic_native:
            self.messages.append({'role': 'assistant', 'content': [{'type': 'text', 'text': text}]})
        else:
            self.messages.append({'role': 'assistant', 'content': text})

    def _append_assistant_with_tool_calls_raw(self, text: str, tool_calls: list[dict]) -> None:
        """Add the assistant message containing tool calls."""
        if self.config.is_anthropic_native:
            content = []
            if text:
                content.append({'type': 'text', 'text': text})
            for tc in tool_calls:
                content.append({
                    'type': 'tool_use',
                    'id': tc['id'],
                    'name': tc['name'],
                    'input': tc['arguments'],
                })
            self.messages.append({'role': 'assistant', 'content': content})
        else:
            msg: dict = {'role': 'assistant', 'content': text or None}
            msg['tool_calls'] = [
                {
                    'id': tc['id'],
                    'type': 'function',
                    'function': {
                        'name': tc['name'],
                        'arguments': json.dumps(tc['arguments']),
                    },
                }
                for tc in tool_calls
            ]
            self.messages.append(msg)

    def _append_tool_result(self, tool_id: str, name: str, output: str, success: bool) -> None:
        """Add a tool result message."""
        if self.config.is_anthropic_native:
            self.messages.append({
                'role': 'user',
                'content': [{
                    'type': 'tool_result',
                    'tool_use_id': tool_id,
                    'content': output,
                    'is_error': not success,
                }],
            })
        else:
            self.messages.append({
                'role': 'tool',
                'tool_call_id': tool_id,
                'name': name,
                'content': output,
            })

    # ── Pretty printing ────────────────────────────────────────────

    def _print_tool_call(self, name: str, arguments: dict) -> None:
        arg_str = ', '.join(f'{k}={_truncate(str(v), 80)}' for k, v in arguments.items())
        console.print(
            Panel(
                Text(f'{name}({arg_str})', style='cyan'),
                title='[bold blue]🔧 Tool Call[/bold blue]',
                border_style='blue',
                padding=(0, 1),
            )
        )

    def _print_tool_result(self, name: str, success: bool, output: str) -> None:
        icon = '✅' if success else '❌'
        style = 'green' if success else 'red'
        display = _truncate(output, 500)
        console.print(
            Panel(
                Text(display, style='dim'),
                title=f'[bold {style}]{icon} {name}[/bold {style}]',
                border_style=style,
                padding=(0, 1),
            )
        )

    # ── Project context ────────────────────────────────────────────

    def _detect_project_context(self) -> str:
        ws = self.config.workspace
        context_parts = []
        markers = {
            'manage.py': 'Django', 'package.json': 'Node.js',
            'Cargo.toml': 'Rust', 'go.mod': 'Go',
            'pom.xml': 'Java/Maven', 'build.gradle': 'Java/Gradle',
            'setup.py': 'Python', 'pyproject.toml': 'Python',
        }
        detected = [kind for marker, kind in markers.items() if (ws / marker).exists()]
        if detected:
            context_parts.append(f'Detected project type(s): {", ".join(detected)}')
        for readme_name in ('README.md', 'readme.md', 'README.txt'):
            readme = ws / readme_name
            if readme.exists():
                try:
                    context_parts.append(f'README:\n{readme.read_text(errors="replace")[:3000]}')
                except Exception:
                    pass
                break
        for dep_name in ['requirements.txt', 'package.json', 'Cargo.toml', 'pyproject.toml']:
            dep = ws / dep_name
            if dep.exists():
                try:
                    context_parts.append(f'Dependencies ({dep_name}):\n{dep.read_text(errors="replace")[:2000]}')
                except Exception:
                    pass
                break
        return '\n\n'.join(context_parts)


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len] + '...'
