"""Interactive REPL — the main user-facing terminal prompt."""
from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .agent import Agent
from .config import PROVIDER_PRESETS, ClawConfig

console = Console()

BANNER = """
   ██████╗██╗      █████╗ ██╗    ██╗
  ██╔════╝██║     ██╔══██╗██║    ██║
  ██║     ██║     ███████║██║ █╗ ██║
  ██║     ██║     ██╔══██║██║███╗██║
  ╚██████╗███████╗██║  ██║╚███╔███╔╝
   ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
"""

HELP_TEXT = """Commands:
  /help       — show this help
  /provider   — show current provider & list all presets
  /clear      — clear conversation history
  /usage      — show token usage
  /quit       — exit (or press Ctrl+C)
"""


def _show_provider_table(cfg: ClawConfig) -> None:
    """Show the current provider and all available presets."""
    console.print(f'\n[bold green]Active provider:[/bold green] {cfg.provider}')
    console.print(f'  Model:    {cfg.model}')
    console.print(f'  Base URL: {cfg.base_url}')
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
                console.print(HELP_TEXT)
                continue
            elif cmd == '/provider':
                _show_provider_table(cfg)
                continue
            elif cmd == '/clear':
                agent.messages.clear()
                console.print('[green]Conversation cleared.[/green]')
                continue
            elif cmd == '/usage':
                console.print(f'[dim]{agent.llm.usage}[/dim]')
                continue
            else:
                console.print(f'[yellow]Unknown command: {cmd}. Type /help[/yellow]')
                continue

        try:
            agent.chat(user_input)
        except Exception as exc:
            console.print(f'[bold red]Error:[/bold red] {exc}')
            console.print('[dim]The conversation is still active. Try again.[/dim]')

    console.print(f'\n[dim]Session {agent.llm.usage}[/dim]')
