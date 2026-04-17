"""Interactive REPL — the main user-facing terminal prompt."""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .agent import Agent
from .config import PROVIDER_PRESETS, ClawConfig
from .skill_registry import (
    build_skill_invocation_prompt,
    discover_skills,
    find_skill,
)

console = Console()

BANNER = """
   ██████╗██╗      █████╗ ██╗    ██╗
  ██╔════╝██║     ██╔══██╗██║    ██║
  ██║     ██║     ███████║██║ █╗ ██║
  ██║     ██║     ██╔══██║██║███╗██║
  ╚██████╗███████╗██║  ██║╚███╔███╔╝
   ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
"""

_GSTACK_HINT_COMMANDS = {
    'autoplan',
    'benchmark',
    'browse',
    'careful',
    'canary',
    'checkpoint',
    'cso',
    'design-consultation',
    'design-html',
    'design-review',
    'design-shotgun',
    'document-release',
    'freeze',
    'guard',
    'investigate',
    'land-and-deploy',
    'learn',
    'office-hours',
    'plan-ceo-review',
    'plan-design-review',
    'plan-devex-review',
    'plan-eng-review',
    'qa',
    'qa-only',
    'review',
    'retro',
    'setup-browser-cookies',
    'setup-deploy',
    'ship',
    'unfreeze',
}


def _show_provider_table(cfg: ClawConfig) -> None:
    """Show the current provider and all available presets."""
    console.print(f'\n[bold green]Active provider:[/bold green] {cfg.provider}')
    console.print(f'  Model:    {cfg.model}')
    console.print(f'  Base URL: {cfg.base_url}')
    console.print(f'  Reason:   {cfg.provider_reason}')
    console.print(f'  Runtime:  {cfg.local_runtime.summary}')
    console.print(f'  Thinking: {cfg.thinking_mode} (effort: {cfg.effort_level})')
    console.print()

    table = Table(title='Available Provider Presets', border_style='dim')
    table.add_column('Provider', style='cyan')
    table.add_column('Base URL', style='dim')
    table.add_column('Default Model')
    table.add_column('Env Key')

    for name, preset in PROVIDER_PRESETS.items():
        marker = ' ◀' if name == cfg.provider else ''
        table.add_row(
            f'{name}{marker}',
            preset['base_url'],
            preset['default_model'],
            preset.get('env_key', '') or '(none)',
        )
    console.print(table)
    console.print('\n[dim]Switch with:  export CLAW_PROVIDER=ollama  (or openai, deepseek, etc.)[/dim]')
    console.print('[dim]Override:     export OPENAI_BASE_URL=... OPENAI_MODEL=... OPENAI_API_KEY=...[/dim]\n')


def _build_help_text(cfg: ClawConfig) -> str:
    skills = discover_skills(workspace=cfg.workspace)
    lines = [
        'Commands:',
        '  /help       — show this help',
        '  /provider   — show current provider & list all presets',
        '  /skills     — list installed slash-skill commands',
        '  /think      — set thinking mode: /think adaptive|enabled|disabled',
        '  /effort     — set effort level: /effort low|medium|high|xhigh|max',
        '  /clear      — clear conversation history',
        '  /usage      — show token usage',
        '  /quit       — exit (or press Ctrl+C)',
        '',
        f'Thinking: {cfg.thinking_mode} | Effort: {cfg.effort_level}',
    ]
    if skills:
        preview = ', '.join(f'/{skill.command_name}' for skill in skills[:8])
        if len(skills) > 8:
            preview += ', ...'
        lines.extend(['', f'Installed skills ({len(skills)}): {preview}'])
    return '\n'.join(lines)


def _show_skill_table(cfg: ClawConfig) -> None:
    skills = discover_skills(workspace=cfg.workspace)
    if not skills:
        console.print('[yellow]No installed skills were discovered.[/yellow]')
        console.print('[dim]Set CLAW_SKILL_ROOTS=/path/to/skills[:...] if your skills live outside the default Claude/Codex locations.[/dim]')
        return

    table = Table(title='Installed Slash Skills', border_style='dim')
    table.add_column('Slash', style='cyan')
    table.add_column('Aliases', style='dim')
    table.add_column('Description')
    table.add_column('Source', style='dim')

    for skill in skills:
        aliases = ', '.join(f'/{alias}' for alias in skill.aliases) or '—'
        table.add_row(
            f'/{skill.command_name}',
            aliases,
            skill.description or 'No description available.',
            str(skill.skill_path),
        )

    console.print(table)
    console.print('[dim]Invoke any listed skill directly, for example: /qa https://staging.example.com[/dim]')


def _looks_like_gstack_skill(command_name: str, workspace: Path) -> bool:
    if command_name in _GSTACK_HINT_COMMANDS or command_name.startswith('gstack-'):
        return True

    claude_md = workspace / 'CLAUDE.md'
    if not claude_md.exists():
        return False

    try:
        return 'gstack' in claude_md.read_text(encoding='utf-8', errors='replace').lower()
    except OSError:
        return False


