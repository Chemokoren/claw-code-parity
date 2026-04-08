from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class InstalledSkill:
    name: str
    command_name: str
    aliases: tuple[str, ...]
    description: str
    skill_path: Path
    source_root: Path

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.command_name, *self.aliases)


def normalize_skill_name(value: str) -> str:
    return value.strip().lstrip('/').strip().lower()


def configured_skill_roots(workspace: Path | None = None) -> tuple[Path, ...]:
    workspace = (workspace or Path.cwd()).resolve()
    home = Path.home()

    roots: list[Path] = []

    env_roots = os.getenv('CLAW_SKILL_ROOTS', '')
    if env_roots:
        for raw_root in env_roots.split(os.pathsep):
            raw_root = raw_root.strip()
            if raw_root:
                roots.append(Path(raw_root).expanduser())

    gstack_root = os.getenv('GSTACK_ROOT', '').strip()
    if gstack_root:
        roots.append(Path(gstack_root).expanduser())

    roots.extend([
        workspace / '.agents' / 'skills',
        workspace / '.claude' / 'skills',
        home / '.codex' / 'skills',
        home / '.claude' / 'skills',
        home / '.gstack' / 'repos' / 'gstack',
    ])

    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return tuple(deduped)


def discover_skills(
    roots: Iterable[Path] | None = None,
    workspace: Path | None = None,
) -> tuple[InstalledSkill, ...]:
    candidate_roots = tuple(roots) if roots is not None else configured_skill_roots(workspace)
    installed: list[InstalledSkill] = []
    seen_names: set[str] = set()

    for root in candidate_roots:
        for skill_dir in _iter_skill_dirs(root):
            skill = _load_skill(skill_dir, root)
            if skill is None:
                continue

            claimed_names = {skill.command_name, *skill.aliases}
            if skill.command_name in seen_names:
                continue

            installed.append(skill)
            seen_names.update(claimed_names)

    installed.sort(key=lambda skill: skill.command_name)
    return tuple(installed)


def find_skill(
    name: str,
    roots: Iterable[Path] | None = None,
    workspace: Path | None = None,
) -> InstalledSkill | None:
    needle = normalize_skill_name(name)
    if not needle:
        return None

    for skill in discover_skills(roots=roots, workspace=workspace):
        if needle in skill.all_names:
            return skill
    return None


def render_skill_index(
    limit: int = 20,
    query: str | None = None,
    roots: Iterable[Path] | None = None,
    workspace: Path | None = None,
) -> str:
    skills = list(discover_skills(roots=roots, workspace=workspace))
    if query:
        needle = normalize_skill_name(query)
        skills = [
            skill for skill in skills
            if needle in skill.command_name
            or needle in skill.description.lower()
            or any(needle in alias for alias in skill.aliases)
        ]

    lines = [f'Installed skills: {len(skills)}', '']
    for skill in skills[:limit]:
        summary = skill.description or 'No description available.'
        lines.append(f'- /{skill.command_name} — {summary}')
        if skill.aliases:
            alias_text = ', '.join(f'/{alias}' for alias in skill.aliases)
            lines.append(f'  aliases: {alias_text}')
    return '\n'.join(lines)


def build_skill_invocation_prompt(
    skill: InstalledSkill,
    user_request: str,
    workspace: Path,
) -> str:
    request = user_request.strip() or 'No extra arguments were provided with the slash command.'
    return (
        f'Run the installed skill `/{skill.command_name}` for this turn.\n\n'
        f'Skill file: {skill.skill_path}\n'
        f'Skill root: {skill.source_root}\n'
        f'Workspace: {workspace}\n\n'
        'Before doing substantive work, use `file_read` to read the skill file and follow it as '
        'closely as possible in this Claw environment.\n'
        'If the skill references Claude Code, Codex, or gstack-specific tool names or paths that '
        'do not exist here, adapt them to the closest available tools.\n'
        f'If the skill refers to `~/.claude/skills/gstack` or `~/.codex/skills/gstack`, treat '
        f'`{skill.source_root}` as the preferred local skill root when appropriate.\n\n'
        f'User request for `/{skill.command_name}`:\n{request}'
    )


def _iter_skill_dirs(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return tuple()

    found: list[Path] = []
    seen: set[Path] = set()

    def add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        found.append(resolved)

    if (root / 'SKILL.md').is_file():
        add(root)

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith('.'):
            continue
        if (child / 'SKILL.md').is_file():
            add(child)
        for grandchild in sorted(child.iterdir()):
            if not grandchild.is_dir() or grandchild.name.startswith('.'):
                continue
            if (grandchild / 'SKILL.md').is_file():
                add(grandchild)

    return tuple(found)


def _load_skill(skill_dir: Path, source_root: Path) -> InstalledSkill | None:
    skill_path = skill_dir / 'SKILL.md'
    if not skill_path.is_file():
        return None

    metadata = _parse_skill_frontmatter(skill_path)
    command_name = normalize_skill_name(metadata.get('name', skill_dir.name))
    if not command_name:
        return None

    aliases: set[str] = set()
    dir_name = normalize_skill_name(skill_dir.name)
    if dir_name and dir_name != command_name:
        aliases.add(dir_name)

    path_parts = {part.lower() for part in skill_dir.parts}
    if 'gstack' in path_parts and not command_name.startswith('gstack-'):
        aliases.add(f'gstack-{command_name}')

    description = _summarize_description(metadata.get('description', ''))

    return InstalledSkill(
        name=metadata.get('name', command_name),
        command_name=command_name,
        aliases=tuple(sorted(alias for alias in aliases if alias != command_name)),
        description=description,
        skill_path=skill_path,
        source_root=source_root.resolve(),
    )


def _parse_skill_frontmatter(skill_path: Path) -> dict[str, str]:
    try:
        lines = skill_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return {}

    if not lines or lines[0].strip() != '---':
        return {}

    metadata: dict[str, str] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == '---':
            break

        if ':' not in line:
            index += 1
            continue

        key, raw_value = line.split(':', 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if raw_value == '|':
            index += 1
            block: list[str] = []
            while index < len(lines):
                next_line = lines[index]
                if next_line.strip() == '---':
                    index -= 1
                    break
                if next_line.startswith(' ') or next_line.startswith('\t'):
                    block.append(next_line.strip())
                    index += 1
                    continue
                index -= 1
                break
            metadata[key] = ' '.join(part for part in block if part)
        else:
            metadata[key] = raw_value.strip('"').strip("'")

        index += 1

    return metadata


def _summarize_description(description: str, max_len: int = 160) -> str:
    compact = ' '.join(description.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + '...'
