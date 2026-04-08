# Rewriting Project Claw Code

<p align="center">
  <strong>⭐ The fastest repo in history to surpass 50K stars, reaching the milestone in just 2 hours after publication ⭐</strong>
</p>

<p align="center">
  <a href="https://star-history.com/#ultraworkers/claw-code&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ultraworkers/claw-code&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ultraworkers/claw-code&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ultraworkers/claw-code&type=Date" width="600" />
    </picture>
  </a>
</p>

<p align="center">
  <img src="assets/clawd-hero.jpeg" alt="Claw" width="300" />
</p>

<p align="center">
  <strong>Autonomously maintained by lobsters/claws — not by human hands</strong>
</p>

<p align="center">
  <a href="https://github.com/Yeachan-Heo/clawhip">clawhip</a> ·
  <a href="https://github.com/code-yeongyu/oh-my-openagent">oh-my-openagent</a> ·
  <a href="https://github.com/Yeachan-Heo/oh-my-claudecode">oh-my-claudecode</a> ·
  <a href="https://github.com/Yeachan-Heo/oh-my-codex">oh-my-codex</a> ·
  <a href="https://discord.gg/6ztZB9jvWq">UltraWorkers Discord</a>
</p>

> [!IMPORTANT]
> The active Rust workspace now lives in [`rust/`](./rust). Start with [`USAGE.md`](./USAGE.md) for build, auth, CLI, session, and parity-harness workflows, then use [`rust/README.md`](./rust/README.md) for crate-level details.

> Want the bigger idea behind this repo? Read [`PHILOSOPHY.md`](./PHILOSOPHY.md) and Sigrid Jin's public explanation: https://x.com/realsigridjin/status/2039472968624185713

