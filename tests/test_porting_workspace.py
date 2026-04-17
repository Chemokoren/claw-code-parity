from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.commands import PORTED_COMMANDS
from src.parity_audit import run_parity_audit
from src.port_manifest import build_port_manifest
from src.query_engine import QueryEnginePort
from src.tools import PORTED_TOOLS


class PortingWorkspaceTests(unittest.TestCase):
    def test_auto_provider_prefers_gpu_backed_ollama(self) -> None:
        from src.config import ClawConfig
        from src.local_runtime import LocalRuntimeStatus, ProviderResolution

        runtime = LocalRuntimeStatus(
            gpu_present=True,
            gpu_usable=True,
            gpu_backend='nvidia',
            gpu_summary='NVIDIA GPU acceleration is available (Mock GPU).',
            ollama_reachable=True,
            ollama_base_url='http://localhost:11434/v1',
            ollama_summary='Ollama is reachable at http://localhost:11434/v1 and should use nvidia acceleration.',
        )

        with patch(
            'src.config.resolve_provider_choice',
            return_value=ProviderResolution(
                provider='ollama',
                reason='Auto-selected Ollama because local GPU-backed inference is available.',
                local_runtime=runtime,
            ),
        ):
            cfg = ClawConfig(provider='auto')

        self.assertEqual(cfg.provider, 'ollama')
        self.assertIn('GPU-backed inference', cfg.provider_reason)
        self.assertTrue(cfg.local_runtime.gpu_usable)

    def test_explicit_provider_is_preserved_even_with_auto_runtime_logic(self) -> None:
        from src.config import ClawConfig
        from src.local_runtime import LocalRuntimeStatus, ProviderResolution

        runtime = LocalRuntimeStatus(
            gpu_present=True,
            gpu_usable=False,
            gpu_backend='nvidia',
            gpu_summary='NVIDIA GPU hardware is present, but the driver/runtime is not active.',
            ollama_reachable=False,
            ollama_base_url='http://localhost:11434/v1',
            ollama_summary='Ollama is not reachable at http://localhost:11434/v1.',
        )

        with patch(
            'src.config.resolve_provider_choice',
            return_value=ProviderResolution(
                provider='anthropic',
                reason='Explicit provider `anthropic` selected.',
                local_runtime=runtime,
            ),
        ):
            cfg = ClawConfig(provider='anthropic', api_key='test-key')

        self.assertEqual(cfg.provider, 'anthropic')
        self.assertIn('Explicit provider', cfg.provider_reason)

    def test_zai_provider_uses_zai_api_key_and_default_model(self) -> None:
        from src.config import ClawConfig
        from src.local_runtime import LocalRuntimeStatus, ProviderResolution

        runtime = LocalRuntimeStatus(
            gpu_present=False,
            gpu_usable=False,
            gpu_backend=None,
            gpu_summary='No supported local GPU acceleration runtime was detected; local inference will use CPU.',
            ollama_reachable=False,
            ollama_base_url='http://localhost:11434/v1',
            ollama_summary='Ollama is not reachable at http://localhost:11434/v1.',
        )

        with patch(
            'src.config.resolve_provider_choice',
            return_value=ProviderResolution(
                provider='zai',
                reason='Explicit provider `zai` selected.',
                local_runtime=runtime,
            ),
        ), patch.dict(
            os.environ,
            {
                'ZAI_API_KEY': 'zai-test-key',
                'ZAI_MODEL': 'glm-5.1',
                'OPENAI_BASE_URL': 'https://api.z.ai/api/coding/paas/v4',
            },
            clear=False,
        ):
            cfg = ClawConfig(provider='zai')

        self.assertEqual(cfg.provider, 'zai')
        self.assertEqual(cfg.api_key, 'zai-test-key')
        self.assertEqual(cfg.model, 'glm-5.1')
        self.assertEqual(cfg.base_url, 'https://api.z.ai/api/coding/paas/v4')

    def test_ollama_provider_prefers_ollama_base_url_over_generic_openai_base_url(self) -> None:
        from src.config import ClawConfig
        from src.local_runtime import LocalRuntimeStatus, ProviderResolution

        runtime = LocalRuntimeStatus(
            gpu_present=False,
            gpu_usable=False,
            gpu_backend=None,
            gpu_summary='No supported local GPU acceleration runtime was detected; local inference will use CPU.',
            ollama_reachable=False,
            ollama_base_url='http://localhost:11434/v1',
            ollama_summary='Ollama is not reachable at http://localhost:11434/v1.',
        )

        with patch(
            'src.config.resolve_provider_choice',
            return_value=ProviderResolution(
                provider='ollama',
                reason='Explicit provider `ollama` selected.',
                local_runtime=runtime,
            ),
        ), patch.dict(
            os.environ,
            {
                'OLLAMA_BASE_URL': 'http://localhost:11434/v1',
                'OPENAI_BASE_URL': 'https://api.z.ai/api/coding/paas/v4',
            },
            clear=False,
        ):
            cfg = ClawConfig(provider='ollama')

        self.assertEqual(cfg.base_url, 'http://localhost:11434/v1')

    def test_auto_provider_can_fallback_to_zai_when_key_is_present(self) -> None:
        from src.local_runtime import LocalRuntimeStatus, resolve_provider_choice

        runtime = LocalRuntimeStatus(
            gpu_present=False,
            gpu_usable=False,
            gpu_backend=None,
            gpu_summary='No supported local GPU acceleration runtime was detected; local inference will use CPU.',
            ollama_reachable=False,
            ollama_base_url='http://localhost:11434/v1',
            ollama_summary='Ollama is not reachable at http://localhost:11434/v1.',
        )

        with patch('src.local_runtime.detect_local_runtime', return_value=runtime), patch.dict(
            os.environ,
            {'ZAI_API_KEY': 'zai-test-key'},
            clear=True,
        ):
            resolution = resolve_provider_choice('auto')

        self.assertEqual(resolution.provider, 'zai')
        self.assertIn('Auto-selected `zai`', resolution.reason)

    def test_manifest_counts_python_files(self) -> None:
        manifest = build_port_manifest()
        self.assertGreaterEqual(manifest.total_python_files, 20)
        self.assertTrue(manifest.top_level_modules)

    def test_query_engine_summary_mentions_workspace(self) -> None:
        summary = QueryEnginePort.from_workspace().render_summary()
        self.assertIn('Python Porting Workspace Summary', summary)
        self.assertIn('Command surface:', summary)
        self.assertIn('Tool surface:', summary)

    def test_cli_summary_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'summary'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Python Porting Workspace Summary', result.stdout)

    def test_parity_audit_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'parity-audit'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Parity Audit', result.stdout)

    def test_root_file_coverage_is_complete_when_local_archive_exists(self) -> None:
        audit = run_parity_audit()
        if audit.archive_present:
            self.assertEqual(audit.root_file_coverage[0], audit.root_file_coverage[1])
            self.assertGreaterEqual(audit.directory_coverage[0], 28)
            self.assertGreaterEqual(audit.command_entry_ratio[0], 150)
            self.assertGreaterEqual(audit.tool_entry_ratio[0], 100)

    def test_command_and_tool_snapshots_are_nontrivial(self) -> None:
        self.assertGreaterEqual(len(PORTED_COMMANDS), 150)
        self.assertGreaterEqual(len(PORTED_TOOLS), 100)

    def test_commands_and_tools_cli_run(self) -> None:
        commands_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'commands', '--limit', '5', '--query', 'review'],
            check=True,
            capture_output=True,
            text=True,
        )
        tools_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'tools', '--limit', '5', '--query', 'MCP'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Command entries:', commands_result.stdout)
        self.assertIn('Tool entries:', tools_result.stdout)

    def test_skill_registry_discovers_skills_and_aliases(self) -> None:
        from src.skill_registry import (
            build_skill_invocation_prompt,
            discover_skills,
            find_skill,
        )

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pack_skill = root / '.claude' / 'skills' / 'gstack' / 'qa'
            pack_skill.mkdir(parents=True)
            pack_skill.joinpath('SKILL.md').write_text(
                '---\n'
                'name: qa\n'
                'description: |\n'
                '  Test the app end to end.\n'
                '---\n'
                '\n'
                '# QA\n',
                encoding='utf-8',
            )

            codex_skill = root / '.agents' / 'skills' / 'gstack-office-hours'
            codex_skill.mkdir(parents=True)
            codex_skill.joinpath('SKILL.md').write_text(
                '---\n'
                'name: office-hours\n'
                'description: |\n'
                '  Brainstorm product directions.\n'
                '---\n'
                '\n'
                '# Office Hours\n',
                encoding='utf-8',
            )

            skills = discover_skills(
                roots=[
                    root / '.claude' / 'skills',
                    root / '.agents' / 'skills',
                ],
            )

            self.assertEqual([skill.command_name for skill in skills], ['office-hours', 'qa'])
            self.assertIsNotNone(find_skill('qa', roots=[root / '.claude' / 'skills']))
            self.assertIsNotNone(find_skill('gstack-office-hours', roots=[root / '.agents' / 'skills']))

            office_hours = find_skill('office-hours', roots=[root / '.agents' / 'skills'])
            self.assertIsNotNone(office_hours)
            prompt = build_skill_invocation_prompt(
                office_hours,
                'Help me think through a launch plan',
                root,
            )
            self.assertIn('EXECUTE SKILL: /office-hours', prompt)
            self.assertIn('EXECUTABLE STEPS, not reference material', prompt)
            self.assertIn('Help me think through a launch plan', prompt)
            self.assertIn(str(root), prompt)
            # Verify skill content is pre-loaded into the prompt
            self.assertIn('# Office Hours', prompt)

    def test_subsystem_packages_expose_archive_metadata(self) -> None:
        from src import assistant, bridge, utils

        self.assertGreater(assistant.MODULE_COUNT, 0)
        self.assertGreater(bridge.MODULE_COUNT, 0)
        self.assertGreater(utils.MODULE_COUNT, 100)
        self.assertTrue(utils.SAMPLE_FILES)

    def test_route_and_show_entry_cli_run(self) -> None:
        route_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'route', 'review MCP tool', '--limit', '5'],
            check=True,
            capture_output=True,
            text=True,
        )
        show_command = subprocess.run(
            [sys.executable, '-m', 'src.main', 'show-command', 'review'],
            check=True,
            capture_output=True,
            text=True,
        )
        show_tool = subprocess.run(
            [sys.executable, '-m', 'src.main', 'show-tool', 'MCPTool'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('review', route_result.stdout.lower())
        self.assertIn('review', show_command.stdout.lower())
        self.assertIn('mcptool', show_tool.stdout.lower())

    def test_bootstrap_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'bootstrap', 'review MCP tool', '--limit', '5'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Runtime Session', result.stdout)
        self.assertIn('Startup Steps', result.stdout)
        self.assertIn('Routed Matches', result.stdout)

    def test_bootstrap_session_tracks_turn_state(self) -> None:
        from src.runtime import PortRuntime

        session = PortRuntime().bootstrap_session('review MCP tool', limit=5)
        self.assertGreaterEqual(len(session.turn_result.matched_tools), 1)
        self.assertIn('Prompt:', session.turn_result.output)
        self.assertGreaterEqual(session.turn_result.usage.input_tokens, 1)

    def test_exec_command_and_tool_cli_run(self) -> None:
        command_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'exec-command', 'review', 'inspect security review'],
            check=True,
            capture_output=True,
            text=True,
        )
        tool_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'exec-tool', 'MCPTool', 'fetch resource list'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Mirrored command 'review'", command_result.stdout)
        self.assertIn("Mirrored tool 'MCPTool'", tool_result.stdout)

    def test_setup_report_and_registry_filters_run(self) -> None:
        setup_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'setup-report'],
            check=True,
            capture_output=True,
            text=True,
        )
        command_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'commands', '--limit', '5', '--no-plugin-commands'],
            check=True,
            capture_output=True,
            text=True,
        )
        tool_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'tools', '--limit', '5', '--simple-mode', '--no-mcp'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Setup Report', setup_result.stdout)
        self.assertIn('Command entries:', command_result.stdout)
        self.assertIn('Tool entries:', tool_result.stdout)

    def test_skills_cli_lists_discovered_skills(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            skill_dir = root / '.agents' / 'skills' / 'gstack-qa'
            skill_dir.mkdir(parents=True)
            skill_dir.joinpath('SKILL.md').write_text(
                '---\n'
                'name: qa\n'
                'description: |\n'
                '  Test the app end to end.\n'
                '---\n',
                encoding='utf-8',
            )

            env = dict(os.environ)
            env['CLAW_SKILL_ROOTS'] = str(root / '.agents' / 'skills')
            result = subprocess.run(
                [sys.executable, '-m', 'src.main', 'skills', '--query', 'qa'],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertIn('Installed skills:', result.stdout)
            self.assertIn('/qa', result.stdout)

    def test_load_session_cli_runs(self) -> None:
        from src.runtime import PortRuntime

        session = PortRuntime().bootstrap_session('review MCP tool', limit=5)
        session_id = Path(session.persisted_session_path).stem
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'load-session', session_id],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn(session_id, result.stdout)
        self.assertIn('messages', result.stdout)

    def test_tool_permission_filtering_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'tools', '--limit', '10', '--deny-prefix', 'mcp'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Tool entries:', result.stdout)
        self.assertNotIn('MCPTool', result.stdout)

    def test_turn_loop_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'turn-loop', 'review MCP tool', '--max-turns', '2', '--structured-output'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('## Turn 1', result.stdout)
        self.assertIn('stop_reason=', result.stdout)

    def test_remote_mode_clis_run(self) -> None:
        remote_result = subprocess.run([sys.executable, '-m', 'src.main', 'remote-mode', 'workspace'], check=True, capture_output=True, text=True)
        ssh_result = subprocess.run([sys.executable, '-m', 'src.main', 'ssh-mode', 'workspace'], check=True, capture_output=True, text=True)
        teleport_result = subprocess.run([sys.executable, '-m', 'src.main', 'teleport-mode', 'workspace'], check=True, capture_output=True, text=True)
        self.assertIn('mode=remote', remote_result.stdout)
        self.assertIn('mode=ssh', ssh_result.stdout)
        self.assertIn('mode=teleport', teleport_result.stdout)

    def test_flush_transcript_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'flush-transcript', 'review MCP tool'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('flushed=True', result.stdout)

    def test_command_graph_and_tool_pool_cli_run(self) -> None:
        command_graph = subprocess.run([sys.executable, '-m', 'src.main', 'command-graph'], check=True, capture_output=True, text=True)
        tool_pool = subprocess.run([sys.executable, '-m', 'src.main', 'tool-pool'], check=True, capture_output=True, text=True)
        self.assertIn('Command Graph', command_graph.stdout)
        self.assertIn('Tool Pool', tool_pool.stdout)

    def test_setup_report_mentions_deferred_init(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'setup-report'],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn('Deferred init:', result.stdout)
        self.assertIn('plugin_init=True', result.stdout)

    def test_execution_registry_runs(self) -> None:
        from src.execution_registry import build_execution_registry

        registry = build_execution_registry()
        self.assertGreaterEqual(len(registry.commands), 150)
        self.assertGreaterEqual(len(registry.tools), 100)
        self.assertIn('Mirrored command', registry.command('review').execute('review security'))
        self.assertIn('Mirrored tool', registry.tool('MCPTool').execute('fetch mcp resources'))

    def test_bootstrap_graph_and_direct_modes_run(self) -> None:
        graph_result = subprocess.run([sys.executable, '-m', 'src.main', 'bootstrap-graph'], check=True, capture_output=True, text=True)
        direct_result = subprocess.run([sys.executable, '-m', 'src.main', 'direct-connect-mode', 'workspace'], check=True, capture_output=True, text=True)
        deep_link_result = subprocess.run([sys.executable, '-m', 'src.main', 'deep-link-mode', 'workspace'], check=True, capture_output=True, text=True)
        self.assertIn('Bootstrap Graph', graph_result.stdout)
        self.assertIn('mode=direct-connect', direct_result.stdout)
        self.assertIn('mode=deep-link', deep_link_result.stdout)


if __name__ == '__main__':
    unittest.main()
