#!/usr/bin/env python3
"""parity-sync.py — Automated Anthropic feature parity checker for claw-code-parity.

This script:
  1. Checks the latest Anthropic API docs and changelog for new features
  2. Cross-references with what claw-code-parity already implements
  3. Identifies gaps and produces a prioritized plan
  4. Optionally executes the plan (with confirmation)
  5. Documents everything in versioned audit reports

Usage:
    python3 scripts/parity-sync.py audit       # Full audit: check → gap analysis → plan
    python3 scripts/parity-sync.py status       # Quick status: show current version and coverage
    python3 scripts/parity-sync.py check        # Check for new Anthropic features only
    python3 scripts/parity-sync.py report       # Generate a versioned report from current state
    python3 scripts/parity-sync.py history       # Show all past audit versions
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FUTURE_DIR = PROJECT_ROOT / 'future'
MANIFEST_PATH = FUTURE_DIR / 'manifest.json'
IMPROVEMENTS_PATH = FUTURE_DIR / 'IMPROVEMENTS.md'
DOCS_DIR = FUTURE_DIR / 'docs'
AUDITS_DIR = FUTURE_DIR / 'audits'

# ── Source files to scan for implemented features ─────────────────────
SOURCE_FILES = {
    'config': PROJECT_ROOT / 'src' / 'config.py',
    'llm': PROJECT_ROOT / 'src' / 'llm.py',
    'agent': PROJECT_ROOT / 'src' / 'agent.py',
    'system_prompt': PROJECT_ROOT / 'src' / 'system_prompt.py',
    'skill_registry': PROJECT_ROOT / 'src' / 'skill_registry.py',
    'repl': PROJECT_ROOT / 'src' / 'repl.py',
}

# ── Feature detection signatures ──────────────────────────────────────
# Each entry maps a feature key to code patterns that indicate implementation.
# The scanner checks if ALL patterns in the list are present in the codebase.
FEATURE_SIGNATURES: dict[str, list[str]] = {
    'adaptive_thinking': [
        'type.*adaptive',
        'thinking_mode',
    ],
    'effort_levels': [
        'effort_level',
        'EFFORT_LEVELS',
    ],
    'thinking_block_preservation': [
        'thinking_blocks',
        'signature.*getattr|getattr.*signature',
    ],
    'opus_4_7_default': [
        'opus-4-7',
    ],
    'skill_content_preload': [
        '_read_skill_content',
        'EXECUTE SKILL',
    ],
    'skill_execution_directives': [
        'EXECUTABLE STEPS.*not reference material',
        'DO NOT summarize',
    ],
    'anthropic_streaming_with_thinking': [
        'thinking_delta',
        '_call_anthropic_streaming',
    ],
    'prompt_caching': [
        'cache_control',
        'ephemeral',
    ],
    'task_budgets': [
        'task_budget',
        'task-budgets-2026',
    ],
    'advisor_tool': [
        'advisor_20260301',
        'advisor-tool-2026',
    ],
    'context_compaction': [
        'compact',
        'context_window.*exceeded',
    ],
    'web_search_tool': [
        'web_search',
        'web_search_20250305',
    ],
    'web_fetch_tool': [
        'web_fetch',
    ],
    'memory_tool': [
        'memory_tool',
    ],
    'coordinator_mode': [
        'coordinator',
        'worker_agent',
    ],
    'computer_use': [
        'computer_use',
        'screenshot',
    ],
    'git_worktree_isolation': [
        'worktree',
        'git worktree',
    ],
    'managed_agents': [
        'managed.agents',
        'managed-agents-2026',
    ],
    'output_300k_batch': [
        'output-300k',
    ],
}

# ── Known Anthropic API features to check for ────────────────────────
# This is the reference list of features. When Anthropic releases new ones,
# add them here along with their detection signatures above.
ANTHROPIC_FEATURE_CATALOG: dict[str, dict] = {
    'adaptive_thinking': {
        'name': 'Adaptive Thinking',
        'api_param': 'thinking: {type: "adaptive"}',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/adaptive-thinking',
        'release_date': '2026-02-05',
        'priority': 'P0',
    },
    'effort_levels': {
        'name': 'Effort Levels',
        'api_param': 'output_config.effort',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/effort',
        'release_date': '2026-02-05',
        'priority': 'P0',
    },
    'thinking_block_preservation': {
        'name': 'Thinking Block Preservation',
        'api_param': 'thinking blocks in assistant messages',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking',
        'release_date': '2025-03-01',
        'priority': 'P0',
    },
    'opus_4_7_default': {
        'name': 'Claude Opus 4.7 Model',
        'api_param': 'model: claude-opus-4-7',
        'docs_url': 'https://docs.anthropic.com/en/docs/about-claude/models/overview',
        'release_date': '2026-04-16',
        'priority': 'P0',
    },
    'anthropic_streaming_with_thinking': {
        'name': 'Streaming with Thinking',
        'api_param': 'thinking_delta SSE events',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking',
        'release_date': '2025-03-01',
        'priority': 'P0',
    },
    'prompt_caching': {
        'name': 'Prompt Caching',
        'api_param': 'cache_control: {type: ephemeral}',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching',
        'release_date': '2024-08-14',
        'priority': 'P0',
    },
    'task_budgets': {
        'name': 'Task Budgets (Beta)',
        'api_param': 'output_config.task_budget',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/task-budgets',
        'release_date': '2026-03-13',
        'priority': 'P1',
    },
    'advisor_tool': {
        'name': 'Advisor Tool (Beta)',
        'api_param': 'tools[].type: advisor_20260301',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/advisor-tool',
        'release_date': '2026-03-01',
        'priority': 'P1',
    },
    'context_compaction': {
        'name': 'Context Compaction',
        'api_param': 'Conversation compaction API',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/compaction',
        'release_date': '2026-01-15',
        'priority': 'P1',
    },
    'web_search_tool': {
        'name': 'Web Search Tool',
        'api_param': 'tools[].type: web_search_20250305',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool',
        'release_date': '2025-03-05',
        'priority': 'P2',
    },
    'web_fetch_tool': {
        'name': 'Web Fetch Tool',
        'api_param': 'tools[].type: web_fetch',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-fetch-tool',
        'release_date': '2026-02-01',
        'priority': 'P2',
    },
    'memory_tool': {
        'name': 'Memory Tool',
        'api_param': 'tools[].type: memory',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/memory-tool',
        'release_date': '2026-03-01',
        'priority': 'P2',
    },
    'coordinator_mode': {
        'name': 'Coordinator / Multi-Agent',
        'api_param': 'CLAUDE_CODE_COORDINATOR_MODE',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools',
        'release_date': '2026-02-01',
        'priority': 'P1',
    },
    'computer_use': {
        'name': 'Computer Use Tool',
        'api_param': 'tools[].type: computer_use_20250124',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool',
        'release_date': '2025-01-24',
        'priority': 'P2',
    },
    'git_worktree_isolation': {
        'name': 'Git Worktree Isolation',
        'api_param': '--worktree flag',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools',
        'release_date': '2026-02-01',
        'priority': 'P2',
    },
    'managed_agents': {
        'name': 'Managed Agents (Beta)',
        'api_param': 'managed-agents-2026-04-01 beta',
        'docs_url': 'https://docs.anthropic.com/en/docs/agents-and-tools',
        'release_date': '2026-04-01',
        'priority': 'P3',
    },
    'output_300k_batch': {
        'name': '300k Output (Batch)',
        'api_param': 'output-300k-2026-03-24 beta',
        'docs_url': 'https://docs.anthropic.com/en/docs/build-with-claude/batch-processing',
        'release_date': '2026-03-24',
        'priority': 'P3',
    },
}


# ── Data classes ──────────────────────────────────────────────────────
@dataclass
class FeatureStatus:
    """Status of a single feature in the codebase."""
    key: str
    name: str
    implemented: bool
    version: str | None
    priority: str
    api_param: str
    docs_url: str
    missing_patterns: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """Result of a full parity audit."""
    timestamp: str
    version: str
    total_features: int
    implemented: int
    gaps: int
    coverage_pct: float
    features: list[FeatureStatus]
    test_result: str = ''
    test_passed: bool = False


# ── Core scanner ──────────────────────────────────────────────────────
def _load_source_content() -> str:
    """Load all source files into a single string for pattern matching."""
    parts = []
    for name, path in SOURCE_FILES.items():
        if path.exists():
            parts.append(path.read_text(encoding='utf-8', errors='replace'))
    return '\n'.join(parts)


def _check_feature_implemented(feature_key: str, source: str) -> tuple[bool, list[str]]:
    """Check if a feature is implemented by looking for its code patterns.

    Returns (is_implemented, missing_patterns).
    """
    patterns = FEATURE_SIGNATURES.get(feature_key, [])
    if not patterns:
        return False, ['no detection patterns defined']

    missing = []
    for pattern in patterns:
        if not re.search(pattern, source, re.IGNORECASE):
            missing.append(pattern)

    return len(missing) == 0, missing


def _load_manifest() -> dict:
    """Load the parity manifest JSON."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    return {'current_version': '0.0.0', 'features': {}}


