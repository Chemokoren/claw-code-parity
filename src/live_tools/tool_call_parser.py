"""Fallback parser for models that emit tool calls as plain text.

Some models (especially smaller ones running on Ollama) don't produce proper
OpenAI-compatible `tool_calls` in the response. Instead, they emit JSON like:

    {"name": "bash", "arguments": {"command": "ls -la"}}

This module detects those patterns in the assistant's text and converts them
into structured tool call dicts that the agent loop can execute.
"""
from __future__ import annotations

import json
import re
from typing import Any


# Pattern: {"name": "...", "arguments": {...}}
# Handles multi-line and nested braces
_TOOL_CALL_RE = re.compile(
    r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})\s*\}',
    re.DOTALL,
)

# Also match ```json blocks that contain tool calls
_JSON_BLOCK_RE = re.compile(
    r'```(?:json)?\s*(\{[^`]*\})\s*```',
    re.DOTALL,
)


def _try_parse_tool_call(text: str) -> dict | None:
    """Try to parse a single JSON object as a tool call."""
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    if isinstance(obj, dict) and 'name' in obj and 'arguments' in obj:
        name = obj['name']
        args = obj['arguments']
        if isinstance(name, str) and isinstance(args, dict):
            return {'name': name, 'arguments': args}
    return None


def extract_tool_calls_from_text(
    text: str,
    known_tool_names: set[str],
) -> tuple[list[dict], str]:
    """Extract embedded tool-call JSON from assistant text.

    Returns:
        (tool_calls, cleaned_text) — list of extracted tool calls and the
        text with those JSON blobs removed.
    """
    tool_calls: list[dict] = []
    removal_spans: list[tuple[int, int]] = []

    # Strategy 1: Look for ```json blocks
    for m in _JSON_BLOCK_RE.finditer(text):
        parsed = _try_parse_tool_call(m.group(1).strip())
        if parsed and parsed['name'] in known_tool_names:
            tool_calls.append(parsed)
            removal_spans.append((m.start(), m.end()))

    # Strategy 2: Look for bare {"name": "...", "arguments": {...}} patterns
    for m in _TOOL_CALL_RE.finditer(text):
        name = m.group(1)
        if name not in known_tool_names:
            continue
        # Check this span isn't already covered
        start, end = m.start(), m.end()
        if any(s <= start < e for s, e in removal_spans):
            continue
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        tool_calls.append({'name': name, 'arguments': args})
        removal_spans.append((start, end))

    # Strategy 3: Try to find tool calls with braces that span further
    # Look for patterns like: {"name": "file_write", "arguments": {"path": "...", "content": "..."}}
    # where the content may contain nested braces
    if not tool_calls:
        for tool_name in known_tool_names:
            pattern = f'{{"name": "{tool_name}", "arguments": '
            idx = text.find(pattern)
            while idx != -1:
                # Find the matching closing brace
                brace_start = idx + len(pattern)
                if brace_start < len(text) and text[brace_start] == '{':
                    depth = 0
                    pos = brace_start
                    while pos < len(text):
                        if text[pos] == '{':
                            depth += 1
                        elif text[pos] == '}':
                            depth -= 1
                            if depth == 0:
                                # Found the end of arguments
                                args_str = text[brace_start:pos + 1]
                                # Now find the outer closing brace
                                rest = text[pos + 1:].lstrip()
                                if rest.startswith('}'):
                                    end_pos = text.index('}', pos + 1) + 1
                                    try:
                                        args = json.loads(args_str)
                                        if isinstance(args, dict):
                                            tool_calls.append({'name': tool_name, 'arguments': args})
                                            removal_spans.append((idx, end_pos))
                                    except json.JSONDecodeError:
                                        pass
                                break
                        pos += 1
                idx = text.find(pattern, idx + 1)

    if not removal_spans:
        return tool_calls, text

    # Remove extracted tool call text, leaving the rest
    removal_spans.sort(reverse=True)
    cleaned = text
    for start, end in removal_spans:
        cleaned = cleaned[:start] + cleaned[end:]

    # Clean up leftover whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    return tool_calls, cleaned


def generate_tool_call_id(name: str, index: int) -> str:
    """Generate a synthetic tool call ID for extracted calls."""
    return f'call_extracted_{name}_{index}'
