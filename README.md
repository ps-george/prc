# prc — PR critic

A small, model-agnostic code review tool. Reviews a git ref and emits a
structured verdict: **approve**, **request changes**, or **discuss** —
with per-issue severity, category, location, and suggested fix.

`prc` is opinionated about three things most LLM review tools get wrong:

1. **Explicit completion verdict.** Every review ends with a single
   top-level decision. No "LGTM with these 14 suggestions."
2. **Author response is part of the protocol.** Every blocker and major
   issue expects an `accept`, `refute`, or `clarify`. Single-word
   refusals are rejected by the protocol, not by social pressure.
3. **Model-agnostic.** Any OpenAI-compatible endpoint works — hosted
   (OpenAI, OpenRouter, Together, Groq) or local (vLLM, llama.cpp,
   LM Studio, ollama).

## 30-second quickstart

```bash
uv sync
export PRC_MODEL=gpt-4o-mini
export PRC_API_KEY=sk-...
uv run prc HEAD
```

That reviews the most recent commit in the current repo and writes a
markdown verdict to stdout.

Pointing at a local model:

```bash
export PRC_MODEL=qwen2.5-coder:7b
export PRC_API_BASE=http://localhost:11434/v1
export PRC_API_KEY=ollama
uv run prc HEAD~3..HEAD --format json
```

Try it without an API key using the built-in mock LLM:

```bash
PRC_MOCK=1 uv run prc HEAD
```

## What ships in v0.1.0

- `prc <git-ref> [--mode quick] [--format md|json]`
- Sequential `understand → correctness → verdict` pipeline.
- Structured verdict with severity / category / location / suggested fix.
- Author response data types ready for the v0.2 interactive loop.
- Bench-A scaffolding with 10 hand-curated injected-bug fixtures.

See `CHANGELOG.md` for the not-yet-shipped list.

## Honest positioning

`prc` is not a replacement for CodeRabbit, Cursor Review, or Greptile if
what you want is broad, polished, auto-posted PR commentary on a busy
shared repo. Those tools have richer integrations, web UIs, and
inline-comment ergonomics that this project does not try to match.

`prc` is a small, local-first tool for one specific case: you want a
single structured verdict on a change, and you want the protocol itself
to push back on hand-wave answers from either side. It runs against any
OpenAI-compatible model, has no hosted dependency, costs nothing
beyond the model call, and the entire pipeline fits in a few hundred
lines you can read in one sitting.

## Configuration

| Variable       | Purpose                                          | Default                       |
| -------------- | ------------------------------------------------ | ----------------------------- |
| `PRC_MODEL`    | Model identifier passed through to the provider. | _(required, unless `PRC_MOCK`)_ |
| `PRC_API_KEY`  | Bearer token. Optional for local servers.        | _(none)_                      |
| `PRC_API_BASE` | OpenAI-compatible base URL.                      | `https://api.openai.com/v1`   |
| `PRC_MOCK`     | If `1`, use a built-in fixed mock LLM.           | _(unset)_                     |

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy src/
```

CI runs the same checks on every push.

## License

MIT. See `LICENSE`.
