"""Configuration for the Claw coding assistant — multi-provider support."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from .local_runtime import LocalRuntimeStatus, resolve_ollama_base_url, resolve_provider_choice

load_dotenv()

# ── Provider presets ────────────────────────────────────────────────
# Each preset maps to a (base_url, default_model) pair.
# Any provider exposing an OpenAI-compatible /v1/chat/completions works.
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    'anthropic': {
        'base_url': 'https://api.anthropic.com/v1',
        'default_model': 'claude-sonnet-4-20250514',
        'env_key': 'ANTHROPIC_API_KEY',
    },
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'default_model': 'gpt-4o',
        'env_key': 'OPENAI_API_KEY',
    },
    'ollama': {
        'base_url': 'http://localhost:11434/v1',
        'default_model': 'qwen2.5-coder:7b',
        'env_key': '',  # no key needed
    },
    'deepseek': {
        'base_url': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat',
        'env_key': 'DEEPSEEK_API_KEY',
    },
    'groq': {
        'base_url': 'https://api.groq.com/openai/v1',
        'default_model': 'llama-3.3-70b-versatile',
        'env_key': 'GROQ_API_KEY',
    },
    'openrouter': {
        'base_url': 'https://openrouter.ai/api/v1',
        'default_model': 'anthropic/claude-sonnet-4-20250514',
        'env_key': 'OPENROUTER_API_KEY',
    },
    'gemini': {
        'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'default_model': 'gemini-2.5-flash',
        'env_key': 'GEMINI_API_KEY',
    },
    'zai': {
        'base_url': 'https://api.z.ai/api/coding/paas/v4',
        'default_model': 'glm-5.1',
        'env_key': 'ZAI_API_KEY',
        'model_env_key': 'ZAI_MODEL',
    },
    'lmstudio': {
        'base_url': 'http://localhost:1234/v1',
        'default_model': 'local-model',
        'env_key': '',
    },
}

OPENAI_COMPATIBLE_PROVIDERS = {
    'openai',
    'deepseek',
    'groq',
    'openrouter',
    'gemini',
    'zai',
    'lmstudio',
}


def _resolve_provider() -> str:
    """Detect provider from env vars, defaulting to auto resolution."""
    return os.getenv('CLAW_PROVIDER', 'auto').lower()


def _resolve_base_url(provider: str) -> str:
    preset = PROVIDER_PRESETS.get(provider, {})
    if provider == 'ollama':
        return resolve_ollama_base_url()
    if provider == 'anthropic':
        return os.getenv('ANTHROPIC_BASE_URL', '').strip() or preset.get(
            'base_url',
            'https://api.anthropic.com/v1',
        )
    if provider == 'zai':
        return (
            os.getenv('ZAI_BASE_URL', '').strip()
            or os.getenv('OPENAI_BASE_URL', '').strip()
            or preset.get('base_url', 'https://api.z.ai/api/coding/paas/v4')
        )
    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        return os.getenv('OPENAI_BASE_URL', '').strip() or preset.get(
            'base_url',
            'http://localhost:11434/v1',
        )
    return os.getenv('OPENAI_BASE_URL', preset.get('base_url', 'http://localhost:11434/v1'))


def _resolve_api_key(provider: str) -> str:
    # Check provider-specific env var
    preset = PROVIDER_PRESETS.get(provider, {})
    env_key = preset.get('env_key', '')
    if env_key:
        key = os.getenv(env_key, '')
        if key:
            return key
    # Fallback to a generic OpenAI-compatible key override
    key = os.getenv('OPENAI_API_KEY', '')
    if key:
        return key
    # For local providers no key needed
    if not key and provider in ('ollama', 'lmstudio'):
        return 'not-needed'
    return key


def _resolve_model(provider: str) -> str:
    preset = PROVIDER_PRESETS.get(provider, {})
    model_env_key = preset.get('model_env_key', '')
    model = (
        os.getenv('CLAW_MODEL', '')
        or (os.getenv(model_env_key, '') if model_env_key else '')
        or os.getenv('OPENAI_MODEL', '')
    )
    if model:
        return model
    return preset.get('default_model', 'qwen2.5-coder:7b')


@dataclass
class ClawConfig:
    """Runtime configuration — auto-resolves from env vars."""

    provider: str = field(default_factory=_resolve_provider)
    api_key: str = ''
    base_url: str = ''
    model: str = ''
    max_tokens: int = 8192
    max_tool_rounds: int = 40
    workspace: Path = field(default_factory=lambda: Path.cwd())
    enable_streaming: bool = True
    provider_reason: str = field(default='', init=False)
    local_runtime: LocalRuntimeStatus = field(init=False)

    def __post_init__(self) -> None:
        resolution = resolve_provider_choice(
            self.provider,
            ollama_base_url=resolve_ollama_base_url(),
        )
        self.provider = resolution.provider
        self.provider_reason = resolution.reason
        self.local_runtime = resolution.local_runtime
        if not self.base_url:
            self.base_url = _resolve_base_url(self.provider)
        if not self.api_key:
            self.api_key = _resolve_api_key(self.provider)
        if not self.model:
            self.model = _resolve_model(self.provider)

    @property
    def is_anthropic_native(self) -> bool:
        """True if using the native Anthropic API (requires anthropic SDK)."""
        return self.provider == 'anthropic' and 'anthropic.com' in self.base_url

    def validate(self) -> None:
        if not self.api_key:
            lines = [
                f'No API key found for provider "{self.provider}".',
                '',
                'Quick setup options:',
                '',
                '  # Ollama (local, free, no key needed)',
                '  export CLAW_PROVIDER=ollama',
                '  export OLLAMA_BASE_URL=http://localhost:11434/v1   # optional override',
                '',
                '  # OpenAI',
                '  export CLAW_PROVIDER=openai',
                '  export OPENAI_API_KEY=sk-...',
                '',
                '  # Z.AI / GLM-5.1',
                '  export CLAW_PROVIDER=zai',
                '  export ZAI_API_KEY=your-zai-key',
                '  export OPENAI_BASE_URL=https://api.z.ai/api/coding/paas/v4',
                '  export ZAI_MODEL=glm-5.1',
                '',
                '  # Any OpenAI-compatible API',
                '  export OPENAI_BASE_URL=http://your-server/v1',
                '  export OPENAI_API_KEY=your-key',
                '  export OPENAI_MODEL=your-model',
                '',
                'Or create a .env file — see .env.example',
            ]
            raise RuntimeError('\n'.join(lines))

    def summary(self) -> str:
        masked_key = '***' + self.api_key[-4:] if len(self.api_key) > 6 else '(none/local)'
        return (
            f'Provider: {self.provider}  |  Model: {self.model}\n'
            f'Base URL: {self.base_url}\n'
            f'API Key:  {masked_key}\n'
            f'Provider reason: {self.provider_reason}\n'
            f'Local runtime: {self.local_runtime.summary}'
        )
