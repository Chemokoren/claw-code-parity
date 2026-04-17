# IMPROVEMENTS.md — Versioned Parity Changelog

Tracks all improvements bringing claw-code-parity towards (and beyond)
feature parity with Claude Code. Each version is a self-contained upgrade
snapshot that can be independently verified.

**Commands:**
```bash
python3 scripts/parity-sync.py status    # Current version and coverage
python3 scripts/parity-sync.py audit     # Full audit: scan → test → report
python3 scripts/parity-sync.py check     # Quick feature scan
python3 scripts/parity-sync.py history   # Past audit reports
```

---

## v0.1.0 — Initial Parity Sync (2026-04-17)

The first versioned release integrating the latest Anthropic features into
claw-code-parity. This version brings the project from a basic API wrapper to
a Claude Code-competitive agentic coding assistant.

### Anthropic API Features

| Feature | What It Does | Why It Matters |
|---------|-------------|----------------|
| **Adaptive Thinking** | Model decides when/how deeply to reason via `thinking: {type: "adaptive"}` | Enables interleaved reasoning between tool calls — the #1 quality driver for code review and QA |
| **Effort Levels** | 5 levels (low/medium/high/xhigh/max) via `output_config.effort` | User controls cost vs quality: `/effort low` for quick tasks, `/effort max` for "ultrathink" |
| **Thinking Block Preservation** | Encrypted thinking blocks passed back unchanged during tool-use loops | Without this, the model loses its chain of thought between tool invocations |
| **Opus 4.7 Model Default** | Default model updated to `claude-opus-4-7` (released 2026-04-16) | 70% CursorBench, 1M context window, 128k output tokens, improved instruction following |

### Claude Code Behavior Parity

| Feature | What It Does | Why It Matters |
|---------|-------------|----------------|
| **Skill Content Preloading** | SKILL.md files read and injected directly into the prompt (up to 40k chars) | Claude Code pre-reads skills; without this, the model just gets a file path and summarizes |
| **Execution Directives** | `EXECUTE SKILL:` header with 10 critical rules forcing execution behavior | Prevents the model from treating skill workflows as documentation to summarize |
| **System Prompt Reinforcement** | Dedicated "Skill execution" section in system prompt | Persistent instruction that skill messages are workflows to execute, not docs to read |
| **Tool Name Mapping** | Automatic gstack→claw tool name mapping (Bash→bash, Read→file_read, etc.) | Skills reference gstack tool names that don't exist in claw; mapping bridges the gap |

### Infrastructure

| Feature | What It Does |
|---------|-------------|
| **REPL `/think` command** | Switch thinking mode at runtime: adaptive, enabled, disabled |
| **REPL `/effort` command** | Switch effort level at runtime: low, medium, high, xhigh, max |
| **Banner display** | Provider panel shows active thinking mode and effort level |
| **Parity sync script** | `scripts/parity-sync.py` — automated feature auditing, gap analysis, versioned reports |
| **Feature manifest** | `future/manifest.json` — machine-readable feature status tracking |

### Files Changed

| File | Change Summary |
|------|----------------|
| `src/config.py` | Added `thinking_mode`, `effort_level`, `EFFORT_LEVELS`; default model → `claude-opus-4-7`; `max_tokens` → 16384 |
| `src/llm.py` | Added `_build_thinking_config()`, `_build_output_config()`, thinking block handling in `_call_anthropic()` |
| `src/agent.py` | Updated `_append_assistant_with_tool_calls_raw()` for thinking block preservation; wired into agentic loop |
| `src/repl.py` | Added `/think`, `/effort` commands; updated banner and help text |
| `src/skill_registry.py` | Added `_read_skill_content()`; rewrote `build_skill_invocation_prompt()` with execution directives |
| `src/system_prompt.py` | Added "Skill execution" section with tool mapping and execution rules |
| `tests/test_porting_workspace.py` | Updated assertions for new skill prompt format; added content preload verification |
| `scripts/parity-sync.py` | New: automated feature parity auditing script |
| `future/manifest.json` | New: machine-readable feature manifest |

### Test Status
- **29/29 tests passing** ✅

### Coverage
- **4/17 Anthropic API features** (23.5%)
- **6/6 Claude Code behavior features** (100%)

---

## Version Index

| Version | Date | Focus | Coverage |
|---------|------|-------|----------|
| v0.1.0 | 2026-04-17 | Adaptive thinking, skill execution, Opus 4.7 | 4/17 API (23.5%) |

---

## Remaining Gaps (as of v0.1.0)

### P0 — Next Sprint
| Feature | Effort | API |
|---------|--------|-----|
| Streaming with Thinking | ~2h | `thinking_delta` SSE events |
| Prompt Caching | ~1h | `cache_control: {type: ephemeral}` |

### P1 — High Value
| Feature | Effort | API |
|---------|--------|-----|
| Task Budgets | ~2h | `output_config.task_budget` (beta) |
| Advisor Tool | ~3h | `advisor_20260301` (beta) |
| Context Compaction | ~4h | Conversation compaction API |
| Coordinator Mode | ~1w | Multi-agent orchestration |

### P2 — Tool Expansion
| Feature | Effort | API |
|---------|--------|-----|
| Web Search Tool | ~2h | `web_search_20250305` |
| Web Fetch Tool | ~1h | `web_fetch` |
| Memory Tool | ~3h | `memory_tool` |
| Computer Use | ~1w | `computer_use_20250124` |
| Git Worktree Isolation | ~4h | `--worktree` flag |

### P3 — Future
| Feature | Effort | API |
|---------|--------|-----|
| Managed Agents | ~1w | `managed-agents-2026-04-01` (beta) |
| 300k Output (Batch) | ~1h | `output-300k-2026-03-24` (beta) |
