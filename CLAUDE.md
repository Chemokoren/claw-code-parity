# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Detected stack
- Languages: Rust.
- Frameworks: none detected from the supported starter markers.

## Verification
- Run Rust verification from `rust/`: `cargo fmt`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`
- `src/` and `tests/` are both present; update both surfaces together when behavior changes.

## Repository shape
- `rust/` contains the Rust workspace and active CLI/runtime implementation.
- `src/` contains source files that should stay consistent with generated guidance and tests.
- `tests/` contains validation surfaces that should be reviewed alongside code changes.

## Working agreement
- Prefer small, reviewable changes and keep generated bootstrap files aligned with actual repo workflows.
- Keep shared defaults in `.claude.json`; reserve `.claude/settings.local.json` for machine-local overrides.
- Do not overwrite existing `CLAUDE.md` content automatically; update it intentionally when repo workflows change.
## gstack guidance
- This repository requires gstack for AI-assisted work (team mode: required).
- gstack provides structured planning, review, QA, and deployment workflows.
- Useful commands in this porting workspace:
  - `/office-hours` — Start here: reframe problems and generate implementation approaches.
  - `/plan-eng-review` — Lock in architecture, data flow, and test plans for porting work.
  - `/review` — Find bugs in code changes before merging.
  - `/qa` — Test the application end-to-end, including browser-based flows.
  - `/investigate` — Systematic root-cause debugging for issues.
  - `/autoplan` — Generate a complete implementation plan for new features or porting tasks.
  - `/ship` — Automate PR creation, testing, and deployment.
- For porting-specific work: Use `/office-hours` to clarify goals, `/plan-eng-review` for technical planning, then `/review` and `/qa` for validation.
- Team mode ensures gstack is available in every Claude Code session; developers install it via `git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup --team`.
- If you encounter issues, run `/investigate` to trace problems systematically.
