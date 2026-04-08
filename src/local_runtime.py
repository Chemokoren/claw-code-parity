from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse, urlunparse


DEFAULT_OLLAMA_BASE_URL = 'http://localhost:11434/v1'
_PROBE_TIMEOUT_SECONDS = 0.75


@dataclass(frozen=True)
class LocalRuntimeStatus:
    gpu_present: bool
    gpu_usable: bool
    gpu_backend: str | None
    gpu_summary: str
    ollama_reachable: bool
    ollama_base_url: str
    ollama_summary: str

    @property
    def summary(self) -> str:
        return f'{self.gpu_summary}; {self.ollama_summary}'


@dataclass(frozen=True)
class ProviderResolution:
    provider: str
    reason: str
    local_runtime: LocalRuntimeStatus


def resolve_provider_choice(
    requested_provider: str | None,
    ollama_base_url: str | None = None,
) -> ProviderResolution:
    requested = (requested_provider or 'auto').strip().lower() or 'auto'
    runtime = detect_local_runtime(ollama_base_url or resolve_ollama_base_url())

    if requested != 'auto':
        return ProviderResolution(
            provider=requested,
            reason=f'Explicit provider `{requested}` selected.',
            local_runtime=runtime,
        )

    if runtime.ollama_reachable and runtime.gpu_usable:
        return ProviderResolution(
            provider='ollama',
            reason='Auto-selected Ollama because local GPU-backed inference is available.',
            local_runtime=runtime,
        )

    if runtime.ollama_reachable:
        return ProviderResolution(
            provider='ollama',
            reason='Auto-selected Ollama because the local server is reachable; it will use CPU until GPU acceleration is available.',
            local_runtime=runtime,
        )

    credential_provider = _first_configured_remote_provider()
    if credential_provider is not None:
        return ProviderResolution(
            provider=credential_provider,
            reason=(
                f'Auto-selected `{credential_provider}` because Ollama is not reachable at '
                f'{runtime.ollama_base_url}.'
            ),
            local_runtime=runtime,
        )

    return ProviderResolution(
        provider='ollama',
        reason=(
            'Defaulting to Ollama. Start `ollama serve` (or the system service) to use the local runtime.'
        ),
        local_runtime=runtime,
    )


def detect_local_runtime(ollama_base_url: str | None = None) -> LocalRuntimeStatus:
    ollama_base_url = ollama_base_url or resolve_ollama_base_url()
    gpu_present, gpu_usable, gpu_backend, gpu_summary = detect_gpu_status()
    ollama_reachable = probe_ollama(ollama_base_url)
    if ollama_reachable:
        if gpu_usable:
            ollama_summary = f'Ollama is reachable at {ollama_base_url} and should use {gpu_backend or "GPU"} acceleration.'
        else:
            ollama_summary = f'Ollama is reachable at {ollama_base_url}, but local inference will fall back to CPU.'
    else:
        ollama_summary = f'Ollama is not reachable at {ollama_base_url}.'
    return LocalRuntimeStatus(
        gpu_present=gpu_present,
        gpu_usable=gpu_usable,
        gpu_backend=gpu_backend,
        gpu_summary=gpu_summary,
        ollama_reachable=ollama_reachable,
        ollama_base_url=ollama_base_url,
        ollama_summary=ollama_summary,
    )


def resolve_ollama_base_url() -> str:
    return os.getenv('OLLAMA_BASE_URL', '').strip() or DEFAULT_OLLAMA_BASE_URL


def detect_gpu_status() -> tuple[bool, bool, str | None, str]:
    nvidia = _detect_nvidia()
    if nvidia is not None:
        return nvidia

    amd = _detect_rocm()
    if amd is not None:
        return amd

    if _lspci_contains(('nvidia',)):
        return (
            True,
            False,
            'nvidia',
            'NVIDIA GPU hardware is present, but the NVIDIA driver/runtime is not active.',
        )

    if _lspci_contains(('amd', 'advanced micro devices', 'radeon')):
        return (
            True,
            False,
            'amd',
            'AMD GPU hardware is present, but ROCm acceleration is not currently usable.',
        )

    if _render_nodes_present():
        return (
            True,
            False,
            'render',
            'A render-capable GPU device is present, but no supported local LLM acceleration runtime was detected.',
        )

    return (
        False,
        False,
        None,
        'No supported local GPU acceleration runtime was detected; local inference will use CPU.',
    )


def probe_ollama(base_url: str) -> bool:
    version_url = _ollama_version_url(base_url)
    try:
        with request.urlopen(version_url, timeout=_PROBE_TIMEOUT_SECONDS) as response:
            return 200 <= getattr(response, 'status', 200) < 300
    except (error.URLError, TimeoutError, ValueError):
        return False


def _first_configured_remote_provider() -> str | None:
    ordered = (
        ('anthropic', 'ANTHROPIC_API_KEY'),
        ('openai', 'OPENAI_API_KEY'),
        ('zai', 'ZAI_API_KEY'),
        ('deepseek', 'DEEPSEEK_API_KEY'),
        ('groq', 'GROQ_API_KEY'),
        ('openrouter', 'OPENROUTER_API_KEY'),
        ('gemini', 'GEMINI_API_KEY'),
    )
    for provider, env_key in ordered:
        if os.getenv(env_key, '').strip():
            return provider
    return None


def _detect_nvidia() -> tuple[bool, bool, str | None, str] | None:
    result = _run_command(
        ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
        timeout=1.0,
    )
    if result is None:
        return None
    if result.returncode == 0 and result.stdout.strip():
        name = result.stdout.strip().splitlines()[0]
        return (
            True,
            True,
            'nvidia',
            f'NVIDIA GPU acceleration is available ({name}).',
        )
    return (
        True,
        False,
        'nvidia',
        'NVIDIA GPU hardware is present, but `nvidia-smi` could not talk to the driver/runtime.',
    )


def _detect_rocm() -> tuple[bool, bool, str | None, str] | None:
    result = _run_command(['rocm-smi'], timeout=1.0)
    if result is None:
        return None
    if result.returncode == 0:
        return (
            True,
            True,
            'amd',
            'AMD ROCm GPU acceleration is available.',
        )
    return (
        True,
        False,
        'amd',
        'AMD GPU hardware is present, but ROCm is not currently usable.',
    )


def _run_command(command: list[str], timeout: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, PermissionError, OSError, subprocess.TimeoutExpired):
        return None


def _lspci_contains(needles: tuple[str, ...]) -> bool:
    result = _run_command(['lspci'], timeout=1.0)
    if result is None or not result.stdout:
        return False
    haystack = result.stdout.lower()
    return any(needle in haystack for needle in needles)


def _render_nodes_present() -> bool:
    dev_dri = Path('/dev/dri')
    if not dev_dri.is_dir():
        return False
    return any(path.name.startswith('renderD') for path in dev_dri.iterdir())


def _ollama_version_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    path = parsed.path.rstrip('/')
    if path.endswith('/v1'):
        path = path[:-3]
    normalized = parsed._replace(path=f'{path}/api/version' if path else '/api/version', params='', query='', fragment='')
    return urlunparse(normalized)