def _render_unknown_command_message(command_name: str, cfg: ClawConfig) -> str:
    lines = [f'Unknown command: /{command_name}. Type /help']
    lines.append('Use /skills to list installed slash-skill commands.')
    lines.append('If your skills live in a custom checkout, set CLAW_SKILL_ROOTS=/path/to/skills[:...].')

    if _looks_like_gstack_skill(command_name, cfg.workspace):
        lines.append(
            'This repo references gstack, but the Python REPL only sees gstack skills when they are '
            'installed under ~/.claude/skills, ~/.codex/skills, the current workspace, or a path from CLAW_SKILL_ROOTS.'
        )

    return '\n'.join(lines)


def run_repl(config: ClawConfig | None = None) -> None:
    """Launch the interactive Claw REPL."""
    cfg = config or ClawConfig()

    try:
        cfg.validate()
    except RuntimeError as exc:
        console.print(f'[bold red]Error:[/bold red] {exc}')
        sys.exit(1)

    console.print(Text(BANNER, style='bold cyan'))
    console.print(
        Panel(
            f'[bold]Workspace:[/bold] {cfg.workspace}\n'
            f'[bold]Provider:[/bold]  {cfg.provider}  |  [bold]Model:[/bold] {cfg.model}\n'
            f'[bold]Base URL:[/bold]  {cfg.base_url}\n\n'
            f'[bold]Runtime:[/bold]   {cfg.local_runtime.summary}\n'
            f'[bold]Thinking:[/bold]  {cfg.thinking_mode} (effort: {cfg.effort_level})\n\n'
            f'Type your coding request, or /help for commands.',
            title='[bold green]🐾 Claw Coding Assistant[/bold green]',
            border_style='green',
            padding=(1, 2),
        )
    )

    agent = Agent(config=cfg)

    while True:
        try:
            console.print()
            user_input = console.input('[bold cyan]claw>[/bold cyan] ').strip()
        except (KeyboardInterrupt, EOFError):
            console.print('\n[dim]Goodbye![/dim]')
            break

        if not user_input:
            continue

        if user_input.startswith('/'):
            cmd = user_input.lower().split()[0]
            if cmd in ('/quit', '/exit', '/q'):
                console.print('[dim]Goodbye![/dim]')
                break
            elif cmd == '/help':
                console.print(_build_help_text(cfg))
                continue
            elif cmd == '/provider':
                _show_provider_table(cfg)
                continue
            elif cmd == '/skills':
                _show_skill_table(cfg)
                continue
            elif cmd == '/clear':
                agent.messages.clear()
                console.print('[green]Conversation cleared.[/green]')
                continue
            elif cmd == '/usage':
                console.print(f'[dim]{agent.llm.usage}[/dim]')
                continue
            elif cmd == '/think':
                parts = user_input.split()
                if len(parts) < 2:
                    console.print(f'[dim]Current thinking mode: {cfg.thinking_mode}[/dim]')
                    console.print('[dim]Usage: /think adaptive|enabled|disabled[/dim]')
                else:
                    mode = parts[1].lower()
                    if mode in ('adaptive', 'enabled', 'disabled'):
                        cfg.thinking_mode = mode
                        agent.config.thinking_mode = mode
                        console.print(f'[green]Thinking mode set to: {mode}[/green]')
                    else:
                        console.print(f'[yellow]Invalid mode: {mode}. Use adaptive, enabled, or disabled.[/yellow]')
                continue
            elif cmd == '/effort':
                from .config import EFFORT_LEVELS
                parts = user_input.split()
                if len(parts) < 2:
                    console.print(f'[dim]Current effort level: {cfg.effort_level}[/dim]')
                    console.print(f'[dim]Usage: /effort {"|".join(EFFORT_LEVELS)}[/dim]')
                else:
                    level = parts[1].lower()
                    if level in EFFORT_LEVELS:
                        cfg.effort_level = level
                        agent.config.effort_level = level
                        console.print(f'[green]Effort level set to: {level}[/green]')
                    else:
                        console.print(f'[yellow]Invalid level: {level}. Use: {"|".join(EFFORT_LEVELS)}[/yellow]')
                continue
            else:
                skill = find_skill(cmd, workspace=cfg.workspace)
                if skill is None:
                    console.print(f'[yellow]{_render_unknown_command_message(cmd.lstrip("/"), cfg)}[/yellow]')
                    continue

                skill_request = user_input[len(cmd):].strip()
                console.print(
                    f'[bold green]Running skill:[/bold green] /{skill.command_name} '
                    f'[dim]({skill.skill_path})[/dim]'
                )
                try:
                    agent.chat(build_skill_invocation_prompt(skill, skill_request, cfg.workspace))
                except Exception as exc:
                    console.print(f'[bold red]Error:[/bold red] {exc}')
                    console.print('[dim]The conversation is still active. Try again.[/dim]')
                continue

        try:
            agent.chat(user_input)
        except Exception as exc:
            console.print(f'[bold red]Error:[/bold red] {exc}')
            console.print('[dim]The conversation is still active. Try again.[/dim]')

    console.print(f'\n[dim]Session {agent.llm.usage}[/dim]')