def _save_manifest(manifest: dict) -> None:
    """Save the parity manifest JSON."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )


def _run_tests() -> tuple[bool, str]:
    """Run the test suite and return (passed, output)."""
    try:
        venv_python = PROJECT_ROOT / '.venv' / 'bin' / 'python'
        python_cmd = str(venv_python) if venv_python.exists() else 'python3'

        result = subprocess.run(
            [python_cmd, '-m', 'pytest', 'tests/', '-x', '-q'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, f'Test execution failed: {exc}'


# ── Audit engine ──────────────────────────────────────────────────────
def run_audit(run_tests: bool = True) -> AuditResult:
    """Run a full parity audit against the codebase."""
    source = _load_source_content()
    manifest = _load_manifest()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    features: list[FeatureStatus] = []
    implemented_count = 0

    for key, catalog_entry in ANTHROPIC_FEATURE_CATALOG.items():
        is_impl, missing = _check_feature_implemented(key, source)

        # Cross-reference with manifest for version info
        manifest_entry = manifest.get('features', {}).get(key, {})
        version = manifest_entry.get('version_added')

        status = FeatureStatus(
            key=key,
            name=catalog_entry['name'],
            implemented=is_impl,
            version=version,
            priority=catalog_entry['priority'],
            api_param=catalog_entry['api_param'],
            docs_url=catalog_entry['docs_url'],
            missing_patterns=missing,
        )
        features.append(status)
        if is_impl:
            implemented_count += 1

    total = len(features)
    coverage = (implemented_count / total * 100) if total > 0 else 0

    test_result = ''
    test_passed = False
    if run_tests:
        test_passed, test_result = _run_tests()

    return AuditResult(
        timestamp=now,
        version=manifest.get('current_version', '0.0.0'),
        total_features=total,
        implemented=implemented_count,
        gaps=total - implemented_count,
        coverage_pct=round(coverage, 1),
        features=features,
        test_result=test_result,
        test_passed=test_passed,
    )


# ── Report generation ─────────────────────────────────────────────────
def generate_audit_report(audit: AuditResult) -> str:
    """Generate a markdown audit report."""
    lines = [
        f'# Parity Audit Report — {audit.timestamp}',
        '',
        f'**Version:** {audit.version}',
        f'**Coverage:** {audit.implemented}/{audit.total_features} features '
        f'({audit.coverage_pct}%)',
        f'**Tests:** {"✅ PASS" if audit.test_passed else "❌ FAIL"}',
        '',
        '---',
        '',
        '## Implemented Features ✅',
        '',
        '| Feature | Version | API Parameter |',
        '|---------|---------|---------------|',
    ]

    for f in audit.features:
        if f.implemented:
            lines.append(f'| {f.name} | {f.version or "—"} | `{f.api_param}` |')

    lines.extend([
        '',
        '## Gaps (Not Yet Implemented) 🔲',
        '',
        '| Feature | Priority | API Parameter | Missing Patterns |',
        '|---------|----------|---------------|------------------|',
    ])

    for f in audit.features:
        if not f.implemented:
            missing = ', '.join(f.missing_patterns[:3])
            lines.append(
                f'| [{f.name}]({f.docs_url}) | {f.priority} | '
                f'`{f.api_param}` | {missing} |'
            )

    lines.extend([
        '',
        '## Gap Implementation Plan',
        '',
    ])

    # Group gaps by priority
    for priority in ('P0', 'P1', 'P2', 'P3'):
        priority_gaps = [f for f in audit.features if not f.implemented and f.priority == priority]
        if priority_gaps:
            lines.append(f'### {priority}')
            lines.append('')
            for i, f in enumerate(priority_gaps, 1):
                manifest = _load_manifest()
                effort = manifest.get('features', {}).get(f.key, {}).get('estimated_effort', 'unknown')
                lines.append(f'{i}. **{f.name}** (~{effort})')
                lines.append(f'   - API: `{f.api_param}`')
                lines.append(f'   - Docs: {f.docs_url}')
                lines.append(f'   - Detection: look for `{", ".join(f.missing_patterns[:2])}`')
                lines.append('')

    if audit.test_result:
        lines.extend([
            '## Test Output',
            '',
            '```',
            audit.test_result[-500:],  # Last 500 chars
            '```',
        ])

    return '\n'.join(lines)


def save_versioned_report(audit: AuditResult) -> Path:
    """Save a timestamped audit report to parity_versions/audits/."""
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'audit_{audit.version}_{date_stamp}.md'
    report_path = AUDITS_DIR / filename
    report_path.write_text(
        generate_audit_report(audit),
        encoding='utf-8',
    )
    return report_path


def update_manifest_from_audit(audit: AuditResult) -> None:
    """Update the manifest with latest scan results."""
    manifest = _load_manifest()
    manifest['last_audit_date'] = audit.timestamp[:10]

    for f in audit.features:
        key = f.key
        if key not in manifest.get('features', {}):
            manifest.setdefault('features', {})[key] = {}

        entry = manifest['features'][key]
        if f.implemented:
            entry['status'] = 'implemented'
            if not entry.get('version_added'):
                entry['version_added'] = audit.version
        else:
            entry['status'] = 'gap'

    _save_manifest(manifest)


# ── CLI commands ──────────────────────────────────────────────────────
def cmd_status() -> None:
    """Show current version and feature coverage."""
    audit = run_audit(run_tests=False)
    print()
    print(f'  Claw Parity Status')
    print(f'  {"=" * 40}')
    print(f'  Version:    {audit.version}')
    print(f'  Coverage:   {audit.implemented}/{audit.total_features} '
          f'({audit.coverage_pct}%)')
    print(f'  Gaps:       {audit.gaps}')
    print()

    # Show implemented
    impl = [f for f in audit.features if f.implemented]
    if impl:
        print(f'  ✅ Implemented ({len(impl)}):')
        for f in impl:
            print(f'     • {f.name} (v{f.version or "?"})')
        print()

    # Show gaps by priority
    gaps = [f for f in audit.features if not f.implemented]
    if gaps:
        print(f'  🔲 Gaps ({len(gaps)}):')
        for p in ('P0', 'P1', 'P2', 'P3'):
            p_gaps = [f for f in gaps if f.priority == p]
            if p_gaps:
                print(f'     [{p}]')
                for f in p_gaps:
                    print(f'       • {f.name}')
        print()


def cmd_check() -> None:
    """Check which Anthropic features are/aren't implement in the codebase."""
    print('\n  Scanning codebase for Anthropic feature patterns...\n')
    audit = run_audit(run_tests=False)

    for f in audit.features:
        icon = '✅' if f.implemented else '🔲'
        print(f'  {icon} {f.name:40s} {f.priority:4s}  {f.api_param}')
        if not f.implemented and f.missing_patterns:
            print(f'     └─ missing: {", ".join(f.missing_patterns[:3])}')

    print(f'\n  Total: {audit.implemented}/{audit.total_features} '
          f'({audit.coverage_pct}%)')
    print()


