"""LLM client — unified via OpenAI-compatible API shim.

Works with: OpenAI, Ollama, DeepSeek, Groq, OpenRouter, Gemini,
LM Studio, and any provider exposing /v1/chat/completions.

For native Anthropic, falls back to the anthropic SDK.

Supports streaming for faster perceived response times.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from .config import ClawConfig

console = Console()


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, input_t: int, output_t: int) -> None:
        self.input_tokens += input_t
        self.output_tokens += output_t

    def __str__(self) -> str:
        return f'tokens: {self.input_tokens} in / {self.output_tokens} out'


# ── Normalised response ────────────────────────────────────────────
@dataclass
class LLMResponse:
    """Provider-agnostic response from any LLM."""
    text_parts: list[str]
    tool_calls: list[dict]         # [{id, name, arguments}]
    raw_message: Any               # provider-specific original
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ''


# ── Client ─────────────────────────────────────────────────────────
@dataclass
class LLMClient:
    config: ClawConfig
    usage: TokenUsage = field(default_factory=TokenUsage)
    _client: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.config.is_anthropic_native:
            self._init_anthropic()
        else:
            self._init_openai_compat()

    # ── OpenAI-compatible path (covers 200+ providers) ─────────────
    def _init_openai_compat(self) -> None:
        from openai import OpenAI
        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    def _call_openai_compat(
        self, messages: list[dict], system: str, tools: list[dict],
    ) -> LLMResponse:
        # Prepend system message
        full_messages = [{'role': 'system', 'content': system}] + messages

        # Convert tool schemas to OpenAI function format
        oai_tools = [
            {'type': 'function', 'function': {'name': t['name'], 'description': t['description'], 'parameters': t['input_schema']}}
            for t in tools
        ]

        kwargs: dict[str, Any] = {
            'model': self.config.model,
            'messages': full_messages,
            'max_tokens': self.config.max_tokens,
        }
        if oai_tools:
            kwargs['tools'] = oai_tools

        # ── Try streaming first for faster perceived response ──────
        if self.config.enable_streaming:
            try:
                return self._call_openai_streaming(kwargs)
            except Exception:
                # Fall back to non-streaming if streaming fails
                pass

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        # Extract text
        text_parts = [msg.content] if msg.content else []

        # Extract tool calls
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append({
                    'id': tc.id,
                    'name': tc.function.name,
                    'arguments': args,
                })

        in_tok = getattr(response.usage, 'prompt_tokens', 0) or 0
        out_tok = getattr(response.usage, 'completion_tokens', 0) or 0
        self.usage.add(in_tok, out_tok)

        return LLMResponse(
            text_parts=text_parts,
            tool_calls=tool_calls,
            raw_message=msg,
            input_tokens=in_tok,
            output_tokens=out_tok,
            stop_reason=choice.finish_reason or '',
        )

    def _call_openai_streaming(self, kwargs: dict) -> LLMResponse:
        """Stream the response for faster perceived response time."""
        kwargs['stream'] = True
        kwargs['stream_options'] = {'include_usage': True}

        stream = self._client.chat.completions.create(**kwargs)

        collected_text = []
        collected_tool_calls: dict[int, dict] = {}  # index -> {id, name, arguments_str}
        finish_reason = ''
        in_tok = 0
        out_tok = 0

        # Print text as it streams in
        current_text = ''
        for chunk in stream:
            if chunk.usage:
                in_tok = getattr(chunk.usage, 'prompt_tokens', 0) or 0
                out_tok = getattr(chunk.usage, 'completion_tokens', 0) or 0

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

            # Accumulate text
            if delta.content:
                sys.stdout.write(delta.content)
                sys.stdout.flush()
                current_text += delta.content

            # Accumulate tool calls
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            'id': tc_delta.id or '',
                            'name': '',
                            'arguments_str': '',
                        }
                    entry = collected_tool_calls[idx]
                    if tc_delta.id:
                        entry['id'] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry['name'] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry['arguments_str'] += tc_delta.function.arguments

        if current_text:
            sys.stdout.write('\n')
            sys.stdout.flush()

        self.usage.add(in_tok, out_tok)

        # Build tool calls
        tool_calls = []
        for idx in sorted(collected_tool_calls.keys()):
            entry = collected_tool_calls[idx]
            try:
                args = json.loads(entry['arguments_str']) if entry['arguments_str'] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                'id': entry['id'],
                'name': entry['name'],
                'arguments': args,
            })

        text_parts = [current_text] if current_text else []

        return LLMResponse(
            text_parts=text_parts,
            tool_calls=tool_calls,
            raw_message=None,
            input_tokens=in_tok,
            output_tokens=out_tok,
            stop_reason=finish_reason,
        )

    # ── Native Anthropic path ──────────────────────────────────────
    def _init_anthropic(self) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=self.config.api_key)

    def _call_anthropic(
        self, messages: list[dict], system: str, tools: list[dict],
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == 'text':
                text_parts.append(block.text)
            elif block.type == 'tool_use':
                tool_calls.append({
                    'id': block.id,
                    'name': block.name,
                    'arguments': block.input,
                })
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        self.usage.add(in_tok, out_tok)
        return LLMResponse(
            text_parts=text_parts,
            tool_calls=tool_calls,
            raw_message=response,
            input_tokens=in_tok,
            output_tokens=out_tok,
            stop_reason=response.stop_reason or '',
        )

    # ── Unified interface ──────────────────────────────────────────
    def create_message(
        self, messages: list[dict], system: str, tools: list[dict],
    ) -> LLMResponse:
        if self.config.is_anthropic_native:
            return self._call_anthropic(messages, system, tools)
        return self._call_openai_compat(messages, system, tools)
