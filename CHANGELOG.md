# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-05-26

Initial release.

### Added
- `prc <git-ref>` CLI with `--mode quick`, `--format md|json`, `--model`,
  `--repo`, and `--version` flags.
- Model-agnostic LLM client speaking the OpenAI-compatible
  chat-completions wire format. Configured via `PRC_MODEL`,
  `PRC_API_KEY`, `PRC_API_BASE`.
- Sequential review pipeline: `understand → correctness → verdict`.
- Structured verdict with `approve` / `request_changes` / `discuss`
  decision and per-issue severity, category, location, and suggested fix.
- Author-side response data types (`accept` / `refute` / `clarify`)
  with a substantive-content guard, ready for the v0.2 interactive loop.
- Markdown and JSON output renderers.
- `MockLLMClient` for deterministic, network-free tests.
- Bench-A scaffolding (`benchmarks/bench_a.py`) with 10 hand-curated
  injected-bug fixtures across five bug categories.
- MIT license, GitHub Actions CI, README quickstart.

### Not yet shipped
- `thorough` and `interactive` review modes.
- GitHub PR-URL parsing and inline-comment posting.
- Cross-file integration and adversarial phases.
- Re-review on new commits with persistent state.
- Bench-A and Bench-B published results.