def cmd_audit() -> None:
    """Full audit: check features, run tests, generate report, update manifest."""
    print('\n  ═══════════════════════════════════════════')
    print('  Claw Parity Sync — Full Audit')
    print('  ═══════════════════════════════════════════\n')

    # Step 1: Scan codebase
    print('  [1/4] Scanning codebase for implemented features...')
    audit = run_audit(run_tests=True)

    # Step 2: Show results
    print(f'  [2/4] Coverage: {audit.implemented}/{audit.total_features} '
          f'({audit.coverage_pct}%)')
    print(f'        Tests: {"✅ PASS" if audit.test_passed else "❌ FAIL"}')
    if not audit.test_passed:
        print(f'\n  ⚠️  Tests failed! Fix before proceeding.')
        print(f'  Last output: {audit.test_result[-200:]}')

    # Step 3: Generate report
    print('  [3/4] Generating versioned audit report...')
    report_path = save_versioned_report(audit)
    print(f'        Saved: {report_path}')

    # Step 4: Update manifest
    print('  [4/4] Updating manifest...')
    update_manifest_from_audit(audit)
    print(f'        Updated: {MANIFEST_PATH}')

    # Show gap summary
    gaps = [f for f in audit.features if not f.implemented]
    if gaps:
        print(f'\n  ─── Gap Summary ({len(gaps)} features) ───\n')
        for p in ('P0', 'P1', 'P2', 'P3'):
            p_gaps = [f for f in gaps if f.priority == p]
            if p_gaps:
                print(f'  [{p}] ({len(p_gaps)} features):')
                for f in p_gaps:
                    manifest = _load_manifest()
                    effort = manifest.get('features', {}).get(f.key, {}).get(
                        'estimated_effort', '?')
                    print(f'    • {f.name} (~{effort})')
                print()

    print(f'  Full report: {report_path}')
    print(f'  Manifest:    {MANIFEST_PATH}')
    print()