> Shout-out to the UltraWorkers ecosystem powering this repo: [clawhip](https://github.com/Yeachan-Heo/clawhip), [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent), [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode), [oh-my-codex](https://github.com/Yeachan-Heo/oh-my-codex), and the [UltraWorkers Discord](https://discord.gg/6ztZB9jvWq).

---

## Backstory

This repo is maintained by **lobsters/claws**, not by a conventional human-only dev team.

The people behind the system are [Bellman / Yeachan Heo](https://github.com/Yeachan-Heo) and friends like [Yeongyu](https://github.com/code-yeongyu), but the repo itself is being pushed forward by autonomous claw workflows: parallel coding sessions, event-driven orchestration, recovery loops, and machine-readable lane state.

In practice, that means this project is not just *about* coding agents — it is being **actively built by them**. Features, tests, telemetry, docs, and workflow hardening are landed through claw-driven loops using [clawhip](https://github.com/Yeachan-Heo/clawhip), [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent), [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode), and [oh-my-codex](https://github.com/Yeachan-Heo/oh-my-codex).

This repository exists to prove that an open coding harness can be built **autonomously, in public, and at high velocity** — with humans setting direction and claws doing the grinding.

See the public build story here:

https://x.com/realsigridjin/status/2039472968624185713

![Tweet screenshot](assets/tweet-screenshot.png)

---

## Porting Status

The main source tree is now Python-first.

- `src/` contains the active Python porting workspace
- `tests/` verifies the current Python workspace
- the exposed snapshot is no longer part of the tracked repository state

The current Python workspace is not yet a complete one-to-one replacement for the original system, but the primary implementation surface is now Python.

## Why this rewrite exists

I originally studied the exposed codebase to understand its harness, tool wiring, and agent workflow. After spending more time with the legal and ethical questions—and after reading the essay linked below—I did not want the exposed snapshot itself to remain the main tracked source tree.

This repository now focuses on Python porting work instead.

## Repository Layout

```text
.
├── src/                                # Python porting workspace
│   ├── __init__.py
│   ├── commands.py
│   ├── main.py
│   ├── models.py
│   ├── port_manifest.py
│   ├── query_engine.py
│   ├── task.py
│   └── tools.py
├── tests/                              # Python verification
├── assets/omx/                         # OmX workflow screenshots
├── 2026-03-09-is-legal-the-same-as-legitimate-ai-reimplementation-and-the-erosion-of-copyleft.md
└── README.md
```

## Python Workspace Overview

The new Python `src/` tree currently provides:

- **`port_manifest.py`** — summarizes the current Python workspace structure
- **`models.py`** — dataclasses for subsystems, modules, and backlog state
- **`commands.py`** — Python-side command port metadata
- **`tools.py`** — Python-side tool port metadata
- **`query_engine.py`** — renders a Python porting summary from the active workspace
- **`main.py`** — a CLI entrypoint for manifest and summary output

## Quickstart

Render the Python porting summary:

```bash
python3 -m src.main summary
```

Print the current Python workspace manifest:

```bash
python3 -m src.main manifest
```

List the current Python modules:

```bash
python3 -m src.main subsystems --limit 16
```

Run verification:

```bash
python3 -m unittest discover -s tests -v
```

Run the parity audit against the local ignored archive (when present):

```bash
python3 -m src.main parity-audit
```

Inspect mirrored command/tool inventories:

```bash
python3 -m src.main commands --limit 10
python3 -m src.main tools --limit 10
```

## Local Assistant

The Python assistant surface now includes a small launcher toolkit under `scripts/`:

| Script | Purpose | Requirements |
| --- | --- | --- |
| `./scripts/status-local-ai.sh` | Show local runtime status, installed tools, active model routing, and detected skills | none |
| `./scripts/run-auto.sh` | Start the assistant in auto mode, preferring local Ollama and GPU-backed local inference when available | none |
| `./scripts/run-ollama.sh` | Force local Ollama using the repo's local-model defaults | local Ollama runtime |
| `./scripts/run-claude.sh` | Force Anthropic API mode for the Python assistant | `ANTHROPIC_API_KEY` |
| `./scripts/run-glm.sh` | Force GLM-5.1 through Z.AI's coding endpoint | `ZAI_API_KEY` |
| `./scripts/setup-gstack-codex.sh` | Install gstack skills for Codex from a detected local gstack checkout | local gstack checkout |
| `./scripts/setup-gstack-claude.sh` | Install gstack skills for Claude from a detected local gstack checkout | local gstack checkout |

All launcher scripts auto-load the repo-root `.env` file. Explicit shell exports still take precedence, and keeping one provider block active at a time remains the clearest setup.

### Default Behavior

The repo-local configuration now defaults to `CLAW_PROVIDER=auto`.

In `auto` mode the assistant:

- prefers local Ollama when it is reachable
- prefers GPU-backed local inference when the local runtime supports it
- falls back cleanly when local Ollama is unavailable

Recommended startup:

```bash
./scripts/run-auto.sh
```

Inspect the detected local state before starting:

```bash
./scripts/status-local-ai.sh
```

### Provider Modes

Force local Ollama with `qwen2.5-coder:7b`:

```bash
./scripts/run-ollama.sh
./scripts/run-ollama.sh ask "explain src/config.py"
```

Force Anthropic API mode for the Python assistant:

```bash
export ANTHROPIC_API_KEY=...
./scripts/run-claude.sh
./scripts/run-claude.sh ask "review src/repl.py"
```

Note: `run-claude.sh` targets the Anthropic API from the Python assistant. It does not install or invoke the separate `claude` terminal CLI.

Force GLM-5.1 through Z.AI's coding endpoint:

```bash
export ZAI_API_KEY=...
./scripts/run-glm.sh
./scripts/run-glm.sh ask "explain src/config.py"
```

`run-glm.sh` reads `ZAI_API_KEY` from either your current shell or the repo-root `.env`.

### REPL Commands

The launcher scripts start the interactive Python REPL. Inside the `claw>` prompt you can use:

- `/help` to show the built-in command list
- `/provider` to show the active provider, model, base URL, and provider presets
- `/skills` to list installed slash-skill commands discovered from gstack, Claude, Codex, or `CLAW_SKILL_ROOTS`
- `/clear` to reset conversation history
- `/usage` to show token usage
- `/quit` to exit the REPL

Installed slash skills accept optional inline arguments after the command name. For example:

```text
/office-hours Help me think through a launch plan for this repo
/qa https://staging.example.com
```

### Skills And Gstack

The launcher scripts automatically expose detected gstack skill roots through `CLAW_SKILL_ROOTS` when a local checkout is found.

Bootstrap gstack for Codex or Claude from the local checkout:

```bash
./scripts/setup-gstack-codex.sh
./scripts/setup-gstack-claude.sh
```

After setup, the Python REPL can list and invoke discovered skills directly. The slash commands are the same across providers; only the backend model changes.

Common flow:

1. Start the REPL with the launcher for the model/provider you want.
2. Run `/skills` to confirm the available slash commands.
3. Run the skill with optional inline arguments.

Example with `auto`:

```bash
./scripts/run-auto.sh
/skills
/office-hours Help me think through a launch plan for this repo
/qa https://your-staging-url
```

Example with local Ollama:

```bash
./scripts/run-ollama.sh
/skills
/office-hours Help me think through a launch plan for this repo
/qa https://your-staging-url
```

Example with Anthropic:

```bash
export ANTHROPIC_API_KEY=...
./scripts/run-claude.sh
/skills
/office-hours Help me think through a launch plan for this repo
/qa https://your-staging-url
```

Example with GLM-5.1:

```bash
export ZAI_API_KEY=...
./scripts/run-glm.sh
/skills
/office-hours Help me think through a launch plan for this repo
/qa https://your-staging-url
```

Notes:

- `/skills` is the quickest way to confirm which slash commands were discovered on the current machine.
- If `/office-hours` or `/qa` is reported as unknown, run one of the gstack setup scripts or set `CLAW_SKILL_ROOTS` to your local gstack checkout.
- Slash skills run only inside the interactive REPL. For one-shot non-skill prompts, use `./scripts/run-*.sh ask "..."`.

## Current Parity Checkpoint

The port now mirrors the archived root-entry file surface, top-level subsystem names, and command/tool inventories much more closely than before. However, it is **not yet** a full runtime-equivalent replacement for the original TypeScript system; the Python tree still contains fewer executable runtime slices than the archived source.


## Built with `oh-my-codex`

The restructuring and documentation work on this repository was AI-assisted and orchestrated with Yeachan Heo's [oh-my-codex (OmX)](https://github.com/Yeachan-Heo/oh-my-codex), layered on top of Codex.

- **`$team` mode:** used for coordinated parallel review and architectural feedback
- **`$ralph` mode:** used for persistent execution, verification, and completion discipline
- **Codex-driven workflow:** used to turn the main `src/` tree into a Python-first porting workspace

### OmX workflow screenshots

![OmX workflow screenshot 1](assets/omx/omx-readme-review-1.png)

*Ralph/team orchestration view while the README and essay context were being reviewed in terminal panes.*

![OmX workflow screenshot 2](assets/omx/omx-readme-review-2.png)

*Split-pane review and verification flow during the final README wording pass.*

## Community

<p align="center">
  <a href="https://instruct.kr/"><img src="assets/instructkr.png" alt="instructkr" width="400" /></a>
</p>

Join the [**instructkr Discord**](https://instruct.kr/) — the best Korean language model community. Come chat about LLMs, harness engineering, agent workflows, and everything in between.

[![Discord](https://img.shields.io/badge/Join%20Discord-instruct.kr-5865F2?logo=discord&style=for-the-badge)](https://instruct.kr/)

## Star History

See the chart at the top of this README.

## Ownership / Affiliation Disclaimer

- This repository does **not** claim ownership of the original Claude Code source material.
- This repository is **not affiliated with, endorsed by, or maintained by Anthropic**.