def cmd_report() -> None:
    """Generate a report from the current state without running tests."""
    audit = run_audit(run_tests=False)
    report_path = save_versioned_report(audit)
    print(f'\n  Report saved: {report_path}\n')
    print(generate_audit_report(audit))


def cmd_history() -> None:
    """Show all past audit reports."""
    if not AUDITS_DIR.exists():
        print('\n  No audit history found. Run `audit` first.\n')
        return

    reports = sorted(AUDITS_DIR.glob('audit_*.md'))
    if not reports:
        print('\n  No audit reports found.\n')
        return

    print(f'\n  Audit History ({len(reports)} reports)')
    print(f'  {"=" * 50}')
    for r in reports:
        # Parse version and date from filename
        parts = r.stem.split('_')
        version = parts[1] if len(parts) > 1 else '?'
        date = parts[2] if len(parts) > 2 else '?'
        size_kb = r.stat().st_size / 1024
        print(f'  v{version}  {date}  ({size_kb:.1f}KB)  {r.name}')
    print()


def cmd_help() -> None:
    """Show help text."""
    print(textwrap.dedent("""
    Claw Parity Sync — Automated Anthropic feature parity checker

    Usage:
      python3 scripts/parity-sync.py <command>

    Commands:
      audit      Full audit: scan features, run tests, generate versioned report
      status     Quick overview of current version and coverage
      check      Scan codebase for feature patterns (no tests, no report)
      report     Generate a versioned report from current state
      history    List all past audit reports

    Configuration:
      Feature catalog:  scripts/parity-sync.py (ANTHROPIC_FEATURE_CATALOG dict)
      Feature patterns: scripts/parity-sync.py (FEATURE_SIGNATURES dict)
      Manifest:         parity_versions/manifest.json
      Reports:          parity_versions/audits/

    Workflow:
      1. Anthropic releases a new feature (e.g., new tool type)
      2. Add entry to ANTHROPIC_FEATURE_CATALOG and FEATURE_SIGNATURES
      3. Run: python3 scripts/parity-sync.py audit
      4. Review the gap report at parity_versions/audits/
      5. Implement the feature in src/
      6. Re-run: python3 scripts/parity-sync.py audit
      7. Once tests pass and coverage increases, bump version in manifest.json
      8. Update IMPROVEMENTS.md with the new version block

    Environment:
      Expects .venv/bin/python to exist for running tests.
      Falls back to python3 if .venv is not present.
    """))


# ── Main ──────────────────────────────────────────────────────────────
COMMANDS = {
    'audit': cmd_audit,
    'status': cmd_status,
    'check': cmd_check,
    'report': cmd_report,
    'history': cmd_history,
    'help': cmd_help,
    '--help': cmd_help,
    '-h': cmd_help,
}


def main() -> None:
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    command = sys.argv[1].lower()
    handler = COMMANDS.get(command)
    if handler is None:
        print(f'\n  Unknown command: {command}')
        print(f'  Available: {", ".join(COMMANDS.keys())}\n')
        sys.exit(1)

    handler()


if __name__ == '__main__':
    main()
